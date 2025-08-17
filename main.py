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
import threading
import time

# Load environment variables
load_dotenv()

class SubscriptionManager:
    def __init__(self):
        self.db_path = "subscriptions.db"
        self.init_database()
        
        # Environment variables
        self.google_client_id = os.getenv('GOOGLE_CLIENT_ID')
        self.google_client_secret = os.getenv('GOOGLE_CLIENT_SECRET')
        self.openai_api_key = os.getenv('OPENAI_API_KEY')
        self.openai_model = os.getenv('OPENAI_MODEL', 'gpt-4o-mini')
        self.confidence_threshold = float(os.getenv('LLM_CONFIDENCE_THRESHOLD', '0.7'))
        
        # Server config
        self.port = 8000
        self.redirect_uri = f"http://localhost:{self.port}/auth/callback"

    def init_database(self):
        """Initialize SQLite database"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Users table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id TEXT PRIMARY KEY DEFAULT '1',
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
                confidence_score DECIMAL(3,2),
                vendor TEXT,
                email_type TEXT,
                FOREIGN KEY (connection_id) REFERENCES connections(id)
            )
        ''')
        
        # Create default user
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

    def fetch_metadata_only(self, connection_id: str, max_results: int = 100):
        """Fetch email metadata only (fast mode) - our core function"""
        import time
        start_time = time.time()
        
        print(f"Starting fast metadata fetch for {max_results} emails...")
        
        access_token = self.get_valid_access_token(connection_id)
        headers = {'Authorization': f'Bearer {access_token}'}
        
        # Get list of message IDs (fast)
        list_url = f'https://gmail.googleapis.com/gmail/v1/users/me/messages?maxResults={max_results}'
        list_response = requests.get(list_url, headers=headers)
        
        if list_response.status_code != 200:
            return {"error": f"Failed to fetch message list: {list_response.text}"}
        
        messages = list_response.json().get('messages', [])
        print(f"Found {len(messages)} messages to process")
        
        if not messages:
            return {"fetched": 0, "stored": 0, "duplicates": 0, "time": 0}
        
        conn = self.get_db_connection()
        cursor = conn.cursor()
        
        stored_count = 0
        duplicate_count = 0
        error_count = 0
        
        # Process messages in batches for efficiency
        for i, message in enumerate(messages):
            try:
                msg_id = message['id']
                
                # Check if already processed
                cursor.execute('SELECT id FROM processed_emails WHERE gmail_message_id = ?', (msg_id,))
                if cursor.fetchone():
                    duplicate_count += 1
                    continue
                
                # Fetch metadata for this message
                msg_url = f'https://gmail.googleapis.com/gmail/v1/users/me/messages/{msg_id}?format=metadata'
                msg_response = requests.get(msg_url, headers=headers)
                
                if msg_response.status_code == 200:
                    msg_data = msg_response.json()
                    headers_list = msg_data.get('payload', {}).get('headers', [])
                    msg_headers = {h['name']: h['value'] for h in headers_list if 'name' in h and 'value' in h}
                    
                    # Store metadata
                    cursor.execute('''
                        INSERT INTO processed_emails 
                        (connection_id, gmail_message_id, subject, sender, received_at)
                        VALUES (?, ?, ?, ?, ?)
                    ''', (
                        connection_id,
                        msg_id,
                        msg_headers.get('Subject', ''),
                        msg_headers.get('From', ''),
                        datetime.now().isoformat()
                    ))
                    stored_count += 1
                else:
                    error_count += 1
                    print(f"Error fetching message {i+1}: {msg_response.status_code}")
                    
                # Progress indicator
                if (i + 1) % 50 == 0:
                    print(f"Processed {i + 1}/{len(messages)} messages...")
                    
            except Exception as e:
                error_count += 1
                print(f"Error processing message {i+1}: {e}")
        
        conn.commit()
        conn.close()
        
        total_time = time.time() - start_time
        
        result = {
            "fetched": len(messages),
            "stored": stored_count,
            "duplicates": duplicate_count,
            "errors": error_count,
            "time": round(total_time, 1)
        }
        
        print(f"Metadata fetch complete: {result}")
        return result

    def get_connections(self):
        """Get all Gmail connections"""
        conn = self.get_db_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM connections ORDER BY created_at DESC')
        columns = [desc[0] for desc in cursor.description]
        results = [dict(zip(columns, row)) for row in cursor.fetchall()]
        conn.close()
        return results

    def get_processed_emails(self, limit: int = 50, offset: int = 0):
        """Get processed emails with pagination"""
        conn = self.get_db_connection()
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
        """Clear all data"""
        conn = self.get_db_connection()
        cursor = conn.cursor()
        cursor.execute('DELETE FROM processed_emails')
        cursor.execute('DELETE FROM connections')
        conn.commit()
        conn.close()
        print("Database reset complete")

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
            <label>Number of emails:</label>
            <select name="count">
                <option value="100">100 emails</option>
                <option value="500">500 emails</option>
                <option value="1000" selected>1,000 emails</option>
                <option value="5000">5,000 emails</option>
            </select>
            <button type="submit">Fetch Metadata</button>
        </form>
        <p><small>Fetches email headers only (fast). No LLM processing yet.</small></p>
    </div>
    
    <div class="section">
        <h2>3. View Data</h2>
        <a href="/emails"><button>View Stored Emails</button></a>
        <a href="/reset"><button onclick="return confirm('Delete all data?')">Reset Database</button></a>
    </div>
    
    <div class="section">
        <h2>4. LLM Integration (Ready)</h2>
        <p>OpenAI API Key: {'✓ Configured' if self.sm.openai_api_key else '✗ Missing'}</p>
        <p>Model: {self.sm.openai_model}</p>
        <p><small>Ready for next phase: grouping and classification</small></p>
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

    def handle_metadata_fetch(self):
        """Handle metadata fetch request"""
        # Parse form data
        content_length = int(self.headers['Content-Length'])
        post_data = self.rfile.read(content_length).decode('utf-8')
        form_data = parse_qs(post_data)
        
        max_results = int(form_data.get('count', ['1000'])[0])
        
        # Get active connection
        connections = self.sm.get_connections()
        if not connections:
            self.send_error(400, "No Gmail connection found")
            return
        
        connection_id = connections[0]['id']
        
        # Run metadata fetch
        result = self.sm.fetch_metadata_only(connection_id, max_results)
        
        # Return simple response
        html = f"""
<!DOCTYPE html>
<html>
<head>
    <title>Fetch Complete</title>
    <style>body {{ font-family: Arial, sans-serif; margin: 40px; }}</style>
</head>
<body>
    <h1>Metadata Fetch Complete</h1>
    <p>Fetched: {result.get('fetched', 0)} emails</p>
    <p>Stored: {result.get('stored', 0)} new emails</p>
    <p>Duplicates skipped: {result.get('duplicates', 0)}</p>
    <p>Time: {result.get('time', 0)}s</p>
    <p>Speed: {result.get('fetched', 0) / max(result.get('time', 1), 1):.1f} emails/sec</p>
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