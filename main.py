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
from contextlib import contextmanager

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


    def get_connections(self):
        """Get all Gmail connections with timeout handling"""
        try:
            with self.db_connection(timeout=5.0) as conn:
                cursor = conn.cursor()
                cursor.execute('SELECT * FROM connections ORDER BY created_at DESC')
                columns = [desc[0] for desc in cursor.description]
                results = [dict(zip(columns, row)) for row in cursor.fetchall()]
            return results
        except sqlite3.OperationalError as e:
            if "database is locked" in str(e).lower() or "timeout" in str(e).lower():
                print(f"Database timeout/lock in get_connections: {e}")
                return []  # Return empty list to allow page to render
            raise

    def get_subscriptions(self):
        """Get all subscriptions with timeout handling"""
        try:
            with self.db_connection(timeout=5.0) as conn:
                cursor = conn.cursor()
                cursor.execute('SELECT * FROM subscriptions ORDER BY created_at DESC')
                columns = [desc[0] for desc in cursor.description]
                results = [dict(zip(columns, row)) for row in cursor.fetchall()]
            return results
        except sqlite3.OperationalError as e:
            if "database is locked" in str(e).lower() or "timeout" in str(e).lower():
                print(f"Database timeout/lock in get_subscriptions: {e}")
                return []  # Return empty list to allow page to render
            raise  # Re-raise other operational errors

    def get_email_count(self):
        """Get total count of processed emails with timeout handling"""
        try:
            with self.db_connection(timeout=5.0) as conn:
                cursor = conn.cursor()
                cursor.execute('SELECT COUNT(*) FROM processed_emails')
                count = cursor.fetchone()[0]
            return count
        except sqlite3.OperationalError as e:
            if "database is locked" in str(e).lower() or "timeout" in str(e).lower():
                print(f"Database timeout/lock in get_email_count: {e}")
                return 0  # Return 0 to allow page to render
            raise

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

    def get_unique_domains(self):
        """Get list of unique sender domains with email counts"""
        with self.db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT sender_domain, COUNT(*) as count 
                FROM processed_emails 
                WHERE sender_domain IS NOT NULL AND sender_domain != ''
                GROUP BY sender_domain 
                ORDER BY count DESC
            ''')
            domains = [{'domain': row[0], 'count': row[1]} for row in cursor.fetchall()]
        return domains

    def reset_database(self):
        """Clear all data and force fresh authentication"""
        with self.db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('DELETE FROM processed_emails')
            cursor.execute('DELETE FROM connections')
            conn.commit()
        print("Database reset complete - fresh authentication required")
    
    def parse_llm_notes(self):
        """Parse llm_notes.md file and extract subscription data for review UI"""
        try:
            with open('resources/llm_notes.md', 'r') as f:
                content = f.read()
        except FileNotFoundError:
            return []
        
        subscriptions = []
        lines = content.split('\n')
        current_subscription = None
        
        for line in lines:
            line = line.strip()
            
            # Look for subscription names (lines starting with **)
            if line.startswith('**') and line.endswith('**'):
                if current_subscription:
                    subscriptions.append(current_subscription)
                
                # Extract name between ** markers
                name = line[2:-2].strip()
                current_subscription = {
                    'name': name,
                    'user_checked': None,
                    'user_notes': ''
                }
            
            # Look for user check status
            elif line.startswith('User Check:') and current_subscription:
                if '[x] Yes' in line:
                    current_subscription['user_checked'] = True
                elif '[x] No' in line:
                    current_subscription['user_checked'] = False
                # else remains None (unchecked)
            
            # Look for user notes
            elif line.startswith('User Notes:') and current_subscription:
                # Extract text after "User Notes: "
                notes_text = line[12:].strip()
                current_subscription['user_notes'] = notes_text
        
        # Don't forget the last subscription
        if current_subscription:
            subscriptions.append(current_subscription)
        
        return subscriptions
    
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
                cost = float(sub.get('cost', 0) or 0)
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
    
    def get_manage_content(self):
        """Generate content for manage view with all data"""
        subscriptions = self.sm.get_subscriptions()
        
        # Calculate totals
        monthly_total = 0
        yearly_total = 0
        active_count = 0
        
        for sub in subscriptions:
            cost = float(sub.get('cost', 0) or 0)
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
        
        # Generate subscription rows
        subscription_rows = ""
        for sub in subscriptions:
            subscription_rows += f'''
            <tr data-subscription-id="{sub.get('id', '')}">
                <td class="editable-cell" contenteditable="true" data-field="name">{sub['name']}</td>
                <td class="editable-cell" contenteditable="true" data-field="category">{sub.get('category', '') or ''}</td>
                <td><span class="status-badge status-active">{sub.get('status', 'active')}</span></td>
                <td>
                    <select name="auto_renewing" class="editable-select">
                        <option value="1" {'selected' if sub.get('auto_renewing') else ''}>Yes</option>
                        <option value="0" {'selected' if not sub.get('auto_renewing') else ''}>No</option>
                    </select>
                </td>
                <td class="editable-cell" contenteditable="true" data-field="cost">{sub.get('cost', '') or ''}</td>
                <td class="editable-cell" contenteditable="true" data-field="billing_cycle">{sub.get('billing_cycle', '') or ''}</td>
                <td style="text-align: center;">
                    <button class="expand-btn" data-subscription-id="{sub.get('id', '')}">+</button>
                </td>
            </tr>'''
        
        return self.render_template('views/manage.html',
            monthly_total=f"{monthly_total:.2f}",
            yearly_total=f"{yearly_total:.2f}",
            active_count=str(active_count),
            subscription_rows=subscription_rows
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

    def render_subscriptions_table(self, subscriptions):
        """Render subscriptions table for home view"""
        if not subscriptions:
            return '''
            <div style="text-align: center; padding: 60px;">
                <h3>No Subscriptions Yet</h3>
                <p>Start by adding subscriptions manually or connecting Gmail to discover them</p>
                <a href="javascript:loadView('manage')" style="text-decoration: none;">
                    <button class="primary">Manage Subscriptions</button>
                </a>
            </div>
            '''
        
        table_html = '''
        <table>
            <thead>
                <tr>
                    <th>Name</th>
                    <th>Category</th>
                    <th>Cost</th>
                    <th>Billing Cycle</th>
                    <th>Status</th>
                </tr>
            </thead>
            <tbody>
        '''
        
        for sub in subscriptions:
            status_class = f"status-{sub.get('status', 'active').lower()}"
            table_html += f'''
            <tr>
                <td>{sub['name']}</td>
                <td>{sub.get('category', '') or '—'}</td>
                <td>${sub.get('cost', '0') or '0'}</td>
                <td>{sub.get('billing_cycle', '') or '—'}</td>
                <td><span class="status-badge {status_class}">{sub.get('status', 'active')}</span></td>
            </tr>
            '''
        
        table_html += '</tbody></table>'
        return table_html

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
        """Serve two-panel dashboard"""
        connections = self.sm.get_connections()
        subscriptions = self.sm.get_subscriptions()
        email_count = self.sm.get_email_count()
        connected = len(connections) > 0
        
        # Check for fetch results in URL params
        url = urlparse(self.path)
        params = parse_qs(url.query)
        fetch_results = params.get('fetch_results', [None])[0]
        
        # Prepare connection content
        if connected:
            connection_style = "display: flex; flex-direction: column; justify-content: space-between; height: 100%;"
            connection_content = f'''
                <div style="text-align: right; padding-top: 10px;">
                    <div>
                        <a href="/auth/gmail" style="text-decoration: none; margin-right: 15px;">
                            <button style="border: none; background: none; color: #666; cursor: pointer; padding: 0; font-size: 14px; font-family: 'SF Mono', monospace;">change email</button>
                        </a>
                        <form action="/fetch" method="post" style="display: inline;">
                            <button type="submit" style="border: none; background: none; color: #666; cursor: pointer; padding: 0; font-size: 14px; font-family: 'SF Mono', monospace;">fetch emails</button>
                        </form>
                    </div>
                    <a href="/?view=notepad" style="text-decoration: none;">
                        <div style="color: #666; font-size: 14px; margin-top: 20px; cursor: pointer;">notepad</div>
                    </a>
                </div>
                <div style="text-align: right;">
                    <div style="color: #666; font-size: 14px; margin-bottom: 10px;">connected:</div>
                    <div class="status" style="color: #008000;">{connections[0]["email"]}</div>
                </div>
                '''
        else:
            connection_style = ""
            connection_content = '''
                <div style="text-align: right; padding-top: 10px;">
                    <a href="/auth/gmail" style="text-decoration: none;">
                        <button style="border: none; background: none; color: #666; cursor: pointer; padding: 0; font-size: 14px; font-family: 'SF Mono', monospace;">connect gmail</button>
                    </a>
                </div>
                '''
        
        # Render template
        html = self.render_template('dashboard.html',
            connection_style=connection_style,
            connection_content=connection_content,
            right_panel_content=self.render_right_panel(params)
        )
        
        self.send_response(200)
        self.send_header('Content-type', 'text/html')
        self.end_headers()
        self.wfile.write(html.encode())

    def render_right_panel(self, params):
        """Render right panel content based on view parameter"""
        view = params.get('view', ['subscriptions'])[0]
        
        if view == 'emails':
            return self.render_emails_view()
        elif view == 'notepad':
            return self.render_notepad_view()
        elif view == 'review':
            return self.render_review_view()
        elif view == 'manage':
            return self.render_manage_view()
        else:
            return self.render_subscriptions_view()
    
    def render_subscriptions_view(self):
        """Render subscriptions table"""
        subscriptions = self.sm.get_subscriptions()
        return self.render_subscriptions_table(subscriptions)
    
    def render_emails_view(self):
        """Render emails table with filters, sorting and enhanced fields"""
        # Get filter parameters from URL
        url = urlparse(self.path)
        params = parse_qs(url.query)
        
        # Parse filters
        filters = {}
        if params.get('domain'):
            filters['domain'] = params['domain'][0]
        if params.get('has_content'):
            filters['has_content'] = params['has_content'][0] == 'true'
        
        # Parse sorting parameters
        sort_by = params.get('sort', [None])[0]
        sort_dir = params.get('dir', ['desc'])[0]
        
        # Parse pagination parameters
        page = int(params.get('page', [1])[0])
        page_size = 50
        offset = (page - 1) * page_size
        
        # Get filtered and sorted emails with pagination
        data = self.sm.get_processed_emails(filters=filters, limit=page_size, offset=offset, 
                                          sort_by=sort_by, sort_dir=sort_dir)
        emails = data['emails']
        total = data['total']
        
        # Get unique domains for filter dropdown
        domains = self.sm.get_unique_domains()
        
        # Build domain filter options
        domain_options = '<option value="">all domains</option>'
        for domain_info in domains[:50]:  # Limit to top 50 domains
            selected = 'selected' if filters.get('domain') == domain_info['domain'] else ''
            domain_options += f'<option value="{domain_info["domain"]}" {selected}>{domain_info["domain"]} ({domain_info["count"]})</option>'
        
        # Build email rows with more fields
        email_rows = ""
        for email in emails:  # No slicing needed - we loaded exactly what we want
            # Check if email has content
            has_content = bool(email.get('content') and email['content'].strip())
            content_indicator = 'Y' if has_content else 'N'
            content_style = 'color: #008000; font-weight: bold;' if has_content else 'color: #999;'
            
            # Truncate subject for display
            subject = email.get('subject', '')
            if len(subject) > 60:
                subject = subject[:57] + '...'
            
            # Format sender
            sender = email.get('sender', '')
            if len(sender) > 40:
                sender = sender[:37] + '...'
            
            email_rows += f"""
            <tr>
                <td style="font-size: 11px;">{email.get('sender_domain', '')}</td>
                <td style="font-size: 11px;">{sender}</td>
                <td style="font-size: 11px;">{subject}</td>
                <td style="text-align: center; {content_style}">{content_indicator}</td>
                <td style="font-size: 11px;">{self.format_datetime_nz(email['received_at']) if email['received_at'] else 'N/A'}</td>
            </tr>
            """
        
        # Set default email rows if empty
        if not email_rows:
            email_rows = '<tr><td colspan="5" style="text-align: center; padding: 20px; color: #666;">No emails found matching filters</td></tr>'
        
        # Current filter status
        filter_status = []
        if filters.get('domain'):
            filter_status.append(f"domain: {filters['domain']}")
        if filters.get('has_content') is not None:
            filter_status.append(f"content: {'yes' if filters['has_content'] else 'no'}")
        filter_text = f" (filtered by {', '.join(filter_status)})" if filter_status else ""
        
        # Prepare template variables
        has_content_true_selected = 'selected' if filters.get('has_content') is True else ''
        has_content_false_selected = 'selected' if filters.get('has_content') is False else ''
        
        # Calculate pagination variables
        total_pages = (total + page_size - 1) // page_size  # Ceiling division
        prev_page = max(1, page - 1) if page > 1 else None
        next_page = page + 1 if page < total_pages else None
        start_item = offset + 1
        end_item = min(offset + page_size, total)
        
        # Build query string for preserving filters and sorting in pagination links
        query_params = []
        if filters.get('domain'):
            query_params.append(f"domain={filters['domain']}")
        if filters.get('has_content') is not None:
            query_params.append(f"has_content={'true' if filters['has_content'] else 'false'}")
        if sort_by:
            query_params.append(f"sort={sort_by}")
            query_params.append(f"dir={sort_dir}")
        query_string = '&'.join(query_params)
        query_suffix = '&' + query_string if query_string else ''
        
        # Generate pagination links
        if prev_page:
            prev_link = f'<a href="/?view=emails&page={prev_page}{query_suffix}" style="text-decoration: none; color: #666; font-size: 12px; margin-right: 10px;">←</a>'
        else:
            prev_link = '<span style="color: #ccc; font-size: 12px; margin-right: 10px;">←</span>'
            
        if next_page:
            next_link = f'<a href="/?view=emails&page={next_page}{query_suffix}" style="text-decoration: none; color: #666; font-size: 12px; margin-left: 10px;">→</a>'
        else:
            next_link = '<span style="color: #ccc; font-size: 12px; margin-left: 10px;">→</span>'
        
        # Generate sortable column headers
        def generate_sort_header(column_name, display_name, current_sort, current_dir):
            """Generate clickable header with sort indicators"""
            if current_sort == column_name:
                # Currently sorted by this column - show indicator and toggle direction
                indicator = ' ↑' if current_dir == 'asc' else ' ↓'
                new_dir = 'desc' if current_dir == 'asc' else 'asc'
            else:
                # Not currently sorted by this column - default to desc, no indicator
                indicator = ''
                new_dir = 'desc'
            
            # Build URL preserving filters
            sort_params = query_params.copy() if query_params else []
            # Remove existing sort params if any
            sort_params = [p for p in sort_params if not (p.startswith('sort=') or p.startswith('dir='))]
            sort_params.extend([f'sort={column_name}', f'dir={new_dir}'])
            sort_query = '&'.join(sort_params)
            sort_url = f'/?view=emails&{sort_query}' if sort_query else f'/?view=emails&sort={column_name}&dir={new_dir}'
            
            return f'<a href="{sort_url}" style="text-decoration: none; color: #333; font-weight: bold;">{display_name}{indicator}</a>'
        
        column_headers = {
            'domain_header': generate_sort_header('domain', 'Domain', sort_by, sort_dir),
            'sender_header': generate_sort_header('sender', 'Sender', sort_by, sort_dir),
            'subject_header': generate_sort_header('subject', 'Subject', sort_by, sort_dir),
            'content_header': generate_sort_header('content', 'Content', sort_by, sort_dir),
            'received_header': generate_sort_header('received', 'Received', sort_by, sort_dir)
        }

        return self.render_template('emails_view.html',
            total=total,
            filter_text=filter_text,
            domain_options=domain_options,
            has_content_true_selected=has_content_true_selected,
            has_content_false_selected=has_content_false_selected,
            email_rows=email_rows,
            # Pagination variables
            current_page=page,
            total_pages=total_pages,
            start_item=start_item,
            end_item=end_item,
            prev_link=prev_link,
            next_link=next_link,
            # Sort headers
            **column_headers
        )
    
    def render_subscriptions_table(self, subscriptions):
        if not subscriptions:
            return self.render_template('empty_subscriptions.html')
        
        subscription_rows = ""
        for sub in subscriptions:
            subscription_rows += f"""<tr>
                <td>{sub['name']}</td>
                <td>{sub['status']}</td>
                <td>{'Yes' if sub.get('auto_renewing') else 'No'}</td>
                <td>{sub.get('cost', '') or ''}</td>
                <td>{sub.get('billing_cycle', '') or ''}</td>
                <td>{sub.get('next_billing_date', '') or ''}</td>
            </tr>"""
        
        return self.render_template('subscriptions_table.html',
            subscription_rows=subscription_rows
        )

    def _parse_notepad_content(self):
        """Parse notepad markdown content into structured data"""
        subscriptions = []
        other_notes = []
        
        # Ensure directory exists
        os.makedirs('resources', exist_ok=True)
        
        try:
            with open('resources/notepad.md', 'r') as f:
                content = f.read()
                
            current_section = None
            for line in content.split('\n'):
                line = line.strip()
                if line == '## Subscriptions':
                    current_section = 'subscriptions'
                elif line == '## Other Notes':
                    current_section = 'other_notes'
                elif line.startswith('- ') and current_section:
                    item = line[2:]  # Remove '- ' prefix
                    if current_section == 'subscriptions':
                        subscriptions.append(item)
                    elif current_section == 'other_notes':
                        other_notes.append(item)
        except FileNotFoundError:
            # File doesn't exist yet, create it with default structure
            default_content = "## Subscriptions\n\n## Other Notes\n"
            with open('resources/notepad.md', 'w') as f:
                f.write(default_content)
        
        return subscriptions, other_notes

    def _generate_notepad_items_html(self, notes, input_name):
        """Generate HTML for notepad items with proper escaping"""
        import html
        items = []
        for note in notes:
            # Calculate initial rows based on content length
            lines = note.count('\n') + 1
            # Also account for wrapped lines (rough estimate)
            estimated_rows = max(1, lines, len(note) // 80)
            
            items.append(f'''
                <div class="note-item">
                    <span class="bullet">•</span>
                    <textarea name="{input_name}" rows="{estimated_rows}" 
                        oninput="this.style.height='auto';this.style.height=this.scrollHeight+'px'"
                        onkeydown="if(event.key==='Enter' && !event.shiftKey){{event.preventDefault();addNote('{input_name.replace('_notes', '-notes') if '_notes' in input_name else input_name}')}}">{html.escape(note)}</textarea>
                </div>''')
        return ''.join(items)

    def render_notepad_view(self):
        """Render notepad view for right panel"""
        subscriptions, other_notes = self._parse_notepad_content()
        
        subscription_items = self._generate_notepad_items_html(subscriptions, 'subscriptions')
        other_notes_items = self._generate_notepad_items_html(other_notes, 'other_notes')
        
        return self.render_template('notepad_view.html', 
            subscription_items=subscription_items,
            other_notes_items=other_notes_items
        )
    
    def render_review_view(self):
        """Render review view for right panel"""
        # Parse llm_notes.md and get subscription data
        subscriptions = self.sm.parse_llm_notes()
        
        # Generate HTML for the subscription checklist
        checklist_html = ""
        for i, sub in enumerate(subscriptions):
            checked_yes = 'checked' if sub['user_checked'] is True else ''
            checked_no = 'checked' if sub['user_checked'] is False else ''
            
            # Escape HTML special characters in name and notes
            escaped_name = sub['name'].replace('"', '&quot;').replace('<', '&lt;').replace('>', '&gt;')
            escaped_notes = sub['user_notes'].replace('"', '&quot;').replace('<', '&lt;').replace('>', '&gt;')
            
            # Determine if notes should be visible (if there's existing content)
            notes_visible = 'block' if escaped_notes else 'none'
            plus_visible = 'inline' if not escaped_notes else 'none'
            
            # Determine completion status for filtering
            is_completed = 'true' if sub['user_checked'] is not None else 'false'
            
            checklist_html += f'''
            <div class="subscription-item" data-completed="{is_completed}" style="margin-bottom: 0; padding: 15px; border-bottom: 1px solid #e0e0e0;">
                <div style="display: grid; grid-template-columns: 40% 60%; align-items: center; margin-bottom: 10px;">
                    <span style="font-size: 12px; font-weight: 400; color: #333;">{escaped_name}</span>
                    <div style="display: flex; gap: 15px;">
                        <label style="font-size: 12px; color: #666;">
                            <input type="radio" name="check_{i}" value="yes" {checked_yes}> Yes
                        </label>
                        <label style="font-size: 12px; color: #666;">
                            <input type="radio" name="check_{i}" value="no" {checked_no}> No
                        </label>
                    </div>
                </div>
                <div style="margin-top: 8px;">
                    <button type="button" id="add-note-btn-{i}" onclick="toggleNotes({i})" 
                            style="border: none; background: none; color: #666; cursor: pointer; font-size: 14px; font-family: inherit; padding: 0; display: {plus_visible};">+</button>
                    <div id="notes-display-{i}" style="font-size: 12px; color: #666; font-style: italic; display: {'block' if escaped_notes else 'none'};">
                        <span style="color: #666;">notes: </span>{escaped_notes}
                    </div>
                    <div id="notes-input-wrapper-{i}" style="display: none; align-items: baseline;">
                        <span style="font-size: 12px; color: #666; font-style: italic;">notes: </span><input type="text" id="notes-input-{i}" name="notes_{i}" value="{escaped_notes}" 
                               placeholder="" 
                               style="border: none; font-size: 12px; font-family: inherit; color: #666; font-style: italic; background: transparent; outline: none; flex: 1;">
                    </div>
                </div>
                <input type="hidden" name="name_{i}" value="{escaped_name}">
            </div>
            '''
        
        return self.render_template('review_view.html', 
            checklist_content=checklist_html,
            subscription_count=len(subscriptions)
        )
    
    def render_manage_view(self):
        """Render manage subscriptions view for right panel"""
        subscriptions = self.sm.get_subscriptions()
        
        # Generate editable subscription rows
        subscription_rows = ""
        for sub in subscriptions:
            # Generate row with editable fields
            subscription_rows += f"""<tr data-subscription-id="{sub.get('id', '')}">
                <td class="editable-cell" contenteditable="true" data-field="name">{sub['name']}</td>
                <td class="editable-cell" contenteditable="true" data-field="category">{sub.get('category', '') or ''}</td>
                <td class="editable-cell" contenteditable="true" data-field="status">{sub.get('status', '') or ''}</td>
                <td>
                    <select name="auto_renewing" class="editable-select">
                        <option value="1" {'selected' if sub.get('auto_renewing') else ''}>Yes</option>
                        <option value="0" {'selected' if not sub.get('auto_renewing') else ''}>No</option>
                    </select>
                </td>
                <td class="editable-cell" contenteditable="true" data-field="cost">{sub.get('cost', '') or ''}</td>
                <td class="editable-cell" contenteditable="true" data-field="billing_cycle">{sub.get('billing_cycle', '') or ''}</td>
                <td style="text-align: center;">
                    <button class="expand-btn" data-subscription-id="{sub.get('id', '')}">+</button>
                </td>
            </tr>"""
        
        # Add the "add new" row at the bottom
        subscription_rows += """
            <tr class="add-row">
                <td colspan="7">
                    <button class="add-btn">+</button>
                </td>
            </tr>
        """
        
        return self.render_template('manage_view.html',
            subscription_rows=subscription_rows
        )

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