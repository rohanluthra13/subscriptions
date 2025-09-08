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
from contextlib import contextmanager

# Load environment variables
load_dotenv()

# Logo fetching utilities
def fetch_favicon_for_domain(domain, timeout=5, max_size=500000):
    """
    Utility function to fetch favicon for a domain
    Returns (logo_data, content_type) tuple or (None, None) if failed
    
    Tries multiple favicon locations in order of preference:
    1. Parse HTML for favicon link tags
    2. Standard favicon.ico location
    3. PNG favicon
    4. Google's favicon service as fallback
    
    Args:
        domain: The domain to fetch favicon for
        timeout: Request timeout in seconds
        max_size: Maximum favicon size in bytes (default 500KB)
    """
    # Clean domain - remove protocol if present
    if '://' in domain:
        domain = urlparse(domain).netloc
    
    headers = {
        'User-Agent': 'SubscriptionManager/1.0 (Favicon Fetcher)',
        'Accept': 'image/*,text/html'
    }
    
    # Create session for proper resource management
    session = requests.Session()
    
    try:
        # First, try to parse HTML for favicon links
        try:
            html_response = session.get(f"https://{domain}", timeout=timeout, headers=headers)
            if html_response.status_code == 200:
                html_content = html_response.text[:50000]  # Limit to first 50KB
            
            # Look for favicon link tags (simple regex approach)
            import re
            # Match <link rel="icon" ... href="..."> or rel="shortcut icon"
            favicon_patterns = [
                r'<link[^>]*rel=["\'](?:shortcut )?icon["\'][^>]*href=["\'](.*?)["\']',
                r'<link[^>]*href=["\'](.*?)["\'][^>]*rel=["\'](?:shortcut )?icon["\']',
                # Also check for apple-touch-icon as fallback
                r'<link[^>]*rel=["\']apple-touch-icon["\'][^>]*href=["\'](.*?)["\']',
            ]
            
            for pattern in favicon_patterns:
                matches = re.findall(pattern, html_content, re.IGNORECASE)
                for match in matches:
                    # Build absolute URL
                    if match.startswith('http'):
                        favicon_url = match
                    elif match.startswith('//'):
                        favicon_url = f"https:{match}"
                    elif match.startswith('/'):
                        favicon_url = f"https://{domain}{match}"
                    else:
                        # Relative path
                        favicon_url = f"https://{domain}/{match}"
                    
                    try:
                        response = session.get(favicon_url, timeout=timeout, headers=headers, stream=True)
                        if response.status_code == 200:
                            # Check content length if provided
                            content_length = response.headers.get('content-length')
                            if content_length and int(content_length) > max_size:
                                print(f"Favicon too large ({content_length} bytes) from {favicon_url}")
                                continue
                            
                            # Read content with size limit
                            content = b''
                            for chunk in response.iter_content(chunk_size=8192):
                                content += chunk
                                if len(content) > max_size:
                                    print(f"Favicon exceeds max size ({max_size} bytes) from {favicon_url}")
                                    break
                            else:
                                # Content is within size limit
                                if content:
                                    # Detect content type from URL or response
                                    content_type = response.headers.get('content-type', '')
                                    if not content_type:
                                        if '.png' in favicon_url.lower():
                                            content_type = 'image/png'
                                        elif '.ico' in favicon_url.lower():
                                            content_type = 'image/x-icon'
                                        elif '.jpg' in favicon_url.lower() or '.jpeg' in favicon_url.lower():
                                            content_type = 'image/jpeg'
                                        else:
                                            content_type = 'image/x-icon'
                                    print(f"Found favicon via HTML parsing: {favicon_url} ({len(content)} bytes)")
                                    return content, content_type
                    except requests.exceptions.Timeout:
                        print(f"Timeout fetching favicon from {favicon_url}")
                    except requests.exceptions.ConnectionError:
                        print(f"Connection error fetching favicon from {favicon_url}")
                    except Exception as e:
                        print(f"Error fetching favicon from {favicon_url}: {e}")
        except requests.exceptions.Timeout:
            print(f"Timeout fetching HTML from {domain}")
        except requests.exceptions.ConnectionError:
            print(f"Connection error fetching HTML from {domain}")
        except Exception as e:
            print(f"Failed to parse HTML for favicon from {domain}: {e}")
    
        # Fallback to standard locations
        favicon_urls = [
            f"https://{domain}/favicon.ico",
            f"https://{domain}/favicon.png", 
            f"https://www.google.com/s2/favicons?domain={domain}&sz=32"
        ]
        
        for url in favicon_urls:
            try:
                response = session.get(url, timeout=timeout, headers=headers, stream=True)
                if response.status_code == 200:
                    # Check size for Google's service (last fallback)
                    content_length = response.headers.get('content-length')
                    if content_length and int(content_length) > max_size:
                        print(f"Favicon too large ({content_length} bytes) from {url}")
                        continue
                    
                    # Read content with size limit
                    content = b''
                    for chunk in response.iter_content(chunk_size=8192):
                        content += chunk
                        if len(content) > max_size:
                            print(f"Favicon exceeds max size ({max_size} bytes) from {url}")
                            break
                    else:
                        if content:
                            # Get content type, default to image/x-icon for .ico files
                            content_type = response.headers.get('content-type', 'image/x-icon')
                            if url.endswith('.ico') and 'icon' not in content_type:
                                content_type = 'image/x-icon'
                            print(f"Found favicon at standard location: {url} ({len(content)} bytes)")
                            return content, content_type
            except requests.exceptions.Timeout:
                print(f"Timeout fetching favicon from {url}")
            except requests.exceptions.ConnectionError:
                print(f"Connection error fetching favicon from {url}")
            except Exception as e:
                print(f"Error fetching favicon from {url}: {e}")
                continue
        
        return None, None
    finally:
        # Always close the session to free resources
        session.close()

def handle_db_errors(default_return=None, should_raise=False):
    """
    Decorator to handle common database errors consistently.
    
    Args:
        default_return: Value to return if database is locked/timeout (default: None)
        should_raise: If True, re-raise database errors instead of returning default
    
    Usage:
        @handle_db_errors(default_return=[])
        def get_data(self): ...
        
        @handle_db_errors(should_raise=True)  
        def update_data(self): ...
    """
    def decorator(func):
        def wrapper(self, *args, **kwargs):
            try:
                return func(self, *args, **kwargs)
            except sqlite3.OperationalError as e:
                if "database is locked" in str(e).lower() or "timeout" in str(e).lower():
                    print(f"Database timeout/lock in {func.__name__}: {e}")
                    if should_raise:
                        raise
                    return default_return
                raise  # Re-raise other operational errors
        return wrapper
    return decorator

class CostUtils:
    """Utility class for consistent cost parsing across all contexts"""
    
    @staticmethod
    def parse_cost_for_calculation(cost_raw):
        """
        Parse cost for mathematical calculations (returns float)
        Used in dashboard totals and financial calculations
        
        Args:
            cost_raw: Raw cost value (string, number, or None)
            
        Returns:
            float: Clean numeric value for calculations, 0.0 if invalid
        """
        if not cost_raw:
            return 0.0
        try:
            if isinstance(cost_raw, str):
                # Remove $ symbols and whitespace, handle empty strings
                clean_str = cost_raw.replace('$', '').strip()
                return float(clean_str) if clean_str else 0.0
            return float(cost_raw)
        except (ValueError, TypeError):
            return 0.0
    
    @staticmethod
    def format_cost_for_display(cost_raw):
        """
        Format cost for user display (returns formatted string)
        Used in subscription cards and UI display elements
        
        Args:
            cost_raw: Raw cost value (string, number, or None)
            
        Returns:
            str: Formatted display string like "$15.99" or "?" for zero/empty
        """
        if not cost_raw:
            return "?"
        try:
            # Remove existing $ symbols and convert to float
            cost_str = str(cost_raw).replace('$', '').strip()
            cost_value = float(cost_str) if cost_str else 0
            # Format with $ prefix if positive, otherwise show "?"
            return f"${cost_value:.2f}" if cost_value > 0 else "?"
        except (ValueError, TypeError):
            return "?"
    
    @staticmethod
    def clean_cost_for_input(cost_raw):
        """
        Clean cost for form input fields (returns string without $)
        Used when populating form inputs for editing
        
        Args:
            cost_raw: Raw cost value (string, number, or None)
            
        Returns:
            str: Clean string value suitable for input fields
        """
        if not cost_raw:
            return ''
        if isinstance(cost_raw, str):
            return cost_raw.replace('$', '').strip()
        return str(cost_raw)

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
    
    @contextmanager
    def db_connection(self, timeout=10.0):
        """Context manager for database connections - ensures proper cleanup"""
        conn = sqlite3.connect(self.db_path, timeout=timeout)
        conn.row_factory = sqlite3.Row  # Enable column access by name
        try:
            yield conn
        finally:
            conn.close()

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
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT NOT NULL,
                gmail_message_id TEXT UNIQUE NOT NULL,
                subject TEXT,
                sender TEXT,
                sender_domain TEXT,
                received_at TIMESTAMP,
                processed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                content TEXT,
                content_fetched BOOLEAN DEFAULT 0,
                analyzed_for_subscriptions BOOLEAN DEFAULT 0
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
                website_url TEXT,
                logo_data BLOB,
                logo_content_type TEXT,
                created_by TEXT DEFAULT 'user',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        
        # Create indexes for better query performance
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_gmail_message_id ON processed_emails(gmail_message_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_sender_domain ON processed_emails(sender_domain)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_email ON processed_emails(email)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_received_at ON processed_emails(received_at DESC)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_content_fetched ON processed_emails(content_fetched)')
        
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
        
        try:
            cursor.execute('ALTER TABLE processed_emails ADD COLUMN analyzed_for_subscriptions BOOLEAN DEFAULT 0')
        except sqlite3.OperationalError:
            pass
        
        # Add logo-related fields to subscriptions table
        try:
            cursor.execute('ALTER TABLE subscriptions ADD COLUMN website_url TEXT')
        except sqlite3.OperationalError:
            pass
        
        try:
            cursor.execute('ALTER TABLE subscriptions ADD COLUMN logo_data BLOB')
        except sqlite3.OperationalError:
            pass
        
        try:
            cursor.execute('ALTER TABLE subscriptions ADD COLUMN logo_content_type TEXT')
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
        if not refresh_token or refresh_token.strip() == '':
            raise Exception("No valid refresh token available")
            
        data = {
            'client_id': self.google_client_id,
            'client_secret': self.google_client_secret,
            'refresh_token': refresh_token,
            'grant_type': 'refresh_token',
            'scope': 'https://www.googleapis.com/auth/gmail.readonly'
        }
        
        response = requests.post('https://oauth2.googleapis.com/token', data=data)
        
        if not response.ok:
            error_detail = response.text
            print(f"Token refresh failed: HTTP {response.status_code} - {error_detail}")
            raise Exception(f"Token refresh failed: {response.status_code} - {error_detail}")
        
        token_data = response.json()
        
        if 'error' in token_data:
            error_msg = token_data.get('error_description', token_data['error'])
            print(f"Token refresh error: {error_msg}")
            raise Exception(f"Token refresh error: {error_msg}")
            
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
        
        # Handle timezone conversion more robustly
        try:
            if token_expiry.endswith('Z'):
                expiry_time = datetime.fromisoformat(token_expiry.replace('Z', '+00:00'))
            elif '+00:00' in token_expiry or 'T' in token_expiry:
                expiry_time = datetime.fromisoformat(token_expiry)
            else:
                # Fallback for simple ISO format
                expiry_time = datetime.fromisoformat(token_expiry)
        except ValueError as e:
            conn.close()
            raise Exception(f"Invalid token expiry format: {token_expiry} - {str(e)}")
        
        # If token expires within 5 minutes, refresh it
        if expiry_time <= datetime.now() + timedelta(minutes=5):
            print("Refreshing access token...")
            try:
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
                    print("Access token refreshed successfully")
                else:
                    conn.close()
                    raise Exception("Failed to refresh token - no access_token in response")
            except Exception as e:
                conn.close()
                print(f"Token refresh failed for {email}: {str(e)}")
                raise Exception(f"Token refresh failed: {str(e)}. Please re-authenticate.")
        
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


    @handle_db_errors(default_return=[])
    def get_connections(self):
        """Get all Gmail connections with timeout handling"""
        with self.db_connection(timeout=5.0) as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM connections ORDER BY created_at DESC')
            columns = [desc[0] for desc in cursor.description]
            results = [dict(zip(columns, row)) for row in cursor.fetchall()]
        return results

    @handle_db_errors(default_return=[])
    def get_subscriptions(self):
        """Get all subscriptions with timeout handling"""
        with self.db_connection(timeout=5.0) as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM subscriptions ORDER BY created_at DESC')
            columns = [desc[0] for desc in cursor.description]
            results = [dict(zip(columns, row)) for row in cursor.fetchall()]
        return results

    @handle_db_errors(should_raise=True)
    def update_subscription(self, subscription_id, field, value):
        """Update a single field of a subscription"""
        with self.db_connection(timeout=5.0) as conn:
            cursor = conn.cursor()
            
            # Validate field name for security
            valid_fields = ['name', 'category', 'cost', 'currency', 'billing_cycle', 
                           'status', 'auto_renewing', 'next_billing_date', 'notes', 'website_url']
            if field not in valid_fields:
                raise ValueError(f"Invalid field: {field}")
            
            # Handle boolean conversion for auto_renewing
            if field == 'auto_renewing':
                value = bool(int(value)) if value in ['0', '1'] else bool(value)
            
            # Update the field and set updated_at timestamp
            cursor.execute(f'''
                UPDATE subscriptions 
                SET {field} = ?, updated_at = CURRENT_TIMESTAMP 
                WHERE id = ?
            ''', (value, subscription_id))
            
            conn.commit()
            
            # Check if the update actually affected a row
            if cursor.rowcount == 0:
                raise ValueError(f"Subscription with id {subscription_id} not found")
            
            # Trigger logo fetch if website_url was updated
            if field == 'website_url' and value:
                def fetch_logo_async():
                    try:
                        print(f"Auto-fetching logo for updated website URL: {value}")
                        self.fetch_logo_for_subscription(subscription_id)
                    except Exception as e:
                        print(f"Background logo fetch failed for subscription {subscription_id}: {e}")
                
                thread = threading.Thread(target=fetch_logo_async, daemon=True)
                thread.start()
                
            return True

    @handle_db_errors(should_raise=True)
    def create_subscription(self, data=None):
        """Create a new subscription with default or provided values"""
        try:
            with self.db_connection(timeout=5.0) as conn:
                cursor = conn.cursor()
                
                # Set defaults if no data provided
                if data is None:
                    data = {}
                
                # Use provided values or defaults
                name = data.get('name', 'New Subscription')
                category = data.get('category', '')
                cost = data.get('cost', 0.00)
                currency = data.get('currency', 'NZD')
                billing_cycle = data.get('billing_cycle', 'monthly')
                status = data.get('status', 'active')
                auto_renewing = data.get('auto_renewing', True)
                notes = data.get('notes', '')
                website_url = data.get('website_url', '')
                
                cursor.execute('''
                    INSERT INTO subscriptions 
                    (name, category, cost, currency, billing_cycle, status, auto_renewing, notes, website_url, created_by)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'user')
                ''', (name, category, cost, currency, billing_cycle, status, auto_renewing, notes, website_url))
                
                conn.commit()
                
                # Get the ID of the newly created subscription
                subscription_id = cursor.lastrowid
                
                # Fetch and return the complete subscription record
                cursor.execute('SELECT * FROM subscriptions WHERE rowid = ?', (subscription_id,))
                columns = [desc[0] for desc in cursor.description]
                row = cursor.fetchone()
                
                result = dict(zip(columns, row)) if row else None
                
                # Trigger logo fetch in background if website URL provided
                if result and website_url:
                    def fetch_logo_async():
                        try:
                            print(f"Auto-fetching logo for new subscription: {name}")
                            self.fetch_logo_for_subscription(result['id'])
                        except Exception as e:
                            print(f"Background logo fetch failed: {e}")
                    
                    thread = threading.Thread(target=fetch_logo_async, daemon=True)
                    thread.start()
                
                return result
                
        except sqlite3.IntegrityError as e:
            if "UNIQUE constraint failed: subscriptions.name" in str(e):
                raise ValueError("A subscription with this name already exists")
            raise

    @handle_db_errors(should_raise=True)
    def delete_subscription(self, subscription_id):
        """Delete a subscription by ID"""
        with self.db_connection(timeout=5.0) as conn:
            cursor = conn.cursor()
            
            cursor.execute('DELETE FROM subscriptions WHERE id = ?', (subscription_id,))
            conn.commit()
            
            # Check if the delete actually affected a row
            if cursor.rowcount == 0:
                raise ValueError(f"Subscription with id {subscription_id} not found")
                
            return True

    @handle_db_errors(default_return=0)
    def get_email_count(self):
        """Get total count of processed emails with timeout handling"""
        with self.db_connection(timeout=5.0) as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT COUNT(*) FROM processed_emails')
            count = cursor.fetchone()[0]
        return count

    def get_processed_emails(self, limit: int = None, offset: int = 0, filters: dict = None, sort_by: str = None, sort_dir: str = 'desc'):
        """Get processed emails with optional pagination, filters, and sorting"""
        with self.db_connection() as conn:
            cursor = conn.cursor()
            
            # Build WHERE clause based on filters
            where_parts = []
            params = []
            
            if filters:
                if filters.get('domain'):
                    where_parts.append('sender_domain = ?')
                    params.append(filters['domain'])
                
                if filters.get('has_content') is not None:
                    if filters['has_content']:
                        where_parts.append('(content IS NOT NULL AND content != "")')
                    else:
                        where_parts.append('(content IS NULL OR content = "")')
                
                if filters.get('email_account'):
                    where_parts.append('email = ?')
                    params.append(filters['email_account'])
            
            where_clause = ' WHERE ' + ' AND '.join(where_parts) if where_parts else ''
            
            # Build ORDER BY clause
            valid_sort_columns = {
                'domain': 'sender_domain',
                'sender': 'sender', 
                'subject': 'subject',
                'content': '(CASE WHEN content IS NOT NULL AND content != "" THEN 1 ELSE 0 END)',
                'received': 'received_at'
            }
            
            if sort_by and sort_by in valid_sort_columns:
                order_column = valid_sort_columns[sort_by]
                order_dir = 'ASC' if sort_dir.lower() == 'asc' else 'DESC'
                order_clause = f'ORDER BY {order_column} {order_dir}'
            else:
                order_clause = 'ORDER BY received_at DESC'  # Default sort
            
            # Get total count with filters
            count_query = f'SELECT COUNT(*) FROM processed_emails{where_clause}'
            cursor.execute(count_query, params)
            total = cursor.fetchone()[0]
            
            # Get emails with optional pagination
            if limit:
                query = f'''
                    SELECT * FROM processed_emails{where_clause}
                    {order_clause}
                    LIMIT ? OFFSET ?
                '''
                cursor.execute(query, params + [limit, offset])
            else:
                query = f'''
                    SELECT * FROM processed_emails{where_clause}
                    {order_clause}
                '''
                cursor.execute(query, params)
            
            columns = [desc[0] for desc in cursor.description]
            emails = [dict(zip(columns, row)) for row in cursor.fetchall()]
        
        return {"emails": emails, "total": total}


    def reset_database(self):
        """Clear all data and force fresh authentication"""
        with self.db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('DELETE FROM processed_emails')
            cursor.execute('DELETE FROM connections')
            conn.commit()
        print("Database reset complete - fresh authentication required")
    
    def update_llm_notes(self, subscription_updates):
        """Update llm_notes.md file with user check/notes data"""
        try:
            with open('resources/llm_notes.md', 'r') as f:
                content = f.read()
        except FileNotFoundError:
            return False
        
        # Create lookup dict by subscription name
        updates = {item['name']: item for item in subscription_updates}
        
        lines = content.split('\n')
        new_lines = []
        current_name = None
        
        for line in lines:
            # Check if this is a subscription name line
            if line.strip().startswith('**') and line.strip().endswith('**'):
                current_name = line.strip()[2:-2].strip()
                new_lines.append(line)
            
            # Update User Check line
            elif line.strip().startswith('User Check:') and current_name and current_name in updates:
                update = updates[current_name]
                if update['user_checked'] is True:
                    new_lines.append('User Check: [x] Yes | [ ] No')
                elif update['user_checked'] is False:
                    new_lines.append('User Check: [ ] Yes | [x] No')
                else:
                    new_lines.append('User Check: [ ] Yes | [ ] No')
            
            # Update User Notes line
            elif line.strip().startswith('User Notes:') and current_name and current_name in updates:
                update = updates[current_name]
                new_lines.append(f"User Notes: {update['user_notes']}")
            
            else:
                new_lines.append(line)
        
        # Write back to file
        try:
            with open('resources/llm_notes.md', 'w') as f:
                f.write('\n'.join(new_lines))
            return True
        except Exception as e:
            print(f"Error writing llm_notes.md: {e}")
            return False
    
    def update_subscription_logo(self, subscription_id, logo_data, content_type):
        """
        Update subscription logo in database
        Args:
            subscription_id: The subscription ID
            logo_data: Binary logo data (bytes)
            content_type: MIME type (e.g., 'image/png', 'image/x-icon')
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            with self.db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    'UPDATE subscriptions SET logo_data = ?, logo_content_type = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?',
                    (logo_data, content_type, subscription_id)
                )
                conn.commit()  # Explicitly commit the transaction
                return cursor.rowcount > 0
        except Exception as e:
            print(f"Error updating logo for subscription {subscription_id}: {e}")
            return False
    
    def fetch_logo_for_subscription(self, subscription_id):
        """
        Fetch and update logo for a subscription based on its website_url
        Args:
            subscription_id: The subscription ID
        Returns:
            dict: Result with 'success' bool and 'message' string
        """
        try:
            # Get subscription details with timeout
            with self.db_connection(timeout=5.0) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    'SELECT name, website_url FROM subscriptions WHERE id = ?',
                    (subscription_id,)
                )
                result = cursor.fetchone()
                
                if not result:
                    return {'success': False, 'message': 'Subscription not found'}
                
                name, website_url = result
                
                if not website_url:
                    return {'success': False, 'message': f'No website URL set for {name}'}
                
                # Extract domain and fetch logo
                domain = urlparse(website_url).netloc if '://' in website_url else website_url
                logo_data, content_type = fetch_favicon_for_domain(domain)
                
                if logo_data:
                    # Update database with logo
                    if self.update_subscription_logo(subscription_id, logo_data, content_type):
                        return {
                            'success': True, 
                            'message': f'Logo fetched and updated for {name}',
                            'content_type': content_type,
                            'size_bytes': len(logo_data)
                        }
                    else:
                        return {'success': False, 'message': f'Failed to save logo for {name}'}
                else:
                    return {'success': False, 'message': f'Could not fetch logo for {name} from {domain}'}
                    
        except Exception as e:
            print(f"Error fetching logo for subscription {subscription_id}: {e}")
            return {'success': False, 'message': f'Error: {str(e)}'}



class SimpleWebServer(BaseHTTPRequestHandler):
    def __init__(self, subscription_manager, job_manager, *args, **kwargs):
        self.sm = subscription_manager
        self.job_manager = job_manager
        super().__init__(*args, **kwargs)
    
    def send_json_response(self, data, status=200):
        """Helper method to send JSON responses consistently"""
        response_json = json.dumps(data, indent=2)
        self.send_response(status)
        self.send_header('Content-type', 'application/json')
        self.send_header('Content-length', str(len(response_json)))
        self.end_headers()
        self.wfile.write(response_json.encode())
    
    def render_template(self, template_name, **kwargs):
        """Simple template rendering using string replacement"""
        template_path = f"templates/{template_name}"
        with open(template_path, 'r') as f:
            template = f.read()
        
        # Replace {{variable}} with actual values
        for key, value in kwargs.items():
            # IMPORTANT: We trust server-generated HTML content
            # User data should be escaped before being put into HTML generation
            # not at the template level
            template = template.replace('{{' + key + '}}', str(value))
        
        return template

    def do_GET(self):
        """Handle GET requests"""
        url = urlparse(self.path)
        path = url.path
        params = parse_qs(url.query)
        
        if path == '/':
            self.serve_base_page()
        elif path.startswith('/api/view/'):
            view_name = path.split('/')[-1]
            self.serve_view_fragment(view_name)
        elif path == '/status':
            self.handle_status_api()
        elif path == '/auth/gmail':
            self.start_gmail_auth()
        elif path == '/auth/callback':
            self.handle_oauth_callback(params)
        elif path == '/reset':
            self.handle_reset()
        # REMOVED: /api/subscriptions endpoint - data now embedded in HTML
        elif path.startswith('/logo/'):
            # Extract subscription ID from path
            sub_id = path.split('/')[-1] if '/' in path else None
            if sub_id:
                self.serve_subscription_logo(sub_id)
            else:
                self.send_error(404)
        else:
            self.send_error(404)

    def do_POST(self):
        """Handle POST requests"""
        url = urlparse(self.path)
        path = url.path
        
        if path == '/fetch':
            self.handle_metadata_fetch()
        elif path == '/save_notepad':
            self.handle_notepad_save()
        elif path == '/save_review':
            self.handle_review_save()
        elif path == '/api/fetch':
            self.handle_api_fetch()
        elif path == '/api/fetch_email_content':
            self.handle_api_fetch_content()
        elif path == '/api/subscriptions/update':
            self.handle_subscription_update()
        elif path == '/api/subscriptions/create':
            self.handle_subscription_create()
        elif path == '/api/subscriptions/delete':
            self.handle_subscription_delete()
        # REMOVED: /api/subscriptions endpoint - data now embedded in HTML
        else:
            self.send_error(404)



    def serve_base_page(self):
        """Serve the base HTML page with navigation"""
        html = self.render_template('base.html')
        
        self.send_response(200)
        self.send_header('Content-type', 'text/html')
        self.end_headers()
        self.wfile.write(html.encode())
    
    def serve_view_fragment(self, view_name):
        """Serve view fragment for AJAX loading"""
        try:
            html = self.get_view_content(view_name)
            
            self.send_response(200)
            self.send_header('Content-type', 'text/html')
            self.end_headers()
            self.wfile.write(html.encode())
        except Exception as e:
            self.send_error(500, f"Failed to load view: {str(e)}")
    
    def serve_subscription_logo(self, subscription_id):
        """Serve logo image for a subscription"""
        try:
            # Get logo data from database
            with self.sm.db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    'SELECT logo_data, logo_content_type FROM subscriptions WHERE id = ?',
                    (subscription_id,)
                )
                result = cursor.fetchone()
                
                if result and result['logo_data']:
                    logo_data = result['logo_data']
                    content_type = result['logo_content_type'] or 'image/x-icon'
                    
                    # Send the image
                    self.send_response(200)
                    self.send_header('Content-type', content_type)
                    self.send_header('Content-length', str(len(logo_data)))
                    self.send_header('Cache-Control', 'public, max-age=86400')  # Cache for 1 day
                    self.end_headers()
                    self.wfile.write(logo_data)
                else:
                    # No logo found - return a 404 or placeholder
                    self.send_error(404, "Logo not found")
        except Exception as e:
            print(f"Error serving logo for subscription {subscription_id}: {e}")
            self.send_error(500, "Failed to serve logo")
    
    def get_view_content(self, view_name):
        """Get content for a specific view"""
        if view_name == 'home':
            return self.get_home_content()
        elif view_name == 'manage':
            return self.get_manage_content()
        elif view_name == 'emails':
            return self.get_emails_content()
        elif view_name == 'review':
            return self.get_review_content()
        elif view_name == 'notepad':
            return self.get_notepad_content()
        else:
            return f"<p>Unknown view: {view_name}</p>"
    
    def get_home_content(self):
        """Generate content for home view with summary bullets"""
        try:
            subscriptions = self.sm.get_subscriptions()
            
            # Calculate totals (same logic as manage view)
            monthly_total = 0
            yearly_total = 0
            active_count = 0
            
            for sub in subscriptions:
                # Use CostUtils for consistent cost parsing
                cost = CostUtils.parse_cost_for_calculation(sub.get('cost'))
                    
                cycle = (sub.get('billing_cycle', '') or '').lower()
                status = (sub.get('status', '') or '').lower()
                
                if status == 'active' and cost > 0:
                    active_count += 1
                    if cycle == 'monthly':
                        monthly_total += cost
                        yearly_total += cost * 12
                    elif cycle in ['yearly', 'annual']:
                        yearly_total += cost
                        monthly_total += cost / 12
            
            # Generate bullet list content
            content = f'''
            <div style="padding: 60px 0;">
                <h2>what am i paying for</h2>
                <ul style="font-size: 14px; line-height: 1.6; list-style: none; padding: 0; margin-top: 30px;">
                    <li style="margin-bottom: 12px;">• {active_count} subscriptions</li>
                    <li style="margin-bottom: 12px;">• ${monthly_total:.2f} per month</li>
                    <li style="margin-bottom: 12px;">• ${yearly_total:.2f} per year</li>
                </ul>
            </div>
            '''
            
            return content
            
        except Exception as e:
            print(f"Error generating home content: {e}")
            # Return a fallback content when database issues occur
            return '''
            <div style="padding: 60px 0;">
                <h2>what am i paying for</h2>
                <div style="text-align: center; padding: 40px; color: #666;">
                    <p>Having trouble loading subscription data.</p>
                    <p style="margin-top: 20px;">
                        <button onclick="loadView('home')" style="margin-right: 10px;">Retry</button>
                        <button onclick="loadView('manage')">Go to Manage Subscriptions</button>
                    </p>
                </div>
            </div>
            '''
    
    def _sanitize_subscription_for_json(self, subscription):
        """Remove BLOB data and prepare subscription for JSON serialization"""
        sub_copy = subscription.copy()
        if 'logo_data' in sub_copy:
            sub_copy['has_logo'] = bool(sub_copy.get('logo_data'))
            del sub_copy['logo_data']  # Remove BLOB data for JSON
        return sub_copy
    
    def get_manage_content(self):
        """Generate content for manage view with all data"""
        import html
        import json
        
        subscriptions = self.sm.get_subscriptions()
        
        # Prepare JSON-safe data for embedding (remove BLOB data for JSON serialization)
        json_safe_subscriptions = [
            self._sanitize_subscription_for_json(sub) 
            for sub in subscriptions
        ]
        
        subscriptions_json = json.dumps(json_safe_subscriptions)
        
        # Generate subscription cards or empty state
        subscription_cards = ""
        
        if not subscriptions:
            # Empty state - show message encouraging first subscription
            subscription_cards = '''
            <div class="empty-state">
                <h3>Add your first subscription</h3>
                <p>Click the + button below to get started</p>
            </div>'''
        else:
            for sub in subscriptions:
                # Use CostUtils for consistent cost display formatting
                cost_display = CostUtils.format_cost_for_display(sub.get('cost'))
                
                # Get billing cycle - show ? if empty
                cycle = sub.get('billing_cycle', '')
                if not cycle or cycle.strip() == '':
                    cycle_display = "?"
                else:
                    cycle_display = cycle
                
                # If both cost and cycle are unknown, just show ?
                if cost_display == "?" and cycle_display == "?":
                    details_display = "?"
                else:
                    details_display = f'<span class="card-cost">{cost_display}</span><span class="card-cycle">{cycle_display}</span>'
                
                # Check if subscription has a logo
                sub_id = sub.get('id', '')
                # Escape user-provided data to prevent XSS
                safe_name = html.escape(sub.get('name', ''))
                
                logo_html = ''
                if sub.get('logo_data'):
                    logo_html = f'<img class="card-logo" src="/logo/{sub_id}" alt="{safe_name} logo">'
                
                subscription_cards += f'''
                <div class="subscription-card" data-subscription-id="{sub_id}">
                    <div class="card-left">
                        {logo_html}
                        <div class="card-name">{safe_name}</div>
                    </div>
                    <div class="card-details">
                        {details_display}
                    </div>
                </div>'''
        
        return self.render_template('views/manage.html',
            subscription_cards=subscription_cards,
            embedded_subscriptions=subscriptions_json
        )
    
    def get_emails_content(self):
        """Generate content for emails view"""
        email_count = self.sm.get_email_count()
        connections = self.sm.get_connections()
        connected = len(connections) > 0
        
        # Email address display
        email_address = connections[0]["email"] if connected else "Not connected"
        
        # Action buttons
        if not connected:
            action_buttons = '''
                <a href="/auth/gmail" style="text-decoration: none;">
                    <button style="padding: 10px 20px; border: 1px solid #1a73e8; background: #1a73e8; color: white; cursor: pointer; font-size: 14px; border-radius: 4px;">
                        Connect Gmail
                    </button>
                </a>
            '''
        else:
            action_buttons = '''
                <button onclick="changeEmail()" style="padding: 10px 20px; margin-right: 10px; border: 1px solid #ddd; background: white; cursor: pointer; font-size: 14px; border-radius: 4px;">
                    Change Email
                </button>
                <button onclick="fetchEmails()" style="padding: 10px 20px; border: 1px solid #ddd; background: white; cursor: pointer; font-size: 14px; border-radius: 4px;">
                    Fetch Emails
                </button>
            '''
        
        # Generate emails table
        emails_table = ""
        if connected and email_count > 0:
            # Get recent emails for display
            emails_data = self.sm.get_processed_emails(limit=20)
            emails = emails_data.get('emails', [])
            if emails:
                emails_table = '''
                <table>
                    <thead>
                        <tr>
                            <th>From</th>
                            <th>Subject</th>
                            <th>Date</th>
                            <th>Domain</th>
                        </tr>
                    </thead>
                    <tbody>
                '''
                for email in emails:
                    # Format date if available
                    date_str = email.get('received_at', '')
                    if date_str:
                        try:
                            # Format timestamp to readable date
                            from datetime import datetime
                            dt = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
                            date_str = dt.strftime('%Y-%m-%d %H:%M')
                        except:
                            pass
                    
                    emails_table += f'''
                    <tr>
                        <td>{email.get('sender', '')}</td>
                        <td>{email.get('subject', '')}</td>
                        <td>{date_str}</td>
                        <td>{email.get('sender_domain', '')}</td>
                    </tr>
                    '''
                emails_table += '</tbody></table>'
            else:
                emails_table = '<p style="color: #666; text-align: center; margin-top: 40px;">No emails processed yet. Click "Fetch Emails" to start.</p>'
        elif connected:
            emails_table = '<p style="color: #666; text-align: center; margin-top: 40px;">No emails fetched yet. Click "Fetch Emails" to start.</p>'
        else:
            emails_table = ''
        
        return self.render_template('views/emails.html', 
            email_address=email_address,
            action_buttons=action_buttons,
            emails_table=emails_table
        )
    
    def get_review_content(self):
        """Generate content for review view using template"""
        checklist_content = ""
        
        try:
            with open('resources/llm_notes.md', 'r') as f:
                content = f.read()
                
            # Parse the markdown to extract subscription items
            current_item = {}
            item_index = 0
            
            lines = content.split('\n')
            for line in lines:
                line = line.strip()
                
                # Start of new subscription item (markdown header)
                if line.startswith('**') and line.endswith('**'):
                    # Save previous item if it exists
                    if current_item:
                        checklist_content += self._generate_review_item(current_item, item_index)
                        item_index += 1
                    
                    # Start new item
                    current_item = {
                        'name': line[2:-2],  # Remove ** markers
                        'domains': '',
                        'notes': '',
                        'user_check': 'pending',
                        'user_notes': ''
                    }
                
                elif line.startswith('Domains:') and current_item:
                    current_item['domains'] = line[8:].strip()
                
                elif line.startswith('Notes:') and current_item:
                    current_item['notes'] = line[6:].strip()
                
                elif line.startswith('User Check:') and current_item:
                    # Parse user check status
                    if '[x] Yes' in line:
                        current_item['user_check'] = 'yes'
                    elif '[x] No' in line:
                        current_item['user_check'] = 'no'
                    else:
                        current_item['user_check'] = 'pending'
                
                elif line.startswith('User Notes:') and current_item:
                    current_item['user_notes'] = line[11:].strip()
            
            # Don't forget the last item
            if current_item:
                checklist_content += self._generate_review_item(current_item, item_index)
        
        except FileNotFoundError:
            checklist_content = '''
            <div style="text-align: center; padding: 40px; color: #666;">
                <p>No LLM analysis found yet.</p>
                <p style="margin-top: 20px;">Connect Gmail and run email analysis to generate subscription suggestions for review.</p>
            </div>
            '''
        
        return self.render_template('views/review.html',
            checklist_content=checklist_content
        )
    
    def get_notepad_content(self):
        """Generate content for notepad view using template"""
        # Read existing notes from resources/notepad.md if it exists
        subscription_items = ""
        other_notes_items = ""
        
        try:
            with open('resources/notepad.md', 'r') as f:
                content = f.read()
                
            # Parse the markdown to extract items
            current_section = None
            for line in content.split('\n'):
                line = line.strip()
                if line == "## Subscriptions":
                    current_section = "subscriptions"
                elif line == "## Other Notes":
                    current_section = "other_notes"
                elif line.startswith('- ') and current_section:
                    item_text = line[2:].strip()
                    if current_section == "subscriptions":
                        subscription_items += f'''
                        <div class="note-item">
                            <span class="bullet">•</span>
                            <input name="subscriptions" value="{item_text}" />
                        </div>
                        '''
                    elif current_section == "other_notes":
                        other_notes_items += f'''
                        <div class="note-item">
                            <span class="bullet">•</span>
                            <textarea name="other_notes" rows="1">{item_text}</textarea>
                        </div>
                        '''
        except FileNotFoundError:
            # File doesn't exist yet, start with empty sections
            pass
        
        return self.render_template('views/notepad.html',
            subscription_items=subscription_items,
            other_notes_items=other_notes_items
        )


    def _generate_review_item(self, item, index):
        """Generate HTML for a single review item"""
        # Determine completion status
        is_completed = item['user_check'] in ['yes', 'no']
        data_completed = 'true' if is_completed else 'false'
        
        # Radio button states
        yes_checked = 'checked' if item['user_check'] == 'yes' else ''
        no_checked = 'checked' if item['user_check'] == 'no' else ''
        
        # Notes display
        notes_display = ''
        notes_input_wrapper = 'display: none;'
        add_note_btn_display = 'display: inline;'
        
        if item['user_notes']:
            notes_display = f'<div id="notes-display-{index}" style="margin-top: 8px; padding: 8px; background: #f8f9fa; border-radius: 4px; font-size: 12px; color: #666;">{item["user_notes"]}</div>'
            notes_input_wrapper = 'display: flex;'
            add_note_btn_display = 'display: none;'
        
        return f'''
        <div class="subscription-item" data-completed="{data_completed}" style="margin-bottom: 20px;">
            <input type="hidden" name="subscription_name_{index}" value="{item["name"]}">
            <div style="padding: 15px; background: white; border-radius: 8px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); position: relative; z-index: 1;">
                <div style="margin-bottom: 10px;">
                    <h4 style="margin: 0 0 5px 0; font-size: 16px; font-weight: 500; color: #333;">{item["name"]}</h4>
                    <div style="font-size: 12px; color: #666; margin-bottom: 8px;">
                        <span style="font-weight: 500;">Domains:</span> {item["domains"]}
                    </div>
                    <div style="font-size: 13px; color: #555; line-height: 1.4;">
                        {item["notes"]}
                    </div>
                </div>
                
                <div style="display: flex; align-items: center; justify-content: space-between; margin-top: 12px;">
                    <div style="display: flex; align-items: center; gap: 15px;">
                        <label style="display: flex; align-items: center; gap: 5px; font-size: 13px; cursor: pointer;">
                            <input type="radio" name="user_check_{index}" value="yes" {yes_checked} onchange="handleRadioChange()" style="margin: 0;">
                            <span>Yes</span>
                        </label>
                        <label style="display: flex; align-items: center; gap: 5px; font-size: 13px; cursor: pointer;">
                            <input type="radio" name="user_check_{index}" value="no" {no_checked} onchange="handleRadioChange()" style="margin: 0;">
                            <span>No</span>
                        </label>
                    </div>
                    
                    <button type="button" id="add-note-btn-{index}" onclick="toggleNotes({index})" style="border: none; background: none; color: #666; cursor: pointer; font-size: 12px; font-family: inherit; padding: 4px 8px; {add_note_btn_display}">
                        add note
                    </button>
                </div>
                
                {notes_display}
                
                <div id="notes-input-wrapper-{index}" style="{notes_input_wrapper} align-items: center; gap: 8px; margin-top: 8px;">
                    <input type="text" name="user_notes_{index}" id="notes-input-{index}" value="{item["user_notes"]}" placeholder="Add your notes..." style="flex: 1; padding: 6px; border: 1px solid #ddd; border-radius: 4px; font-size: 12px; font-family: inherit;">
                </div>
            </div>
        </div>
        '''
    def _generate_notepad_markdown(self, subscriptions, other_notes):
        """Generate markdown content from notepad sections"""
        lines = ["## Subscriptions"]
        for note in subscriptions:
            if note.strip():  # Only add non-empty notes
                lines.append(f"- {note}")
        
        lines.extend(["", "## Other Notes"])
        for note in other_notes:
            if note.strip():  # Only add non-empty notes
                lines.append(f"- {note}")
        
        return '\n'.join(lines) + '\n'

    def handle_notepad_save(self):
        """Handle saving notepad content"""
        try:
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length).decode('utf-8')
            form_data = parse_qs(post_data)
            
            # Extract and clean form data
            subscriptions = form_data.get('subscriptions', [])
            other_notes = form_data.get('other_notes', [])
            
            # Generate and save markdown content
            content = self._generate_notepad_markdown(subscriptions, other_notes)
            
            # Ensure directory exists
            os.makedirs('resources', exist_ok=True)
            
            # Write to file
            with open('resources/notepad.md', 'w') as f:
                f.write(content)
            
            # Return success response for AJAX
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(b'{"success": true}')
            
        except Exception as e:
            print(f"Error saving notepad: {e}")
            # Return error response
            self.send_response(500)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            error_msg = json.dumps({"success": False, "error": str(e)})
            self.wfile.write(error_msg.encode())

    def handle_review_save(self):
        """Handle saving review form data back to llm_notes.md"""
        try:
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length).decode('utf-8')
            form_data = parse_qs(post_data)
            
            # Parse form data into subscription updates
            subscription_updates = []
            
            # Group form data by subscription index
            subscription_data = {}
            for key, value in form_data.items():
                # Handle field names like user_check_0, user_notes_0, subscription_name_0
                if key.startswith('user_check_'):
                    index = key.replace('user_check_', '')
                    if index not in subscription_data:
                        subscription_data[index] = {}
                    subscription_data[index]['check'] = value[0] if value else ''
                elif key.startswith('user_notes_'):
                    index = key.replace('user_notes_', '')
                    if index not in subscription_data:
                        subscription_data[index] = {}
                    subscription_data[index]['notes'] = value[0] if value else ''
                elif key.startswith('subscription_name_'):
                    index = key.replace('subscription_name_', '')
                    if index not in subscription_data:
                        subscription_data[index] = {}
                    subscription_data[index]['name'] = value[0] if value else ''
            
            # Convert to update format
            for index_data in subscription_data.values():
                if 'name' in index_data:  # Ensure we have a name
                    user_checked = None
                    if 'check' in index_data:
                        user_checked = True if index_data['check'] == 'yes' else False
                    
                    subscription_updates.append({
                        'name': index_data['name'],
                        'user_checked': user_checked,
                        'user_notes': index_data.get('notes', '')
                    })
            
            # Update the markdown file
            success = self.sm.update_llm_notes(subscription_updates)
            
            if success:
                # Return success response
                self.send_response(200)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                self.wfile.write(b'{"success": true}')
            else:
                raise Exception("Failed to update llm_notes.md file")
                
        except Exception as e:
            print(f"Error saving review: {e}")
            # Return error response
            self.send_response(500)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            error_msg = json.dumps({"success": False, "error": str(e)})
            self.wfile.write(error_msg.encode())

    def start_gmail_auth(self):
        """Redirect to Gmail OAuth"""
        auth_url = self.sm.get_gmail_auth_url()
        self.send_response(302)
        self.send_header('Location', auth_url)
        self.end_headers()

    def handle_subscription_update(self):
        """Handle subscription update requests"""
        try:
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length).decode('utf-8')
            data = json.loads(post_data)
            
            subscription_id = data.get('id')
            
            if not subscription_id:
                self.send_response(400)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                response = {'success': False, 'error': 'Missing subscription id'}
                self.wfile.write(json.dumps(response).encode())
                return
            
            # Check if this is a single field update or bulk update
            if 'field' in data and 'value' in data:
                # Single field update (original behavior)
                field = data.get('field')
                value = data.get('value')
                success = self.sm.update_subscription(subscription_id, field, value)
            else:
                # Bulk update - update multiple fields
                success = True
                website_url_updated = False
                for field in ['name', 'cost', 'currency', 'billing_cycle', 'notes', 'website_url']:
                    if field in data:
                        value = data[field]
                        # Skip empty values for optional fields
                        if field == 'name' and not value:
                            continue  # Name is required, don't update if empty
                        field_success = self.sm.update_subscription(subscription_id, field, value)
                        success = success and field_success
                        # Track if website_url was updated (logo fetch already triggered in update_subscription)
                        if field == 'website_url' and value:
                            website_url_updated = True
            
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            response = {'success': True, 'message': 'Subscription updated successfully'}
            self.wfile.write(json.dumps(response).encode())
            
        except ValueError as e:
            self.send_response(400)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            response = {'success': False, 'error': str(e)}
            self.wfile.write(json.dumps(response).encode())
        except Exception as e:
            self.send_response(500)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            response = {'success': False, 'error': f'Server error: {str(e)}'}
            self.wfile.write(json.dumps(response).encode())

    def handle_subscription_create(self):
        """Handle subscription creation requests"""
        try:
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length).decode('utf-8')
            data = json.loads(post_data) if post_data.strip() else {}
            
            # Create the subscription
            new_subscription = self.sm.create_subscription(data)
            
            if new_subscription:
                self.send_response(201)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                response = {
                    'success': True, 
                    'message': 'Subscription created successfully',
                    'subscription': new_subscription
                }
                self.wfile.write(json.dumps(response).encode())
            else:
                self.send_response(500)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                response = {'success': False, 'error': 'Failed to create subscription'}
                self.wfile.write(json.dumps(response).encode())
                
        except ValueError as e:
            self.send_response(400)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            response = {'success': False, 'error': str(e)}
            self.wfile.write(json.dumps(response).encode())
        except Exception as e:
            self.send_response(500)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            response = {'success': False, 'error': f'Server error: {str(e)}'}
            self.wfile.write(json.dumps(response).encode())

    # REMOVED: handle_subscriptions_list() method - no longer needed after embedding data fix
    # The manage view now embeds subscription data directly in HTML instead of using AJAX

    def handle_subscription_delete(self):
        """Handle subscription deletion requests"""
        try:
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length).decode('utf-8')
            data = json.loads(post_data)
            
            subscription_id = data.get('id')
            
            if not subscription_id:
                self.send_response(400)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                response = {'success': False, 'error': 'Missing required field: id'}
                self.wfile.write(json.dumps(response).encode())
                return
            
            # Delete the subscription
            success = self.sm.delete_subscription(subscription_id)
            
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            response = {'success': True, 'message': 'Subscription deleted successfully'}
            self.wfile.write(json.dumps(response).encode())
            
        except ValueError as e:
            self.send_response(400)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            response = {'success': False, 'error': str(e)}
            self.wfile.write(json.dumps(response).encode())
        except Exception as e:
            self.send_response(500)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            response = {'success': False, 'error': f'Server error: {str(e)}'}
            self.wfile.write(json.dumps(response).encode())

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
        
        refresh_token = token_data.get('refresh_token', '')
        if not refresh_token:
            raise Exception("No refresh token received from Google OAuth")
            
        cursor.execute('''
            INSERT OR REPLACE INTO connections 
            (email, access_token, refresh_token, token_expiry)
            VALUES (?, ?, ?, ?)
        ''', (
            profile['emailAddress'],
            token_data['access_token'],
            refresh_token,
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
        
        self.send_json_response(response_data)

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

    def api_fetch_email_content(self, request_data):
        """Selectively fetch email content for specific messages"""
        # Get active connection
        connections = self.sm.get_connections()
        if not connections:
            return {
                "success": False,
                "error": "No Gmail connection found",
                "data": None
            }
        
        email = connections[0]['email']
        
        # Parse request parameters
        email_ids = request_data.get('email_ids', [])
        sender_domains = request_data.get('sender_domains', [])
        date_from = request_data.get('date_from')  # YYYY-MM-DD format
        date_to = request_data.get('date_to')      # YYYY-MM-DD format
        limit = request_data.get('limit', 50)      # Default limit
        
        # Validate limit
        if limit > 200:
            limit = 200  # Cap at 200 for safety
        
        try:
            # Find emails to fetch content for
            conn = sqlite3.connect(self.sm.db_path)
            cursor = conn.cursor()
            
            # Build query to find emails that need content fetching
            query_parts = ["content_fetched = 0 OR content_fetched IS NULL"]
            params = []
            
            if email_ids:
                placeholders = ','.join('?' * len(email_ids))
                query_parts.append(f"gmail_message_id IN ({placeholders})")
                params.extend(email_ids)
            
            if sender_domains:
                domain_conditions = []
                for domain in sender_domains:
                    domain_conditions.append("sender_domain = ?")
                    params.append(domain.lower())
                query_parts.append(f"({' OR '.join(domain_conditions)})")
            
            if date_from:
                query_parts.append("DATE(received_at) >= ?")
                params.append(date_from)
            
            if date_to:
                query_parts.append("DATE(received_at) <= ?")
                params.append(date_to)
            
            # Execute query
            query = f"""
                SELECT gmail_message_id, subject, sender, sender_domain, received_at 
                FROM processed_emails 
                WHERE {' AND '.join(query_parts)}
                ORDER BY received_at DESC 
                LIMIT ?
            """
            params.append(limit)
            
            cursor.execute(query, params)
            emails_to_fetch = cursor.fetchall()
            
            if not emails_to_fetch:
                conn.close()
                return {
                    "success": True,
                    "message": "No emails found matching criteria or all already have content",
                    "data": {
                        "fetched": 0,
                        "updated": 0,
                        "errors": 0
                    }
                }
            
            # Fetch content for each email
            access_token = self.sm.get_valid_access_token(email)
            headers = {'Authorization': f'Bearer {access_token}'}
            
            fetched_count = 0
            updated_count = 0
            error_count = 0
            
            for email_data in emails_to_fetch:
                gmail_message_id, subject, sender, sender_domain, received_at = email_data
                
                try:
                    # Fetch full email content
                    url = f'https://gmail.googleapis.com/gmail/v1/users/me/messages/{gmail_message_id}?format=full'
                    response = requests.get(url, headers=headers)
                    
                    if response.status_code == 200:
                        msg_data = response.json()
                        
                        # Extract content from payload
                        content = self.extract_email_content(msg_data.get('payload', {}))
                        
                        # Update database with content
                        cursor.execute('''
                            UPDATE processed_emails 
                            SET content = ?, content_fetched = 1
                            WHERE gmail_message_id = ?
                        ''', (content, gmail_message_id))
                        
                        fetched_count += 1
                        updated_count += 1
                        
                    else:
                        print(f"Failed to fetch content for {gmail_message_id}: {response.status_code}")
                        error_count += 1
                    
                    # Small delay to be nice to the API
                    time.sleep(0.1)
                    
                except Exception as e:
                    print(f"Error fetching content for {gmail_message_id}: {e}")
                    error_count += 1
            
            conn.commit()
            conn.close()
            
            return {
                "success": True,
                "message": f"Fetched content for {fetched_count} emails",
                "data": {
                    "fetched": fetched_count,
                    "updated": updated_count,
                    "errors": error_count,
                    "total_candidates": len(emails_to_fetch)
                }
            }
            
        except Exception as e:
            if 'conn' in locals():
                conn.close()
            return {
                "success": False,
                "error": f"Failed to fetch email content: {str(e)}",
                "data": None
            }

    def extract_email_content(self, payload):
        """Extract readable text content from Gmail API payload"""
        content_parts = []
        
        def extract_parts(part):
            """Recursively extract content from message parts"""
            mime_type = part.get('mimeType', '')
            
            # Handle text parts
            if mime_type in ['text/plain', 'text/html']:
                body = part.get('body', {}).get('data')
                if body:
                    import base64
                    try:
                        # Decode base64url encoded content
                        decoded = base64.urlsafe_b64decode(body + '==')  # Add padding if needed
                        text = decoded.decode('utf-8', errors='replace')
                        
                        # For HTML, we could strip tags, but keep it simple for now
                        if mime_type == 'text/html':
                            # Basic HTML tag removal (simple approach)
                            import re
                            text = re.sub(r'<[^>]+>', '', text)
                            text = text.replace('&nbsp;', ' ').replace('&amp;', '&').replace('&lt;', '<').replace('&gt;', '>')
                        
                        content_parts.append(text.strip())
                    except Exception as e:
                        print(f"Failed to decode email part: {e}")
            
            # Handle multipart - recursively process parts
            elif 'parts' in part:
                for subpart in part['parts']:
                    extract_parts(subpart)
        
        extract_parts(payload)
        
        # Join all text parts
        full_content = '\n\n'.join(content_parts)
        
        # Limit content size (e.g., to 50KB) to avoid huge database entries
        if len(full_content) > 50000:
            full_content = full_content[:50000] + "\n\n[Content truncated at 50KB]"
        
        return full_content if full_content.strip() else "[No readable content found]"

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
        self.send_json_response(result, status=200 if result["success"] else 400)

    def handle_api_fetch_content(self):
        """Handle API fetch email content request (returns JSON)"""
        # Get request body
        content_length = int(self.headers.get('Content-Length', 0))
        if content_length > 0:
            request_body = self.rfile.read(content_length).decode('utf-8')
            try:
                request_data = json.loads(request_body)
            except json.JSONDecodeError:
                self.send_error(400, "Invalid JSON in request body")
                return
        else:
            request_data = {}
        
        result = self.api_fetch_email_content(request_data)
        self.send_json_response(result, status=200 if result["success"] else 400)



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
        return SimpleWebServer(subscription_manager, job_manager, *args, **kwargs)
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