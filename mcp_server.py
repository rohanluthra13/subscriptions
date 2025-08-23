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

# Initialize MCP server
mcp = FastMCP("subscriptions")

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
def trigger_email_fetch(quick_sync: bool = True) -> str:
    """Trigger Gmail email fetch from running app
    
    Args:
        quick_sync: If True, fetch recent emails only (fast). If False, full year sync.
    
    Requires main.py to be running on localhost:8000
    """
    try:
        # Check if app is running
        app_url = "http://localhost:8000"
        
        # Try to reach the app with debugging
        try:
            print(f"DEBUG: Attempting to connect to {app_url}/status", file=sys.stderr)
            status_response = requests.get(f"{app_url}/status", timeout=5)
            print(f"DEBUG: Got response {status_response.status_code}", file=sys.stderr)
            if status_response.status_code != 200:
                return json.dumps({
                    "success": False,
                    "error": f"App status check failed: HTTP {status_response.status_code}",
                    "hint": "Check if main.py is running correctly"
                })
        except requests.exceptions.RequestException as e:
            print(f"DEBUG: Request failed with exception: {type(e).__name__}: {str(e)}", file=sys.stderr)
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
                "message": f"Email fetch triggered ({'quick' if quick_sync else 'full'} sync)",
                "note": "This may take 1-15 minutes depending on email volume",
                "status_url": f"{app_url}/status"
            })
        else:
            return json.dumps({
                "success": False,
                "error": f"Failed to trigger fetch: {response.status_code}"
            })
            
    except Exception as e:
        print(f"Error in trigger_email_fetch: {e}", file=sys.stderr)
        return json.dumps({"success": False, "error": str(e)})

@mcp.tool()
def get_email_status() -> str:
    """Get email system status and statistics
    
    Returns:
        - Gmail connection status and account
        - Total emails in database
        - Recent email activity (last 24h)
        - Last sync timestamp
        - Whether main.py server is running
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
        print(f"Error in get_email_status: {e}", file=sys.stderr)
        return json.dumps({"error": str(e)})

if __name__ == "__main__":
    mcp.run()