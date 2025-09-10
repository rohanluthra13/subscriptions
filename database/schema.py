#!/usr/bin/env python3
"""
Database schema initialization and migration management.
Extracted from main.py for cleaner separation of concerns.

This module handles:
- Initial database table creation
- Index creation for performance
- Schema migrations for existing databases
"""

import sqlite3
from typing import Optional


def initialize_database(db_path: str = "subscriptions.db") -> None:
    """
    Initialize SQLite database with all required tables and indexes.
    
    Args:
        db_path: Path to the SQLite database file
    """
    conn = sqlite3.connect(db_path, timeout=10.0)
    conn.row_factory = sqlite3.Row  # Enable column access by name - CRITICAL for main.py compatibility
    
    try:
        cursor = conn.cursor()
        
        # Create core tables
        _create_connections_table(cursor)
        _create_processed_emails_table(cursor)
        _create_subscriptions_table(cursor)
        _create_categories_table(cursor)
        
        # Create indexes for performance
        _create_indexes(cursor)
        
        # Apply any pending migrations
        _apply_migrations(cursor)
        
        # Initialize default data
        _initialize_default_categories(cursor)
        
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def _create_connections_table(cursor: sqlite3.Cursor) -> None:
    """Create Gmail OAuth connections table."""
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


def _create_processed_emails_table(cursor: sqlite3.Cursor) -> None:
    """Create processed emails metadata table."""
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


def _create_subscriptions_table(cursor: sqlite3.Cursor) -> None:
    """Create subscriptions table."""
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


def _create_categories_table(cursor: sqlite3.Cursor) -> None:
    """Create categories table."""
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS categories (
            name TEXT PRIMARY KEY,
            is_standard BOOLEAN DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')


def _create_indexes(cursor: sqlite3.Cursor) -> None:
    """Create database indexes for query performance."""
    indexes = [
        ('idx_gmail_message_id', 'processed_emails', 'gmail_message_id'),
        ('idx_sender_domain', 'processed_emails', 'sender_domain'),
        ('idx_email', 'processed_emails', 'email'),
        ('idx_received_at', 'processed_emails', 'received_at DESC'),
        ('idx_content_fetched', 'processed_emails', 'content_fetched'),
    ]
    
    for index_name, table_name, columns in indexes:
        cursor.execute(f'CREATE INDEX IF NOT EXISTS {index_name} ON {table_name}({columns})')


def _apply_migrations(cursor: sqlite3.Cursor) -> None:
    """
    Apply database migrations for existing databases.
    
    Each migration is wrapped in try/except to handle already-applied changes.
    This is safer than checking column existence first.
    """
    migrations = [
        # Add sender_domain column to processed_emails
        "ALTER TABLE processed_emails ADD COLUMN sender_domain TEXT",
        
        # Add email column to processed_emails
        "ALTER TABLE processed_emails ADD COLUMN email TEXT",
        
        # Add content column to processed_emails
        "ALTER TABLE processed_emails ADD COLUMN content TEXT",
        
        # Add content_fetched flag to processed_emails
        "ALTER TABLE processed_emails ADD COLUMN content_fetched BOOLEAN DEFAULT 0",
        
        # Add analyzed_for_subscriptions flag to processed_emails
        "ALTER TABLE processed_emails ADD COLUMN analyzed_for_subscriptions BOOLEAN DEFAULT 0",
        
        # Add website_url to subscriptions
        "ALTER TABLE subscriptions ADD COLUMN website_url TEXT",
        
        # Add logo_data to subscriptions
        "ALTER TABLE subscriptions ADD COLUMN logo_data BLOB",
        
        # Add logo_content_type to subscriptions
        "ALTER TABLE subscriptions ADD COLUMN logo_content_type TEXT",
    ]
    
    for migration in migrations:
        try:
            cursor.execute(migration)
        except sqlite3.OperationalError:
            # Column already exists, skip
            pass
    
    # Special case: Remove unused column if it exists
    # Note: SQLite doesn't support DROP COLUMN in older versions
    # This is kept for documentation but may fail on older SQLite
    try:
        cursor.execute('ALTER TABLE connections DROP COLUMN history_id')
    except sqlite3.OperationalError:
        pass


def _initialize_default_categories(cursor: sqlite3.Cursor) -> None:
    """Initialize standard categories if the table is empty."""
    cursor.execute('SELECT COUNT(*) FROM categories')
    if cursor.fetchone()[0] == 0:
        standard_categories = [
            'content',
            'productivity', 
            'health',
            'other'
        ]
        for category in standard_categories:
            cursor.execute('''
                INSERT INTO categories (name, is_standard)
                VALUES (?, 1)
            ''', (category,))


def get_schema_version(db_path: str = "subscriptions.db") -> int:
    """
    Get the current schema version.
    
    Future enhancement: Track schema version for more robust migrations.
    
    Args:
        db_path: Path to the SQLite database file
        
    Returns:
        Schema version number
    """
    # For now, return 1 as we don't have versioning yet
    # Future: SELECT version FROM schema_version
    return 1


if __name__ == "__main__":
    # Allow running standalone for testing
    import sys
    db_path = sys.argv[1] if len(sys.argv) > 1 else "subscriptions.db"
    print(f"Initializing database at {db_path}")
    initialize_database(db_path)
    print(f"Database initialized successfully. Schema version: {get_schema_version(db_path)}")