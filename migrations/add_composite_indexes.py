#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
BUG-FIX #6: Add composite indexes for better query performance
Run this migration to create indexes on transactions table
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app
from models import db

def create_composite_indexes():
    """Create composite indexes for common query patterns"""
    
    with app.app_context():
        # Get database connection
        conn = db.engine.connect()
        
        try:
            # Index for date + hotel queries (common in reports)
            conn.execute(db.text("""
                CREATE INDEX IF NOT EXISTS ix_transactions_date_hotel 
                ON transactions (transaction_date, hotel_id)
            """))
            print("✅ Created index: ix_transactions_date_hotel")
            
            # Index for hotel + item + deleted status (common in stock queries)
            conn.execute(db.text("""
                CREATE INDEX IF NOT EXISTS ix_transactions_hotel_item 
                ON transactions (hotel_id, item_id, is_deleted)
            """))
            print("✅ Created index: ix_transactions_hotel_item")
            
            # Index for batch + deleted status (for import rollback)
            conn.execute(db.text("""
                CREATE INDEX IF NOT EXISTS ix_transactions_batch_deleted 
                ON transactions (import_batch_id, is_deleted)
            """))
            print("✅ Created index: ix_transactions_batch_deleted")
            
            conn.commit()
            print("✅ All composite indexes created successfully")
            
        except Exception as e:
            conn.rollback()
            print(f"❌ Error creating indexes: {e}")
            raise
        finally:
            conn.close()

def drop_composite_indexes():
    """Drop composite indexes (rollback migration)"""
    
    with app.app_context():
        conn = db.engine.connect()
        
        try:
            conn.execute(db.text("DROP INDEX IF EXISTS ix_transactions_date_hotel"))
            conn.execute(db.text("DROP INDEX IF EXISTS ix_transactions_hotel_item"))
            conn.execute(db.text("DROP INDEX IF EXISTS ix_transactions_batch_deleted"))
            
            conn.commit()
            print("✅ All composite indexes dropped successfully")
            
        except Exception as e:
            conn.rollback()
            print(f"❌ Error dropping indexes: {e}")
            raise
        finally:
            conn.close()

if __name__ == '__main__':
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == 'down':
        print("Rolling back migration...")
        drop_composite_indexes()
    else:
        print("Running migration...")
        create_composite_indexes()
