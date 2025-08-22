#!/usr/bin/env python3
"""
Minimal MCP server for subscription management
Exposes subscription data via Model Context Protocol
"""

import sqlite3
import json
import sys
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
        
        # Build query
        query = """
            SELECT 
                name,
                domain,
                status,
                renewing,
                cost,
                currency,
                billing_cycle,
                next_date,
                notes
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
            name, domain, status, renewing, cost, currency, billing_cycle, next_date, notes = sub
            
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
                "domain": domain,
                "status": status,
                "renewing": bool(renewing),
                "cost": cost,
                "currency": currency or "USD",
                "billing_cycle": billing_cycle,
                "monthly_equivalent": round(monthly_cost, 2) if monthly_cost else None,
                "next_date": next_date,
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

if __name__ == "__main__":
    mcp.run()