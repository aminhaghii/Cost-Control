#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Migration Script for NEW_CHANGES.md (P0/P1 December 2025)

This script applies the following changes:
- P0-1: ImportBatch is_active field, remove unique on file_hash
- P0-2/P0-3: Transaction direction/signed_quantity consistency
- P0-4: Transaction money columns to Numeric (handled by SQLAlchemy)
- P1-4: HotelSheetAlias table
- P1-5: Item.base_unit, Transaction.unit, conversion_factor_to_base

Run with: python migrate_new_changes.py
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import app
from models import db, Item, Transaction, ImportBatch, HotelSheetAlias, Hotel
from sqlalchemy import text, inspect


def check_column_exists(table_name, column_name):
    """Check if a column exists in a table"""
    with app.app_context():
        inspector = inspect(db.engine)
        columns = [c['name'] for c in inspector.get_columns(table_name)]
        return column_name in columns


def check_table_exists(table_name):
    """Check if a table exists"""
    with app.app_context():
        inspector = inspect(db.engine)
        return table_name in inspector.get_table_names()


def run_migration():
    """Run all migrations"""
    print("\n" + "="*60)
    print("NEW CHANGES MIGRATION (December 2025)")
    print("="*60)
    
    with app.app_context():
        # Step 1: Create hotel_sheet_aliases table if not exists
        print("\n[Step 1] Creating hotel_sheet_aliases table...")
        if not check_table_exists('hotel_sheet_aliases'):
            try:
                db.session.execute(text('''
                    CREATE TABLE hotel_sheet_aliases (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        hotel_id INTEGER NOT NULL,
                        alias_text VARCHAR(100) NOT NULL UNIQUE,
                        description VARCHAR(255),
                        is_active BOOLEAN DEFAULT 1,
                        created_at DATETIME,
                        created_by_id INTEGER,
                        FOREIGN KEY (hotel_id) REFERENCES hotels(id),
                        FOREIGN KEY (created_by_id) REFERENCES users(id)
                    )
                '''))
                db.session.commit()
                print("  ✓ Created hotel_sheet_aliases table")
            except Exception as e:
                print(f"  ✗ Error creating table: {e}")
                db.session.rollback()
        else:
            print("  - Table already exists")
        
        # Step 2: Add is_active to import_batches if not exists
        print("\n[Step 2] Adding is_active to import_batches...")
        if not check_column_exists('import_batches', 'is_active'):
            try:
                db.session.execute(text(
                    'ALTER TABLE import_batches ADD COLUMN is_active BOOLEAN DEFAULT 1'
                ))
                db.session.commit()
                print("  ✓ Added is_active column")
            except Exception as e:
                print(f"  ✗ Error: {e}")
                db.session.rollback()
        else:
            print("  - Column already exists")
        
        # Step 3: Add replaces_batch_id to import_batches if not exists
        print("\n[Step 3] Adding replaces_batch_id to import_batches...")
        if not check_column_exists('import_batches', 'replaces_batch_id'):
            try:
                db.session.execute(text(
                    'ALTER TABLE import_batches ADD COLUMN replaces_batch_id INTEGER REFERENCES import_batches(id)'
                ))
                db.session.commit()
                print("  ✓ Added replaces_batch_id column")
            except Exception as e:
                print(f"  ✗ Error: {e}")
                db.session.rollback()
        else:
            print("  - Column already exists")
        
        # Step 4: Add base_unit to items if not exists
        print("\n[Step 4] Adding base_unit to items...")
        if not check_column_exists('items', 'base_unit'):
            try:
                db.session.execute(text(
                    'ALTER TABLE items ADD COLUMN base_unit VARCHAR(20)'
                ))
                db.session.commit()
                print("  ✓ Added base_unit column")
            except Exception as e:
                print(f"  ✗ Error: {e}")
                db.session.rollback()
        else:
            print("  - Column already exists")
        
        # Step 5: Add unit to transactions if not exists
        print("\n[Step 5] Adding unit to transactions...")
        if not check_column_exists('transactions', 'unit'):
            try:
                db.session.execute(text(
                    'ALTER TABLE transactions ADD COLUMN unit VARCHAR(20)'
                ))
                db.session.commit()
                print("  ✓ Added unit column")
            except Exception as e:
                print(f"  ✗ Error: {e}")
                db.session.rollback()
        else:
            print("  - Column already exists")
        
        # Step 6: Add conversion_factor_to_base to transactions if not exists
        print("\n[Step 6] Adding conversion_factor_to_base to transactions...")
        if not check_column_exists('transactions', 'conversion_factor_to_base'):
            try:
                db.session.execute(text(
                    'ALTER TABLE transactions ADD COLUMN conversion_factor_to_base FLOAT DEFAULT 1.0'
                ))
                db.session.commit()
                print("  ✓ Added conversion_factor_to_base column")
            except Exception as e:
                print(f"  ✗ Error: {e}")
                db.session.rollback()
        else:
            print("  - Column already exists")
        
        # Step 7: Seed default sheet aliases from hardcoded mapping
        print("\n[Step 7] Seeding default sheet aliases...")
        hotels = {h.hotel_name: h.id for h in Hotel.query.all()}
        
        default_aliases = [
            ('biston', 'لاله بیستون'),
            ('biston 2', 'لاله بیستون'),
            ('zagroos ghazaei', 'زاگرس بروجرد'),
            ('zagros Behdashti', 'زاگرس بروجرد'),
            ('Abdarmani', 'آبدرمانی سبلان'),
            ('sarein', 'لاله سرعین'),
            ('kandovan malzumat', 'لاله کندوان'),
            ('kandovan eng', 'لاله کندوان'),
            ('kandovan Drink', 'لاله کندوان'),
        ]
        
        aliases_created = 0
        for alias_text, hotel_name in default_aliases:
            hotel_id = hotels.get(hotel_name)
            if hotel_id:
                existing = HotelSheetAlias.query.filter_by(alias_text=alias_text).first()
                if not existing:
                    try:
                        alias = HotelSheetAlias(
                            hotel_id=hotel_id,
                            alias_text=alias_text,
                            description=f'Auto-migrated from hardcoded mapping'
                        )
                        db.session.add(alias)
                        aliases_created += 1
                    except Exception as e:
                        print(f"  ✗ Error creating alias '{alias_text}': {e}")
        
        if aliases_created > 0:
            db.session.commit()
            print(f"  ✓ Created {aliases_created} sheet aliases")
        else:
            print("  - All aliases already exist or hotels not found")
        
        # Step 8: Backfill base_unit for items
        print("\n[Step 8] Backfilling base_unit for items...")
        from models.item import UNIT_CONVERSIONS, BASE_UNITS
        
        items_updated = 0
        items = Item.query.filter(Item.base_unit == None).all()
        for item in items:
            if item.unit in UNIT_CONVERSIONS:
                unit_type, _ = UNIT_CONVERSIONS[item.unit]
                item.base_unit = BASE_UNITS.get(unit_type, item.unit)
                items_updated += 1
            else:
                item.base_unit = item.unit
                items_updated += 1
        
        if items_updated > 0:
            db.session.commit()
            print(f"  ✓ Updated {items_updated} items with base_unit")
        else:
            print("  - No items need base_unit update")
        
        # Step 9: Ensure all transactions have valid direction
        print("\n[Step 9] Validating transaction direction values...")
        invalid_directions = Transaction.query.filter(
            ~Transaction.direction.in_([1, -1])
        ).count()
        
        if invalid_directions > 0:
            # Fix invalid directions
            Transaction.query.filter(
                ~Transaction.direction.in_([1, -1])
            ).update({'direction': 1}, synchronize_session=False)
            db.session.commit()
            print(f"  ✓ Fixed {invalid_directions} transactions with invalid direction")
        else:
            print("  - All transactions have valid direction")
        
        # Step 10: Ensure signed_quantity consistency
        print("\n[Step 10] Checking signed_quantity consistency...")
        mismatches = 0
        transactions = Transaction.query.filter(Transaction.is_deleted != True).all()
        for tx in transactions:
            expected = tx.quantity * tx.direction
            if tx.signed_quantity is None or abs(tx.signed_quantity - expected) > 0.001:
                tx.signed_quantity = expected
                mismatches += 1
        
        if mismatches > 0:
            db.session.commit()
            print(f"  ✓ Fixed {mismatches} transactions with inconsistent signed_quantity")
        else:
            print("  - All signed_quantity values are consistent")
        
        # Step 11: Mark existing import batches as active
        print("\n[Step 11] Marking existing import batches as active...")
        batches_updated = ImportBatch.query.filter(
            ImportBatch.is_active == None
        ).update({'is_active': True}, synchronize_session=False)
        db.session.commit()
        if batches_updated:
            print(f"  ✓ Marked {batches_updated} batches as active")
        else:
            print("  - All batches already have is_active set")

        # Step 12: Ensure partial unique index on (file_hash) WHERE is_active=1
        print("\n[Step 12] Ensuring partial unique index for active import batches...")
        try:
            # Drop legacy composite index if it exists (non-partial)
            db.session.execute(text('DROP INDEX IF EXISTS idx_import_batch_hash_active'))
            db.session.commit()
            print("  - Dropped legacy idx_import_batch_hash_active (if existed)")
        except Exception as e:
            print(f"  ✗ Warning dropping legacy index: {e}")
            db.session.rollback()

        try:
            db.session.execute(text('''
                CREATE UNIQUE INDEX IF NOT EXISTS idx_import_batches_active_hash
                ON import_batches(file_hash) WHERE is_active = 1
            '''))
            db.session.commit()
            print("  ✓ Created partial unique index idx_import_batches_active_hash")
        except Exception as e:
            print(f"  ✗ Error creating partial unique index: {e}")
            db.session.rollback()
        
        print("\n" + "="*60)
        print("MIGRATION COMPLETED SUCCESSFULLY")
        print("="*60)
        
        # Summary
        print("\nSummary:")
        print(f"  - HotelSheetAlias records: {HotelSheetAlias.query.count()}")
        print(f"  - ImportBatches: {ImportBatch.query.count()}")
        print(f"  - Items with base_unit: {Item.query.filter(Item.base_unit != None).count()}")
        print(f"  - Transactions: {Transaction.query.count()}")


if __name__ == '__main__':
    run_migration()
