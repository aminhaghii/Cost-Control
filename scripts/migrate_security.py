#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Migration script to add security columns to users table
Run this script to update the database with new security features
"""
import sqlite3
import os

# Database path
db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'database', 'inventory.db')

def migrate():
    print("Starting security migration...")
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Get existing columns
    cursor.execute("PRAGMA table_info(users)")
    existing_columns = [col[1] for col in cursor.fetchall()]
    
    # New columns to add
    new_columns = [
        ("totp_secret", "VARCHAR(32)"),
        ("is_2fa_enabled", "BOOLEAN DEFAULT 0"),
        ("password_changed_at", "DATETIME"),
        ("must_change_password", "BOOLEAN DEFAULT 0"),
        ("failed_login_attempts", "INTEGER DEFAULT 0"),
        ("locked_until", "DATETIME"),
        ("last_failed_login", "DATETIME"),
        ("password_history", "TEXT"),
    ]
    
    added = 0
    for col_name, col_type in new_columns:
        if col_name not in existing_columns:
            try:
                cursor.execute(f"ALTER TABLE users ADD COLUMN {col_name} {col_type}")
                print(f"  Column added: {col_name}")
                added += 1
            except sqlite3.OperationalError as e:
                print(f"  Error adding {col_name}: {e}")
        else:
            print(f"  Column already exists: {col_name}")
    
    conn.commit()
    conn.close()
    
    print(f"\nMigration completed. Added {added} new columns.")

if __name__ == '__main__':
    migrate()
