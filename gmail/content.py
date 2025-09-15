"""Gmail email content processing utilities

Direct lift-and-shift of email processing methods from main.py
"""

import base64
import re
import sqlite3
import requests
from datetime import datetime
from email.utils import parsedate_to_datetime


class EmailContentProcessor:
    """Processes Gmail email content - exact methods from main.py"""
    
    def __init__(self, subscription_manager):
        """Initialize with reference to subscription manager for access to other methods
        
        Args:
            subscription_manager: Reference to main SubscriptionManager instance
        """
        self.sm = subscription_manager
    
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
    
    def process_batch_simple(self, batch: list, email: str, cursor) -> bool:
        """Process a batch of messages - returns True if successful, False if any errors"""
        try:
            access_token = self.sm.get_valid_access_token(email)
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
                sender_domain = self.sm.extract_domain(sender)
                
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