#!/usr/bin/env python3
"""
Simple Subscription Manager - Gmail metadata fetcher
Core functionality only: Gmail OAuth + fast metadata ingestion + basic UI
"""

import os
import sqlite3
import json
import requests
from datetime import datetime, timedelta
from urllib.parse import urlencode, parse_qs, urlparse
from http.server import HTTPServer, BaseHTTPRequestHandler
from dotenv import load_dotenv
import time
import pytz

# Load environment variables
load_dotenv()

class SubscriptionManager:
    def __init__(self):
        self.db_path = "subscriptions.db"
        self.init_database()
        
        self.google_client_id = os.getenv('GOOGLE_CLIENT_ID')
        self.google_client_secret = os.getenv('GOOGLE_CLIENT_SECRET')
        self.openai_api_key = os.getenv('OPENAI_API_KEY')
        self.openai_model = os.getenv('OPENAI_MODEL', 'gpt-4o-mini')
        self.confidence_threshold = float(os.getenv('LLM_CONFIDENCE_THRESHOLD', '0.7'))
        
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
                history_id TEXT,
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
                is_subscription BOOLEAN DEFAULT 0,
                confidence_score DECIMAL(3,2),
                vendor TEXT,
                email_type TEXT
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS subscriptions (
                id TEXT PRIMARY KEY DEFAULT (hex(randomblob(16))),
                email TEXT NOT NULL,
                name TEXT NOT NULL,
                domain TEXT NOT NULL,
                status TEXT DEFAULT 'active',
                renewing BOOLEAN DEFAULT 1,
                cost DECIMAL(10,2),
                billing_cycle TEXT,
                next_date DATE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(email, domain)
            )
        ''')
        
        # Add columns to existing table if they don't exist
        try:
            cursor.execute('ALTER TABLE processed_emails ADD COLUMN sender_domain TEXT')
        except sqlite3.OperationalError:
            pass  # Column already exists
        
        try:
            cursor.execute('ALTER TABLE processed_emails ADD COLUMN email TEXT')
        except sqlite3.OperationalError:
            pass  # Column already exists
            
        try:
            cursor.execute('ALTER TABLE connections ADD CONSTRAINT unique_email UNIQUE (email)')
        except sqlite3.OperationalError:
            pass  # Constraint already exists
            
        # Migrate existing data to new schema if needed
        try:
            # First check if connection_id column exists
            cursor.execute("PRAGMA table_info(processed_emails)")
            columns = [col[1] for col in cursor.fetchall()]
            
            if 'connection_id' in columns and 'email' in columns:
                # Migrate connection_id to email
                cursor.execute('''
                    UPDATE processed_emails 
                    SET email = (
                        SELECT c.email FROM connections c 
                        WHERE c.id = processed_emails.connection_id
                    )
                    WHERE email IS NULL OR email = ''
                ''')
            
            # Now we can safely drop old columns if they exist
            # Note: SQLite doesn't support DROP COLUMN in older versions
            # We'll just ignore these columns going forward
            
        except sqlite3.OperationalError as e:
            pass  # Migration issues, continue anyway
        
        # No users table needed - removed
        
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

    def fetch_year_of_emails(self, email: str, years_back: int = 1):
        """Simple approach: Get message IDs from last year, then fetch in small batches with retry"""
        start_time = time.time()
        
        # Step 1: Get all message IDs from the last year
        print(f"Step 1: Getting message IDs from last {years_back} year(s)...")
        
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
            conn.close()
            return {"fetched": len(all_messages), "stored": 0, "duplicates": duplicate_count, "errors": 0, "time": 0}
        
        # Step 3: Process in small batches with simple retry
        print(f"Step 3: Fetching metadata for {len(new_messages)} emails...")
        batch_size = 10  # Smaller batches to reduce rate limit issues
        stored_count = 0
        error_count = 0
        
        for i in range(0, len(new_messages), batch_size):
            batch = new_messages[i:i + batch_size]
            batch_num = (i // batch_size) + 1
            total_batches = (len(new_messages) + batch_size - 1) // batch_size
            
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
                    from email.utils import parsedate_to_datetime
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
        return f"""
            <h2>Subscriptions</h2>
            {self.render_subscriptions_table(subscriptions)}
        """
    
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
            return '<p>No subscriptions found. Connect Gmail and fetch emails to get started.</p>'
        
        rows = ""
        for sub in subscriptions:
            rows += f"""
            <tr>
                <td>{sub['name']}</td>
                <td>{sub['domain']}</td>
                <td>{sub.get('cost', 'N/A')}</td>
                <td>{sub['status']}</td>
                <td>{sub.get('next_date', 'N/A')}</td>
            </tr>
            """
        
        return f"""
        <table>
            <thead>
                <tr>
                    <th>Name</th>
                    <th>Domain</th>
                    <th>Cost</th>
                    <th>Status</th>
                    <th>Next Date</th>
                </tr>
            </thead>
            <tbody>
                {rows}
            </tbody>
        </table>
        """

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

    def handle_metadata_fetch(self):
        """Handle metadata fetch request"""
        # Get active connection
        connections = self.sm.get_connections()
        if not connections:
            self.send_error(400, "No Gmail connection found")
            return
        
        email = connections[0]['email']
        
        # Run simplified fetch for 1 year
        result = self.sm.fetch_year_of_emails(email, years_back=1)
        
        # Format results for display
        fetch_results = f"fetched: {result.get('stored', 0)} new"
        if result.get('duplicates', 0) > 0:
            fetch_results += f", {result.get('duplicates', 0)} duplicates"
        if result.get('errors', 0) > 0:
            fetch_results += f", {result.get('errors', 0)} errors"
        
        # Redirect back to dashboard with results in URL
        self.send_response(302)
        self.send_header('Location', f'/?fetch_results={fetch_results}')
        self.end_headers()

    def serve_emails_page(self, params):
        """Serve emails listing page"""
        page = int(params.get('page', ['1'])[0])
        limit = 50
        offset = (page - 1) * limit
        
        data = self.sm.get_processed_emails(limit, offset)
        emails = data['emails']
        total = data['total']
        total_pages = (total + limit - 1) // limit
        
        # Generate email rows
        email_rows = ""
        for email in emails:
            email_rows += f"""
            <tr>
                <td>{email['subject'][:50]}...</td>
                <td>{email['sender'][:30]}...</td>
                <td>{email['processed_at'][:16]}</td>
                <td>{'Yes' if email['is_subscription'] else 'No'}</td>
            </tr>
            """
        
        # Generate pagination
        pagination = ""
        if page > 1:
            pagination += f'<a href="/emails?page={page-1}"><button>Previous</button></a> '
        if page < total_pages:
            pagination += f'<a href="/emails?page={page+1}"><button>Next</button></a>'
        
        html = f"""
<!DOCTYPE html>
<html>
<head>
    <title>Stored Emails</title>
    <style>
        body {{ font-family: "SF Mono", monospace; margin: 40px; }}
        table {{ border-collapse: collapse; width: 100%; }}
        th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
        th {{ background-color: #f5f5f5; }}
    </style>
</head>
<body>
    <h1>Stored Emails</h1>
    <p>Total: {total} emails | Page {page} of {total_pages}</p>
    
    <table>
        <tr>
            <th>Subject</th>
            <th>Sender</th>
            <th>Processed</th>
            <th>Subscription</th>
        </tr>
        {email_rows}
    </table>
    
    <p>{pagination}</p>
    <a href="/"><button>Back to Dashboard</button></a>
</body>
</html>
        """
        
        self.send_response(200)
        self.send_header('Content-type', 'text/html')
        self.end_headers()
        self.wfile.write(html.encode())

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
            import re
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


def create_handler(subscription_manager):
    """Create request handler with subscription manager"""
    def handler(*args, **kwargs):
        SimpleWebServer(subscription_manager, *args, **kwargs)
    return handler

def main():
    """Main function to start the application"""
    print("🚀 Starting Simple Subscription Manager...")
    
    # Initialize subscription manager
    sm = SubscriptionManager()
    
    # Create web server
    server_address = ('', sm.port)
    httpd = HTTPServer(server_address, create_handler(sm))
    
    print(f"✅ Server running at http://localhost:{sm.port}")
    print("   Visit the URL above to use the application")
    
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n👋 Shutting down server...")
        httpd.shutdown()

if __name__ == "__main__":
    main()