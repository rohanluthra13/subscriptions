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
import html
from datetime import datetime, timedelta
from urllib.parse import urlencode, parse_qs, urlparse
from http.server import HTTPServer, BaseHTTPRequestHandler
from socketserver import ThreadingMixIn
from dotenv import load_dotenv
from email.utils import parsedate_to_datetime
import time
from contextlib import contextmanager

# Import utility modules
from utils.cost import CostUtils
from utils.favicon import fetch_favicon_for_domain
from utils.decorators import handle_db_errors
from database.schema import initialize_database
from gmail.auth import GmailAuthManager
from gmail.content import EmailContentProcessor

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
        
        # Initialize Gmail auth manager
        self.gmail_auth = GmailAuthManager(
            client_id=self.google_client_id,
            client_secret=self.google_client_secret,
            redirect_uri=self.redirect_uri,
            db_path=self.db_path
        )
        
        # Initialize email content processor
        self.email_processor = EmailContentProcessor(self)
    
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
        initialize_database(self.db_path)

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
        return self.gmail_auth.get_auth_url()

    def exchange_code_for_tokens(self, code: str):
        """Exchange OAuth code for access tokens"""
        return self.gmail_auth.exchange_code_for_tokens(code)

    def refresh_access_token(self, refresh_token: str):
        """Refresh expired access token"""
        return self.gmail_auth.refresh_access_token(refresh_token)

    def get_valid_access_token(self, email: str) -> str:
        """Get valid access token, refreshing if necessary"""
        return self.gmail_auth.get_valid_access_token(email)

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
        return self.email_processor.process_batch_simple(batch, email, cursor)


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
    def get_subscription_by_id(self, subscription_id):
        """Get a single subscription by ID"""
        with self.db_connection(timeout=5.0) as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM subscriptions WHERE id = ?', (subscription_id,))
            columns = [desc[0] for desc in cursor.description]
            row = cursor.fetchone()
            if row:
                return dict(zip(columns, row))
            return None

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

    @handle_db_errors(default_return=[])
    def get_categories(self):
        """Get all categories ordered by standard categories first, then alphabetically"""
        with self.db_connection(timeout=5.0) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT name, is_standard, created_at
                FROM categories 
                ORDER BY is_standard DESC, name ASC
            ''')
            columns = [desc[0] for desc in cursor.description]
            results = [dict(zip(columns, row)) for row in cursor.fetchall()]
        return results

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

    def _generate_subscription_card_html(self, subscription):
        """Generate HTML for a single subscription card.
        Private method to avoid code duplication between get_manage_content
        and get_subscription_cards_fragment.
        """
        # Use CostUtils for consistent cost display formatting
        cost_display = CostUtils.format_cost_for_display(subscription.get('cost'))

        # Get billing cycle - show ? if empty
        cycle = subscription.get('billing_cycle', '')
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
        sub_id = subscription.get('id', '')
        # Escape user-provided data to prevent XSS
        safe_name = html.escape(subscription.get('name', ''))

        logo_html = ''
        if subscription.get('logo_data'):
            logo_html = f'<img class="card-logo" src="/logo/{sub_id}" alt="{safe_name} logo">'

        return f'''
        <div class="subscription-card" data-subscription-id="{sub_id}">
            <div class="card-left">
                {logo_html}
                <div class="card-name">{safe_name}</div>
            </div>
            <div class="card-details">
                {details_display}
            </div>
        </div>'''

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
        elif path == '/api/fragment/subscription-cards':
            self.serve_subscription_cards_fragment()
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
        elif path == '/api/subscription/new':
            # Handle GET /api/subscription/new - returns HTML form for new subscription
            self.handle_subscription_form_new()
        elif path.startswith('/api/subscription/') and path.endswith('/edit') and len(path.split('/')) == 5:
            # Handle GET /api/subscription/{id}/edit - returns populated HTML form
            subscription_id = path.split('/')[3]  # Get ID from /api/subscription/{id}/edit
            self.handle_subscription_form_edit(subscription_id)
        elif path.startswith('/api/subscriptions/') and len(path.split('/')) == 4:
            # Handle GET /api/subscriptions/{id}
            subscription_id = path.split('/')[-1]
            self.handle_subscription_get(subscription_id)
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
            
            # Generate bullet list content with consistent cost formatting
            monthly_display = CostUtils.format_cost_for_display(monthly_total)
            yearly_display = CostUtils.format_cost_for_display(yearly_total)
            
            content = f'''
            <div style="padding: 60px 0;">
                <h2>what am i paying for</h2>
                <ul style="font-size: 14px; line-height: 1.6; list-style: none; padding: 0; margin-top: 30px;">
                    <li style="margin-bottom: 12px;">• {active_count} subscriptions</li>
                    <li style="margin-bottom: 12px;">• {monthly_display} per month</li>
                    <li style="margin-bottom: 12px;">• {yearly_display} per year</li>
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
        categories = self.sm.get_categories()
        
        # Prepare JSON-safe data for embedding (remove BLOB data for JSON serialization)
        json_safe_subscriptions = [
            self._sanitize_subscription_for_json(sub) 
            for sub in subscriptions
        ]
        
        subscriptions_json = json.dumps(json_safe_subscriptions)
        categories_json = json.dumps(categories)
        
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
                subscription_cards += self._generate_subscription_card_html(sub)
        
        return self.render_template('views/manage.html',
            subscription_cards=subscription_cards,
            embedded_subscriptions=subscriptions_json,
            embedded_categories=categories_json
        )
    
    def serve_subscription_cards_fragment(self):
        """Return just the subscription cards HTML fragment for AJAX updates"""
        try:
            # Get fresh subscription data from database
            subscriptions = self.sm.get_subscriptions()

            # Generate just the cards HTML (reuse logic from get_manage_content)
            subscription_cards = ""

            if not subscriptions:
                # Empty state - same as in get_manage_content
                subscription_cards = '''
                <div class="empty-state">
                    <h3>Add your first subscription</h3>
                    <p>Click the + button below to get started</p>
                </div>'''
            else:
                # Use the shared method to generate cards
                for sub in subscriptions:
                    subscription_cards += self._generate_subscription_card_html(sub)
            
            # Return just the HTML fragment (not a full template)
            self.send_response(200)
            self.send_header('Content-type', 'text/html')
            self.end_headers()
            self.wfile.write(subscription_cards.encode())
            
        except Exception as e:
            self.send_error(500, f"Failed to load subscription cards: {str(e)}")
    
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
    
    def start_gmail_auth(self):
        """Redirect to Gmail OAuth"""
        auth_url = self.sm.get_gmail_auth_url()
        self.send_response(302)
        self.send_header('Location', auth_url)
        self.end_headers()

    def handle_subscription_update(self):
        """Handle subscription update requests - returns HTML fragment"""
        try:
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length).decode('utf-8')
            data = json.loads(post_data)

            subscription_id = data.get('id')

            if not subscription_id:
                self.send_error(400, 'Missing subscription id')
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
                for field in ['name', 'cost', 'currency', 'billing_cycle', 'category', 'status', 'auto_renewing', 'notes', 'website_url']:
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

            if success:
                # Return updated cards HTML fragment instead of JSON
                self.serve_subscription_cards_fragment()
            else:
                self.send_error(500, 'Failed to update subscription')

        except ValueError as e:
            self.send_error(400, str(e))
        except Exception as e:
            self.send_error(500, f'Server error: {str(e)}')

    def handle_subscription_create(self):
        """Handle subscription creation requests - returns HTML fragment"""
        try:
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length).decode('utf-8')
            data = json.loads(post_data) if post_data.strip() else {}

            # Create the subscription
            new_subscription = self.sm.create_subscription(data)

            if new_subscription:
                # Return updated cards HTML fragment instead of JSON
                self.serve_subscription_cards_fragment()
            else:
                self.send_error(500, 'Failed to create subscription')

        except ValueError as e:
            self.send_error(400, str(e))
        except Exception as e:
            self.send_error(500, f'Server error: {str(e)}')

    # REMOVED: handle_subscriptions_list() method - no longer needed after embedding data fix
    # The manage view now embeds subscription data directly in HTML instead of using AJAX

    def handle_subscription_delete(self):
        """Handle subscription deletion requests - returns HTML fragment"""
        try:
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length).decode('utf-8')
            data = json.loads(post_data)

            subscription_id = data.get('id')

            if not subscription_id:
                self.send_error(400, 'Missing required field: id')
                return

            # Delete the subscription
            success = self.sm.delete_subscription(subscription_id)

            if success:
                # Return updated cards HTML fragment instead of JSON
                self.serve_subscription_cards_fragment()
            else:
                self.send_error(500, 'Failed to delete subscription')

        except ValueError as e:
            self.send_error(400, str(e))
        except Exception as e:
            self.send_error(500, f'Server error: {str(e)}')

    def handle_subscription_get(self, subscription_id):
        """Handle individual subscription retrieval requests"""
        try:
            if not subscription_id:
                self.send_json_response({'success': False, 'error': 'Missing subscription ID'}, status=400)
                return

            # Get the subscription from database
            subscription = self.sm.get_subscription_by_id(subscription_id)

            if not subscription:
                self.send_json_response({'success': False, 'error': 'Subscription not found'}, status=404)
                return

            # Sanitize subscription data for JSON serialization
            sanitized_subscription = self._sanitize_subscription_for_json(subscription)
            self.send_json_response({'success': True, 'subscription': sanitized_subscription}, status=200)

        except Exception as e:
            self.send_json_response({'success': False, 'error': f'Server error: {str(e)}'}, status=500)

    def handle_subscription_form_new(self):
        """Handle GET /api/subscription/new - returns HTML form for new subscription"""
        try:
            categories = self.sm.get_categories()
            form_html = self._generate_subscription_form_html(categories=categories)

            self.send_response(200)
            self.send_header('Content-type', 'text/html')
            self.end_headers()
            self.wfile.write(form_html.encode('utf-8'))

        except Exception as e:
            self.send_error(500, f'Server error: {str(e)}')

    def handle_subscription_form_edit(self, subscription_id):
        """Handle GET /api/subscription/{id}/edit - returns populated HTML form"""
        try:
            if not subscription_id:
                self.send_error(400, 'Missing subscription ID')
                return

            # Get the subscription from database
            subscription = self.sm.get_subscription_by_id(subscription_id)
            if not subscription:
                self.send_error(404, 'Subscription not found')
                return

            categories = self.sm.get_categories()
            form_html = self._generate_subscription_form_html(subscription=subscription, categories=categories)

            self.send_response(200)
            self.send_header('Content-type', 'text/html')
            self.end_headers()
            self.wfile.write(form_html.encode('utf-8'))

        except Exception as e:
            self.send_error(500, f'Server error: {str(e)}')

    def _generate_subscription_form_html(self, subscription=None, categories=None):
        """Generate HTML form with populated data"""
        if categories is None:
            categories = []

        # Determine if this is edit mode
        is_edit = subscription is not None

        # Set default values or use subscription data
        if is_edit:
            form_data = {
                'id': subscription.get('id', ''),
                'name': subscription.get('name', ''),
                'cost': str(subscription.get('cost', '')).replace('$', '') if subscription.get('cost') else '',
                'currency': subscription.get('currency', 'NZD'),
                'billing_cycle': subscription.get('billing_cycle', 'monthly'),
                'category': subscription.get('category', ''),
                'status': subscription.get('status', 'active'),
                'auto_renewing': subscription.get('auto_renewing', True),
                'website_url': subscription.get('website_url', ''),
                'notes': subscription.get('notes', '')
            }
            submit_text = 'Save'
            delete_button_display = 'flex'
        else:
            form_data = {
                'id': '',
                'name': '',
                'cost': '',
                'currency': 'NZD',
                'billing_cycle': 'monthly',
                'category': '',
                'status': 'active',
                'auto_renewing': True,
                'website_url': '',
                'notes': ''
            }
            submit_text = 'Add'
            delete_button_display = 'none'

        # Generate category options
        category_options = ''
        for category in categories:
            selected = 'selected' if category.get('name') == form_data['category'] else ''
            category_options += f'<div class="dropdown-option {selected}" data-value="{category.get("name", "")}">{category.get("name", "")}</div>'

        # Generate form HTML (similar to the modal content but server-rendered)
        form_html = f'''
        <form id="subscription-form" autocomplete="off">
            <input type="hidden" id="subscription-id" name="id" value="{form_data['id']}">

            <div class="form-field">
                <label for="sub-name"{'class="hidden"' if form_data['name'] else ''}>name</label>
                <input type="text" id="sub-name" name="name" value="{form_data['name']}" required autocomplete="off">
            </div>

            <div class="form-row">
                <div class="form-field cost-field">
                    <div class="cost-input-wrapper">
                        <input type="text" id="sub-cost" name="cost" value="{form_data['cost']}" autocomplete="off">
                        <span class="dollar-prefix">$</span>
                    </div>
                </div>

                <div class="form-field cycle-field">
                    <div class="custom-dropdown" data-field="billing_cycle">
                        <span class="dropdown-value">{form_data['billing_cycle']}</span>
                        <span class="dropdown-arrow">▼</span>
                        <div class="dropdown-menu">
                            <div class="dropdown-option {'selected' if form_data['billing_cycle'] == 'weekly' else ''}" data-value="weekly">weekly</div>
                            <div class="dropdown-option {'selected' if form_data['billing_cycle'] == 'monthly' else ''}" data-value="monthly">monthly</div>
                            <div class="dropdown-option {'selected' if form_data['billing_cycle'] == 'annually' else ''}" data-value="annually">annually</div>
                        </div>
                    </div>
                    <input type="hidden" id="sub-cycle" name="billing_cycle" value="{form_data['billing_cycle']}">
                </div>

                <div class="form-field currency-field">
                    <div class="custom-dropdown" data-field="currency">
                        <span class="dropdown-value">{form_data['currency']}</span>
                        <span class="dropdown-arrow">▼</span>
                        <div class="dropdown-menu">
                            <div class="dropdown-option {'selected' if form_data['currency'] == 'NZD' else ''}" data-value="NZD">NZD</div>
                            <div class="dropdown-option {'selected' if form_data['currency'] == 'USD' else ''}" data-value="USD">USD</div>
                            <div class="dropdown-option {'selected' if form_data['currency'] == 'INR' else ''}" data-value="INR">INR</div>
                            <div class="dropdown-option {'selected' if form_data['currency'] == 'GBP' else ''}" data-value="GBP">GBP</div>
                            <div class="dropdown-option {'selected' if form_data['currency'] == 'EUR' else ''}" data-value="EUR">EUR</div>
                            <div class="dropdown-option {'selected' if form_data['currency'] == 'AUD' else ''}" data-value="AUD">AUD</div>
                        </div>
                    </div>
                    <input type="hidden" id="sub-currency" name="currency" value="{form_data['currency']}">
                </div>
            </div>

            <div class="form-row">
                <div class="form-field category-field">
                    <div class="custom-dropdown" data-field="category">
                        <span class="dropdown-value">{'category' if not form_data['category'] else form_data['category']}</span>
                        <span class="dropdown-arrow">▼</span>
                        <div class="dropdown-menu">
                            {category_options}
                        </div>
                    </div>
                    <input type="hidden" id="sub-category" name="category" value="{form_data['category']}">
                </div>
            </div>

            <div class="form-row">
                <div class="form-field status-field">
                    <div class="custom-dropdown" data-field="status">
                        <span class="dropdown-value">{form_data['status']}</span>
                        <span class="dropdown-arrow">▼</span>
                        <div class="dropdown-menu">
                            <div class="dropdown-option {'selected' if form_data['status'] == 'active' else ''}" data-value="active">active</div>
                            <div class="dropdown-option {'selected' if form_data['status'] == 'trial' else ''}" data-value="trial">trial</div>
                            <div class="dropdown-option {'selected' if form_data['status'] == 'paused' else ''}" data-value="paused">paused</div>
                            <div class="dropdown-option {'selected' if form_data['status'] == 'cancelled' else ''}" data-value="cancelled">cancelled</div>
                        </div>
                    </div>
                    <input type="hidden" id="sub-status" name="status" value="{form_data['status']}">
                </div>
            </div>

            <div class="form-row">
                <div class="form-field renewing-field">
                    <div class="renewing-toggle">
                        <span class="toggle-label">renewing?</span>
                        <input type="hidden" id="sub-renewing" name="renewing" value="{'true' if form_data['auto_renewing'] else 'false'}">
                        <span class="toggle-icons">
                            <svg class="icon-option icon-check {'active' if form_data['auto_renewing'] else ''}" data-value="true" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                                <polyline points="20 6 9 17 4 12"></polyline>
                            </svg>
                            <svg class="icon-option icon-x {'' if form_data['auto_renewing'] else 'active'}" data-value="false" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                                <line x1="18" y1="6" x2="6" y2="18"></line>
                                <line x1="6" y1="6" x2="18" y2="18"></line>
                            </svg>
                        </span>
                    </div>
                </div>
            </div>

            <div class="form-field">
                <label for="sub-website"{'class="hidden"' if form_data['website_url'] else ''}>website</label>
                <input type="url" id="sub-website" name="website_url" value="{form_data['website_url']}" autocomplete="off">
            </div>

            <div class="form-field">
                <label for="sub-notes"{'class="hidden"' if form_data['notes'] else ''}>notes</label>
                <textarea id="sub-notes" name="notes" rows="3" autocomplete="off">{form_data['notes']}</textarea>
            </div>

            <div class="form-actions">
                <button type="submit" id="submit-btn">{submit_text}</button>
                <button type="button" id="delete-btn" class="delete-btn" style="display: {delete_button_display};">
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                        <path d="M3 6h18"/>
                        <path d="M19 6v14c0 1-1 2-2 2H7c-1 0-2-1-2-2V6"/>
                        <path d="M8 6V4c0-1 1-2 2-2h4c1 0 2 1 2 2v2"/>
                        <line x1="10" y1="11" x2="10" y2="17"/>
                        <line x1="14" y1="11" x2="14" y2="17"/>
                    </svg>
                </button>
            </div>
        </form>
        '''

        return form_html

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
        return self.email_processor.extract_email_content(payload)

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