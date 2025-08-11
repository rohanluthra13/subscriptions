#!/usr/bin/env python3
"""
Subscription Manager - Single File Implementation
Replaces the entire Next.js/TypeScript/Drizzle codebase with pure Python + SQL
"""

import os
import sqlite3
import json
import base64
from datetime import datetime, timedelta
from urllib.parse import urlencode, parse_qs
import webbrowser
from typing import Dict, List, Optional, Any

# Web server
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
import threading
import time

# API clients
import requests
from dotenv import load_dotenv

# Load environment variables from existing .env file
load_dotenv()

class SubscriptionManager:
    def __init__(self):
        self.db_path = "subscriptions.db"
        self.init_database()
        
        # Environment variables (from your existing .env)
        self.google_client_id = os.getenv('GOOGLE_CLIENT_ID')
        self.google_client_secret = os.getenv('GOOGLE_CLIENT_SECRET')
        self.openai_api_key = os.getenv('OPENAI_API_KEY')
        self.openai_model = os.getenv('OPENAI_MODEL', 'gpt-4o-mini')
        self.confidence_threshold = float(os.getenv('LLM_CONFIDENCE_THRESHOLD', '0.7'))
        
        # Server config
        self.port = 8000
        self.redirect_uri = f"http://localhost:{self.port}/auth/callback"

    def init_database(self):
        """Initialize SQLite database with schema matching your PostgreSQL setup"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Users table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id TEXT PRIMARY KEY DEFAULT (hex(randomblob(16))),
                email TEXT UNIQUE NOT NULL,
                name TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Connections table (Gmail OAuth)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS connections (
                id TEXT PRIMARY KEY DEFAULT (hex(randomblob(16))),
                user_id TEXT NOT NULL DEFAULT '1',
                email TEXT NOT NULL,
                access_token TEXT NOT NULL,
                refresh_token TEXT NOT NULL,
                token_expiry TIMESTAMP NOT NULL,
                history_id TEXT,
                last_sync_at TIMESTAMP,
                fetch_page_token TEXT,
                is_active BOOLEAN DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
        ''')
        
        # Subscriptions table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS subscriptions (
                id TEXT PRIMARY KEY DEFAULT (hex(randomblob(16))),
                user_id TEXT NOT NULL DEFAULT '1',
                connection_id TEXT NOT NULL,
                vendor_name TEXT NOT NULL,
                vendor_email TEXT,
                amount DECIMAL(10,2),
                currency TEXT DEFAULT 'USD',
                billing_cycle TEXT,
                next_billing_date DATE,
                last_billing_date DATE,
                detected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                status TEXT DEFAULT 'active',
                renewal_type TEXT DEFAULT 'auto_renew',
                confidence_score DECIMAL(3,2),
                user_verified BOOLEAN DEFAULT 0,
                category TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (connection_id) REFERENCES connections(id)
            )
        ''')
        
        # Processed emails table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS processed_emails (
                id TEXT PRIMARY KEY DEFAULT (hex(randomblob(16))),
                connection_id TEXT NOT NULL,
                gmail_message_id TEXT UNIQUE NOT NULL,
                subject TEXT,
                sender TEXT,
                received_at TIMESTAMP,
                processed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                is_subscription BOOLEAN DEFAULT 0,
                subscription_id TEXT,
                confidence_score DECIMAL(3,2),
                vendor TEXT,
                email_type TEXT,
                FOREIGN KEY (connection_id) REFERENCES connections(id),
                FOREIGN KEY (subscription_id) REFERENCES subscriptions(id)
            )
        ''')
        
        # Create default user if doesn't exist
        cursor.execute('INSERT OR IGNORE INTO users (id, email, name) VALUES (?, ?, ?)', 
                      ('1', 'user@example.com', 'Default User'))
        
        # Migration: Add fetch_page_token column if it doesn't exist
        cursor.execute("PRAGMA table_info(connections)")
        columns = [column[1] for column in cursor.fetchall()]
        if 'fetch_page_token' not in columns:
            cursor.execute('ALTER TABLE connections ADD COLUMN fetch_page_token TEXT')
            print("Added fetch_page_token column to connections table")
        
        conn.commit()
        conn.close()

    def get_db_connection(self):
        """Get database connection"""
        return sqlite3.connect(self.db_path)

    def get_gmail_auth_url(self):
        """Generate Gmail OAuth URL"""
        params = {
            'client_id': self.google_client_id,
            'redirect_uri': self.redirect_uri,
            'scope': 'https://www.googleapis.com/auth/gmail.readonly',
            'response_type': 'code',
            'access_type': 'offline',
            'prompt': 'consent'
        }
        return f"https://accounts.google.com/o/oauth2/auth?{urlencode(params)}"

    def exchange_code_for_tokens(self, code: str):
        """Exchange OAuth code for access tokens"""
        data = {
            'client_id': self.google_client_id,
            'client_secret': self.google_client_secret,
            'code': code,
            'grant_type': 'authorization_code',
            'redirect_uri': self.redirect_uri
        }
        
        response = requests.post('https://oauth2.googleapis.com/token', data=data)
        return response.json()

    def refresh_access_token(self, refresh_token: str):
        """Refresh expired access token"""
        data = {
            'client_id': self.google_client_id,
            'client_secret': self.google_client_secret,
            'refresh_token': refresh_token,
            'grant_type': 'refresh_token'
        }
        
        response = requests.post('https://oauth2.googleapis.com/token', data=data)
        return response.json()

    def get_valid_access_token(self, connection_id: str) -> str:
        """Get valid access token, refreshing if necessary"""
        conn = self.get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT access_token, refresh_token, token_expiry 
            FROM connections WHERE id = ?
        ''', (connection_id,))
        
        result = cursor.fetchone()
        if not result:
            conn.close()
            raise Exception("Connection not found")
            
        access_token, refresh_token, token_expiry = result
        expiry_time = datetime.fromisoformat(token_expiry.replace('Z', '+00:00'))
        
        # If token expires within 5 minutes, refresh it
        if expiry_time <= datetime.now() + timedelta(minutes=5):
            token_data = self.refresh_access_token(refresh_token)
            
            new_expiry = datetime.now() + timedelta(seconds=token_data['expires_in'])
            cursor.execute('''
                UPDATE connections 
                SET access_token = ?, token_expiry = ? 
                WHERE id = ?
            ''', (token_data['access_token'], new_expiry.isoformat(), connection_id))
            
            conn.commit()
            access_token = token_data['access_token']
        
        conn.close()
        return access_token

    def fetch_gmail_messages(self, connection_id: str, max_results: int = 50, fetch_direction: str = 'recent'):
        """Fetch Gmail messages"""
        access_token = self.get_valid_access_token(connection_id)
        
        headers = {'Authorization': f'Bearer {access_token}'}
        
        # Build query URL based on direction
        list_url = f'https://gmail.googleapis.com/gmail/v1/users/me/messages?maxResults={max_results}'
        
        if fetch_direction == 'older':
            # Get the stored page token for fetching older emails
            conn = self.get_db_connection()
            cursor = conn.cursor()
            cursor.execute('SELECT fetch_page_token FROM connections WHERE id = ?', (connection_id,))
            result = cursor.fetchone()
            conn.close()
            
            if result and result[0]:
                # Use the stored page token to get the next batch of older emails
                list_url += f'&pageToken={result[0]}'
                print(f"Fetching older emails using saved page token...")
            else:
                print("Fetching emails (no previous page token)...")
        else:
            # For recent emails, clear the page token to start fresh
            conn = self.get_db_connection()
            cursor = conn.cursor()
            cursor.execute('UPDATE connections SET fetch_page_token = NULL WHERE id = ?', (connection_id,))
            conn.commit()
            conn.close()
            print("Fetching recent emails (reset page token)...")
        
        print(f"Gmail API URL: {list_url}")
        response = requests.get(list_url, headers=headers)
        response_data = response.json()
        messages = response_data.get('messages', [])
        next_page_token = response_data.get('nextPageToken')
        print(f"Gmail API returned {len(messages)} messages")
        
        # Save the nextPageToken for future "older" fetches
        if next_page_token:
            conn = self.get_db_connection()
            cursor = conn.cursor()
            cursor.execute('UPDATE connections SET fetch_page_token = ? WHERE id = ?', 
                          (next_page_token, connection_id))
            conn.commit()
            conn.close()
            print(f"Saved page token for next older fetch")
        
        email_data = []
        for message in messages:
            # Get full message
            msg_url = f'https://gmail.googleapis.com/gmail/v1/users/me/messages/{message["id"]}'
            msg_response = requests.get(msg_url, headers=headers)
            msg_data = msg_response.json()
            
            # Extract email details
            headers_data = {h['name']: h['value'] for h in msg_data['payload'].get('headers', [])}
            
            # Get email body
            body = self.extract_email_body(msg_data['payload'])
            
            email_data.append({
                'id': message['id'],
                'thread_id': msg_data['threadId'],
                'subject': headers_data.get('Subject', ''),
                'sender': headers_data.get('From', ''),
                'date': headers_data.get('Date', ''),
                'body': body
            })
        
        return email_data

    def extract_email_body(self, payload):
        """Extract text content from Gmail message payload"""
        body = ""
        
        if 'parts' in payload:
            for part in payload['parts']:
                if part['mimeType'] == 'text/plain':
                    data = part['body'].get('data', '')
                    if data:
                        body = base64.urlsafe_b64decode(data).decode('utf-8')
                        break
        elif payload['mimeType'] == 'text/plain':
            data = payload['body'].get('data', '')
            if data:
                body = base64.urlsafe_b64decode(data).decode('utf-8')
        
        return body

    def classify_email_with_llm(self, email_content: str) -> Dict[str, Any]:
        """Use OpenAI to classify if email is subscription-related"""
        headers = {
            'Authorization': f'Bearer {self.openai_api_key}',
            'Content-Type': 'application/json'
        }
        
        prompt = f"""
        Analyze this email and determine if it's subscription-related. Return JSON with:
        {{
            "is_subscription": boolean,
            "confidence": float (0.0-1.0),
            "vendor_name": string or null,
            "vendor_email": string or null,
            "amount": float or null,
            "currency": string or null,
            "billing_cycle": string or null,
            "category": string or null
        }}
        
        Email content:
        {email_content[:2000]}  # Limit content length
        """
        
        data = {
            'model': self.openai_model,
            'messages': [
                {'role': 'system', 'content': 'You are an expert at analyzing emails for subscription information.'},
                {'role': 'user', 'content': prompt}
            ],
            'response_format': {'type': 'json_object'}
        }
        
        # Only add temperature for models that support it
        if 'gpt-5-nano' not in self.openai_model:
            data['temperature'] = 0.1
        
        try:
            response = requests.post('https://api.openai.com/v1/chat/completions', 
                                   headers=headers, json=data, timeout=30)
            
            result = response.json()
            
            if response.status_code != 200:
                print(f"OpenAI API error: {result.get('error', {}).get('message', 'Unknown error')}")
                return {"is_subscription": False, "confidence": 0.0}
            
            if 'choices' not in result or len(result['choices']) == 0:
                print(f"No choices in OpenAI response: {result}")
                return {"is_subscription": False, "confidence": 0.0}
                
            classification = json.loads(result['choices'][0]['message']['content'])
            return classification
            
        except json.JSONDecodeError as e:
            print(f"JSON decode error: {e}")
            print(f"Raw content: {result['choices'][0]['message']['content'] if 'choices' in result else 'No choices'}")
            return {"is_subscription": False, "confidence": 0.0}
        except Exception as e:
            print(f"LLM classification error: {e}")
            return {"is_subscription": False, "confidence": 0.0}

    def sync_emails(self, connection_id: str, max_results: int = 20, fetch_direction: str = 'recent'):
        """Main sync process - fetch emails and classify them"""
        print(f"Starting email sync: {max_results} emails from {fetch_direction}...")
        
        # Fetch emails from Gmail
        emails = self.fetch_gmail_messages(connection_id, max_results, fetch_direction)
        
        conn = self.get_db_connection()
        cursor = conn.cursor()
        
        new_subscriptions = 0
        processed_count = 0
        
        for email in emails:
            # Check if already processed
            cursor.execute('SELECT id FROM processed_emails WHERE gmail_message_id = ?', 
                          (email['id'],))
            if cursor.fetchone():
                print(f"  Skipping already processed: {email['subject'][:50]}")
                continue
                
            processed_count += 1
            print(f"Processing email: {email['subject'][:50]}...")
            
            # Classify with LLM
            classification = self.classify_email_with_llm(f"Subject: {email['subject']}\nFrom: {email['sender']}\nBody: {email['body']}")
            
            # Insert processed email record
            cursor.execute('''
                INSERT INTO processed_emails 
                (connection_id, gmail_message_id, subject, sender, received_at, 
                 is_subscription, confidence_score, vendor)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                connection_id, email['id'], email['subject'], email['sender'],
                datetime.now().isoformat(), classification['is_subscription'],
                classification['confidence'], classification.get('vendor_name')
            ))
            
            # If it's a subscription with high confidence, create subscription record
            if classification['is_subscription'] and classification['confidence'] >= self.confidence_threshold:
                cursor.execute('''
                    INSERT INTO subscriptions 
                    (connection_id, vendor_name, vendor_email, amount, currency, 
                     billing_cycle, confidence_score, category)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    connection_id,
                    classification.get('vendor_name', 'Unknown'),
                    classification.get('vendor_email'),
                    classification.get('amount'),
                    classification.get('currency', 'USD'),
                    classification.get('billing_cycle'),
                    classification['confidence'],
                    classification.get('category')
                ))
                
                new_subscriptions += 1
                print(f"  → Found subscription: {classification['vendor_name']}")
        
        conn.commit()
        conn.close()
        
        print(f"Sync complete: {processed_count} emails processed, {new_subscriptions} subscriptions found")
        return {"processed": processed_count, "subscriptions": new_subscriptions}

    def get_subscriptions(self) -> List[Dict]:
        """Get all subscriptions for dashboard"""
        conn = self.get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT s.*, c.email as connection_email
            FROM subscriptions s
            JOIN connections c ON s.connection_id = c.id
            WHERE s.user_id = '1'
            ORDER BY s.created_at DESC
        ''')
        
        columns = [desc[0] for desc in cursor.description]
        subscriptions = [dict(zip(columns, row)) for row in cursor.fetchall()]
        
        conn.close()
        return subscriptions

    def get_connections(self) -> List[Dict]:
        """Get all Gmail connections"""
        conn = self.get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute('SELECT id, email, is_active, last_sync_at FROM connections WHERE user_id = "1"')
        columns = [desc[0] for desc in cursor.description]
        connections = [dict(zip(columns, row)) for row in cursor.fetchall()]
        
        conn.close()
        return connections

    def get_processed_emails(self, classified_only: bool = False, limit: int = 10, offset: int = 0) -> Dict:
        """Get processed emails with optional filtering"""
        conn = self.get_db_connection()
        cursor = conn.cursor()
        
        where_clause = "WHERE pe.connection_id = c.id"
        if classified_only:
            where_clause += " AND pe.is_subscription = 1"
        
        # Get total count
        cursor.execute(f'''
            SELECT COUNT(*) FROM processed_emails pe
            JOIN connections c ON pe.connection_id = c.id
            {where_clause}
        ''')
        total = cursor.fetchone()[0]
        
        # Get emails with pagination
        cursor.execute(f'''
            SELECT pe.*, c.email as connection_email
            FROM processed_emails pe
            JOIN connections c ON pe.connection_id = c.id
            {where_clause}
            ORDER BY pe.received_at DESC
            LIMIT ? OFFSET ?
        ''', (limit, offset))
        
        columns = [desc[0] for desc in cursor.description]
        emails = [dict(zip(columns, row)) for row in cursor.fetchall()]
        
        conn.close()
        return {"emails": emails, "total": total}

    def reset_database(self):
        """Clear all data from database"""
        conn = self.get_db_connection()
        cursor = conn.cursor()
        
        # Clear all tables (except users table)
        cursor.execute('DELETE FROM processed_emails')
        cursor.execute('DELETE FROM subscriptions') 
        cursor.execute('DELETE FROM connections')
        
        print("🗑️ Database reset - all data cleared")
        
        conn.commit()
        conn.close()

class WebServer(BaseHTTPRequestHandler):
    def __init__(self, subscription_manager, *args, **kwargs):
        self.sm = subscription_manager
        super().__init__(*args, **kwargs)

    def do_GET(self):
        """Handle GET requests"""
        url = urlparse(self.path)
        path = url.path
        params = parse_qs(url.query)
        
        if path == '/':
            self.serve_dashboard()
        elif path.startswith('/fonts/'):
            self.serve_static_file(path)
        elif path == '/auth/gmail':
            self.start_gmail_auth()
        elif path == '/auth/callback':
            self.handle_oauth_callback(params)
        elif path == '/sync':
            self.handle_sync()
        elif path == '/api/emails':
            self.handle_emails_api(params)
        elif path == '/reset':
            self.handle_reset()
        else:
            self.send_error(404)

    def serve_dashboard(self):
        """Serve main dashboard HTML"""
        subscriptions = self.sm.get_subscriptions()
        connections = self.sm.get_connections()
        
        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Subscription Manager</title>
            <style>
                /* Windows 98 Theme - Adapted from 98.css */
                
                /* Font Faces */
                @font-face {{
                    font-family: "Pixelated MS Sans Serif";
                    src: url(/fonts/ms_sans_serif.woff) format("woff");
                    src: url(/fonts/ms_sans_serif.woff2) format("woff2");
                    font-weight: 400;
                }}
                @font-face {{
                    font-family: "Pixelated MS Sans Serif";
                    src: url(/fonts/ms_sans_serif_bold.woff) format("woff");
                    src: url(/fonts/ms_sans_serif_bold.woff2) format("woff2");
                    font-weight: 700;
                }}
                
                /* Base Styles */
                * {{
                    box-sizing: border-box;
                }}
                
                body {{
                    background: #008080;  /* Classic teal desktop */
                    font-family: "Pixelated MS Sans Serif", Arial;
                    font-size: 11px;
                    color: #000;
                    margin: 0;
                    padding: 20px;
                    -webkit-font-smoothing: none;
                }}
                
                /* Window Component */
                .window {{
                    background: #c0c0c0;
                    border: 2px solid;
                    border-color: #ffffff #0a0a0a #0a0a0a #ffffff;
                    box-shadow: inset -1px -1px #0a0a0a, inset 1px 1px #dfdfdf, inset -2px -2px grey, inset 2px 2px #fff;
                    margin-bottom: 20px;
                }}
                
                /* Title Bar */
                .title-bar {{
                    background: linear-gradient(90deg, #000080, #1084d0);
                    padding: 3px 2px 3px 3px;
                    display: flex;
                    justify-content: space-between;
                    align-items: center;
                    font-weight: bold;
                    color: white;
                }}
                
                .title-bar-text {{
                    padding: 0 0 0 3px;
                    font-weight: bold;
                    color: white;
                    letter-spacing: 0;
                }}
                
                .title-bar-controls {{
                    display: flex;
                }}
                
                .title-bar-controls button {{
                    padding: 0;
                    display: block;
                    min-width: 16px;
                    min-height: 14px;
                    margin-left: 2px;
                }}
                
                /* Window Body */
                .window-body {{
                    margin: 8px;
                }}
                
                /* Buttons */
                button {{
                    background: silver;
                    box-shadow: inset -1px -1px #0a0a0a, inset 1px 1px #fff, inset -2px -2px grey, inset 2px 2px #dfdfdf;
                    border: none;
                    border-radius: 0;
                    font-family: "Pixelated MS Sans Serif", Arial;
                    font-size: 11px;
                    padding: 6px 12px;
                    min-width: 75px;
                    min-height: 23px;
                    outline: none;
                }}
                
                button:active {{
                    box-shadow: inset -1px -1px #fff, inset 1px 1px #0a0a0a, inset -2px -2px #dfdfdf, inset 2px 2px grey;
                    padding: 7px 11px 5px 13px;
                }}
                
                button:focus {{
                    outline: 1px dotted #000;
                    outline-offset: -4px;
                }}
                
                button:disabled {{
                    color: #808080;
                    text-shadow: 1px 1px 0 #fff;
                }}
                
                /* Form Elements */
                select, input[type="text"], input[type="email"], input[type="password"] {{
                    background-color: #fff;
                    box-shadow: inset -1px -1px #fff, inset 1px 1px grey, inset -2px -2px #dfdfdf, inset 2px 2px #0a0a0a;
                    border: none;
                    border-radius: 0;
                    font-family: "Pixelated MS Sans Serif", Arial;
                    font-size: 11px;
                    padding: 3px 4px;
                    height: 21px;
                    -webkit-appearance: none;
                    -moz-appearance: none;
                    appearance: none;
                }}
                
                select {{
                    padding-right: 32px;
                    background-image: url("data:image/svg+xml;charset=utf-8,%3Csvg width='16' height='17' fill='none' xmlns='http://www.w3.org/2000/svg'%3E%3Cpath fill-rule='evenodd' clip-rule='evenodd' d='M15 0H0v16h1V1h14V0z' fill='%23DFDFDF'/%3E%3Cpath fill-rule='evenodd' clip-rule='evenodd' d='M2 1H1v14h1V2h12V1H2z' fill='%23fff'/%3E%3Cpath fill-rule='evenodd' clip-rule='evenodd' d='M16 17H0v-1h15V0h1v17z' fill='%23000'/%3E%3Cpath fill-rule='evenodd' clip-rule='evenodd' d='M15 1h-1v14H1v1h14V1z' fill='gray'/%3E%3Cpath fill='silver' d='M2 2h12v13H2z'/%3E%3Cpath fill-rule='evenodd' clip-rule='evenodd' d='M11 6H4v1h1v1h1v1h1v1h1V9h1V8h1V7h1V6z' fill='%23000'/%3E%3C/svg%3E");
                    background-position: top 2px right 2px;
                    background-repeat: no-repeat;
                }}
                
                label {{
                    display: inline-flex;
                    align-items: center;
                    margin-right: 8px;
                }}
                
                /* Field Row */
                .field-row {{
                    display: flex;
                    align-items: center;
                    margin-bottom: 6px;
                }}
                
                .field-row > * + * {{
                    margin-left: 6px;
                }}
                
                /* Desktop Layout */
                .desktop {{
                    min-height: 100vh;
                    padding: 20px;
                }}
                
                .windows-container {{
                    max-width: 1024px;
                    margin: 0 auto;
                }}
            </style>
        </head>
        <body>
            <div class="desktop">
                <div class="windows-container">
                    
                    <!-- Gmail Connection Window -->
                    <div class="window">
                        <div class="title-bar">
                            <div class="title-bar-text">Gmail Connection</div>
                            <div class="title-bar-controls">
                                <button aria-label="Minimize"></button>
                                <button aria-label="Maximize"></button>
                                <button aria-label="Close">×</button>
                            </div>
                        </div>
                        <div class="window-body">
                            {self.render_connections(connections)}
                        </div>
                    </div>
                    
                    <!-- Email Sync Window -->
                    <div class="window">
                        <div class="title-bar">
                            <div class="title-bar-text">Email Sync</div>
                            <div class="title-bar-controls">
                                <button aria-label="Minimize"></button>
                                <button aria-label="Maximize"></button>
                                <button aria-label="Close">×</button>
                            </div>
                        </div>
                        <div class="window-body">
                            <div class="field-row">
                                <label for="emailCount">Number of emails:</label>
                                <select id="emailCount">
                                    <option value="5">5</option>
                                    <option value="30" selected>30</option>
                                    <option value="100">100</option>
                                    <option value="500">500</option>
                                </select>
                            </div>
                            <div class="field-row">
                                <label for="syncDirection">Sync direction:</label>
                                <select id="syncDirection">
                                    <option value="recent" selected>Most recent emails</option>
                                    <option value="older">Older emails (from last processed)</option>
                                </select>
                            </div>
                            <div class="field-row" style="margin-top: 12px;">
                                <button onclick="syncEmails()">Sync Emails</button>
                            </div>
                        </div>
                    </div>
                    
                    <!-- Data Viewer Window -->
                    <div class="window">
                        <div class="title-bar">
                            <div class="title-bar-text">Subscription Data</div>
                            <div class="title-bar-controls">
                                <button aria-label="Minimize"></button>
                                <button aria-label="Maximize"></button>
                                <button aria-label="Close">×</button>
                            </div>
                        </div>
                        <div class="window-body" style="padding: 0;">
                            <!-- Tab Bar -->
                            <div style="background: #c0c0c0; border-bottom: 1px solid #808080; padding: 2px 8px;">
                                <menu role="tablist" style="margin: 0; padding: 0; list-style: none; display: flex; font-size: 11px;">
                                    <button onclick="showTab('all-emails')" id="all-emails-tab" 
                                            aria-selected="true" style="padding: 4px 12px; margin-right: 2px; background: #c0c0c0; border: 1px solid; border-color: #fff #808080 #808080 #fff; border-bottom: none;">
                                        All Emails
                                    </button>
                                    <button onclick="showTab('classified')" id="classified-tab"
                                            aria-selected="false" style="padding: 4px 12px; margin-right: 2px; background: #c0c0c0; border: 1px solid; border-color: #fff #808080 #808080 #fff;">
                                        Classified Emails
                                    </button>
                                    <button onclick="showTab('subscriptions')" id="subscriptions-tab"
                                            aria-selected="false" style="padding: 4px 12px; margin-right: 2px; background: #c0c0c0; border: 1px solid; border-color: #fff #808080 #808080 #fff;">
                                        Subscriptions ({len(subscriptions)})
                                    </button>
                                </menu>
                            </div>
                            
                            <!-- Tab Content -->
                            <div style="padding: 8px;">
                                <!-- All Emails Tab -->
                                <div id="all-emails-content" class="tab-content">
                                    <div id="all-emails-data" style="font-size: 11px;">Loading...</div>
                                </div>
                                
                                <!-- Classified Emails Tab -->
                                <div id="classified-content" class="tab-content" style="display: none;">
                                    <div id="classified-data" style="font-size: 11px;">Loading...</div>
                                </div>
                                
                                <!-- Subscriptions Tab -->
                                <div id="subscriptions-content" class="tab-content" style="display: none;">
                                    {self.render_subscriptions(subscriptions)}
                                </div>
                            </div>
                        </div>
                    </div>
                    
                </div>
            </div>
                
                <script>
                    function syncEmails() {{
                        const count = document.getElementById('emailCount').value;
                        const direction = document.getElementById('syncDirection').value;
                        window.location.href = `/sync?count=${{count}}&direction=${{direction}}`;
                    }}
                    
                    function showTab(tabName) {{
                        // Hide all tab contents
                        document.querySelectorAll('.tab-content').forEach(el => el.style.display = 'none');
                        
                        // Reset all tab buttons
                        document.querySelectorAll('button[role="tab"], menu[role="tablist"] button').forEach(el => {{
                            el.setAttribute('aria-selected', 'false');
                            el.style.borderBottom = '1px solid #808080';
                            el.style.marginTop = '0';
                        }});
                        
                        // Show selected tab content
                        document.getElementById(tabName + '-content').style.display = 'block';
                        
                        // Activate selected tab
                        const activeTab = document.getElementById(tabName + '-tab');
                        activeTab.setAttribute('aria-selected', 'true');
                        activeTab.style.borderBottom = 'none';
                        activeTab.style.marginTop = '-1px';
                        
                        // Load email data if needed
                        if (tabName === 'all-emails') {{
                            loadEmails(false);
                        }} else if (tabName === 'classified') {{
                            loadEmails(true);
                        }}
                    }}
                    
                    function loadEmails(classifiedOnly) {{
                        const targetDiv = classifiedOnly ? 'classified-data' : 'all-emails-data';
                        document.getElementById(targetDiv).innerHTML = 'Loading...';
                        
                        fetch(`/api/emails?classified=${{classifiedOnly}}&limit=50`)
                            .then(response => response.json())
                            .then(data => {{
                                document.getElementById(targetDiv).innerHTML = renderEmailTable(data, classifiedOnly);
                            }})
                            .catch(error => {{
                                document.getElementById(targetDiv).innerHTML = '<span style=\"color: red;\">Error loading emails</span>';
                            }});
                    }}
                    
                    function renderEmailTable(data, showClassified) {{
                        if (data.emails.length === 0) {{
                            return '<p style=\"text-align: center; color: #666; padding: 20px;\">No emails found. Try syncing first.</p>';
                        }}
                        
                        let html = `
                            <table style=\"width: 100%; border-collapse: collapse; font-size: 11px;\">
                                <thead>
                                    <tr style=\"background: #c0c0c0;\">
                                        <th style=\"border: 1px inset #c0c0c0; padding: 4px; text-align: left;\">Subject</th>
                                        <th style=\"border: 1px inset #c0c0c0; padding: 4px; text-align: left;\">Sender</th>`;
                        
                        if (showClassified) {{
                            html += `
                                        <th style=\"border: 1px inset #c0c0c0; padding: 4px; text-align: left;\">Subscription</th>
                                        <th style=\"border: 1px inset #c0c0c0; padding: 4px; text-align: left;\">Vendor</th>
                                        <th style=\"border: 1px inset #c0c0c0; padding: 4px; text-align: left;\">Confidence</th>`;
                        }}
                        
                        html += `
                                        <th style=\"border: 1px inset #c0c0c0; padding: 4px; text-align: left;\">Received</th>
                                    </tr>
                                </thead>
                                <tbody>`;
                        
                        data.emails.forEach((email, index) => {{
                            const truncatedSubject = email.subject.length > 50 ? email.subject.substring(0, 50) + '...' : email.subject;
                            const truncatedSender = email.sender.length > 30 ? email.sender.substring(0, 30) + '...' : email.sender;
                            const receivedDate = new Date(email.received_at).toLocaleString();
                            const bgColor = index % 2 === 0 ? '#ffffff' : '#f8f8f8';
                            
                            html += `
                                <tr style=\"background: ${{bgColor}};\">
                                    <td style=\"border: 1px inset #c0c0c0; padding: 4px;\">${{truncatedSubject}}</td>
                                    <td style=\"border: 1px inset #c0c0c0; padding: 4px;\">${{truncatedSender}}</td>`;
                            
                            if (showClassified) {{
                                const isSubscription = email.is_subscription ? 'Yes' : 'No';
                                const vendor = email.vendor || '-';
                                const confidence = email.confidence_score ? (parseFloat(email.confidence_score) * 100).toFixed(1) + '%' : '-';
                                
                                html += `
                                    <td style=\"border: 1px inset #c0c0c0; padding: 4px;\">${{isSubscription}}</td>
                                    <td style=\"border: 1px inset #c0c0c0; padding: 4px;\">${{vendor}}</td>
                                    <td style=\"border: 1px inset #c0c0c0; padding: 4px;\">${{confidence}}</td>`;
                            }}
                            
                            html += `
                                    <td style=\"border: 1px inset #c0c0c0; padding: 4px;\">${{receivedDate}}</td>
                                </tr>`;
                        }});
                        
                        html += `
                                </tbody>
                            </table>
                            <div style=\"margin-top: 8px; font-size: 10px; color: #666;\">
                                Total: ${{data.total}} emails
                            </div>`;
                        
                        return html;
                    }}
                    
                    // Initialize first tab on load
                    document.addEventListener('DOMContentLoaded', function() {{
                        showTab('all-emails');
                    }});
                </script>
        </body>
        </html>
        """
        
        self.send_response(200)
        self.send_header('Content-type', 'text/html')
        self.end_headers()
        self.wfile.write(html.encode())

    def render_connections(self, connections):
        """Render Gmail connections section"""
        if not connections:
            return '''
                <p style="margin-bottom: 12px;">No Gmail connection found.</p>
                <button onclick="window.location.href='/auth/gmail';">
                    Connect Gmail
                </button>
            '''
        
        html = ""
        for conn in connections:
            status = "✅ Active" if conn['is_active'] else "❌ Inactive"
            last_sync = conn['last_sync_at'] if conn['last_sync_at'] else 'Never'
            html += f'''
                <div style="border: 1px inset #c0c0c0; padding: 8px; margin-bottom: 8px; background: #f8f8f8;">
                    <div style="font-weight: bold; margin-bottom: 4px;">{conn['email']}</div>
                    <div style="font-size: 10px; color: #666;">
                        Status: {status} | Last sync: {last_sync}
                    </div>
                </div>
            '''
        return html

    def render_subscriptions(self, subscriptions):
        """Render subscriptions table"""
        if not subscriptions:
            return '<p style="text-align: center; color: #666; padding: 20px;">No subscriptions found. Try syncing your emails first.</p>'
        
        html = '''
            <table style="width: 100%; border-collapse: collapse; font-size: 11px;">
                <thead>
                    <tr style="background: #c0c0c0;">
                        <th style="border: 1px inset #c0c0c0; padding: 4px; text-align: left;">Vendor</th>
                        <th style="border: 1px inset #c0c0c0; padding: 4px; text-align: left;">Amount</th>
                        <th style="border: 1px inset #c0c0c0; padding: 4px; text-align: left;">Billing</th>
                        <th style="border: 1px inset #c0c0c0; padding: 4px; text-align: left;">Status</th>
                        <th style="border: 1px inset #c0c0c0; padding: 4px; text-align: left;">Confidence</th>
                    </tr>
                </thead>
                <tbody>
        '''
        
        for i, sub in enumerate(subscriptions):
            amount = f"${sub['amount']} {sub['currency']}" if sub['amount'] else 'Unknown'
            billing = sub['billing_cycle'] or 'Unknown'
            confidence = f"{float(sub['confidence_score'] or 0):.1%}"
            bgColor = '#ffffff' if i % 2 == 0 else '#f8f8f8'
            
            html += f'''
                <tr style="background: {bgColor};">
                    <td style="border: 1px inset #c0c0c0; padding: 4px;">
                        <div style="font-weight: bold;">{sub['vendor_name']}</div>
                        <div style="font-size: 10px; color: #666;">{sub['vendor_email'] or ''}</div>
                    </td>
                    <td style="border: 1px inset #c0c0c0; padding: 4px;">{amount}</td>
                    <td style="border: 1px inset #c0c0c0; padding: 4px;">{billing}</td>
                    <td style="border: 1px inset #c0c0c0; padding: 4px;">{sub['status']}</td>
                    <td style="border: 1px inset #c0c0c0; padding: 4px;">{confidence}</td>
                </tr>
            '''
        
        html += '</tbody></table>'
        return html

    def start_gmail_auth(self):
        """Redirect to Gmail OAuth"""
        auth_url = self.sm.get_gmail_auth_url()
        self.send_response(302)
        self.send_header('Location', auth_url)
        self.end_headers()

    def handle_oauth_callback(self, params):
        """Handle OAuth callback from Gmail"""
        code = params.get('code', [None])[0]
        
        if not code:
            self.send_error(400, "Missing authorization code")
            return
        
        # Exchange code for tokens
        token_data = self.sm.exchange_code_for_tokens(code)
        
        if 'access_token' not in token_data:
            self.send_error(400, "Failed to get access token")
            return
        
        # Get user email
        headers = {'Authorization': f'Bearer {token_data["access_token"]}'}
        profile_response = requests.get('https://gmail.googleapis.com/gmail/v1/users/me/profile', headers=headers)
        profile = profile_response.json()
        
        # Save connection to database
        conn = self.sm.get_db_connection()
        cursor = conn.cursor()
        
        expiry_time = datetime.now() + timedelta(seconds=token_data['expires_in'])
        
        cursor.execute('''
            INSERT OR REPLACE INTO connections 
            (user_id, email, access_token, refresh_token, token_expiry)
            VALUES (?, ?, ?, ?, ?)
        ''', (
            '1',
            profile['emailAddress'],
            token_data['access_token'],
            token_data.get('refresh_token', ''),
            expiry_time.isoformat()
        ))
        
        conn.commit()
        conn.close()
        
        # Redirect back to dashboard
        self.send_response(302)
        self.send_header('Location', '/?connected=1')
        self.end_headers()

    def handle_sync(self):
        """Handle email sync request"""
        # Get active connection
        connections = self.sm.get_connections()
        if not connections:
            self.send_error(400, "No Gmail connection found")
            return
        
        # Parse query parameters
        url = urlparse(self.path)
        params = parse_qs(url.query)
        
        max_results = int(params.get('count', [30])[0])
        fetch_direction = params.get('direction', ['recent'])[0]
        
        connection_id = connections[0]['id']
        
        # Run sync with parameters
        result = self.sm.sync_emails(connection_id, max_results, fetch_direction)
        
        # Return to dashboard with results
        self.send_response(302)
        self.send_header('Location', f'/?synced={result["processed"]}&found={result["subscriptions"]}')
        self.end_headers()

    def handle_emails_api(self, params):
        """Handle emails API endpoint"""
        classified_only = params.get('classified', ['false'])[0].lower() == 'true'
        limit = int(params.get('limit', [10])[0])
        offset = int(params.get('offset', [0])[0])
        
        # Get emails data
        result = self.sm.get_processed_emails(classified_only, limit, offset)
        
        # Return JSON response
        self.send_response(200)
        self.send_header('Content-type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps(result).encode())

    def handle_reset(self):
        """Reset database - clear all data"""
        self.sm.reset_database()
        
        # Redirect back to dashboard
        self.send_response(302)
        self.send_header('Location', '/?reset=1')
        self.end_headers()

    def serve_static_file(self, path):
        """Serve static files (fonts, etc.)"""
        try:
            # Remove leading slash and construct file path
            file_path = path[1:]  # Remove leading /
            
            # Security check - only serve from fonts directory
            if not file_path.startswith('fonts/'):
                self.send_error(403)
                return
                
            # Open and serve the file
            with open(file_path, 'rb') as f:
                content = f.read()
                
            # Determine content type
            if file_path.endswith('.woff'):
                content_type = 'font/woff'
            elif file_path.endswith('.woff2'):
                content_type = 'font/woff2'
            else:
                content_type = 'application/octet-stream'
                
            self.send_response(200)
            self.send_header('Content-type', content_type)
            self.send_header('Cache-Control', 'public, max-age=31536000')  # Cache fonts for 1 year
            self.end_headers()
            self.wfile.write(content)
            
        except FileNotFoundError:
            self.send_error(404)
        except Exception as e:
            print(f"Error serving static file: {e}")
            self.send_error(500)

def create_handler(subscription_manager):
    """Create request handler with subscription manager"""
    def handler(*args, **kwargs):
        WebServer(subscription_manager, *args, **kwargs)
    return handler

def main():
    """Main function to start the application"""
    print("🚀 Starting Subscription Manager...")
    
    # Initialize subscription manager
    sm = SubscriptionManager()
    
    # Create web server
    server_address = ('', sm.port)
    handler = create_handler(sm)
    httpd = HTTPServer(server_address, handler)
    
    print(f"✅ Server running at http://localhost:{sm.port}")
    print("   Visit the URL above to use the application")
    
    # Optionally open browser
    webbrowser.open(f'http://localhost:{sm.port}')
    
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n👋 Shutting down...")
        httpd.shutdown()

if __name__ == '__main__':
    main()