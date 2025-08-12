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
        """Fetch Gmail messages using batch requests for efficiency"""
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
        print(f"Gmail API returned {len(messages)} message IDs")
        
        # Save the nextPageToken for future "older" fetches
        if next_page_token:
            conn = self.get_db_connection()
            cursor = conn.cursor()
            cursor.execute('UPDATE connections SET fetch_page_token = ? WHERE id = ?', 
                          (next_page_token, connection_id))
            conn.commit()
            conn.close()
            print(f"Saved page token for next older fetch")
        
        # Use threaded individual fetches for reliability and speed
        email_data = self.threaded_fetch_messages(messages, headers)
        
        return email_data
    
    def threaded_fetch_messages(self, messages, headers):
        """Fetch messages using concurrent threads for speed"""
        import threading
        from concurrent.futures import ThreadPoolExecutor, as_completed
        import time
        
        email_data = []
        fetch_lock = threading.Lock()
        
        def fetch_single_message(message, index):
            """Fetch a single message - thread worker function"""
            try:
                msg_url = f'https://gmail.googleapis.com/gmail/v1/users/me/messages/{message["id"]}'
                msg_response = requests.get(msg_url, headers=headers, timeout=15)
                
                if msg_response.status_code == 429:
                    # Rate limited - wait and retry once
                    time.sleep(1)
                    msg_response = requests.get(msg_url, headers=headers, timeout=15)
                
                if msg_response.status_code == 200:
                    msg_data = msg_response.json()
                    
                    # Extract email details
                    headers_list = msg_data['payload'].get('headers', [])
                    msg_headers = {h['name']: h['value'] for h in headers_list if 'name' in h and 'value' in h}
                    
                    try:
                        body = self.extract_email_body(msg_data['payload'])
                    except Exception as e:
                        print(f"      Warning: Error extracting body for email {index+1}: {e}")
                        body = ""
                    
                    email_info = {
                        'id': message['id'],
                        'thread_id': msg_data.get('threadId', ''),
                        'subject': msg_headers.get('Subject', ''),
                        'sender': msg_headers.get('From', ''),
                        'date': msg_headers.get('Date', ''),
                        'body': body
                    }
                    
                    # Thread-safe append
                    with fetch_lock:
                        email_data.append(email_info)
                        if (index + 1) % 25 == 0:  # Progress every 25 emails
                            print(f"    Progress: {index + 1}/{len(messages)} emails fetched...")
                    
                    return True
                else:
                    print(f"      Error fetching email {index+1}: HTTP {msg_response.status_code}")
                    return False
                    
            except requests.exceptions.Timeout:
                print(f"      Timeout fetching email {index+1}")
                return False
            except Exception as e:
                print(f"      Error fetching email {index+1}: {e}")
                return False
        
        # Use ThreadPoolExecutor for concurrent fetching
        max_workers = min(10, len(messages))  # Limit concurrent requests
        print(f"  Using {max_workers} concurrent threads to fetch {len(messages)} emails...")
        
        start_time = time.time()
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            # Submit all fetch tasks
            future_to_index = {
                executor.submit(fetch_single_message, message, i): i 
                for i, message in enumerate(messages)
            }
            
            # Wait for completion
            completed = 0
            for future in as_completed(future_to_index):
                completed += 1
                # Progress updates handled in the worker function
        
        fetch_time = time.time() - start_time
        print(f"  ✓ Threaded fetch complete: {len(email_data)}/{len(messages)} emails in {fetch_time:.1f}s")
        print(f"    Average: {fetch_time/len(messages):.2f}s per email")
        
        return email_data
    
    def batch_fetch_messages(self, messages, headers):
        """Fetch multiple messages efficiently using Gmail batch API"""
        import uuid
        from email.mime.multipart import MIMEMultipart
        from email.mime.application import MIMEApplication
        
        email_data = []
        batch_size = 100  # Gmail allows up to 100 requests per batch
        
        for batch_start in range(0, len(messages), batch_size):
            batch_end = min(batch_start + batch_size, len(messages))
            batch_messages = messages[batch_start:batch_end]
            
            batch_num = batch_start//batch_size + 1
            total_batches = (len(messages) + batch_size - 1) // batch_size
            print(f"  Batch {batch_num}/{total_batches}: Fetching emails {batch_start+1}-{batch_end} of {len(messages)} total")
            
            # Create multipart request for batch
            boundary = f"batch_{uuid.uuid4()}"
            batch_body = ""
            
            for i, message in enumerate(batch_messages):
                batch_body += f"--{boundary}\n"
                batch_body += "Content-Type: application/http\n"
                batch_body += f"Content-ID: <item{i}>\n\n"
                batch_body += f"GET /gmail/v1/users/me/messages/{message['id']} HTTP/1.1\n\n"
            
            batch_body += f"--{boundary}--"
            
            # Send batch request - Gmail uses standard Google batch endpoint
            batch_url = "https://www.googleapis.com/batch"
            batch_headers = {
                'Authorization': headers['Authorization'],
                'Content-Type': f'multipart/mixed; boundary={boundary}'
            }
            
            try:
                batch_response = requests.post(batch_url, headers=batch_headers, data=batch_body, timeout=30)
                
                if batch_response.status_code == 200:
                    # Parse multipart response
                    try:
                        responses = self.parse_batch_response(batch_response.text)
                        print(f"    ✓ Batch successful: {len(responses)} emails returned")
                    except Exception as parse_error:
                        print(f"    ✗ Batch parsing error: {parse_error}")
                        print(f"    → Response preview: {batch_response.text[:200]}...")
                        responses = []
                    
                    for response_data in responses:
                        if response_data:
                            try:
                                # Validate response has required fields
                                if 'payload' not in response_data:
                                    print(f"      Warning: Email response missing 'payload' field, skipping...")
                                    continue
                                    
                                if 'id' not in response_data:
                                    print(f"      Warning: Email response missing 'id' field, skipping...")
                                    continue
                                
                                # Extract email details safely
                                payload = response_data['payload']
                                headers_list = payload.get('headers', [])
                                msg_headers = {h['name']: h['value'] for h in headers_list if 'name' in h and 'value' in h}
                                
                                try:
                                    body = self.extract_email_body(payload)
                                except Exception as e:
                                    print(f"      Warning: Error extracting body for email {response_data.get('id', 'unknown')}: {e}")
                                    body = ""
                                
                                email_data.append({
                                    'id': response_data['id'],
                                    'thread_id': response_data.get('threadId', ''),
                                    'subject': msg_headers.get('Subject', ''),
                                    'sender': msg_headers.get('From', ''),
                                    'date': msg_headers.get('Date', ''),
                                    'body': body
                                })
                                
                            except Exception as e:
                                print(f"      Warning: Error processing email in batch: {e}")
                                continue
                else:
                    print(f"    ✗ Batch failed (status {batch_response.status_code}), falling back to individual requests...")
                    # Fall back to individual requests for this batch
                    for message in batch_messages:
                        try:
                            msg_url = f'https://gmail.googleapis.com/gmail/v1/users/me/messages/{message["id"]}'
                            msg_response = requests.get(msg_url, headers=headers, timeout=10)
                            if msg_response.status_code == 200:
                                msg_data = msg_response.json()
                                msg_headers = {h['name']: h['value'] for h in msg_data['payload'].get('headers', [])}
                                body = self.extract_email_body(msg_data['payload'])
                                
                                email_data.append({
                                    'id': message['id'],
                                    'thread_id': msg_data.get('threadId', ''),
                                    'subject': msg_headers.get('Subject', ''),
                                    'sender': msg_headers.get('From', ''),
                                    'date': msg_headers.get('Date', ''),
                                    'body': body
                                })
                        except Exception as e:
                            print(f"Error fetching individual message: {e}")
                            continue
                            
            except Exception as e:
                print(f"    ✗ Batch request error: {e}")
                print(f"    → Falling back to individual requests for batch {batch_num}...")
                # Fall back to individual fetches for this batch
                for message in batch_messages:
                    try:
                        msg_url = f'https://gmail.googleapis.com/gmail/v1/users/me/messages/{message["id"]}'
                        msg_response = requests.get(msg_url, headers=headers, timeout=10)
                        if msg_response.status_code == 200:
                            msg_data = msg_response.json()
                            msg_headers = {h['name']: h['value'] for h in msg_data['payload'].get('headers', [])}
                            body = self.extract_email_body(msg_data['payload'])
                            
                            email_data.append({
                                'id': message['id'],
                                'thread_id': msg_data.get('threadId', ''),
                                'subject': msg_headers.get('Subject', ''),
                                'sender': msg_headers.get('From', ''),
                                'date': msg_headers.get('Date', ''),
                                'body': body
                            })
                    except Exception as e:
                        print(f"Error fetching individual message: {e}")
                        continue
        
        print(f"Successfully fetched {len(email_data)} emails")
        return email_data
    
    def parse_batch_response(self, response_text):
        """Parse multipart batch response from Gmail API"""
        import json
        import re
        
        responses = []
        # Split by boundary markers - look for the actual boundary in response
        boundary_match = re.search(r'boundary=([a-zA-Z0-9_-]+)', response_text)
        if boundary_match:
            boundary = boundary_match.group(1)
            parts = response_text.split(f'--{boundary}')
        else:
            # Fallback: split by any batch boundary pattern
            parts = re.split(r'--batch_[a-zA-Z0-9-]+', response_text)
        
        for part in parts:
            if 'Content-Type: application/http' in part:
                try:
                    # Look for HTTP response (after the double newline)
                    http_parts = part.split('\n\n', 2)
                    if len(http_parts) >= 2:
                        # Find JSON in the HTTP response body
                        json_text = http_parts[-1].strip()
                        
                        # Clean up any extra newlines or boundaries
                        json_text = re.sub(r'\n--.*$', '', json_text, flags=re.MULTILINE)
                        json_text = json_text.strip()
                        
                        if json_text and json_text.startswith('{'):
                            response_data = json.loads(json_text)
                            # Validate it has required fields
                            if 'id' in response_data and 'payload' in response_data:
                                responses.append(response_data)
                            else:
                                print(f"      Warning: Response missing required fields: {list(response_data.keys())}")
                        
                except json.JSONDecodeError as e:
                    print(f"      Warning: JSON decode error in batch response: {e}")
                    continue
                except Exception as e:
                    print(f"      Warning: Error parsing batch response part: {e}")
                    continue
        
        print(f"    Parsed {len(responses)} valid email responses from batch")
        return responses

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
        import time
        start_time = time.time()
        
        print(f"\n{'='*60}")
        print(f"STARTING EMAIL SYNC")
        print(f"{'='*60}")
        print(f"Request: {max_results} emails ({fetch_direction})")
        print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"{'='*60}\n")
        
        # Phase 1: Fetch emails from Gmail
        print(f"PHASE 1: Fetching emails from Gmail...")
        fetch_start = time.time()
        emails = self.fetch_gmail_messages(connection_id, max_results, fetch_direction)
        fetch_time = time.time() - fetch_start
        print(f"✓ Fetched {len(emails)} emails in {fetch_time:.1f} seconds")
        print(f"  Average: {fetch_time/len(emails):.2f} seconds per email\n" if emails else "\n")
        
        # Phase 2: Process and classify emails
        print(f"PHASE 2: Processing and classifying emails...")
        print(f"{'='*60}")
        
        conn = self.get_db_connection()
        cursor = conn.cursor()
        
        new_subscriptions = 0
        processed_count = 0
        skipped_count = 0
        error_count = 0
        
        for i, email in enumerate(emails, 1):
            # Check if already processed
            cursor.execute('SELECT id FROM processed_emails WHERE gmail_message_id = ?', 
                          (email['id'],))
            if cursor.fetchone():
                skipped_count += 1
                print(f"  [{i}/{len(emails)}] SKIP (already processed): {email['subject'][:50]}")
                continue
            
            processed_count += 1
            print(f"  [{i}/{len(emails)}] PROCESSING: {email['subject'][:50]}")
            
            # Classify with LLM
            classify_start = time.time()
            classification = self.classify_email_with_llm(f"Subject: {email['subject']}\nFrom: {email['sender']}\nBody: {email['body']}")
            classify_time = time.time() - classify_start
            
            # Show classification result
            if classification['is_subscription']:
                confidence_pct = classification['confidence'] * 100
                print(f"       → SUBSCRIPTION DETECTED! {classification.get('vendor_name', 'Unknown')} ({confidence_pct:.0f}% confidence)")
                print(f"         Time: {classify_time:.1f}s")
            else:
                print(f"       → Not a subscription (Time: {classify_time:.1f}s)")
            
            try:
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
                    if classification.get('amount'):
                        print(f"       ✓ Saved: ${classification['amount']} {classification.get('billing_cycle', 'Unknown cycle')}")
                    else:
                        print(f"       ✓ Saved to subscriptions")
                        
            except Exception as e:
                error_count += 1
                print(f"       ✗ ERROR saving to database: {e}")
        
        conn.commit()
        conn.close()
        
        # Summary
        total_time = time.time() - start_time
        print(f"\n{'='*60}")
        print(f"SYNC COMPLETE")
        print(f"{'='*60}")
        print(f"Total time: {total_time:.1f} seconds")
        print(f"Emails fetched: {len(emails)}")
        print(f"Emails processed: {processed_count}")
        print(f"Emails skipped (duplicates): {skipped_count}")
        print(f"Subscriptions found: {new_subscriptions}")
        if error_count > 0:
            print(f"Errors: {error_count}")
        print(f"Average time per email: {total_time/len(emails):.2f}s" if emails else "No emails to process")
        print(f"{'='*60}\n")
        
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
        elif path.startswith('/icons/'):
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
                    position: relative;
                    min-width: 200px;
                    min-height: 150px;
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
                    font-size: 12px;
                    line-height: 1;
                    background: #c0c0c0;
                    color: #000;
                    cursor: pointer;
                }}
                
                .title-bar-controls button:hover {{
                    background: #dfdfdf;
                }}
                
                .title-bar-controls button:active {{
                    background: #a0a0a0;
                    box-shadow: inset 1px 1px #808080, inset -1px -1px #fff;
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
                    position: relative;
                    overflow: hidden;
                    background: #008080;
                }}
                
                .desktop-icons {{
                    position: absolute;
                    top: 20px;
                    left: 20px;
                    display: grid;
                    grid-template-columns: repeat(auto-fill, 80px);
                    gap: 20px;
                    z-index: 10;
                }}
                
                .desktop-icon {{
                    width: 64px;
                    height: 80px;
                    display: flex;
                    flex-direction: column;
                    align-items: center;
                    justify-content: center;
                    cursor: pointer;
                    padding: 4px;
                    border: 1px solid transparent;
                    user-select: none;
                }}
                
                .desktop-icon:hover {{
                    background: rgba(255, 255, 255, 0.1);
                    border: 1px dotted #fff;
                }}
                
                .desktop-icon.selected {{
                    background: rgba(0, 0, 128, 0.3);
                    border: 1px dotted #fff;
                }}
                
                .desktop-icon-image {{
                    width: 32px;
                    height: 32px;
                    margin-bottom: 4px;
                    display: flex;
                    align-items: center;
                    justify-content: center;
                }}
                
                .desktop-icon-image img {{
                    width: 32px;
                    height: 32px;
                    image-rendering: pixelated;
                    image-rendering: -moz-crisp-edges;
                    image-rendering: crisp-edges;
                }}
                
                .desktop-icon-label {{
                    font-size: 10px;
                    color: white;
                    text-align: center;
                    line-height: 1.2;
                    text-shadow: 1px 1px 0px #000;
                    max-width: 60px;
                    overflow: hidden;
                    text-overflow: ellipsis;
                }}
                
                .windows-container {{
                    position: relative;
                    width: 100%;
                    height: 100vh;
                }}
                
                /* Window positioning */
                .window {{
                    width: 500px;
                    min-height: 200px;
                    max-width: 90vw;
                    display: none; /* Hidden by default */
                }}
                
                /* Data viewer window (larger) */
                .window:nth-child(3) {{
                    width: 700px;
                    min-height: 400px;
                }}
                
                /* Taskbar */
                .taskbar {{
                    position: fixed;
                    bottom: 0;
                    left: 0;
                    right: 0;
                    height: 28px;
                    background: #c0c0c0;
                    border-top: 1px solid #ffffff;
                    border-bottom: 1px solid #0a0a0a;
                    box-shadow: inset 0 1px 0 #ffffff, inset 0 -1px 0 #0a0a0a;
                    display: flex;
                    align-items: center;
                    font-family: "Pixelated MS Sans Serif", Arial;
                    font-size: 11px;
                    z-index: 1000;
                }}
                
                .start-button {{
                    height: 22px;
                    padding: 2px 4px 2px 2px;
                    margin: 2px;
                    background: #c0c0c0;
                    border: 1px solid;
                    border-color: #ffffff #0a0a0a #0a0a0a #ffffff;
                    box-shadow: inset 1px 1px 0 #dfdfdf, inset -1px -1px 0 #808080;
                    cursor: pointer;
                    display: flex;
                    align-items: center;
                    font-family: "Pixelated MS Sans Serif", Arial;
                    font-size: 11px;
                    color: #000;
                    font-weight: bold;
                }}
                
                .start-button:hover {{
                    background: #dfdfdf;
                }}
                
                .start-button:active {{
                    border-color: #0a0a0a #ffffff #ffffff #0a0a0a;
                    box-shadow: inset -1px -1px 0 #dfdfdf, inset 1px 1px 0 #808080;
                }}
                
                .task-buttons {{
                    flex: 1;
                    display: flex;
                    margin: 0 4px;
                    gap: 2px;
                }}
                
                .task-button {{
                    height: 22px;
                    padding: 2px 8px;
                    background: #c0c0c0;
                    border: 1px solid;
                    border-color: #ffffff #0a0a0a #0a0a0a #ffffff;
                    box-shadow: inset 1px 1px 0 #dfdfdf, inset -1px -1px 0 #808080;
                    cursor: pointer;
                    font-family: "Pixelated MS Sans Serif", Arial;
                    font-size: 11px;
                    color: #000;
                    white-space: nowrap;
                    overflow: hidden;
                    text-overflow: ellipsis;
                    min-width: 100px;
                    max-width: 200px;
                }}
                
                .task-button:hover {{
                    background: #dfdfdf;
                }}
                
                .task-button.active {{
                    border-color: #0a0a0a #ffffff #ffffff #0a0a0a;
                    box-shadow: inset -1px -1px 0 #dfdfdf, inset 1px 1px 0 #808080;
                    background: #dfdfdf;
                }}
                
                .system-tray {{
                    height: 22px;
                    margin: 2px;
                    padding: 2px 6px;
                    background: #c0c0c0;
                    border: 1px inset #c0c0c0;
                    display: flex;
                    align-items: center;
                }}
                
                .tray-clock {{
                    font-family: "Pixelated MS Sans Serif", Arial;
                    font-size: 11px;
                    color: #000;
                }}
                
                /* Add padding to desktop to avoid overlap with taskbar */
                .desktop {{
                    padding-bottom: 40px;
                }}
                
                /* Window Resize Handles */
                .resize-handle {{
                    position: absolute;
                    background: transparent;
                }}
                
                .resize-handle.n {{
                    top: 0;
                    left: 8px;
                    right: 8px;
                    height: 4px;
                    cursor: n-resize;
                }}
                
                .resize-handle.s {{
                    bottom: 0;
                    left: 8px;
                    right: 8px;
                    height: 4px;
                    cursor: s-resize;
                }}
                
                .resize-handle.e {{
                    top: 8px;
                    right: 0;
                    bottom: 8px;
                    width: 4px;
                    cursor: e-resize;
                }}
                
                .resize-handle.w {{
                    top: 8px;
                    left: 0;
                    bottom: 8px;
                    width: 4px;
                    cursor: w-resize;
                }}
                
                .resize-handle.ne {{
                    top: 0;
                    right: 0;
                    width: 8px;
                    height: 8px;
                    cursor: ne-resize;
                }}
                
                .resize-handle.nw {{
                    top: 0;
                    left: 0;
                    width: 8px;
                    height: 8px;
                    cursor: nw-resize;
                }}
                
                .resize-handle.se {{
                    bottom: 0;
                    right: 0;
                    width: 8px;
                    height: 8px;
                    cursor: se-resize;
                }}
                
                .resize-handle.sw {{
                    bottom: 0;
                    left: 0;
                    width: 8px;
                    height: 8px;
                    cursor: sw-resize;
                }}
                
                /* Visual resize indicator (optional subtle border on hover) */
                .window:hover .resize-handle {{
                    background: rgba(0, 0, 0, 0.1);
                }}
            </style>
        </head>
        <body>
            <div class="desktop">
                <!-- Desktop Icons -->
                <div class="desktop-icons">
                    <div class="desktop-icon" data-window="0">
                        <div class="desktop-icon-image">
                            <img src="/icons/settings.png" alt="Settings" />
                        </div>
                        <div class="desktop-icon-label">Gmail Connection</div>
                    </div>
                    <div class="desktop-icon" data-window="1">
                        <div class="desktop-icon-image">
                            <img src="/icons/mail.png" alt="Mail" />
                        </div>
                        <div class="desktop-icon-label">Email Sync</div>
                    </div>
                    <div class="desktop-icon" data-window="2">
                        <div class="desktop-icon-image">
                            <img src="/icons/chart.png" alt="Chart" />
                        </div>
                        <div class="desktop-icon-label">Processing Data</div>
                    </div>
                    <div class="desktop-icon" data-action="reset">
                        <div class="desktop-icon-image">
                            <img src="/icons/trash.png" alt="Trash" />
                        </div>
                        <div class="desktop-icon-label">Reset Database</div>
                    </div>
                </div>
                
                <div class="windows-container">
                    
                    <!-- Gmail Connection Window -->
                    <div class="window">
                        <div class="title-bar">
                            <div class="title-bar-text">Gmail Connection</div>
                            <div class="title-bar-controls">
                                <button aria-label="Minimize"></button>
                                <button aria-label="Maximize"></button>
                                <button aria-label="Close"></button>
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
                                <button aria-label="Close"></button>
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
                            <div class="title-bar-text">Processing Data</div>
                            <div class="title-bar-controls">
                                <button aria-label="Minimize"></button>
                                <button aria-label="Maximize"></button>
                                <button aria-label="Close"></button>
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
                                </menu>
                            </div>
                            
                            <!-- Tab Content -->
                            <div style="padding: 8px;">
                                <!-- All Emails Tab -->
                                <div id="all-emails-content" class="tab-content">
                                    <!-- Pagination Controls -->
                                    <div id="all-emails-pagination" style="margin-bottom: 8px; display: flex; justify-content: space-between; align-items: center;">
                                        <div style="display: flex; align-items: center; gap: 4px;">
                                            <button onclick="changePage('all-emails', -1)" id="all-emails-prev" style="min-width: 60px;">◄ Prev</button>
                                            <span id="all-emails-page-info" style="font-size: 11px; padding: 0 8px;">Page 1 of 1</span>
                                            <button onclick="changePage('all-emails', 1)" id="all-emails-next" style="min-width: 60px;">Next ►</button>
                                        </div>
                                        <div style="font-size: 10px; color: #666;">
                                            <span id="all-emails-total">0 emails total</span>
                                        </div>
                                    </div>
                                    <!-- Scrollable Data Container -->
                                    <div style="max-height: 300px; overflow-y: auto; border: 1px inset #c0c0c0; background: #fff;">
                                        <div id="all-emails-data" style="font-size: 11px;">Loading...</div>
                                    </div>
                                </div>
                                
                                <!-- Classified Emails Tab -->
                                <div id="classified-content" class="tab-content" style="display: none;">
                                    <!-- Pagination Controls -->
                                    <div id="classified-pagination" style="margin-bottom: 8px; display: flex; justify-content: space-between; align-items: center;">
                                        <div style="display: flex; align-items: center; gap: 4px;">
                                            <button onclick="changePage('classified', -1)" id="classified-prev" style="min-width: 60px;">◄ Prev</button>
                                            <span id="classified-page-info" style="font-size: 11px; padding: 0 8px;">Page 1 of 1</span>
                                            <button onclick="changePage('classified', 1)" id="classified-next" style="min-width: 60px;">Next ►</button>
                                        </div>
                                        <div style="font-size: 10px; color: #666;">
                                            <span id="classified-total">0 emails total</span>
                                        </div>
                                    </div>
                                    <!-- Scrollable Data Container -->
                                    <div style="max-height: 300px; overflow-y: auto; border: 1px inset #c0c0c0; background: #fff;">
                                        <div id="classified-data" style="font-size: 11px;">Loading...</div>
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>
                    
                </div>
            </div>
                
            <!-- Taskbar -->
            <div class="taskbar">
                <button class="start-button">
                    <img src="/icons/settings.png" alt="Start" style="width: 16px; height: 16px; margin-right: 4px;" />
                    Start
                </button>
                <div class="task-buttons" id="task-buttons">
                    <!-- Task buttons will be dynamically added here -->
                </div>
                <div class="system-tray">
                    <div class="tray-clock" id="tray-clock">12:00 PM</div>
                </div>
            </div>
                
                <script>
                    // Window Management System
                    class WindowManager {{
                        constructor() {{
                            this.windows = new Map();
                            this.zIndex = 1000;
                            this.activeWindow = null;
                            this.initializeWindows();
                            this.initializeTaskbar();
                        }}
                        
                        initializeWindows() {{
                            const windows = document.querySelectorAll('.window');
                            windows.forEach((window, index) => {{
                                const id = `window-${{index}}`;
                                window.id = id;
                                window.style.position = 'absolute';
                                window.style.zIndex = this.zIndex + index;
                                
                                // Set initial positions (staggered)
                                window.style.left = `${{50 + (index * 30)}}px`;
                                window.style.top = `${{50 + (index * 40)}}px`;
                                
                                // Store original dimensions for restore
                                const rect = window.getBoundingClientRect();
                                
                                this.windows.set(id, {{
                                    element: window,
                                    isDragging: false,
                                    startX: 0,
                                    startY: 0,
                                    initialX: 0,
                                    initialY: 0,
                                    isMinimized: false,
                                    isMaximized: false,
                                    originalWidth: window.style.width || `${{rect.width}}px`,
                                    originalHeight: window.style.height || `${{rect.height}}px`,
                                    originalLeft: `${{50 + (index * 30)}}px`,
                                    originalTop: `${{50 + (index * 40)}}px`
                                }});
                                
                                this.makeDraggable(window);
                                this.addWindowControls(window);
                                this.addResizeHandles(window);
                            }});
                        }}
                        
                        makeDraggable(windowElement) {{
                            const titleBar = windowElement.querySelector('.title-bar');
                            const windowData = this.windows.get(windowElement.id);
                            
                            titleBar.style.cursor = 'move';
                            titleBar.style.userSelect = 'none';
                            
                            // Mouse down on title bar
                            titleBar.addEventListener('mousedown', (e) => {{
                                // Don't drag if clicking on window controls
                                if (e.target.closest('.title-bar-controls')) return;
                                
                                this.startDrag(windowElement, e);
                                e.preventDefault();
                            }});
                            
                            // Bring window to front when clicked anywhere
                            windowElement.addEventListener('mousedown', () => {{
                                this.bringToFront(windowElement);
                            }});
                        }}
                        
                        startDrag(windowElement, e) {{
                            const windowData = this.windows.get(windowElement.id);
                            const rect = windowElement.getBoundingClientRect();
                            
                            windowData.isDragging = true;
                            windowData.startX = e.clientX - rect.left;
                            windowData.startY = e.clientY - rect.top;
                            windowData.initialX = rect.left;
                            windowData.initialY = rect.top;
                            
                            this.bringToFront(windowElement);
                            
                            // Add global mouse move and up listeners
                            document.addEventListener('mousemove', this.dragWindow.bind(this, windowElement));
                            document.addEventListener('mouseup', this.stopDrag.bind(this, windowElement));
                            
                            // Prevent text selection during drag
                            document.body.style.userSelect = 'none';
                        }}
                        
                        dragWindow(windowElement, e) {{
                            const windowData = this.windows.get(windowElement.id);
                            if (!windowData.isDragging) return;
                            
                            const newX = e.clientX - windowData.startX;
                            const newY = e.clientY - windowData.startY;
                            
                            // Constrain to viewport
                            const maxX = window.innerWidth - windowElement.offsetWidth;
                            const maxY = window.innerHeight - windowElement.offsetHeight;
                            
                            const constrainedX = Math.max(0, Math.min(newX, maxX));
                            const constrainedY = Math.max(0, Math.min(newY, maxY));
                            
                            windowElement.style.left = `${{constrainedX}}px`;
                            windowElement.style.top = `${{constrainedY}}px`;
                        }}
                        
                        stopDrag(windowElement, e) {{
                            const windowData = this.windows.get(windowElement.id);
                            windowData.isDragging = false;
                            
                            // Remove global listeners
                            document.removeEventListener('mousemove', this.dragWindow.bind(this, windowElement));
                            document.removeEventListener('mouseup', this.stopDrag.bind(this, windowElement));
                            
                            // Re-enable text selection
                            document.body.style.userSelect = '';
                        }}
                        
                        bringToFront(windowElement) {{
                            if (this.activeWindow === windowElement) return;
                            
                            this.zIndex += 1;
                            windowElement.style.zIndex = this.zIndex;
                            this.activeWindow = windowElement;
                            
                            // Update title bar appearance for active window
                            this.updateWindowAppearance();
                        }}
                        
                        updateWindowAppearance() {{
                            // Reset all title bars to inactive
                            document.querySelectorAll('.title-bar').forEach(titleBar => {{
                                titleBar.style.background = 'linear-gradient(90deg, #808080, #c0c0c0)';
                            }});
                            
                            // Make active window title bar blue
                            if (this.activeWindow) {{
                                const activeTitleBar = this.activeWindow.querySelector('.title-bar');
                                activeTitleBar.style.background = 'linear-gradient(90deg, #000080, #1084d0)';
                            }}
                        }}
                        
                        addWindowControls(windowElement) {{
                            const controls = windowElement.querySelector('.title-bar-controls');
                            const buttons = controls.querySelectorAll('button');
                            
                            // Clear existing button content and add proper icons
                            buttons[0].innerHTML = '_';  // Minimize
                            buttons[1].innerHTML = '□';  // Maximize/Restore
                            buttons[2].innerHTML = '×';  // Close
                            
                            // Add click handlers
                            buttons[0].addEventListener('click', (e) => {{
                                e.stopPropagation();
                                this.minimizeWindow(windowElement);
                            }});
                            
                            buttons[1].addEventListener('click', (e) => {{
                                e.stopPropagation();
                                this.toggleMaximize(windowElement);
                            }});
                            
                            buttons[2].addEventListener('click', (e) => {{
                                e.stopPropagation();
                                this.closeWindow(windowElement);
                            }});
                        }}
                        
                        minimizeWindow(windowElement) {{
                            const windowData = this.windows.get(windowElement.id);
                            
                            if (windowData.isMinimized) {{
                                // Restore window
                                windowElement.style.display = 'block';
                                windowData.isMinimized = false;
                                this.bringToFront(windowElement);
                            }} else {{
                                // Minimize window
                                windowElement.style.display = 'none';
                                windowData.isMinimized = true;
                                
                                // If this was the active window, find next visible window
                                if (this.activeWindow === windowElement) {{
                                    this.activeWindow = null;
                                    const visibleWindows = Array.from(this.windows.values())
                                        .filter(w => !w.isMinimized && w.element !== windowElement);
                                    if (visibleWindows.length > 0) {{
                                        this.bringToFront(visibleWindows[visibleWindows.length - 1].element);
                                    }}
                                }}
                            }}
                            
                            // Update taskbar button
                            this.updateTaskButton(windowElement.id);
                        }}
                        
                        toggleMaximize(windowElement) {{
                            const windowData = this.windows.get(windowElement.id);
                            
                            if (windowData.isMaximized) {{
                                // Restore window
                                windowElement.style.width = windowData.originalWidth;
                                windowElement.style.height = windowData.originalHeight;
                                windowElement.style.left = windowData.originalLeft;
                                windowElement.style.top = windowData.originalTop;
                                windowData.isMaximized = false;
                                
                                // Update button icon
                                const maximizeBtn = windowElement.querySelector('.title-bar-controls button:nth-child(2)');
                                maximizeBtn.innerHTML = '□';
                            }} else {{
                                // Store current position before maximizing
                                windowData.originalWidth = windowElement.style.width;
                                windowData.originalHeight = windowElement.style.height;
                                windowData.originalLeft = windowElement.style.left;
                                windowData.originalTop = windowElement.style.top;
                                
                                // Maximize window
                                windowElement.style.width = '100vw';
                                windowElement.style.height = '100vh';
                                windowElement.style.left = '0px';
                                windowElement.style.top = '0px';
                                windowData.isMaximized = true;
                                
                                // Update button icon
                                const maximizeBtn = windowElement.querySelector('.title-bar-controls button:nth-child(2)');
                                maximizeBtn.innerHTML = '❐';
                            }}
                            
                            this.bringToFront(windowElement);
                        }}
                        
                        closeWindow(windowElement) {{
                            const windowData = this.windows.get(windowElement.id);
                            
                            // Hide window with fade effect
                            windowElement.style.opacity = '0';
                            windowElement.style.transition = 'opacity 0.2s ease';
                            
                            setTimeout(() => {{
                                windowElement.style.display = 'none';
                                windowElement.style.opacity = '1';
                                windowElement.style.transition = '';
                                
                                // If this was the active window, find next visible window
                                if (this.activeWindow === windowElement) {{
                                    this.activeWindow = null;
                                    const visibleWindows = Array.from(this.windows.values())
                                        .filter(w => w.element.style.display !== 'none' && w.element !== windowElement);
                                    if (visibleWindows.length > 0) {{
                                        this.bringToFront(visibleWindows[visibleWindows.length - 1].element);
                                    }}
                                }}
                            }}, 200);
                        }}
                        
                        // Method to reopen a closed window
                        openWindow(windowElement) {{
                            const windowData = this.windows.get(windowElement.id);
                            windowElement.style.display = 'block';
                            windowData.isMinimized = false;
                            this.bringToFront(windowElement);
                            this.updateTaskButton(windowElement.id);
                        }}
                        
                        // Taskbar functionality
                        initializeTaskbar() {{
                            this.updateClock();
                            setInterval(() => this.updateClock(), 1000);
                        }}
                        
                        updateClock() {{
                            const now = new Date();
                            const timeString = now.toLocaleTimeString([], {{hour: '2-digit', minute:'2-digit'}});
                            const clockElement = document.getElementById('tray-clock');
                            if (clockElement) {{
                                clockElement.textContent = timeString;
                            }}
                        }}
                        
                        createTaskButton(windowId, title) {{
                            const taskButtons = document.getElementById('task-buttons');
                            const button = document.createElement('button');
                            button.className = 'task-button';
                            button.id = `task-${{windowId}}`;
                            button.textContent = title;
                            button.addEventListener('click', () => {{
                                this.restoreFromTaskbar(windowId);
                            }});
                            taskButtons.appendChild(button);
                        }}
                        
                        removeTaskButton(windowId) {{
                            const button = document.getElementById(`task-${{windowId}}`);
                            if (button) {{
                                button.remove();
                            }}
                        }}
                        
                        updateTaskButton(windowId) {{
                            const button = document.getElementById(`task-${{windowId}}`);
                            const windowData = this.windows.get(windowId);
                            
                            if (windowData.isMinimized) {{
                                if (!button) {{
                                    const titleElement = windowData.element.querySelector('.title-bar-text');
                                    const title = titleElement ? titleElement.textContent : 'Window';
                                    this.createTaskButton(windowId, title);
                                }}
                            }} else {{
                                if (button) {{
                                    button.remove();
                                }}
                            }}
                        }}
                        
                        restoreFromTaskbar(windowId) {{
                            const windowData = this.windows.get(windowId);
                            if (windowData && windowData.isMinimized) {{
                                this.minimizeWindow(windowData.element); // This will restore it
                            }}
                        }}
                        
                        // Window Resizing functionality
                        addResizeHandles(windowElement) {{
                            const handles = ['n', 's', 'e', 'w', 'ne', 'nw', 'se', 'sw'];
                            
                            handles.forEach(direction => {{
                                const handle = document.createElement('div');
                                handle.className = `resize-handle ${{direction}}`;
                                handle.style.zIndex = '1001';
                                
                                handle.addEventListener('mousedown', (e) => {{
                                    e.preventDefault();
                                    e.stopPropagation();
                                    this.startResize(e, windowElement, direction);
                                }});
                                
                                windowElement.appendChild(handle);
                            }});
                        }}
                        
                        startResize(e, windowElement, direction) {{
                            const windowData = this.windows.get(windowElement.id);
                            if (windowData.isMaximized) return; // Don't allow resize when maximized
                            
                            const startX = e.clientX;
                            const startY = e.clientY;
                            const rect = windowElement.getBoundingClientRect();
                            const startWidth = rect.width;
                            const startHeight = rect.height;
                            const startLeft = rect.left;
                            const startTop = rect.top;
                            
                            const minWidth = 200;
                            const minHeight = 150;
                            const maxWidth = window.innerWidth - 50;
                            const maxHeight = window.innerHeight - 100;
                            
                            const onMouseMove = (e) => {{
                                const deltaX = e.clientX - startX;
                                const deltaY = e.clientY - startY;
                                
                                let newWidth = startWidth;
                                let newHeight = startHeight;
                                let newLeft = startLeft;
                                let newTop = startTop;
                                
                                // Calculate new dimensions based on resize direction
                                if (direction.includes('e')) {{
                                    newWidth = Math.max(minWidth, Math.min(maxWidth, startWidth + deltaX));
                                }}
                                if (direction.includes('w')) {{
                                    const widthDelta = Math.max(minWidth - startWidth, Math.min(maxWidth - startWidth, -deltaX));
                                    newWidth = startWidth + widthDelta;
                                    newLeft = startLeft - widthDelta;
                                }}
                                if (direction.includes('s')) {{
                                    newHeight = Math.max(minHeight, Math.min(maxHeight, startHeight + deltaY));
                                }}
                                if (direction.includes('n')) {{
                                    const heightDelta = Math.max(minHeight - startHeight, Math.min(maxHeight - startHeight, -deltaY));
                                    newHeight = startHeight + heightDelta;
                                    newTop = startTop - heightDelta;
                                }}
                                
                                // Apply new dimensions and position
                                windowElement.style.width = `${{newWidth}}px`;
                                windowElement.style.height = `${{newHeight}}px`;
                                windowElement.style.left = `${{newLeft}}px`;
                                windowElement.style.top = `${{newTop}}px`;
                            }};
                            
                            const onMouseUp = () => {{
                                document.removeEventListener('mousemove', onMouseMove);
                                document.removeEventListener('mouseup', onMouseUp);
                                document.body.style.cursor = '';
                                windowElement.style.userSelect = '';
                            }};
                            
                            document.addEventListener('mousemove', onMouseMove);
                            document.addEventListener('mouseup', onMouseUp);
                            document.body.style.cursor = getComputedStyle(e.target).cursor;
                            windowElement.style.userSelect = 'none';
                        }}
                    }}
                    
                    // Desktop Icon Manager
                    class DesktopManager {{
                        constructor(windowManager) {{
                            this.windowManager = windowManager;
                            this.selectedIcon = null;
                            this.initializeDesktop();
                        }}
                        
                        initializeDesktop() {{
                            const icons = document.querySelectorAll('.desktop-icon');
                            
                            icons.forEach(icon => {{
                                // Single click to select
                                icon.addEventListener('click', (e) => {{
                                    this.selectIcon(icon);
                                    e.stopPropagation();
                                }});
                                
                                // Double click to open
                                icon.addEventListener('dblclick', (e) => {{
                                    this.openIcon(icon);
                                    e.stopPropagation();
                                }});
                            }});
                            
                            // Click on desktop to deselect all icons
                            document.querySelector('.desktop').addEventListener('click', () => {{
                                this.deselectAllIcons();
                            }});
                            
                            // Keyboard support (Enter to open selected icon)
                            document.addEventListener('keydown', (e) => {{
                                if (e.key === 'Enter' && this.selectedIcon) {{
                                    this.openIcon(this.selectedIcon);
                                }}
                            }});
                        }}
                        
                        selectIcon(icon) {{
                            this.deselectAllIcons();
                            icon.classList.add('selected');
                            this.selectedIcon = icon;
                        }}
                        
                        deselectAllIcons() {{
                            document.querySelectorAll('.desktop-icon').forEach(icon => {{
                                icon.classList.remove('selected');
                            }});
                            this.selectedIcon = null;
                        }}
                        
                        openIcon(icon) {{
                            const windowIndex = icon.dataset.window;
                            const action = icon.dataset.action;
                            
                            if (windowIndex !== undefined) {{
                                // Open corresponding window
                                const windowElement = document.querySelectorAll('.window')[parseInt(windowIndex)];
                                if (windowElement && this.windowManager) {{
                                    this.windowManager.openWindow(windowElement);
                                }}
                            }} else if (action === 'reset') {{
                                // Handle reset database action
                                if (confirm('Are you sure you want to reset the database? This will clear all subscription data and email history.')) {{
                                    window.location.href = '/reset';
                                }}
                            }}
                            
                            this.deselectAllIcons();
                        }}
                    }}
                    
                    // Initialize window manager and desktop when page loads
                    let windowManager, desktopManager;
                    document.addEventListener('DOMContentLoaded', function() {{
                        windowManager = new WindowManager();
                        desktopManager = new DesktopManager(windowManager);
                        showTab('all-emails');
                    }});
                    
                    // Global helper functions for window management
                    function reopenWindow(windowIndex) {{
                        const windows = document.querySelectorAll('.window');
                        if (windows[windowIndex] && windowManager) {{
                            windowManager.openWindow(windows[windowIndex]);
                        }}
                    }}
                    
                    function minimizeAllWindows() {{
                        if (windowManager) {{
                            const windows = document.querySelectorAll('.window');
                            windows.forEach(window => {{
                                windowManager.minimizeWindow(window);
                            }});
                        }}
                    }}
                    
                    function openFromDesktop(iconIndex) {{
                        const icons = document.querySelectorAll('.desktop-icon');
                        if (icons[iconIndex] && desktopManager) {{
                            desktopManager.openIcon(icons[iconIndex]);
                        }}
                    }}
                    
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
                    
                    // Pagination state
                    let emailsPageState = {{
                        'all-emails': {{ page: 1, limit: 25, total: 0 }},
                        'classified': {{ page: 1, limit: 25, total: 0 }}
                    }};
                    
                    function loadEmails(classifiedOnly, page = 1) {{
                        const tabType = classifiedOnly ? 'classified' : 'all-emails';
                        const targetDiv = tabType + '-data';
                        
                        // Update page state
                        emailsPageState[tabType].page = page;
                        const limit = emailsPageState[tabType].limit;
                        const offset = (page - 1) * limit;
                        
                        document.getElementById(targetDiv).innerHTML = 'Loading...';
                        
                        fetch(`/api/emails?classified=${{classifiedOnly}}&limit=${{limit}}&offset=${{offset}}`)
                            .then(response => response.json())
                            .then(data => {{
                                // Update total and render table
                                emailsPageState[tabType].total = data.total;
                                document.getElementById(targetDiv).innerHTML = renderEmailTable(data, classifiedOnly);
                                updatePaginationControls(tabType);
                            }})
                            .catch(error => {{
                                document.getElementById(targetDiv).innerHTML = '<span style=\"color: red;\">Error loading emails</span>';
                            }});
                    }}
                    
                    function changePage(tabType, direction) {{
                        const currentPage = emailsPageState[tabType].page;
                        const newPage = currentPage + direction;
                        const classifiedOnly = tabType === 'classified';
                        
                        if (newPage >= 1) {{
                            loadEmails(classifiedOnly, newPage);
                        }}
                    }}
                    
                    function updatePaginationControls(tabType) {{
                        const state = emailsPageState[tabType];
                        const totalPages = Math.ceil(state.total / state.limit);
                        
                        // Update page info
                        document.getElementById(tabType + '-page-info').textContent = 
                            `Page ${{state.page}} of ${{totalPages || 1}}`;
                        
                        // Update total count
                        document.getElementById(tabType + '-total').textContent = 
                            `${{state.total}} emails total`;
                        
                        // Update button states
                        const prevBtn = document.getElementById(tabType + '-prev');
                        const nextBtn = document.getElementById(tabType + '-next');
                        
                        prevBtn.disabled = state.page <= 1;
                        nextBtn.disabled = state.page >= totalPages || totalPages === 0;
                        
                        // Visual feedback for disabled buttons
                        if (prevBtn.disabled) {{
                            prevBtn.style.color = '#808080';
                        }} else {{
                            prevBtn.style.color = '';
                        }}
                        
                        if (nextBtn.disabled) {{
                            nextBtn.style.color = '#808080';
                        }} else {{
                            nextBtn.style.color = '';
                        }}
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
                            </table>`;
                        
                        return html;
                    }}
                    
                    // Tab initialization is handled by WindowManager
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
            
            # Security check - only serve from fonts and icons directories
            if not (file_path.startswith('fonts/') or file_path.startswith('icons/')):
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
            elif file_path.endswith('.png'):
                content_type = 'image/png'
            elif file_path.endswith('.svg'):
                content_type = 'image/svg+xml'
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