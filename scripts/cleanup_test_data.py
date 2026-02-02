#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Database Cleanup Script
=======================
Safely removes all test data from the database while preserving schema.

CAUTION: This will delete ALL data including:
- Transactions
- Inventory Counts
- Alerts
- Items
- Users (except admin)
- Hotels (except MAIN)

Usage:
    python scripts/cleanup_test_data.py
    
    # With confirmation skip (USE WITH CAUTION):
    python scripts/cleanup_test_data.py --force
"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import create_app
from models import db, User, Hotel, Item, Transaction, InventoryCount, Alert, WarehouseSettings, AuditLog
from sqlalchemy import text

app = create_app()


def confirm_cleanup(force=False):
    """Ask user for confirmation"""
    if force:
        return True
    
    print("\n" + "="*60)
    print("⚠️  WARNING: DATABASE CLEANUP")
    print("="*60)
    print("\nThis will DELETE ALL data from the database:")
    print("  - All Transactions")
    print("  - All Inventory Counts")
    print("  - All Alerts")
    print("  - All Items")
    print("  - All Users (except admin)")
    print("  - All Hotels (except MAIN)")
    print("\nThis action CANNOT be undone!")
    print("="*60)
    
    response = input("\nType 'DELETE ALL DATA' to confirm: ")
    return response == 'DELETE ALL DATA'


def cleanup_database():
    """Remove all test data"""
    print("\nStarting database cleanup...")
    
    try:
        # Disable foreign key constraints temporarily (SQLite)
        db.session.execute(text('PRAGMA foreign_keys = OFF'))
        
        # 1. Delete Audit Logs
        count = AuditLog.query.delete()
        print(f"  ✓ Deleted {count} audit logs")
        
        # 2. Delete Alerts
        count = Alert.query.delete()
        print(f"  ✓ Deleted {count} alerts")
        
        # 3. Delete Inventory Counts
        count = InventoryCount.query.delete()
        print(f"  ✓ Deleted {count} inventory counts")
        
        # 4. Delete Transactions
        count = Transaction.query.delete()
        print(f"  ✓ Deleted {count} transactions")
        
        # 5. Delete Items
        count = Item.query.delete()
        print(f"  ✓ Deleted {count} items")
        
        # 6. Delete Warehouse Settings
        count = WarehouseSettings.query.delete()
        print(f"  ✓ Deleted {count} warehouse settings")
        
        # 7. Delete Users (except admin)
        count = User.query.filter(User.username != 'admin').delete()
        print(f"  ✓ Deleted {count} users (kept admin)")
        
        # 8. Delete Hotels (except MAIN)
        count = Hotel.query.filter(Hotel.hotel_code != 'MAIN').delete()
        print(f"  ✓ Deleted {count} hotels (kept MAIN)")
        
        # Re-enable foreign key constraints
        db.session.execute(text('PRAGMA foreign_keys = ON'))
        
        # Commit all changes
        db.session.commit()
        
        # Vacuum database to reclaim space
        print("\n  Optimizing database...")
        db.session.execute(text('VACUUM'))
        
        print("\n✓ Database cleanup completed successfully!")
        return True
        
    except Exception as e:
        print(f"\n✗ Error during cleanup: {e}")
        import traceback
        traceback.print_exc()
        db.session.rollback()
        return False


def show_final_status():
    """Show remaining data in database"""
    print("\n" + "="*60)
    print("Final Database Status:")
    print("="*60)
    print(f"  Users: {User.query.count()}")
    print(f"  Hotels: {Hotel.query.count()}")
    print(f"  Items: {Item.query.count()}")
    print(f"  Transactions: {Transaction.query.count()}")
    print(f"  Inventory Counts: {InventoryCount.query.count()}")
    print(f"  Alerts: {Alert.query.count()}")
    print(f"  Audit Logs: {AuditLog.query.count()}")
    print("="*60)


def main():
    """Main cleanup function"""
    force = '--force' in sys.argv
    
    print("="*60)
    print("Database Cleanup Script")
    print("="*60)
    
    with app.app_context():
        # Show current status
        print("\nCurrent Database Status:")
        print(f"  Users: {User.query.count()}")
        print(f"  Hotels: {Hotel.query.count()}")
        print(f"  Items: {Item.query.count()}")
        print(f"  Transactions: {Transaction.query.count()}")
        print(f"  Inventory Counts: {InventoryCount.query.count()}")
        print(f"  Alerts: {Alert.query.count()}")
        
        # Confirm
        if not confirm_cleanup(force):
            print("\n✗ Cleanup cancelled by user")
            return 1
        
        # Execute cleanup
        success = cleanup_database()
        
        if success:
            show_final_status()
            print("\n✓ You can now run populate_test_data.py to add fresh test data")
            return 0
        else:
            return 1


if __name__ == '__main__':
    sys.exit(main())
