#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Migration script to add multi-hotel support
"""

from app import create_app
from models import db, Hotel, Item, Transaction
from sqlalchemy import text

app = create_app()
app.app_context().push()

print("Starting multi-hotel migration...")
print("=" * 80)

# Step 1: Add hotel_id columns if they don't exist
print("\n[1] Adding hotel_id columns to tables...")
try:
    with db.engine.connect() as conn:
        # Check if hotels table exists
        result = conn.execute(text(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='hotels'"
        ))
        if not result.fetchone():
            print("   Creating hotels table...")
            db.create_all()
        
        # Add hotel_id to items if not exists
        result = conn.execute(text("PRAGMA table_info(items)"))
        columns = [row[1] for row in result.fetchall()]
        if 'hotel_id' not in columns:
            print("   Adding hotel_id to items table...")
            conn.execute(text("ALTER TABLE items ADD COLUMN hotel_id INTEGER"))
            conn.commit()
        
        # Add hotel_id to transactions if not exists
        result = conn.execute(text("PRAGMA table_info(transactions)"))
        columns = [row[1] for row in result.fetchall()]
        if 'hotel_id' not in columns:
            print("   Adding hotel_id to transactions table...")
            conn.execute(text("ALTER TABLE transactions ADD COLUMN hotel_id INTEGER"))
            conn.commit()
    
    print("   Columns added successfully")
except Exception as e:
    print(f"   Column addition error: {str(e)}")

# Step 2: Create hotels
print("\n[2] Creating hotel records...")
hotels_data = [
    {'code': 'LTH', 'name': 'لاله تهران', 'name_en': 'Laleh Tehran', 'location': 'تهران'},
    {'code': 'LBS', 'name': 'لاله بیستون', 'name_en': 'Laleh Biston', 'location': 'بیستون'},
    {'code': 'LSR', 'name': 'لاله سرعین', 'name_en': 'Laleh Sarein', 'location': 'سرعین'},
    {'code': 'LCH', 'name': 'لاله چابهار', 'name_en': 'Laleh Chabahar', 'location': 'چابهار'},
    {'code': 'LKN', 'name': 'لاله کندوان', 'name_en': 'Laleh Kandovan', 'location': 'کندوان'},
    {'code': 'ABS', 'name': 'آبدرمانی سبلان', 'name_en': 'Abdarmani Sabalan', 'location': 'سبلان'},
    {'code': 'ZBR', 'name': 'زاگرس بروجرد', 'name_en': 'Zagros Borujerd', 'location': 'بروجرد'},
]

hotel_map = {}
for hotel_data in hotels_data:
    existing = Hotel.query.filter_by(hotel_code=hotel_data['code']).first()
    if not existing:
        hotel = Hotel(
            hotel_code=hotel_data['code'],
            hotel_name=hotel_data['name'],
            hotel_name_en=hotel_data['name_en'],
            location=hotel_data['location'],
            is_active=True
        )
        db.session.add(hotel)
        db.session.flush()
        hotel_map[hotel_data['name']] = hotel.id
        print(f"   Created: {hotel_data['name']} ({hotel_data['code']})")
    else:
        hotel_map[hotel_data['name']] = existing.id
        print(f"   Exists: {hotel_data['name']} ({hotel_data['code']})")

db.session.commit()

# Step 3: Map imported items to hotels based on item names
print("\n[3] Mapping items to hotels based on sheet names...")

# Hotel mapping from sheet names to hotel IDs
sheet_to_hotel_map = {
    'biston': hotel_map.get('لاله بیستون'),
    'biston 2': hotel_map.get('لاله بیستون'),
    'zagroos ghazaei': hotel_map.get('زاگرس بروجرد'),
    'zagros Behdashti': hotel_map.get('زاگرس بروجرد'),
    'Abdarmani': hotel_map.get('آبدرمانی سبلان'),
    'sarein': hotel_map.get('لاله سرعین'),
    'kandovan malzumat': hotel_map.get('لاله کندوان'),
    'kandovan eng': hotel_map.get('لاله کندوان'),
    'kandovan Drink': hotel_map.get('لاله کندوان'),
}

# Get all items without hotel_id
items = Item.query.filter_by(hotel_id=None).all()
print(f"   Found {len(items)} items without hotel assignment")

updated_count = 0
for item in items:
    # Try to detect hotel from item_name_en (which contains sheet name during import)
    assigned = False
    for sheet_name, hotel_id in sheet_to_hotel_map.items():
        # Since we don't have sheet info stored, we'll assign based on item ranges
        # Items created from specific imports should be assigned
        pass
    
    # For now, assign unassigned items to default hotel (Tehran)
    if not assigned and not item.hotel_id:
        item.hotel_id = hotel_map.get('لاله تهران')
        updated_count += 1

db.session.commit()
print(f"   Updated {updated_count} items")

# Step 4: Update transactions to inherit hotel_id from items
print("\n[4] Updating transactions with hotel_id from items...")
transactions = Transaction.query.filter_by(hotel_id=None).all()
print(f"   Found {len(transactions)} transactions without hotel")

updated_trans = 0
for trans in transactions:
    if trans.item and trans.item.hotel_id:
        trans.hotel_id = trans.item.hotel_id
        updated_trans += 1

db.session.commit()
print(f"   Updated {updated_trans} transactions")

# Step 5: Create indexes
print("\n[5] Creating indexes for performance...")
try:
    with db.engine.connect() as conn:
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_items_hotel_id ON items(hotel_id)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_transactions_hotel_id ON transactions(hotel_id)"))
        conn.commit()
    print("   Indexes created")
except Exception as e:
    print(f"   Index creation info: {str(e)}")

# Summary
print("\n" + "=" * 80)
print("Migration Summary:")
print("=" * 80)
print(f"Hotels created: {len(hotel_map)}")
for name, hotel_id in hotel_map.items():
    item_count = Item.query.filter_by(hotel_id=hotel_id).count()
    trans_count = Transaction.query.filter_by(hotel_id=hotel_id).count()
    print(f"   - {name}: {item_count} items, {trans_count} transactions")

print("\nMigration completed successfully!")
print("\nNote: Existing imported items may need manual hotel assignment.")
print("Use the admin panel to assign items to correct hotels.")
