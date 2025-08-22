#!/usr/bin/env python3
"""
Simple schema migration - just transform the subscriptions table
"""

import sqlite3
import json

def simple_migrate():
    """Simple migration for subscriptions only"""
    conn = sqlite3.connect('subscriptions.db')
    cursor = conn.cursor()
    
    print("Simple migration: updating subscriptions table...")
    
    # Get current subscriptions
    cursor.execute("SELECT id, name, domain, status, renewing, cost, currency, billing_cycle, next_date, notes, created_at, updated_at FROM subscriptions")
    subs = cursor.fetchall()
    
    # Drop and recreate subscriptions table with new schema
    cursor.execute("DROP TABLE subscriptions")
    
    cursor.execute('''
        CREATE TABLE subscriptions (
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
    
    # Insert data with domain as JSON array
    for sub in subs:
        old_id, name, domain, status, renewing, cost, currency, billing_cycle, next_date, notes, created_at, updated_at = sub
        
        # Convert single domain to JSON array
        domains_json = json.dumps([domain]) if domain else None
        
        cursor.execute('''
            INSERT INTO subscriptions (
                id, name, domains, cost, currency, billing_cycle, 
                status, auto_renewing, next_billing_date, notes, 
                created_at, updated_at, created_by
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            old_id, name, domains_json, cost, currency, billing_cycle,
            status, renewing, next_date, notes, 
            created_at, updated_at, 'migration'
        ))
    
    conn.commit()
    
    # Verify
    cursor.execute("SELECT COUNT(*) FROM subscriptions")
    count = cursor.fetchone()[0]
    print(f"✅ Migrated {count} subscriptions")
    
    cursor.execute("SELECT name, domains FROM subscriptions LIMIT 2")
    samples = cursor.fetchall()
    for name, domains in samples:
        print(f"   {name}: {domains}")
    
    conn.close()
    print("Done!")

if __name__ == "__main__":
    simple_migrate()