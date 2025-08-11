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
            # Get oldest processed message to fetch older emails
            conn = self.get_db_connection()
            cursor = conn.cursor()
            cursor.execute('''
                SELECT gmail_message_id FROM processed_emails 
                WHERE connection_id = ? 
                ORDER BY received_at ASC 
                LIMIT 1
            ''', (connection_id,))
            oldest_result = cursor.fetchone()
            conn.close()
            
            if oldest_result:
                # Use Gmail search to get messages older than the oldest processed
                list_url += f'&q=before:{oldest_result[0]}'
        
        response = requests.get(list_url, headers=headers)
        messages = response.json().get('messages', [])
        
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
            <script src="https://cdn.tailwindcss.com"></script>
            <style>
                .card {{ background: white; border-radius: 8px; padding: 20px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }}
                .tab-button.active {{ border-color: #3b82f6; color: #2563eb; }}
                .tab-button {{ border-color: transparent; color: #6b7280; }}
                .tab-button:hover {{ color: #374151; }}
            </style>
        </head>
        <body class="bg-gray-100 min-h-screen">
            <div class="container mx-auto px-4 py-8">
                <h1 class="text-3xl font-bold mb-8">Subscription Manager</h1>
                
                <!-- Gmail Connection -->
                <div class="card mb-8">
                    <h2 class="text-xl font-semibold mb-4">Gmail Connection</h2>
                    {self.render_connections(connections)}
                </div>
                
                <!-- Sync Section -->
                <div class="card mb-8">
                    <h2 class="text-xl font-semibold mb-4">Email Sync</h2>
                    <div class="space-y-4">
                        <div class="flex items-center space-x-4">
                            <label class="font-medium">Number of emails:</label>
                            <select id="emailCount" class="border rounded px-3 py-1">
                                <option value="5">5</option>
                                <option value="30" selected>30</option>
                                <option value="100">100</option>
                                <option value="500">500</option>
                            </select>
                        </div>
                        <div class="flex items-center space-x-4">
                            <label class="font-medium">Sync direction:</label>
                            <select id="syncDirection" class="border rounded px-3 py-1">
                                <option value="recent" selected>Most recent emails</option>
                                <option value="older">Older emails (from last processed)</option>
                            </select>
                        </div>
                        <button onclick="syncEmails()" 
                                class="bg-blue-500 text-white px-4 py-2 rounded hover:bg-blue-600">
                            Sync Emails
                        </button>
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
                        document.querySelectorAll('.tab-content').forEach(el => el.classList.add('hidden'));
                        
                        // Remove active class from all tabs
                        document.querySelectorAll('.tab-button').forEach(el => {{
                            el.classList.remove('active', 'border-blue-500', 'text-blue-600');
                            el.classList.add('border-transparent', 'text-gray-500');
                        }});
                        
                        // Show selected tab content
                        document.getElementById(tabName + '-content').classList.remove('hidden');
                        
                        // Activate selected tab
                        const activeTab = document.getElementById(tabName + '-tab');
                        activeTab.classList.add('active', 'border-blue-500', 'text-blue-600');
                        activeTab.classList.remove('border-transparent', 'text-gray-500');
                        
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
                                document.getElementById(targetDiv).innerHTML = '<p class=\"text-red-600\">Error loading emails</p>';
                            }});
                    }}
                    
                    function renderEmailTable(data, showClassified) {{
                        if (data.emails.length === 0) {{
                            return '<p class=\"text-gray-500 text-center py-8\">No emails found. Try syncing first.</p>';
                        }}
                        
                        let html = `
                            <div class=\"overflow-x-auto\">
                                <table class=\"min-w-full divide-y divide-gray-200\">
                                    <thead class=\"bg-gray-50\">
                                        <tr>
                                            <th class=\"px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase\">Subject</th>
                                            <th class=\"px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase\">Sender</th>`;
                        
                        if (showClassified) {{
                            html += `
                                            <th class=\"px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase\">Subscription</th>
                                            <th class=\"px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase\">Vendor</th>
                                            <th class=\"px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase\">Confidence</th>`;
                        }}
                        
                        html += `
                                            <th class=\"px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase\">Received</th>
                                        </tr>
                                    </thead>
                                    <tbody class=\"bg-white divide-y divide-gray-200\">`;
                        
                        data.emails.forEach(email => {{
                            const truncatedSubject = email.subject.length > 50 ? email.subject.substring(0, 50) + '...' : email.subject;
                            const truncatedSender = email.sender.length > 30 ? email.sender.substring(0, 30) + '...' : email.sender;
                            const receivedDate = new Date(email.received_at).toLocaleString();
                            
                            html += `
                                <tr>
                                    <td class=\"px-6 py-4 whitespace-nowrap font-medium text-gray-900\">${{truncatedSubject}}</td>
                                    <td class=\"px-6 py-4 whitespace-nowrap text-gray-800\">${{truncatedSender}}</td>`;
                            
                            if (showClassified) {{
                                const isSubscription = email.is_subscription ? 'Yes' : 'No';
                                const subscriptionClass = email.is_subscription ? 'bg-green-100 text-green-800' : 'bg-gray-100 text-gray-600';
                                const vendor = email.vendor || '-';
                                const confidence = email.confidence_score ? (parseFloat(email.confidence_score) * 100).toFixed(1) + '%' : '-';
                                
                                html += `
                                    <td class=\"px-6 py-4 whitespace-nowrap\">
                                        <span class=\"px-2 inline-flex text-xs leading-5 font-semibold rounded-full ${{subscriptionClass}}\">
                                            ${{isSubscription}}
                                        </span>
                                    </td>
                                    <td class=\"px-6 py-4 whitespace-nowrap text-sm text-gray-900\">${{vendor}}</td>
                                    <td class=\"px-6 py-4 whitespace-nowrap text-sm text-gray-900\">${{confidence}}</td>`;
                            }}
                            
                            html += `
                                    <td class=\"px-6 py-4 whitespace-nowrap text-sm text-gray-600\">${{receivedDate}}</td>
                                </tr>`;
                        }});
                        
                        html += `
                                    </tbody>
                                </table>
                            </div>
                            <div class=\"mt-4 text-sm text-gray-600\">
                                Total: ${{data.total}} emails
                            </div>`;
                        
                        return html;
                    }}
                    
                    // Initialize first tab on load
                    document.addEventListener('DOMContentLoaded', function() {{
                        showTab('all-emails');
                    }});
                </script>
                
                <!-- Email Data Tabs -->
                <div class="card">
                    <div class="border-b border-gray-200 mb-6">
                        <nav class="-mb-px flex space-x-8">
                            <button onclick="showTab('all-emails')" id="all-emails-tab" 
                                    class="tab-button active py-2 px-1 border-b-2 font-medium text-sm">
                                All Emails
                            </button>
                            <button onclick="showTab('classified')" id="classified-tab"
                                    class="tab-button py-2 px-1 border-b-2 font-medium text-sm">
                                Classified Emails
                            </button>
                            <button onclick="showTab('subscriptions')" id="subscriptions-tab"
                                    class="tab-button py-2 px-1 border-b-2 font-medium text-sm">
                                Subscriptions ({len(subscriptions)})
                            </button>
                        </nav>
                    </div>
                    
                    <!-- All Emails Tab -->
                    <div id="all-emails-content" class="tab-content">
                        <div id="all-emails-data">Loading...</div>
                    </div>
                    
                    <!-- Classified Emails Tab -->
                    <div id="classified-content" class="tab-content hidden">
                        <div id="classified-data">Loading...</div>
                    </div>
                    
                    <!-- Subscriptions Tab -->
                    <div id="subscriptions-content" class="tab-content hidden">
                        {self.render_subscriptions(subscriptions)}
                    </div>
                </div>
            </div>
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
                <p class="text-gray-600 mb-4">No Gmail connection found.</p>
                <a href="/auth/gmail" class="bg-red-500 text-white px-4 py-2 rounded hover:bg-red-600">
                    Connect Gmail
                </a>
            '''
        
        html = "<div class='space-y-4'>"
        for conn in connections:
            status = "✅ Active" if conn['is_active'] else "❌ Inactive"
            last_sync = conn['last_sync_at'] if conn['last_sync_at'] else 'Never'
            html += f'''
                <div class="flex justify-between items-center p-4 bg-gray-50 rounded">
                    <div>
                        <strong>{conn['email']}</strong>
                        <span class="ml-4 text-sm text-gray-600">{status}</span>
                    </div>
                    <div class="text-sm text-gray-600">Last sync: {last_sync}</div>
                </div>
            '''
        html += "</div>"
        return html

    def render_subscriptions(self, subscriptions):
        """Render subscriptions table"""
        if not subscriptions:
            return "<p class='text-gray-600'>No subscriptions found. Try syncing your emails first.</p>"
        
        html = '''
            <div class="overflow-x-auto">
                <table class="min-w-full divide-y divide-gray-200">
                    <thead class="bg-gray-50">
                        <tr>
                            <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Vendor</th>
                            <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Amount</th>
                            <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Billing</th>
                            <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Status</th>
                            <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Confidence</th>
                        </tr>
                    </thead>
                    <tbody class="bg-white divide-y divide-gray-200">
        '''
        
        for sub in subscriptions:
            amount = f"${sub['amount']} {sub['currency']}" if sub['amount'] else 'Unknown'
            billing = sub['billing_cycle'] or 'Unknown'
            confidence = f"{float(sub['confidence_score'] or 0):.1%}"
            
            html += f'''
                <tr>
                    <td class="px-6 py-4 whitespace-nowrap">
                        <div class="font-medium text-gray-900">{sub['vendor_name']}</div>
                        <div class="text-sm text-gray-500">{sub['vendor_email'] or ''}</div>
                    </td>
                    <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-900">{amount}</td>
                    <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-900">{billing}</td>
                    <td class="px-6 py-4 whitespace-nowrap">
                        <span class="px-2 inline-flex text-xs leading-5 font-semibold rounded-full bg-green-100 text-green-800">
                            {sub['status']}
                        </span>
                    </td>
                    <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-900">{confidence}</td>
                </tr>
            '''
        
        html += '</tbody></table></div>'
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