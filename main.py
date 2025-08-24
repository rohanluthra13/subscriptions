#!/usr/bin/env python3
"""
Simple Subscription Manager - Gmail metadata fetcher
Core functionality only: Gmail OAuth + fast metadata ingestion + basic UI
"""

import os
import sqlite3
import json
import requests
import re
import threading
import uuid
from datetime import datetime, timedelta
from urllib.parse import urlencode, parse_qs, urlparse
from http.server import HTTPServer, BaseHTTPRequestHandler
from socketserver import ThreadingMixIn
from dotenv import load_dotenv
from email.utils import parsedate_to_datetime
import time
import pytz

# Load environment variables
load_dotenv()

class JobManager:
    """Manages background jobs for long-running operations"""
    def __init__(self):
        self.jobs = {}
        self.lock = threading.Lock()
    
    def create_job(self, job_type):
        """Create a new job and return its ID"""
        job_id = f"job_{uuid.uuid4().hex[:8]}"
        
        with self.lock:
            self.jobs[job_id] = {
                "id": job_id,
                "type": job_type,
                "status": "running",
                "started_at": datetime.now().isoformat(),
                "progress": {},
                "result": None,
                "error": None
            }
        
        return job_id
    
    def update_job(self, job_id, updates):
        """Update job information (thread-safe)"""
        with self.lock:
            if job_id in self.jobs:
                self.jobs[job_id].update(updates)
    
    def get_job(self, job_id):
        """Get job information (thread-safe)"""
        with self.lock:
            return self.jobs.get(job_id, None)

class SubscriptionManager:
    def __init__(self, job_manager=None):
        self.db_path = "subscriptions.db"
        self.job_manager = job_manager
        self.init_database()
        
        self.google_client_id = os.getenv('GOOGLE_CLIENT_ID')
        self.google_client_secret = os.getenv('GOOGLE_CLIENT_SECRET')
        
        self.port = 8000
        self.redirect_uri = f"http://localhost:{self.port}/auth/callback"

    def init_database(self):
        """Initialize SQLite database"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS connections (
                id TEXT PRIMARY KEY DEFAULT (hex(randomblob(16))),
                email TEXT NOT NULL UNIQUE,
                access_token TEXT NOT NULL,
                refresh_token TEXT NOT NULL,
                token_expiry TIMESTAMP NOT NULL,
                last_sync_at TIMESTAMP,
                is_active BOOLEAN DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS processed_emails (
                id TEXT PRIMARY KEY DEFAULT (hex(randomblob(16))),
                email TEXT NOT NULL,
                gmail_message_id TEXT UNIQUE NOT NULL,
                subject TEXT,
                sender TEXT,
                sender_domain TEXT,
                received_at TIMESTAMP,
                processed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                content TEXT,
                content_fetched BOOLEAN DEFAULT 0
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS subscriptions (
                id TEXT PRIMARY KEY DEFAULT (hex(randomblob(16))),
                name TEXT NOT NULL UNIQUE,
                domains TEXT,  -- JSON array
                category TEXT,
                cost DECIMAL(10,2),
                currency TEXT DEFAULT 'USD',
                billing_cycle TEXT,
                status TEXT DEFAULT 'active',
                auto_renewing BOOLEAN DEFAULT 1,
                next_billing_date DATE,
                notes TEXT,
                created_by TEXT DEFAULT 'user',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS scratchpad (
                id TEXT PRIMARY KEY DEFAULT (hex(randomblob(16))),
                item TEXT NOT NULL,
                processed BOOLEAN DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Simple migration: add missing columns if they don't exist
        try:
            cursor.execute('ALTER TABLE processed_emails ADD COLUMN sender_domain TEXT')
        except sqlite3.OperationalError:
            pass
        
        try:
            cursor.execute('ALTER TABLE processed_emails ADD COLUMN email TEXT')
        except sqlite3.OperationalError:
            pass
        
        try:
            cursor.execute('ALTER TABLE processed_emails ADD COLUMN content TEXT')
        except sqlite3.OperationalError:
            pass
        
        try:
            cursor.execute('ALTER TABLE processed_emails ADD COLUMN content_fetched BOOLEAN DEFAULT 0')
        except sqlite3.OperationalError:
            pass
        
        # Remove unused column
        try:
            cursor.execute('ALTER TABLE connections DROP COLUMN history_id')
        except sqlite3.OperationalError:
            pass
        
        conn.commit()
        conn.close()

    def extract_domain(self, sender: str) -> str:
        """Extract domain from sender email address"""
        if not sender:
            return ""
        
        # Handle formats like "Name <email@domain.com>" or just "email@domain.com"
        if '<' in sender and '>' in sender:
            # Extract email from "Name <email@domain.com>" format
            start = sender.find('<') + 1
            end = sender.find('>')
            if start > 0 and end > start:
                email = sender[start:end]
            else:
                email = sender
        else:
            email = sender
        
        # Extract domain from email
        if '@' in email:
            domain = email.split('@')[-1].strip().lower()
            return domain
        
        return ""

    def get_gmail_auth_url(self):
        """Generate Gmail OAuth URL"""
        params = {
            'client_id': self.google_client_id,
            'redirect_uri': self.redirect_uri,
            'scope': 'https://www.googleapis.com/auth/gmail.readonly',
            'response_type': 'code',
            'access_type': 'offline',
            'prompt': 'select_account consent'  # Force account selection and consent
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
        token_data = response.json()
        return token_data

    def refresh_access_token(self, refresh_token: str):
        """Refresh expired access token"""
        data = {
            'client_id': self.google_client_id,
            'client_secret': self.google_client_secret,
            'refresh_token': refresh_token,
            'grant_type': 'refresh_token',
            'scope': 'https://www.googleapis.com/auth/gmail.readonly'
        }
        
        response = requests.post('https://oauth2.googleapis.com/token', data=data)
        token_data = response.json()
        return token_data

    def get_valid_access_token(self, email: str) -> str:
        """Get valid access token, refreshing if necessary"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT access_token, refresh_token, token_expiry 
            FROM connections WHERE email = ?
        ''', (email,))
        
        result = cursor.fetchone()
        if not result:
            conn.close()
            raise Exception("Connection not found")
            
        access_token, refresh_token, token_expiry = result
        expiry_time = datetime.fromisoformat(token_expiry.replace('Z', '+00:00'))
        
        # If token expires within 5 minutes, refresh it
        if expiry_time <= datetime.now() + timedelta(minutes=5):
            print("Refreshing access token...")
            token_data = self.refresh_access_token(refresh_token)
            
            if 'access_token' in token_data:
                new_expiry = datetime.now() + timedelta(seconds=token_data['expires_in'])
                cursor.execute('''
                    UPDATE connections 
                    SET access_token = ?, token_expiry = ?
                    WHERE email = ?
                ''', (token_data['access_token'], new_expiry.isoformat(), email))
                conn.commit()
                access_token = token_data['access_token']
            else:
                conn.close()
                raise Exception("Failed to refresh token")
        
        conn.close()
        return access_token

    def fetch_year_of_emails(self, email: str, years_back: int = 1, job_id=None):
        """Simple approach: Get message IDs from last year, then fetch in small batches with retry"""
        start_time = time.time()
        
        # Step 1: Get all message IDs from the last year
        print(f"Step 1: Getting message IDs from last {years_back} year(s)...")
        
        # Update job progress if job_id provided
        if job_id and self.job_manager:
            self.job_manager.update_job(job_id, {
                "progress": {"step": "Getting message IDs", "current": 0, "total": 0}
            })
        
        access_token = self.get_valid_access_token(email)
        headers = {'Authorization': f'Bearer {access_token}'}
        
        # Calculate date for query
        date_from = (datetime.now() - timedelta(days=365 * years_back)).strftime("%Y/%m/%d")
        query = f"after:{date_from} -in:trash -in:sent"
        
        # Collect all message IDs with pagination
        all_messages = []
        next_page_token = None
        page_count = 0
        
        while True:
            page_count += 1
            # Build URL with query and pagination
            url = f'https://gmail.googleapis.com/gmail/v1/users/me/messages?q={query}&maxResults=500'
            if next_page_token:
                url += f'&pageToken={next_page_token}'
            
            response = requests.get(url, headers=headers)
            if response.status_code != 200:
                return {"error": f"Failed to get message list: {response.text}"}
            
            data = response.json()
            messages = data.get('messages', [])
            all_messages.extend(messages)
            
            print(f"  Page {page_count}: Got {len(messages)} message IDs (total: {len(all_messages)})")
            
            # Check for more pages
            next_page_token = data.get('nextPageToken')
            if not next_page_token:
                break
        
        print(f"Step 1 complete: Found {len(all_messages)} emails from last {years_back} year(s)")
        
        if not all_messages:
            return {"fetched": 0, "stored": 0, "duplicates": 0, "errors": 0, "time": 0}
        
        # Step 2: Filter out already processed messages
        print("Step 2: Checking for already processed emails...")
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Debug: Check current database state
        cursor.execute('SELECT COUNT(*) FROM processed_emails WHERE email = ?', (email,))
        current_count = cursor.fetchone()[0]
        print(f"  Current database has {current_count} emails for {email}")
        
        new_messages = []
        duplicate_count = 0
        debug_sample_new = []
        debug_sample_dup = []
        
        for message in all_messages:
            msg_id = message['id']
            cursor.execute('SELECT id FROM processed_emails WHERE gmail_message_id = ? AND email = ?', (msg_id, email))
            result = cursor.fetchone()
            if result:
                duplicate_count += 1
                if len(debug_sample_dup) < 3:
                    debug_sample_dup.append(msg_id)
            else:
                new_messages.append(message)
                if len(debug_sample_new) < 3:
                    debug_sample_new.append(msg_id)
        
        print(f"  {duplicate_count} already processed, {len(new_messages)} new emails to fetch")
        if debug_sample_new:
            print(f"  Sample new IDs: {debug_sample_new}")
        if debug_sample_dup:
            print(f"  Sample duplicate IDs: {debug_sample_dup}")
        
        if not new_messages:
            # Update last_sync_at even when no new emails found
            cursor.execute('''
                UPDATE connections 
                SET last_sync_at = ?
                WHERE email = ?
            ''', (datetime.now().isoformat(), email))
            conn.commit()
            conn.close()
            
            total_time = time.time() - start_time
            result = {"fetched": len(all_messages), "stored": 0, "duplicates": duplicate_count, "errors": 0, "time": round(total_time, 1)}
            
            # Update job with final results if job_id provided
            if job_id and self.job_manager:
                self.job_manager.update_job(job_id, {
                    "status": "completed", 
                    "result": result,
                    "completed_at": datetime.now().isoformat()
                })
            
            return result
        
        # Step 3: Process in small batches with simple retry
        print(f"Step 3: Fetching metadata for {len(new_messages)} emails...")
        batch_size = 10  # Smaller batches to reduce rate limit issues
        stored_count = 0
        error_count = 0
        
        for i in range(0, len(new_messages), batch_size):
            batch = new_messages[i:i + batch_size]
            batch_num = (i // batch_size) + 1
            total_batches = (len(new_messages) + batch_size - 1) // batch_size
            
            # Update job progress
            if job_id and self.job_manager:
                self.job_manager.update_job(job_id, {
                    "progress": {
                        "step": "Fetching email metadata",
                        "current_batch": batch_num,
                        "total_batches": total_batches,
                        "emails_processed": stored_count,
                        "total_emails": len(new_messages)
                    }
                })
            
            # Simple retry logic - if batch fails, retry up to 3 times
            for attempt in range(3):
                success = self.process_batch_simple(batch, email, cursor)
                
                if success:
                    stored_count += len(batch)
                    print(f"  Batch {batch_num}/{total_batches}: Success ({len(batch)} emails)")
                    break
                else:
                    if attempt < 2:
                        wait_time = 2 ** (attempt + 1)  # 2, 4 seconds
                        print(f"  Batch {batch_num}/{total_batches}: Failed attempt {attempt + 1}, waiting {wait_time}s...")
                        time.sleep(wait_time)
                    else:
                        error_count += len(batch)
                        print(f"  Batch {batch_num}/{total_batches}: Failed after 3 attempts")
            
            # Small delay between batches to be nice to the API
            if i + batch_size < len(new_messages):
                time.sleep(0.5)
            
            # Commit every 10 batches
            if batch_num % 10 == 0:
                conn.commit()
        
        # Update last_sync_at timestamp
        cursor.execute('''
            UPDATE connections 
            SET last_sync_at = ?
            WHERE email = ?
        ''', (datetime.now().isoformat(), email))
        
        conn.commit()
        conn.close()
        
        total_time = time.time() - start_time
        
        result = {
            "fetched": len(all_messages),
            "stored": stored_count,
            "duplicates": duplicate_count,
            "errors": error_count,
            "time": round(total_time, 1)
        }
        
        # Update job with final results
        if job_id and self.job_manager:
            self.job_manager.update_job(job_id, {
                "status": "completed",
                "result": result,
                "completed_at": datetime.now().isoformat()
            })
        
        print(f"\nComplete! Processed {len(all_messages)} emails in {total_time:.1f} seconds")
        print(f"  Stored: {stored_count}, Duplicates: {duplicate_count}, Errors: {error_count}")
        
        return result

    def process_batch_simple(self, batch: list, email: str, cursor) -> bool:
        """Process a batch of messages - returns True if successful, False if any errors"""
        try:
            access_token = self.get_valid_access_token(email)
            headers = {'Authorization': f'Bearer {access_token}'}
            
            # Process each message in the batch individually (simpler than batch API)
            for message in batch:
                msg_id = message['id']
                
                # Get message metadata
                url = f'https://gmail.googleapis.com/gmail/v1/users/me/messages/{msg_id}?format=metadata'
                response = requests.get(url, headers=headers)
                
                if response.status_code != 200:
                    # Any error means batch failed - will retry whole batch
                    return False
                
                msg_data = response.json()
                
                # Extract headers
                headers_list = msg_data.get('payload', {}).get('headers', [])
                msg_headers = {h['name']: h['value'] for h in headers_list if 'name' in h and 'value' in h}
                
                # Extract domain and store in database (skip if duplicate)
                sender = msg_headers.get('From', '')[:300]
                sender_domain = self.extract_domain(sender)
                
                # Parse Gmail date preserving timezone
                email_date_str = msg_headers.get('Date', '')
                try:
                    email_date = parsedate_to_datetime(email_date_str)
                    received_at = email_date.isoformat()
                except (ValueError, TypeError):
                    received_at = datetime.now().isoformat()
                
                try:
                    cursor.execute('''
                        INSERT INTO processed_emails 
                        (email, gmail_message_id, subject, sender, sender_domain, received_at)
                        VALUES (?, ?, ?, ?, ?, ?)
                    ''', (
                        email,
                        msg_id,
                        msg_headers.get('Subject', '')[:500],
                        sender,
                        sender_domain,
                        received_at
                    ))
                except sqlite3.IntegrityError as e:
                    # Debug: Track what emails are being caught as duplicates
                    print(f"    IntegrityError for {msg_id}: {str(e)}")
                    pass
            
            return True
            
        except Exception as e:
            print(f"    Batch error: {e}")
            return False


    def get_connections(self):
        """Get all Gmail connections"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM connections ORDER BY created_at DESC')
        columns = [desc[0] for desc in cursor.description]
        results = [dict(zip(columns, row)) for row in cursor.fetchall()]
        conn.close()
        return results

    def get_subscriptions(self):
        """Get all subscriptions"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM subscriptions ORDER BY created_at DESC')
        columns = [desc[0] for desc in cursor.description]
        results = [dict(zip(columns, row)) for row in cursor.fetchall()]
        conn.close()
        return results

    def get_email_count(self):
        """Get total count of processed emails"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('SELECT COUNT(*) FROM processed_emails')
        count = cursor.fetchone()[0]
        conn.close()
        return count

    def get_processed_emails(self, limit: int = None, offset: int = 0):
        """Get processed emails with optional pagination"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Get total count
        cursor.execute('SELECT COUNT(*) FROM processed_emails')
        total = cursor.fetchone()[0]
        
        # Get emails with optional pagination
        if limit:
            cursor.execute('''
                SELECT * FROM processed_emails 
                ORDER BY received_at DESC 
                LIMIT ? OFFSET ?
            ''', (limit, offset))
        else:
            cursor.execute('''
                SELECT * FROM processed_emails 
                ORDER BY received_at DESC
            ''')
        
        columns = [desc[0] for desc in cursor.description]
        emails = [dict(zip(columns, row)) for row in cursor.fetchall()]
        conn.close()
        
        return {"emails": emails, "total": total}

    def reset_database(self):
        """Clear all data and force fresh authentication"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('DELETE FROM processed_emails')
        cursor.execute('DELETE FROM connections')
        conn.commit()
        conn.close()
        print("Database reset complete - fresh authentication required")



class SimpleWebServer(BaseHTTPRequestHandler):
    def __init__(self, subscription_manager, job_manager, *args, **kwargs):
        self.sm = subscription_manager
        self.job_manager = job_manager
        super().__init__(*args, **kwargs)

    def do_GET(self):
        """Handle GET requests"""
        url = urlparse(self.path)
        path = url.path
        params = parse_qs(url.query)
        
        if path == '/':
            self.serve_dashboard()
        elif path == '/status':
            self.handle_status_api()
        elif path == '/auth/gmail':
            self.start_gmail_auth()
        elif path == '/auth/callback':
            self.handle_oauth_callback(params)
        elif path == '/reset':
            self.handle_reset()
        else:
            self.send_error(404)

    def do_POST(self):
        """Handle POST requests"""
        url = urlparse(self.path)
        path = url.path
        
        if path == '/fetch':
            self.handle_metadata_fetch()
        elif path == '/api/fetch':
            self.handle_api_fetch()
        else:
            self.send_error(404)



    def serve_dashboard(self):
        """Serve two-panel dashboard"""
        connections = self.sm.get_connections()
        subscriptions = self.sm.get_subscriptions()
        email_count = self.sm.get_email_count()
        connected = len(connections) > 0
        
        # Check for fetch results in URL params
        url = urlparse(self.path)
        params = parse_qs(url.query)
        fetch_results = params.get('fetch_results', [None])[0]
        
        html = f"""
<!DOCTYPE html>
<html>
<head>
    <title>Subscription Manager</title>
    <style>
        body {{ margin: 0; font-family: "SF Mono", monospace; background: white; }}
        
        /* Main layout: 1/3 left, 2/3 right */
        .container {{ display: grid; grid-template-columns: 1fr 2fr; height: 100vh; }}
        
        /* Left panel with 4 sections */
        .left-panel {{ border-right: 1px solid #e0e0e0; display: flex; flex-direction: column; }}
        
        /* Each section has fixed height */
        .section {{ 
            border-bottom: 1px solid #e0e0e0;
        }}
        .section:nth-child(1) {{ 
            height: 10vh; 
            display: flex;
            align-items: end;
            padding-bottom: 20px;
        }}
        .section:nth-child(2), 
        .section:nth-child(3), 
        .section:nth-child(4) {{ 
            display: grid; 
            grid-template-columns: 1fr 2fr;
            align-items: end;
            padding-bottom: 20px;
        }}
        .section:nth-child(2) {{ height: 25vh; }}
        .section:nth-child(3) {{ height: 25vh; }}
        .section:nth-child(4) {{ height: 25vh; }}
        
        /* Left side of each section (title) */
        .section-title {{ 
            padding-left: 30px;
            font-size: 24px; 
            font-weight: 700; 
            color: #000;
        }}
        
        /* Right side of each section (content/actions) */
        .section-content {{ 
            padding-right: 30px;
            text-align: right;
        }}
        
        /* Right panel for subscriptions */
        .right-panel {{ padding: 30px; }}
        .right-panel h2 {{ margin: 0 0 30px 0; font-size: 28px; font-weight: 700; }}
        
        /* Table styling */
        table {{ width: 100%; border-collapse: collapse; }}
        th, td {{ padding: 16px; text-align: left; border-bottom: 1px solid #e0e0e0; word-wrap: break-word; }}
        th {{ font-weight: 600; font-size: 14px; color: #666; }}
        td {{ font-size: 12px; }}
        
        /* Button styling */
        button {{ 
            padding: 10px 20px; 
            margin-left: 10px;
            border: 1px solid #ddd; 
            background: white; 
            cursor: pointer; 
            font-size: 14px;
        }}
        button:hover {{ background: #f8f9fa; }}
        .primary {{ background: #007bff; color: white; border-color: #007bff; }}
        .primary:hover {{ background: #0056b3; }}
        
        /* Status text */
        .status {{ color: #666; font-size: 14px; margin-bottom: 10px; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="left-panel">
            <div class="section">
                <div class="section-title">subscriptions</div>
            </div>
            
            <div class="section">
                <div class="section-title">connect email</div>
                <div class="section-content" style="{'display: flex; flex-direction: column; justify-content: space-between; height: 100%;' if connected else ''}">
                    {f'''
                    <div style="text-align: right; padding-top: 10px;">
                        <a href="/auth/gmail" style="text-decoration: none;">
                            <button style="border: none; background: none; color: #666; cursor: pointer; padding: 0; font-size: 14px; font-family: 'SF Mono', monospace;">change email</button>
                        </a>
                    </div>
                    <div style="text-align: right;">
                        <div style="color: #666; font-size: 14px; margin-bottom: 30px;">emails connected:</div>
                        <div class="status" style="color: #008000;">{connections[0]["email"]}</div>
                    </div>
                    ''' if connected else '''
                    <div style="text-align: right; padding-top: 10px;">
                        <a href="/auth/gmail" style="text-decoration: none;">
                            <button style="border: none; background: none; color: #666; cursor: pointer; padding: 0; font-size: 14px; font-family: 'SF Mono', monospace;">connect gmail</button>
                        </a>
                    </div>
                    '''}
                </div>
            </div>
            
            <div class="section">
                <div class="section-title">check emails</div>
                <div class="section-content" style="display: flex; flex-direction: column; justify-content: space-between; height: 100%;">
                    <div style="text-align: right; padding-top: 10px;">
                        <form action="/fetch" method="post" style="display: inline;">
                            <button type="submit" style="border: none; background: none; color: #666; cursor: pointer; padding: 0; font-size: 14px; font-family: 'SF Mono', monospace;">fetch emails</button>
                        </form>
                    </div>
                    {f'''
                    <div style="text-align: right;">
                        {f'<div style="color: #008000; font-size: 14px; margin-bottom: 15px;">{fetch_results}</div>' if fetch_results else ''}
                        <div style="color: #666; font-size: 14px; margin-bottom: 30px;">last fetched:</div>
                        <div style="color: #008000; font-size: 14px;">{connections[0]["last_sync_at"][:16] if connections[0]["last_sync_at"] else "never"}</div>
                    </div>
                    ''' if connected else ''}
                </div>
            </div>
            
            <div class="section">
                <div class="section-title">view data</div>
                <div class="section-content" style="display: flex; flex-direction: column; justify-content: space-between; height: 100%;">
                    <div style="text-align: right; padding-top: 10px;">
                        <a href="/?view=emails" style="text-decoration: none;">
                            <button style="border: none; background: none; color: #666; cursor: pointer; padding: 0; font-size: 14px; font-family: 'SF Mono', monospace;">view emails</button>
                        </a>
                        <span style="margin: 0 10px;"></span>
                        <a href="/reset" style="text-decoration: none;">
                            <button onclick="return confirm('Delete all data?')" style="border: none; background: none; color: #666; cursor: pointer; padding: 0; font-size: 14px; font-family: 'SF Mono', monospace;">reset</button>
                        </a>
                    </div>
                    <div style="text-align: right;">
                        <div style="color: #666; font-size: 14px; margin-bottom: 30px;">emails stored:</div>
                        <div style="color: #008000; font-size: 14px;">{email_count}</div>
                    </div>
                </div>
            </div>
        </div>
        
        <div class="right-panel">
            {self.render_right_panel(params)}
        </div>
    </div>
</body>
</html>
        """
        
        self.send_response(200)
        self.send_header('Content-type', 'text/html')
        self.end_headers()
        self.wfile.write(html.encode())

    def render_right_panel(self, params):
        """Render right panel content based on view parameter"""
        view = params.get('view', ['subscriptions'])[0]
        
        if view == 'emails':
            return self.render_emails_view()
        else:
            return self.render_subscriptions_view()
    
    def render_subscriptions_view(self):
        """Render subscriptions table"""
        subscriptions = self.sm.get_subscriptions()
        return self.render_subscriptions_table(subscriptions)
    
    def render_emails_view(self):
        """Render emails table with back button"""
        data = self.sm.get_processed_emails()
        emails = data['emails']
        total = data['total']
        
        email_rows = ""
        for email in emails:
            email_rows += f"""
            <tr>
                <td>{email['sender']}</td>
                <td>{email['subject']}</td>
                <td>{self.format_datetime_nz(email['received_at']) if email['received_at'] else 'N/A'}</td>
            </tr>
            """
        
        return f"""
            <div style="margin-bottom: 30px;">
                <a href="/" style="text-decoration: none;">
                    <button style="border: none; background: none; color: #666; cursor: pointer; padding: 0; font-size: 14px; font-family: 'SF Mono', monospace;">back</button>
                </a>
            </div>
            <div style="height: 80vh; overflow-y: auto;">
                <table>
                <thead>
                    <tr>
                        <th>Sender</th>
                        <th>Subject</th>
                        <th>Received</th>
                    </tr>
                </thead>
                <tbody>
                    {email_rows}
                </tbody>
                </table>
            </div>
        """
    
    def render_subscriptions_table(self, subscriptions):
        if not subscriptions:
            return '<div style="height: 80vh; overflow-y: auto;"><p style="padding: 20px; color: #666;">No subscriptions yet. Add items to the scratchpad and process them to see subscriptions here.</p></div>'
        
        rows = ""
        for sub in subscriptions:
            rows += f"""<tr>
                <td>{sub['name']}</td>
                <td>{sub['status']}</td>
                <td>{'Yes' if sub.get('auto_renewing') else 'No'}</td>
                <td>{sub.get('cost', '') or ''}</td>
                <td>{sub.get('billing_cycle', '') or ''}</td>
                <td>{sub.get('next_billing_date', '') or ''}</td>
            </tr>"""
        
        return f"""<div style="height: 80vh; overflow-y: auto;">
            <table>
                <thead>
                    <tr>
                        <th>Name</th>
                        <th>Status</th>
                        <th>Renewing</th>
                        <th>Cost</th>
                        <th>Billing Cycle</th>
                        <th>Next Date</th>
                    </tr>
                </thead>
                <tbody>{rows}</tbody>
            </table>
        </div>"""


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
        conn = sqlite3.connect(self.sm.db_path)
        cursor = conn.cursor()
        
        expiry_time = datetime.now() + timedelta(seconds=token_data['expires_in'])
        
        cursor.execute('''
            INSERT OR REPLACE INTO connections 
            (email, access_token, refresh_token, token_expiry)
            VALUES (?, ?, ?, ?)
        ''', (
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

    def handle_status_api(self):
        """Handle status API request (returns JSON)"""
        connections = self.sm.get_connections()
        email_count = self.sm.get_email_count()
        
        # Standardized API response format
        response_data = {
            "success": True,
            "data": {
                "status": "running",
                "gmail_connected": len(connections) > 0,
                "gmail_account": connections[0]["email"] if connections else None,
                "last_sync": connections[0]["last_sync_at"] if connections else None,
                "connection_active": bool(connections[0]["is_active"]) if connections else False,
                "total_emails": email_count,
                "app_url": f"http://localhost:{self.sm.port}"
            }
        }
        
        response_json = json.dumps(response_data, indent=2)
        
        self.send_response(200)
        self.send_header('Content-type', 'application/json')
        self.send_header('Content-length', str(len(response_json)))
        self.end_headers()
        self.wfile.write(response_json.encode())

    def api_fetch_emails(self):
        """Start email fetch in background and return job ID"""
        # Get active connection
        connections = self.sm.get_connections()
        if not connections:
            return {
                "success": False,
                "error": "No Gmail connection found",
                "data": None
            }
        
        email = connections[0]['email']
        
        # Create background job
        job_id = self.job_manager.create_job("email_fetch")
        
        # Start fetch in background thread
        def run_fetch():
            try:
                result = self.sm.fetch_year_of_emails(email, years_back=1, job_id=job_id)
            except Exception as e:
                # Update job with error
                self.job_manager.update_job(job_id, {
                    "status": "failed",
                    "error": str(e),
                    "completed_at": datetime.now().isoformat()
                })
        
        thread = threading.Thread(target=run_fetch)
        thread.daemon = True  # Don't block app shutdown
        thread.start()
        
        return {
            "success": True,
            "message": "Email fetch started in background",
            "data": {
                "job_id": job_id,
                "status": "started",
                "note": "This may take 10-30 minutes depending on email volume"
            }
        }

    def handle_metadata_fetch(self):
        """Handle metadata fetch request (web interface)"""
        result = self.api_fetch_emails()
        
        if not result["success"]:
            self.send_error(400, result.get("error", "Unknown error"))
            return
        
        # Format results for display - now shows job started message
        job_id = result.get('data', {}).get('job_id', 'unknown')
        fetch_results = f"started: {job_id} (running in background)"
        
        # Redirect back to dashboard with results in URL
        self.send_response(302)
        self.send_header('Location', f'/?fetch_results={fetch_results}')
        self.end_headers()

    def handle_api_fetch(self):
        """Handle API fetch request (returns JSON)"""
        result = self.api_fetch_emails()
        
        response_json = json.dumps(result, indent=2)
        
        self.send_response(200 if result["success"] else 400)
        self.send_header('Content-type', 'application/json')
        self.send_header('Content-length', str(len(response_json)))
        self.end_headers()
        self.wfile.write(response_json.encode())


    def format_datetime_nz(self, iso_datetime_str):
        """Convert ISO datetime to New Zealand timezone for display"""
        try:
            # Parse the ISO datetime (with timezone)
            dt = datetime.fromisoformat(iso_datetime_str.replace('Z', '+00:00'))
            # Convert to New Zealand timezone
            nz_tz = pytz.timezone('Pacific/Auckland')
            nz_dt = dt.astimezone(nz_tz)
            # Format for display
            formatted = nz_dt.strftime('%d %b %Y %I:%M%p')
            # Remove leading zero from hour and fix am/pm case
            formatted = re.sub(r' 0(\d):', r' \1:', formatted)
            return formatted.replace('AM', 'am').replace('PM', 'pm')
        except (ValueError, AttributeError):
            return iso_datetime_str

    def handle_reset(self):
        """Reset database"""
        self.sm.reset_database()
        self.send_response(302)
        self.send_header('Location', '/?reset=1')
        self.end_headers()


class ThreadedHTTPServer(ThreadingMixIn, HTTPServer):
    """Handle requests in separate threads to prevent blocking"""
    pass

def create_handler(subscription_manager, job_manager):
    """Create request handler with subscription manager and job manager"""
    def handler(*args, **kwargs):
        SimpleWebServer(subscription_manager, job_manager, *args, **kwargs)
    return handler

def main():
    """Main function to start the application"""
    print("🚀 Starting Simple Subscription Manager...")
    
    # Initialize job manager and subscription manager
    job_manager = JobManager()
    sm = SubscriptionManager(job_manager)
    
    # Create threaded web server
    server_address = ('', sm.port)
    httpd = ThreadedHTTPServer(server_address, create_handler(sm, job_manager))
    
    print(f"✅ Server running at http://localhost:{sm.port}")
    print("   Visit the URL above to use the application")
    
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n👋 Shutting down server...")
        httpd.shutdown()

if __name__ == "__main__":
    main()