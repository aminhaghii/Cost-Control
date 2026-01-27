#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Migration script for P0 changes from NEW_CHANGES.md
- Add new tables: import_batches, user_hotels
- Add new columns to transactions
- Add indexes
- Backfill signed_quantity
"""

import os
import sys

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import app
from models import db, Transaction, Item, User, Hotel, TRANSACTION_DIRECTION


def run_migration():
    """Run all P0 migrations"""
    with app.app_context():
        print("="*60)
        print("Running P0 Migrations")
        print("="*60)
        
        # Step 1: Create new tables
        print("\n[1/5] Creating new tables...")
        try:
            db.create_all()
            print("  - Tables created successfully")
        except Exception as e:
            print(f"  - Error creating tables: {e}")
        
        # Step 2: Add new columns to transactions (if not exist)
        print("\n[2/5] Adding new columns to transactions...")
        conn = db.engine.connect()
        
        # Check and add columns
        columns_to_add = [
            ("direction", "INTEGER DEFAULT 1"),
            ("signed_quantity", "FLOAT"),
            ("is_opening_balance", "BOOLEAN DEFAULT 0"),
            ("source", "VARCHAR(50) DEFAULT 'manual'"),
            ("import_batch_id", "INTEGER"),
            ("is_deleted", "BOOLEAN DEFAULT 0"),
            ("deleted_at", "DATETIME"),
        ]
        
        for col_name, col_type in columns_to_add:
            try:
                conn.execute(db.text(f"ALTER TABLE transactions ADD COLUMN {col_name} {col_type}"))
                print(f"  - Added column: {col_name}")
            except Exception as e:
                if "duplicate column" in str(e).lower() or "already exists" in str(e).lower():
                    print(f"  - Column {col_name} already exists")
                else:
                    print(f"  - Error adding {col_name}: {e}")
        
        conn.commit()
        
        # Step 3: Add indexes
        print("\n[3/5] Creating indexes...")
        indexes = [
            ("idx_tx_hotel_date", "transactions", "hotel_id, transaction_date"),
            ("idx_tx_item_date", "transactions", "item_id, transaction_date"),
            ("idx_tx_batch", "transactions", "import_batch_id"),
            ("idx_tx_opening", "transactions", "is_opening_balance"),
            ("idx_tx_deleted", "transactions", "is_deleted"),
            ("idx_item_hotel_code", "items", "hotel_id, item_code"),
        ]
        
        for idx_name, table, columns in indexes:
            try:
                conn.execute(db.text(f"CREATE INDEX IF NOT EXISTS {idx_name} ON {table}({columns})"))
                print(f"  - Created index: {idx_name}")
            except Exception as e:
                print(f"  - Index {idx_name}: {e}")
        
        conn.commit()
        
        # Step 4: Backfill signed_quantity for existing transactions
        print("\n[4/5] Backfilling signed_quantity...")
        transactions = Transaction.query.filter(
            Transaction.signed_quantity == None
        ).all()
        
        updated = 0
        for tx in transactions:
            # Calculate direction based on transaction type
            direction = TRANSACTION_DIRECTION.get(tx.transaction_type, 1)
            tx.direction = direction
            tx.signed_quantity = tx.quantity * direction
            
            # Set source if not set
            if not tx.source:
                tx.source = 'manual'
            
            updated += 1
        
        if updated > 0:
            db.session.commit()
        print(f"  - Updated {updated} transactions")
        
        # Step 5: Verify stock consistency
        print("\n[5/5] Verifying stock consistency...")
        from sqlalchemy import func
        
        mismatches = []
        items = Item.query.all()
        
        for item in items:
            calculated = db.session.query(
                func.coalesce(func.sum(Transaction.signed_quantity), 0)
            ).filter(
                Transaction.item_id == item.id,
                Transaction.is_deleted != True
            ).scalar()
            
            calculated = float(calculated or 0)
            current = float(item.current_stock or 0)
            
            if abs(calculated - current) > 0.001:
                mismatches.append({
                    'item_id': item.id,
                    'item_code': item.item_code,
                    'calculated': calculated,
                    'stored': current,
                    'diff': calculated - current
                })
        
        if mismatches:
            print(f"  - Found {len(mismatches)} stock mismatches:")
            for m in mismatches[:5]:
                print(f"    Item {m['item_code']}: calc={m['calculated']}, stored={m['stored']}, diff={m['diff']}")
            if len(mismatches) > 5:
                print(f"    ... and {len(mismatches) - 5} more")
        else:
            print("  - All stock values are consistent!")
        
        # Close connection
        conn.close()
        
        print("\n" + "="*60)
        print("Migration completed!")
        print("="*60)
        
        return {
            'transactions_updated': updated,
            'stock_mismatches': len(mismatches)
        }


def fix_stock_mismatches():
    """Fix stock mismatches by recalculating from transactions"""
    with app.app_context():
        from services.stock_service import rebuild_stock
        result = rebuild_stock()
        print(f"Fixed {result['fixed']} stock mismatches")
        return result


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description='Run P0 migrations')
    parser.add_argument('--fix-stock', action='store_true', help='Fix stock mismatches')
    args = parser.parse_args()
    
    if args.fix_stock:
        fix_stock_mismatches()
    else:
        run_migration()
