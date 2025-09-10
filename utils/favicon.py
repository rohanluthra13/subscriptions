#!/usr/bin/env python3
"""
Favicon/logo fetching utilities.
Extracted from main.py for cleaner logo handling.

This module handles:
- Multi-strategy favicon fetching
- HTML parsing for favicon links
- Fallback to standard locations
- Google favicon service as last resort
- Size limits and error handling
"""

import requests
import re
from urllib.parse import urlparse


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
                                try:
                                    # Check content length if provided - with validation
                                    content_length = response.headers.get('content-length')
                                    if content_length:
                                        try:
                                            content_len = int(content_length)
                                            if content_len > max_size:
                                                print(f"Favicon too large ({content_length} bytes) from {favicon_url}")
                                                continue
                                        except ValueError:
                                            # Invalid content-length header, proceed with streaming
                                            pass
                                    
                                    # Read content with size limit - ensure proper cleanup
                                    content = b''
                                    try:
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
                                    finally:
                                        # Ensure response stream is properly closed
                                        response.close()
                                finally:
                                    # Extra safety net for response cleanup
                                    if hasattr(response, 'close'):
                                        response.close()
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
                    try:
                        # Check size for Google's service (last fallback) - with validation
                        content_length = response.headers.get('content-length')
                        if content_length:
                            try:
                                content_len = int(content_length)
                                if content_len > max_size:
                                    print(f"Favicon too large ({content_length} bytes) from {url}")
                                    continue
                            except ValueError:
                                # Invalid content-length header, proceed with streaming
                                pass
                        
                        # Read content with size limit - ensure proper cleanup
                        content = b''
                        try:
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
                        finally:
                            # Ensure response stream is properly closed
                            response.close()
                    finally:
                        # Extra safety net for response cleanup
                        if hasattr(response, 'close'):
                            response.close()
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


if __name__ == "__main__":
    # Allow standalone testing
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python favicon.py <domain> [domain2] [domain3] ...")
        print("Example: python favicon.py google.com github.com")
        sys.exit(1)
    
    domains = sys.argv[1:]
    
    print(f"Testing favicon fetching for {len(domains)} domain(s):")
    print("-" * 60)
    
    for domain in domains:
        print(f"\nTesting: {domain}")
        logo_data, content_type = fetch_favicon_for_domain(domain, timeout=10)
        
        if logo_data:
            print(f"✓ Success: {len(logo_data)} bytes, {content_type}")
        else:
            print(f"✗ Failed: No favicon found")