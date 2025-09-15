"""Gmail OAuth authentication manager

Handles OAuth flow for Gmail API access:
- Authorization URL generation
- Code-to-token exchange
- Token refresh
- Access token validation
"""

import sqlite3
import requests
from datetime import datetime, timedelta
from urllib.parse import urlencode
from typing import Optional, Dict, Any


class GmailAuthManager:
    """Manages Gmail OAuth authentication and token lifecycle"""
    
    def __init__(self, client_id: str, client_secret: str, redirect_uri: str, db_path: str):
        """Initialize with OAuth credentials and database path
        
        Args:
            client_id: Google OAuth client ID
            client_secret: Google OAuth client secret
            redirect_uri: OAuth callback URL
            db_path: Path to SQLite database for token storage
        """
        self.client_id = client_id
        self.client_secret = client_secret
        self.redirect_uri = redirect_uri
        self.db_path = db_path
        self.scope = 'https://www.googleapis.com/auth/gmail.readonly'
    
    def get_auth_url(self) -> str:
        """Generate Gmail OAuth authorization URL
        
        Returns:
            Authorization URL for user consent
        """
        params = {
            'client_id': self.client_id,
            'redirect_uri': self.redirect_uri,
            'scope': self.scope,
            'response_type': 'code',
            'access_type': 'offline',
            'prompt': 'select_account consent'  # Force account selection and consent
        }
        return f"https://accounts.google.com/o/oauth2/auth?{urlencode(params)}"
    
    def exchange_code_for_tokens(self, code: str) -> Dict[str, Any]:
        """Exchange authorization code for access and refresh tokens
        
        Args:
            code: Authorization code from OAuth callback
            
        Returns:
            Token response dict with access_token, refresh_token, expires_in
        """
        data = {
            'client_id': self.client_id,
            'client_secret': self.client_secret,
            'code': code,
            'grant_type': 'authorization_code',
            'redirect_uri': self.redirect_uri
        }
        
        response = requests.post('https://oauth2.googleapis.com/token', data=data)
        token_data = response.json()
        return token_data
    
    def refresh_access_token(self, refresh_token: str) -> Dict[str, Any]:
        """Refresh an expired access token
        
        Args:
            refresh_token: Stored refresh token
            
        Returns:
            New token data with fresh access_token
            
        Raises:
            Exception: If refresh fails or refresh_token is invalid
        """
        if not refresh_token or refresh_token.strip() == '':
            raise Exception("No valid refresh token available")
            
        data = {
            'client_id': self.client_id,
            'client_secret': self.client_secret,
            'refresh_token': refresh_token,
            'grant_type': 'refresh_token',
            'scope': self.scope
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
        """Get a valid access token, refreshing if necessary
        
        This method handles the complete token lifecycle:
        1. Retrieves stored token from database
        2. Checks expiration
        3. Refreshes if needed
        4. Updates database with new token
        
        Args:
            email: Gmail account email
            
        Returns:
            Valid access token ready for API calls
            
        Raises:
            Exception: If connection not found or refresh fails
        """
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
        
        # Parse the expiry time - handle different ISO format variations
        # Tokens come as strings like "2024-01-15T10:30:00Z" or "2024-01-15T10:30:00+00:00"
        try:
            if token_expiry.endswith('Z'):
                # Replace 'Z' with '+00:00' for Python's datetime parser
                expiry_time = datetime.fromisoformat(token_expiry.replace('Z', '+00:00'))
            elif '+00:00' in token_expiry or 'T' in token_expiry:
                # Already in ISO format with timezone
                expiry_time = datetime.fromisoformat(token_expiry)
            else:
                # Simple ISO format without timezone
                expiry_time = datetime.fromisoformat(token_expiry)
        except ValueError as e:
            conn.close()
            raise Exception(f"Invalid token expiry format: {token_expiry} - {str(e)}")
        
        # Check if token expires within 5 minutes
        # We refresh early to avoid making API calls with an expired token
        if expiry_time <= datetime.now() + timedelta(minutes=5):
            print("Access token expiring soon, refreshing...")
            try:
                # Use the refresh token to get a new access token
                token_data = self.refresh_access_token(refresh_token)
                
                if 'access_token' in token_data:
                    # Calculate new expiry time (usually 1 hour from now)
                    new_expiry = datetime.now() + timedelta(seconds=token_data['expires_in'])
                    
                    # Update database with new token and expiry
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