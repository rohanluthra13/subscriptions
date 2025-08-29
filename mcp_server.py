#!/usr/bin/env python3
"""
Minimal MCP server for subscription management
Exposes subscription data via Model Context Protocol
"""

import sqlite3
import json
import sys
import requests
from datetime import datetime, timedelta
from typing import Optional
from mcp.server.fastmcp import FastMCP
from mcp.server.fastmcp.prompts import base
from pydantic import Field

# Initialize MCP server
mcp = FastMCP("subscriptions")

# Register prompts
@mcp.prompt(
    name="analyze_email_metadata",
    description="Analyze email metadata to identify subscription services"
)
def analyze_email_metadata() -> list[base.Message]:
    """Analyze email metadata to identify subscription services
    
    This prompt guides the LLM to:
    1. Retrieve existing subscriptions and email metadata
    2. Analyze patterns to identify subscription services
    3. Write findings to resources/llm_notes.md
    """
    prompt = """You are analyzing email metadata to identify subscription services.

Process:
1. Call get_subscriptions() to see existing subscriptions
2. Repeatedly call get_email_metadata() to process all unanalyzed emails:
   - Each call returns ~300-400 emails that fit in the response
   - Only unanalyzed emails are returned (analyzed_for_subscriptions=false)
   - Response format: {"count": N, "emails": [{"id": 1, "subj": "...", "from": "...", "date": "..."}]}
3. After each batch, call mark_emails_analyzed(email_ids) with all the IDs you processed (e.g., [1, 2, 3, 4, ...])
4. Continue until get_email_metadata() returns count=0 (all emails analyzed)

Analysis approach:
- Track subscription patterns across all batches in your conversation memory
- Look for recurring billing, renewal, account notification patterns
- Group related domains (e.g., netflix.com + dvd.netflix.com)
- Focus on domains NOT already in the subscriptions table

Final output:
After processing all emails, append your findings to resources/llm_notes.md in this format:

**[Service Name]**
Domains: [domain1.com, domain2.com] 
Notes: [Evidence across all batches, e.g. "12 monthly billing emails", "renewal notices every 30 days"]

User Check: [ ] Yes | [ ] No
User Notes: 

Add each discovered subscription as a new block at the end of the "## Discovered Subscriptions" section.

The system handles batching automatically - just keep calling get_email_metadata() until done."""
    
    return [base.UserMessage(prompt)]

def get_db_connection():
    """Get SQLite database connection"""
    import os
    # Get absolute path to database file relative to this script
    script_dir = os.path.dirname(os.path.abspath(__file__))
    db_path = os.path.join(script_dir, "subscriptions.db")
    return sqlite3.connect(db_path)

@mcp.tool()
def get_subscriptions(status: Optional[str] = None) -> str:
    """Get all subscriptions with their details
    
    Args:
        status: Filter by status (active, cancelled, trial, paused). Optional.
    """
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Build query using new schema
        query = """
            SELECT 
                name,
                domains,
                status,
                auto_renewing,
                cost,
                currency,
                billing_cycle,
                next_billing_date,
                notes,
                category
            FROM subscriptions
        """
        
        params = []
        if status:
            query += " WHERE status = ?"
            params.append(status)
        
        query += " ORDER BY name"
        
        cursor.execute(query, params)
        subscriptions = cursor.fetchall()
        conn.close()
        
        # Format results
        result = []
        total_monthly = 0
        
        for sub in subscriptions:
            name, domains, status, auto_renewing, cost, currency, billing_cycle, next_date, notes, category = sub
            
            # Parse domains JSON
            domain_list = json.loads(domains) if domains else []
            
            # Calculate monthly cost if available
            monthly_cost = None
            if cost:
                if billing_cycle == "monthly":
                    monthly_cost = cost
                elif billing_cycle == "yearly" or billing_cycle == "annual":
                    monthly_cost = cost / 12
                elif billing_cycle == "quarterly":
                    monthly_cost = cost / 3
                
                if monthly_cost and status == "active":
                    total_monthly += monthly_cost
            
            subscription_info = {
                "name": name,
                "domains": domain_list,
                "category": category,
                "status": status,
                "auto_renewing": bool(auto_renewing),
                "cost": cost,
                "currency": currency or "USD",
                "billing_cycle": billing_cycle,
                "monthly_equivalent": round(monthly_cost, 2) if monthly_cost else None,
                "next_billing_date": next_date,
                "notes": notes
            }
            result.append(subscription_info)
        
        # Create summary
        summary = {
            "total_subscriptions": len(result),
            "active_subscriptions": sum(1 for s in result if s["status"] == "active"),
            "estimated_monthly_cost": round(total_monthly, 2),
            "subscriptions": result
        }
        
        return json.dumps(summary, indent=2)
    
    except Exception as e:
        print(f"Error in get_subscriptions: {e}", file=sys.stderr)
        return f"Error: {e}"

@mcp.tool()
def add_subscription(
    name: str,
    domains: Optional[list] = None,
    cost: Optional[float] = None,
    billing_cycle: Optional[str] = "monthly",
    status: Optional[str] = "active",
    currency: Optional[str] = "USD",
    category: Optional[str] = None,
    notes: Optional[str] = None
) -> str:
    """Add a new subscription
    
    Args:
        name: Name of the subscription service (e.g., "Netflix")
        domains: List of domains for the service (e.g., ["netflix.com", "help.netflix.com"]) - optional
        cost: Cost per billing cycle (optional)
        billing_cycle: One of: monthly, yearly, annual, quarterly (default: monthly)
        status: One of: active, cancelled, trial, paused (default: active)
        currency: Currency code (default: USD)
        category: Category like "streaming", "productivity", etc (optional)
        notes: Additional notes (optional)
    """
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Check if subscription already exists by name
        cursor.execute("SELECT name FROM subscriptions WHERE name = ?", (name,))
        if cursor.fetchone():
            conn.close()
            return json.dumps({
                "success": False,
                "error": f"Subscription '{name}' already exists"
            })
        
        # Convert domains to JSON
        domains_json = json.dumps(domains) if domains else None
        
        # Insert new subscription
        cursor.execute("""
            INSERT INTO subscriptions (
                name, domains, status, auto_renewing, cost, currency, 
                billing_cycle, category, notes, created_by, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'), datetime('now'))
        """, (
            name, domains_json, status, 
            1 if status == "active" else 0,  # auto_renewing based on status
            cost, currency, billing_cycle, category, notes, 'user'
        ))
        
        conn.commit()
        subscription_id = cursor.lastrowid
        conn.close()
        
        return json.dumps({
            "success": True,
            "message": f"Added '{name}' subscription",
            "subscription": {
                "id": subscription_id,
                "name": name,
                "domains": domains or [],
                "status": status,
                "cost": cost,
                "currency": currency,
                "billing_cycle": billing_cycle,
                "category": category
            }
        }, indent=2)
        
    except Exception as e:
        print(f"Error in add_subscription: {e}", file=sys.stderr)
        return json.dumps({"success": False, "error": str(e)})

@mcp.tool()
def update_subscription(
    name: str,
    new_name: Optional[str] = None,
    domains: Optional[list] = None,
    cost: Optional[float] = None,
    billing_cycle: Optional[str] = None,
    status: Optional[str] = None,
    currency: Optional[str] = None,
    category: Optional[str] = None,
    notes: Optional[str] = None
) -> str:
    """Update an existing subscription
    
    Args:
        name: Current name of the subscription to update (required)
        new_name: New name for the subscription (optional)
        domains: New list of domains (optional)
        cost: New cost (optional)
        billing_cycle: New billing cycle: monthly, yearly, annual, quarterly (optional)
        status: New status: active, cancelled, trial, paused (optional)
        currency: New currency code (optional)
        category: New category (optional)
        notes: New notes (optional)
    """
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Check if subscription exists
        cursor.execute("SELECT * FROM subscriptions WHERE name = ?", (name,))
        if not cursor.fetchone():
            conn.close()
            return json.dumps({
                "success": False,
                "error": f"No subscription found with name '{name}'"
            })
        
        # Build update query dynamically
        updates = []
        params = []
        
        if new_name is not None:
            # Check if new name already exists
            cursor.execute("SELECT name FROM subscriptions WHERE name = ? AND name != ?", (new_name, name))
            if cursor.fetchone():
                conn.close()
                return json.dumps({
                    "success": False,
                    "error": f"Subscription '{new_name}' already exists"
                })
            updates.append("name = ?")
            params.append(new_name)
            
        if domains is not None:
            updates.append("domains = ?")
            params.append(json.dumps(domains))
            
        if cost is not None:
            updates.append("cost = ?")
            params.append(cost)
            
        if billing_cycle is not None:
            updates.append("billing_cycle = ?")
            params.append(billing_cycle)
            
        if status is not None:
            updates.append("status = ?")
            params.append(status)
            # Update auto_renewing based on status
            updates.append("auto_renewing = ?")
            params.append(1 if status == "active" else 0)
            
        if currency is not None:
            updates.append("currency = ?")
            params.append(currency)
            
        if category is not None:
            updates.append("category = ?")
            params.append(category)
            
        if notes is not None:
            updates.append("notes = ?")
            params.append(notes)
            
        if not updates:
            conn.close()
            return json.dumps({
                "success": False,
                "error": "No fields to update"
            })
        
        # Add updated_at timestamp
        updates.append("updated_at = datetime('now')")
        
        # Execute update
        params.append(name)
        query = f"UPDATE subscriptions SET {', '.join(updates)} WHERE name = ?"
        cursor.execute(query, params)
        
        conn.commit()
        
        # Get updated subscription
        cursor.execute(
            "SELECT name, domains, status, cost, currency, billing_cycle, category FROM subscriptions WHERE name = ?",
            (new_name if new_name else name,)
        )
        updated = cursor.fetchone()
        conn.close()
        
        updated_name, domains_json, status, cost, currency, billing_cycle, category = updated
        domain_list = json.loads(domains_json) if domains_json else []
        
        return json.dumps({
            "success": True,
            "message": f"Updated '{updated_name}' subscription",
            "subscription": {
                "name": updated_name,
                "domains": domain_list,
                "status": status,
                "cost": cost,
                "currency": currency,
                "billing_cycle": billing_cycle,
                "category": category
            }
        }, indent=2)
        
    except Exception as e:
        print(f"Error in update_subscription: {e}", file=sys.stderr)
        return json.dumps({"success": False, "error": str(e)})

@mcp.tool()
def fetch_email_metadata(quick_sync: bool = True) -> str:
    """Trigger Gmail email metadata fetch from running app
    
    Args:
        quick_sync: If True, fetch recent emails only (fast). If False, full year sync.
    
    Requires main.py to be running on localhost:8000
    """
    try:
        # Check if app is running
        app_url = "http://localhost:8000"
        
        # Try to reach the app
        try:
            status_response = requests.get(f"{app_url}/status", timeout=5)
            if status_response.status_code != 200:
                return json.dumps({
                    "success": False,
                    "error": f"App status check failed: HTTP {status_response.status_code}",
                    "hint": "Check if main.py is running correctly"
                })
        except requests.exceptions.RequestException as e:
            return json.dumps({
                "success": False,
                "error": f"Cannot connect to app: {type(e).__name__}: {str(e)}",
                "hint": "Run: python main.py and ensure it's accessible at localhost:8000"
            })
        
        # Trigger the fetch
        fetch_endpoint = f"{app_url}/api/fetch"
        
        # For now, main.py doesn't have different endpoints for quick vs full
        # This is a placeholder for future enhancement
        response = requests.post(fetch_endpoint, timeout=5)
        
        if response.status_code == 200:
            return json.dumps({
                "success": True,
                "message": f"Email metadata fetch triggered ({'quick' if quick_sync else 'full'} sync)",
                "note": "This may take 1-15 minutes depending on email volume",
                "status_url": f"{app_url}/status"
            })
        else:
            return json.dumps({
                "success": False,
                "error": f"Failed to trigger fetch: {response.status_code}"
            })
            
    except Exception as e:
        print(f"Error in fetch_email_metadata: {e}", file=sys.stderr)
        return json.dumps({"success": False, "error": str(e)})

@mcp.tool()
def fetch_email_content(
    email_ids: Optional[list] = None,
    sender_domains: Optional[list] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    limit: Optional[int] = 50
) -> str:
    """Trigger background fetching of full email content from Gmail
    
    Args:
        email_ids: List of specific Gmail message IDs to fetch content for (optional)
        sender_domains: List of sender domains to fetch content for (e.g., ["netflix.com", "spotify.com"]) (optional)
        date_from: Start date for filtering in YYYY-MM-DD format (optional)
        date_to: End date for filtering in YYYY-MM-DD format (optional)  
        limit: Maximum number of emails to fetch content for (default: 50, max: 200)
        
    Only fetches content for emails where content hasn't been fetched yet.
    This is a background operation that may take several minutes.
    
    Requires main.py to be running on localhost:8000
    """
    try:
        # Check if app is running
        app_url = "http://localhost:8000"
        
        try:
            status_response = requests.get(f"{app_url}/status", timeout=5)
            if status_response.status_code != 200:
                return json.dumps({
                    "success": False,
                    "error": f"App status check failed: HTTP {status_response.status_code}",
                    "hint": "Check if main.py is running correctly"
                })
        except requests.exceptions.RequestException as e:
            return json.dumps({
                "success": False,
                "error": f"Cannot connect to app: {type(e).__name__}: {str(e)}",
                "hint": "Run: python main.py and ensure it's accessible at localhost:8000"
            })
        
        # Build request payload
        request_data = {}
        if email_ids:
            request_data["email_ids"] = email_ids
        if sender_domains:
            request_data["sender_domains"] = sender_domains
        if date_from:
            request_data["date_from"] = date_from
        if date_to:
            request_data["date_to"] = date_to
        if limit:
            request_data["limit"] = min(limit, 200)  # Cap at 200 for safety
        
        # Call the content fetch endpoint
        content_endpoint = f"{app_url}/api/fetch_email_content"
        
        response = requests.post(
            content_endpoint, 
            json=request_data,
            headers={'Content-Type': 'application/json'},
            timeout=60  # Longer timeout since content fetching takes time
        )
        
        if response.status_code == 200:
            result = response.json()
            if result.get("success"):
                return json.dumps({
                    "success": True,
                    "message": result.get("message", "Content fetch completed"),
                    "data": result.get("data", {}),
                    "filters_used": {
                        "email_ids": email_ids or "none",
                        "sender_domains": sender_domains or "none", 
                        "date_range": f"{date_from} to {date_to}" if date_from or date_to else "none",
                        "limit": limit
                    }
                }, indent=2)
            else:
                return json.dumps({
                    "success": False,
                    "error": result.get("error", "Unknown error from app")
                })
        else:
            return json.dumps({
                "success": False,
                "error": f"HTTP {response.status_code}: {response.text}"
            })
            
    except Exception as e:
        print(f"Error in fetch_email_content: {e}", file=sys.stderr)
        return json.dumps({"success": False, "error": str(e)})

@mcp.tool()
def get_app_status() -> str:
    """Get comprehensive system status and email database statistics
    
    Returns detailed information including:
        - Gmail connection status and authenticated account
        - Total emails stored in local database
        - Recent email processing activity (last 24 hours)
        - Last synchronization timestamp and time elapsed
        - Whether main.py web server is accessible on localhost:8000
    """
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Get connection status
        cursor.execute("""
            SELECT email, last_sync_at, is_active 
            FROM connections 
            LIMIT 1
        """)
        connection = cursor.fetchone()
        
        # Count total emails
        cursor.execute("SELECT COUNT(*) FROM processed_emails")
        total_emails = cursor.fetchone()[0]
        
        # Count recent emails (last 24 hours)
        yesterday = datetime.now() - timedelta(days=1)
        cursor.execute("""
            SELECT COUNT(*) FROM processed_emails 
            WHERE processed_at > ?
        """, (yesterday.isoformat(),))
        recent_emails = cursor.fetchone()[0]
        
        # Check if main.py is accessible
        app_running = False
        try:
            requests.get("http://localhost:8000/status", timeout=1)
            app_running = True
        except:
            pass
        
        conn.close()
        
        status = {
            "gmail_connected": connection is not None,
            "gmail_account": connection[0] if connection else None,
            "last_sync": connection[1] if connection else None,
            "connection_active": bool(connection[2]) if connection else False,
            "total_emails": total_emails,
            "emails_last_24h": recent_emails,
            "app_running": app_running,
            "app_url": "http://localhost:8000" if app_running else None
        }
        
        # Add human-readable summary
        if connection and connection[1]:
            last_sync_dt = datetime.fromisoformat(connection[1])
            hours_ago = (datetime.now() - last_sync_dt).total_seconds() / 3600
            status["hours_since_sync"] = round(hours_ago, 1)
            
        return json.dumps(status, indent=2)
        
    except Exception as e:
        print(f"Error in get_app_status: {e}", file=sys.stderr)
        return json.dumps({"error": str(e)})

@mcp.tool()
def get_email_content(
    sender_domains: Optional[list] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    subject_contains: Optional[str] = None,
    limit: Optional[int] = 20
) -> str:
    """Retrieve stored full email content from database
    
    Args:
        sender_domains: Filter by sender domains (e.g., ["netflix.com", "spotify.com"]) (optional)
        date_from: Start date in YYYY-MM-DD format (optional)
        date_to: End date in YYYY-MM-DD format (optional)
        subject_contains: Filter by subject line content (case-insensitive) (optional)
        limit: Maximum number of emails to return (default: 20, max: 100)
        
    Returns emails that have full content stored (content_fetched = 1).
    Use when you need to read actual email body text for detailed analysis.
    """
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Build query to get emails with content
        query_parts = ["content_fetched = 1", "content IS NOT NULL"]
        params = []
        
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
        
        if subject_contains:
            query_parts.append("subject LIKE ?")
            params.append(f"%{subject_contains}%")
        
        # Validate and cap limit
        if limit is None or limit > 100:
            limit = 20
        elif limit < 1:
            limit = 1
        
        query = f"""
            SELECT 
                gmail_message_id,
                subject,
                sender,
                sender_domain,
                received_at,
                content
            FROM processed_emails 
            WHERE {' AND '.join(query_parts)}
            ORDER BY received_at DESC 
            LIMIT ?
        """
        params.append(limit)
        
        cursor.execute(query, params)
        emails = cursor.fetchall()
        conn.close()
        
        if not emails:
            return json.dumps({
                "success": True,
                "message": "No emails found matching criteria",
                "count": 0,
                "emails": [],
                "filters_applied": {
                    "sender_domains": sender_domains or "none",
                    "date_range": f"{date_from} to {date_to}" if date_from or date_to else "none",
                    "subject_contains": subject_contains or "none",
                    "limit": limit
                }
            }, indent=2)
        
        # Format results
        result_emails = []
        for email_data in emails:
            gmail_id, subject, sender, sender_domain, received_at, content = email_data
            
            result_emails.append({
                "gmail_message_id": gmail_id,
                "subject": subject,
                "sender": sender,
                "sender_domain": sender_domain,
                "received_at": received_at,
                "content": content,
                "content_length": len(content) if content else 0
            })
        
        return json.dumps({
            "success": True,
            "message": f"Found {len(emails)} emails with content",
            "count": len(emails),
            "emails": result_emails,
            "filters_applied": {
                "sender_domains": sender_domains or "none",
                "date_range": f"{date_from} to {date_to}" if date_from or date_to else "none", 
                "subject_contains": subject_contains or "none",
                "limit": limit
            }
        }, indent=2)
        
    except Exception as e:
        print(f"Error in get_email_content: {e}", file=sys.stderr)
        return json.dumps({"success": False, "error": str(e)})

@mcp.tool()
def get_email_metadata(
    sender_domains: Optional[list] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    include_analyzed: bool = False
) -> str:
    """Get unanalyzed email metadata for subscription analysis
    
    Args:
        sender_domains: Filter by specific domains if needed (optional)
        date_from: Start date in YYYY-MM-DD format (optional)
        date_to: End date in YYYY-MM-DD format (optional)
        include_analyzed: Include emails already analyzed for subscriptions (default: False)
    
    Returns unanalyzed emails in compact format: {"id", "subj", "from", "date"}.
    Automatically limited by response size (~300-400 emails per call).
    Call repeatedly until count=0 to process all unanalyzed emails.
    """
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Build query
        query_parts = []
        params = []
        
        # Skip already analyzed emails by default
        if not include_analyzed:
            query_parts.append("(analyzed_for_subscriptions = 0 OR analyzed_for_subscriptions IS NULL)")
        
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
        
        where_clause = f"WHERE {' AND '.join(query_parts)}" if query_parts else ""
        
        query = f"""
            SELECT 
                id,
                gmail_message_id,
                subject,
                sender,
                sender_domain,
                received_at,
                content_fetched
            FROM processed_emails 
            {where_clause}
            ORDER BY received_at DESC
        """
        
        cursor.execute(query, params)
        emails = cursor.fetchall()
        conn.close()
        
        # Format results - optimized for size with character limit
        result_emails = []
        char_count = 100  # Approximate starting size for wrapper JSON
        max_chars = 95000  # Stay well under 100K limit
        actual_count = 0
        
        for email_data in emails:
            id, gmail_id, subject, sender, sender_domain, received_at, content_fetched = email_data
            
            # Compact format: shorter keys, no redundant data
            email_obj = {
                "id": id,  # Now using our sequential ID
                "subj": subject,
                "from": sender,
                "date": received_at
            }
            
            # Estimate size of this email in JSON (rough but fast)
            email_json_size = len(json.dumps(email_obj)) + 2  # +2 for comma and space
            
            if char_count + email_json_size > max_chars:
                break  # Stop adding emails if we'd exceed limit
                
            result_emails.append(email_obj)
            char_count += email_json_size
            actual_count += 1
        
        response = {
            "success": True,
            "count": actual_count,
            "total_available": len(emails),
            "emails": result_emails
        }
        
        if actual_count < len(emails):
            response["truncated"] = True
            response["message"] = f"Limited to {actual_count} of {len(emails)} emails due to size constraints"
        
        return json.dumps(response)  # No indent for compact output
        
    except Exception as e:
        print(f"Error in get_email_metadata: {e}", file=sys.stderr)
        return json.dumps({"success": False, "error": str(e)})

@mcp.tool()
def mark_emails_analyzed(email_ids: list[int]) -> str:
    """Mark emails as analyzed for subscription detection
    
    Args:
        email_ids: List of email IDs (integers) to mark as analyzed
    
    Updates the analyzed_for_subscriptions flag to prevent re-analysis.
    """
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Build placeholders for SQL IN clause
        placeholders = ','.join('?' * len(email_ids))
        
        cursor.execute(f"""
            UPDATE processed_emails 
            SET analyzed_for_subscriptions = 1
            WHERE id IN ({placeholders})
        """, email_ids)
        
        updated_count = cursor.rowcount
        conn.commit()
        conn.close()
        
        return json.dumps({
            "success": True,
            "message": f"Marked {updated_count} emails as analyzed",
            "updated_count": updated_count,
            "requested_count": len(email_ids)
        }, indent=2)
        
    except Exception as e:
        print(f"Error in mark_emails_analyzed: {e}", file=sys.stderr)
        return json.dumps({"success": False, "error": str(e)})

if __name__ == "__main__":
    mcp.run()