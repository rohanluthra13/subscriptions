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
            CREATE TABLE IF NOT EXISTS users (
                id TEXT PRIMARY KEY DEFAULT '1',
                email TEXT UNIQUE NOT NULL,
                name TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
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
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS processed_emails (
                id TEXT PRIMARY KEY DEFAULT (hex(randomblob(16))),
                connection_id TEXT NOT NULL,
                gmail_message_id TEXT UNIQUE NOT NULL,
                subject TEXT,
                sender TEXT,
                sender_domain TEXT,
                subscription_status TEXT DEFAULT NULL,
                user_selected BOOLEAN DEFAULT 0,
                received_at TIMESTAMP,
                processed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                is_subscription BOOLEAN DEFAULT 0,
                confidence_score DECIMAL(3,2),
                vendor TEXT,
                email_type TEXT,
                FOREIGN KEY (connection_id) REFERENCES connections(id)
            )
        ''')
        
        # Add columns to existing table if they don't exist
        try:
            cursor.execute('ALTER TABLE processed_emails ADD COLUMN sender_domain TEXT')
        except sqlite3.OperationalError:
            pass  # Column already exists
        
        try:
            cursor.execute('ALTER TABLE processed_emails ADD COLUMN subscription_status TEXT DEFAULT NULL')
        except sqlite3.OperationalError:
            pass  # Column already exists
            
        try:
            cursor.execute('ALTER TABLE processed_emails ADD COLUMN user_selected BOOLEAN DEFAULT 0')
        except sqlite3.OperationalError:
            pass  # Column already exists
            
        # Migrate existing data to new schema
        try:
            cursor.execute('''
                UPDATE processed_emails 
                SET subscription_status = CASE 
                    WHEN subscription_status = 'subscription' THEN 'active'
                    WHEN domain_is_subscription = 1 THEN 'active'
                    WHEN domain_is_subscription = 0 THEN 'not_subscription'
                    ELSE subscription_status
                END
                WHERE subscription_status = 'subscription' 
                   OR subscription_status = 'pending_review'
                   OR domain_is_subscription IS NOT NULL
            ''')
        except sqlite3.OperationalError:
            pass  # Migration already done or old column doesn't exist
        
        cursor.execute('INSERT OR IGNORE INTO users (id, email, name) VALUES (?, ?, ?)', 
                      ('1', 'user@example.com', 'Default User'))
        
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

    def get_valid_access_token(self, connection_id: str) -> str:
        """Get valid access token, refreshing if necessary"""
        conn = sqlite3.connect(self.db_path)
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
            print("Refreshing access token...")
            token_data = self.refresh_access_token(refresh_token)
            
            if 'access_token' in token_data:
                new_expiry = datetime.now() + timedelta(seconds=token_data['expires_in'])
                cursor.execute('''
                    UPDATE connections 
                    SET access_token = ?, token_expiry = ?
                    WHERE id = ?
                ''', (token_data['access_token'], new_expiry.isoformat(), connection_id))
                conn.commit()
                access_token = token_data['access_token']
            else:
                conn.close()
                raise Exception("Failed to refresh token")
        
        conn.close()
        return access_token

    def fetch_year_of_emails(self, connection_id: str, years_back: int = 1):
        """Simple approach: Get message IDs from last year, then fetch in small batches with retry"""
        start_time = time.time()
        
        # Step 1: Get all message IDs from the last year
        print(f"Step 1: Getting message IDs from last {years_back} year(s)...")
        
        access_token = self.get_valid_access_token(connection_id)
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
        
        new_messages = []
        duplicate_count = 0
        
        for message in all_messages:
            msg_id = message['id']
            cursor.execute('SELECT id FROM processed_emails WHERE gmail_message_id = ?', (msg_id,))
            if cursor.fetchone():
                duplicate_count += 1
            else:
                new_messages.append(message)
        
        print(f"  {duplicate_count} already processed, {len(new_messages)} new emails to fetch")
        
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
                success = self.process_batch_simple(batch, connection_id, cursor)
                
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

    def process_batch_simple(self, batch: list, connection_id: str, cursor) -> bool:
        """Process a batch of messages - returns True if successful, False if any errors"""
        try:
            access_token = self.get_valid_access_token(connection_id)
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
                
                try:
                    cursor.execute('''
                        INSERT INTO processed_emails 
                        (connection_id, gmail_message_id, subject, sender, sender_domain, received_at)
                        VALUES (?, ?, ?, ?, ?, ?)
                    ''', (
                        connection_id,
                        msg_id,
                        msg_headers.get('Subject', '')[:500],
                        sender,
                        sender_domain,
                        datetime.now().isoformat()
                    ))
                except sqlite3.IntegrityError:
                    # Duplicate - that's fine, continue
                    pass
            
            return True
            
        except Exception as e:
            print(f"    Batch error: {e}")
            return False

    def analyze_domains(self):
        """Extract and update domains for all existing emails"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Get all emails without domain info
        cursor.execute('SELECT id, sender FROM processed_emails WHERE sender_domain IS NULL OR sender_domain = ""')
        emails_to_update = cursor.fetchall()
        
        print(f"Analyzing domains for {len(emails_to_update)} emails...")
        
        updated_count = 0
        for email_id, sender in emails_to_update:
            domain = self.extract_domain(sender)
            cursor.execute('UPDATE processed_emails SET sender_domain = ? WHERE id = ?', (domain, email_id))
            updated_count += 1
            
            if updated_count % 100 == 0:
                print(f"  Updated {updated_count}/{len(emails_to_update)} emails...")
        
        conn.commit()
        conn.close()
        
        print(f"Domain analysis complete: {updated_count} emails updated")
        return {"updated": updated_count, "total": len(emails_to_update)}

    def get_domain_stats(self):
        """Get domain statistics for clustering"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT sender_domain, 
                   COUNT(*) as email_count,
                   subscription_status,
                   user_selected,
                   MAX(processed_at) as last_seen
            FROM processed_emails 
            WHERE sender_domain IS NOT NULL AND sender_domain != ""
            GROUP BY sender_domain, subscription_status, user_selected
            ORDER BY email_count DESC
        ''')
        
        results = cursor.fetchall()
        conn.close()
        
        # Group by domain (since subscription_status might be different for same domain)
        domain_stats = {}
        for domain, count, subscription_status, user_selected, last_seen in results:
            if domain not in domain_stats:
                domain_stats[domain] = {
                    'domain': domain,
                    'email_count': 0,
                    'subscription_status': subscription_status,
                    'user_selected': user_selected,
                    'last_seen': last_seen
                }
            domain_stats[domain]['email_count'] += count
            # Use the most recent classification (prioritize user_selected=1)
            if user_selected == 1:
                domain_stats[domain]['subscription_status'] = subscription_status
                domain_stats[domain]['user_selected'] = user_selected
        
        return list(domain_stats.values())

    def update_domain_classification(self, domain: str, subscription_status: str):
        """Update domain classification for all emails from that domain"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Set user_selected based on whether status is being set or cleared
        user_selected = 1 if subscription_status is not None else 0
        
        cursor.execute('''
            UPDATE processed_emails 
            SET subscription_status = ?, user_selected = ?
            WHERE sender_domain = ?
        ''', (subscription_status, user_selected, domain))
        
        affected_rows = cursor.rowcount
        conn.commit()
        conn.close()
        
        return affected_rows

    def get_connections(self):
        """Get all Gmail connections"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM connections ORDER BY created_at DESC')
        columns = [desc[0] for desc in cursor.description]
        results = [dict(zip(columns, row)) for row in cursor.fetchall()]
        conn.close()
        return results

    def get_processed_emails(self, limit: int = 50, offset: int = 0):
        """Get processed emails with pagination"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Get total count
        cursor.execute('SELECT COUNT(*) FROM processed_emails')
        total = cursor.fetchone()[0]
        
        # Get emails with pagination
        cursor.execute('''
            SELECT * FROM processed_emails 
            ORDER BY processed_at DESC 
            LIMIT ? OFFSET ?
        ''', (limit, offset))
        
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
        elif path == '/emails':
            self.serve_emails_page(params)
        elif path == '/domains':
            self.serve_domains_page()
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
        elif path == '/analyze-domains':
            self.handle_analyze_domains()
        elif path == '/classify-domains':
            self.handle_domain_classification()
        else:
            self.send_error(404)

    def serve_dashboard(self):
        """Serve simple dashboard"""
        connections = self.sm.get_connections()
        
        html = f"""
<!DOCTYPE html>
<html>
<head>
    <title>Subscription Manager</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 40px; }}
        .section {{ margin: 30px 0; padding: 20px; border: 1px solid #ddd; }}
        button {{ padding: 10px 20px; margin: 10px; }}
        input, select {{ padding: 8px; margin: 5px; }}
        table {{ border-collapse: collapse; width: 100%; }}
        th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
    </style>
</head>
<body>
    <h1>Subscription Manager</h1>
    
    <div class="section">
        <h2>1. Gmail Connection</h2>
        {self.render_connections(connections)}
    </div>
    
    <div class="section">
        <h2>2. Fetch Email Metadata</h2>
        <form action="/fetch" method="post">
            <button type="submit" style="background: #4CAF50; color: white; font-size: 16px;">
                Fetch Last Year of Emails
            </button>
            <p><small>Fetches all emails from the last 12 months (excluding trash/sent)</small></p>
        </form>
    </div>
    
    <div class="section">
        <h2>3. Domain Clustering</h2>
        <form action="/analyze-domains" method="post">
            <button type="submit" style="background: #2196F3; color: white;">
                Analyze Domains
            </button>
            <p><small>Extract domains from existing emails for classification</small></p>
        </form>
        <a href="/domains"><button>Classify Domains</button></a>
    </div>
    
    <div class="section">
        <h2>4. View Data</h2>
        <a href="/emails"><button>View Stored Emails</button></a>
        <a href="/reset"><button onclick="return confirm('Delete all data?')">Reset Database</button></a>
    </div>
    
    <div class="section">
        <h2>5. LLM Integration (Ready)</h2>
        <p>OpenAI API Key: {'✓ Configured' if self.sm.openai_api_key else '✗ Missing'}</p>
        <p>Model: {self.sm.openai_model}</p>
        <p><small>Ready for next phase: subscription email processing</small></p>
    </div>
</body>
</html>
        """
        
        self.send_response(200)
        self.send_header('Content-type', 'text/html')
        self.end_headers()
        self.wfile.write(html.encode())

    def render_connections(self, connections):
        if not connections:
            return '<p>No Gmail connection found. <a href="/auth/gmail"><button>Connect Gmail</button></a></p>'
        
        conn = connections[0]
        return f'''
        <p>✓ Connected: {conn['email']}</p>
        <p>Connected at: {conn['created_at']}</p>
        <a href="/auth/gmail"><button>Reconnect Gmail</button></a>
        '''

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

    def handle_metadata_fetch(self):
        """Handle metadata fetch request"""
        # Get active connection
        connections = self.sm.get_connections()
        if not connections:
            self.send_error(400, "No Gmail connection found")
            return
        
        connection_id = connections[0]['id']
        
        # Run simplified fetch for 1 year
        result = self.sm.fetch_year_of_emails(connection_id, years_back=1)
        
        # Return simple response
        html = f"""
<!DOCTYPE html>
<html>
<head>
    <title>Fetch Complete</title>
    <style>body {{ font-family: Arial, sans-serif; margin: 40px; }}</style>
</head>
<body>
    <h1>Email Fetch Complete</h1>
    <p><strong>Total found: {result.get('fetched', 0)} emails from last year</strong></p>
    <p>✅ Successfully stored: {result.get('stored', 0)} new emails</p>
    <p>⏩ Skipped duplicates: {result.get('duplicates', 0)}</p>
    {f'<p>❌ Failed to fetch: {result.get("errors", 0)} emails</p>' if result.get('errors', 0) > 0 else ''}
    <p>⏱️ Time taken: {result.get('time', 0)} seconds</p>
    
    <a href="/"><button>Back to Dashboard</button></a>
    <a href="/emails"><button>View Emails</button></a>
</body>
</html>
        """
        
        self.send_response(200)
        self.send_header('Content-type', 'text/html')
        self.end_headers()
        self.wfile.write(html.encode())

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
        body {{ font-family: Arial, sans-serif; margin: 40px; }}
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

    def handle_reset(self):
        """Reset database"""
        self.sm.reset_database()
        self.send_response(302)
        self.send_header('Location', '/?reset=1')
        self.end_headers()

    def handle_analyze_domains(self):
        """Handle domain analysis request"""
        result = self.sm.analyze_domains()
        
        html = f"""
<!DOCTYPE html>
<html>
<head>
    <title>Domain Analysis Complete</title>
    <style>body {{ font-family: Arial, sans-serif; margin: 40px; }}</style>
</head>
<body>
    <h1>Domain Analysis Complete</h1>
    <p>✅ Updated: {result.get('updated', 0)} emails</p>
    <p>📊 Total processed: {result.get('total', 0)} emails</p>
    
    <a href="/"><button>Back to Dashboard</button></a>
    <a href="/domains"><button>Classify Domains</button></a>
</body>
</html>
        """
        
        self.send_response(200)
        self.send_header('Content-type', 'text/html')
        self.end_headers()
        self.wfile.write(html.encode())

    def serve_domains_page(self):
        """Serve domain classification page"""
        domain_stats = self.sm.get_domain_stats()
        
        # Generate domain rows
        domain_rows = ""
        for stats in domain_stats:
            domain = stats['domain']
            count = stats['email_count']
            subscription_status = stats['subscription_status']
            user_selected = stats['user_selected']
            
            # Determine if checkbox should be checked
            checked = 'checked' if subscription_status == 'subscription' else ''
            
            # Row styling based on status
            if subscription_status == 'active':
                row_class = 'active-row'
                status_text = '✓ Active'
            elif subscription_status == 'inactive':
                row_class = 'inactive-row'
                status_text = '⏸ Inactive'
            elif subscription_status == 'trial':
                row_class = 'trial-row'
                status_text = '🔄 Trial'
            elif subscription_status == 'not_subscription':
                row_class = 'not-subscription-row'
                status_text = '✗ Not Subscription'
            else:
                row_class = ''
                status_text = '? Unclassified'
            
            # Show if user-selected or LLM-suggested
            source_indicator = '👤' if user_selected else '🤖'
            
            # Set selected option for dropdown
            active_selected = 'selected' if subscription_status == 'active' else ''
            inactive_selected = 'selected' if subscription_status == 'inactive' else ''
            trial_selected = 'selected' if subscription_status == 'trial' else ''
            not_subscription_selected = 'selected' if subscription_status == 'not_subscription' else ''
            unclassified_selected = 'selected' if subscription_status is None else ''
            
            domain_rows += f"""
            <tr class="{row_class}">
                <td>{domain}</td>
                <td>{count}</td>
                <td>{status_text} {source_indicator}</td>
                <td>
                    <select name="domain_{domain}" style="width: 100%;">
                        <option value="unclassified" {unclassified_selected}>? Unclassified</option>
                        <option value="active" {active_selected}>✓ Active</option>
                        <option value="inactive" {inactive_selected}>⏸ Inactive</option>
                        <option value="trial" {trial_selected}>🔄 Trial</option>
                        <option value="not_subscription" {not_subscription_selected}>✗ Not Subscription</option>
                    </select>
                </td>
            </tr>
            """
        
        html = f"""
<!DOCTYPE html>
<html>
<head>
    <title>Domain Classification</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 40px; }}
        table {{ border-collapse: collapse; width: 100%; }}
        th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
        th {{ background-color: #f5f5f5; }}
        .active-row {{ background-color: #e8f5e8; }}
        .inactive-row {{ background-color: #fff3cd; }}
        .trial-row {{ background-color: #e3f2fd; }}
        .not-subscription-row {{ background-color: #f5f5f5; }}
        .form-buttons {{ margin: 20px 0; }}
        button {{ padding: 10px 20px; margin: 10px 5px; }}
        .legend {{ margin: 20px 0; padding: 15px; background: #f8f9fa; border-radius: 5px; }}
        .legend span {{ margin-right: 20px; }}
    </style>
</head>
<body>
    <h1>Domain Classification</h1>
    <p>Mark domains that send subscription-related emails:</p>
    
    <div class="legend">
        <strong>Legend:</strong>
        <span>👤 User Selected</span>
        <span>🤖 LLM Suggested</span>
        <span style="background: #e8f5e8; padding: 2px 5px;">✓ Active</span>
        <span style="background: #fff3cd; padding: 2px 5px;">⏸ Inactive</span>
        <span style="background: #e3f2fd; padding: 2px 5px;">🔄 Trial</span>
        <span style="background: #f5f5f5; padding: 2px 5px;">✗ Not Subscription</span>
    </div>
    
    <form action="/classify-domains" method="post">
        <table>
            <tr>
                <th>Domain</th>
                <th>Email Count</th>
                <th>Current Status</th>
                <th>Set Status</th>
            </tr>
            {domain_rows}
        </table>
        
        <div class="form-buttons">
            <button type="submit" style="background: #4CAF50; color: white;">
                Save Classifications
            </button>
            <a href="/"><button type="button">Back to Dashboard</button></a>
        </div>
    </form>
</body>
</html>
        """
        
        self.send_response(200)
        self.send_header('Content-type', 'text/html')
        self.end_headers()
        self.wfile.write(html.encode())

    def handle_domain_classification(self):
        """Handle domain classification form submission"""
        # Parse form data
        content_length = int(self.headers['Content-Length'])
        post_data = self.rfile.read(content_length).decode('utf-8')
        form_data = parse_qs(post_data)
        
        # Process dropdown selections
        updated_count = 0
        active_count = 0
        inactive_count = 0
        trial_count = 0
        not_subscription_count = 0
        unclassified_count = 0
        
        # Get all domain dropdown values
        for key, value_list in form_data.items():
            if key.startswith('domain_'):
                domain = key[7:]  # Remove 'domain_' prefix
                new_status = value_list[0] if value_list else 'unclassified'
                
                # Convert 'unclassified' to NULL for database
                db_status = None if new_status == 'unclassified' else new_status
                
                affected = self.sm.update_domain_classification(domain, db_status)
                updated_count += affected
                
                # Count by category
                if new_status == 'active':
                    active_count += 1
                elif new_status == 'inactive':
                    inactive_count += 1
                elif new_status == 'trial':
                    trial_count += 1
                elif new_status == 'not_subscription':
                    not_subscription_count += 1
                else:
                    unclassified_count += 1
        
        total_domains = active_count + inactive_count + trial_count + not_subscription_count + unclassified_count
        
        html = f"""
<!DOCTYPE html>
<html>
<head>
    <title>Classification Saved</title>
    <style>body {{ font-family: Arial, sans-serif; margin: 40px; }}</style>
</head>
<body>
    <h1>Domain Classifications Saved</h1>
    <p>✅ Updated {updated_count} emails across {total_domains} domains</p>
    
    <div style="margin: 20px 0;">
        <h3>Classification Summary:</h3>
        <p>✓ Active Subscriptions: {active_count} domains</p>
        <p>⏸ Inactive Subscriptions: {inactive_count} domains</p>
        <p>🔄 Trials: {trial_count} domains</p>
        <p>✗ Not Subscriptions: {not_subscription_count} domains</p>
        <p>? Unclassified: {unclassified_count} domains</p>
    </div>
    
    <a href="/"><button>Back to Dashboard</button></a>
    <a href="/domains"><button>View Classifications</button></a>
    <a href="/emails"><button>View Emails</button></a>
</body>
</html>
        """
        
        self.send_response(200)
        self.send_header('Content-type', 'text/html')
        self.end_headers()
        self.wfile.write(html.encode())

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