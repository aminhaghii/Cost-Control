"""
Warehouse Management Migration Script
Adds new tables and columns for warehouse management features
"""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app
from models import db, Hotel, WarehouseSettings

def run_migration():
    """Run warehouse management migration"""
    app = create_app()
    
    with app.app_context():
        print("Starting warehouse management migration...")
        
        # Create all new tables
        print("Creating new tables...")
        db.create_all()
        
        # Add new columns to transactions table if they don't exist
        print("Adding new columns to transactions...")
        try:
            db.session.execute(db.text("""
                ALTER TABLE transactions ADD COLUMN waste_reason VARCHAR(50)
            """))
        except Exception as e:
            if 'duplicate column' not in str(e).lower():
                print(f"  waste_reason: {e}")
        
        try:
            db.session.execute(db.text("""
                ALTER TABLE transactions ADD COLUMN waste_reason_detail TEXT
            """))
        except Exception as e:
            if 'duplicate column' not in str(e).lower():
                print(f"  waste_reason_detail: {e}")
        
        try:
            db.session.execute(db.text("""
                ALTER TABLE transactions ADD COLUMN reference_number VARCHAR(100)
            """))
        except Exception as e:
            if 'duplicate column' not in str(e).lower():
                print(f"  reference_number: {e}")
        
        try:
            db.session.execute(db.text("""
                ALTER TABLE transactions ADD COLUMN destination_department VARCHAR(100)
            """))
        except Exception as e:
            if 'duplicate column' not in str(e).lower():
                print(f"  destination_department: {e}")
        
        try:
            db.session.execute(db.text("""
                ALTER TABLE transactions ADD COLUMN requires_approval BOOLEAN DEFAULT 0
            """))
        except Exception as e:
            if 'duplicate column' not in str(e).lower():
                print(f"  requires_approval: {e}")
        
        try:
            db.session.execute(db.text("""
                ALTER TABLE transactions ADD COLUMN approved_by_id INTEGER REFERENCES users(id)
            """))
        except Exception as e:
            if 'duplicate column' not in str(e).lower():
                print(f"  approved_by_id: {e}")
        
        try:
            db.session.execute(db.text("""
                ALTER TABLE transactions ADD COLUMN approved_at DATETIME
            """))
        except Exception as e:
            if 'duplicate column' not in str(e).lower():
                print(f"  approved_at: {e}")
        
        try:
            db.session.execute(db.text("""
                ALTER TABLE transactions ADD COLUMN approval_status VARCHAR(20) DEFAULT 'not_required'
            """))
        except Exception as e:
            if 'duplicate column' not in str(e).lower():
                print(f"  approval_status: {e}")
        
        # Add new columns to alerts table
        print("Adding new columns to alerts...")
        try:
            db.session.execute(db.text("""
                ALTER TABLE alerts ADD COLUMN hotel_id INTEGER REFERENCES hotels(id)
            """))
        except Exception as e:
            if 'duplicate column' not in str(e).lower():
                print(f"  hotel_id: {e}")
        
        try:
            db.session.execute(db.text("""
                ALTER TABLE alerts ADD COLUMN related_transaction_id INTEGER REFERENCES transactions(id)
            """))
        except Exception as e:
            if 'duplicate column' not in str(e).lower():
                print(f"  related_transaction_id: {e}")
        
        try:
            db.session.execute(db.text("""
                ALTER TABLE alerts ADD COLUMN related_count_id INTEGER REFERENCES inventory_counts(id)
            """))
        except Exception as e:
            if 'duplicate column' not in str(e).lower():
                print(f"  related_count_id: {e}")
        
        try:
            db.session.execute(db.text("""
                ALTER TABLE alerts ADD COLUMN threshold_value NUMERIC(12,3)
            """))
        except Exception as e:
            if 'duplicate column' not in str(e).lower():
                print(f"  threshold_value: {e}")
        
        try:
            db.session.execute(db.text("""
                ALTER TABLE alerts ADD COLUMN actual_value NUMERIC(12,3)
            """))
        except Exception as e:
            if 'duplicate column' not in str(e).lower():
                print(f"  actual_value: {e}")
        
        try:
            db.session.execute(db.text("""
                ALTER TABLE alerts ADD COLUMN status VARCHAR(20) DEFAULT 'active'
            """))
        except Exception as e:
            if 'duplicate column' not in str(e).lower():
                print(f"  status: {e}")
        
        try:
            db.session.execute(db.text("""
                ALTER TABLE alerts ADD COLUMN acknowledged_by_id INTEGER REFERENCES users(id)
            """))
        except Exception as e:
            if 'duplicate column' not in str(e).lower():
                print(f"  acknowledged_by_id: {e}")
        
        try:
            db.session.execute(db.text("""
                ALTER TABLE alerts ADD COLUMN acknowledged_at DATETIME
            """))
        except Exception as e:
            if 'duplicate column' not in str(e).lower():
                print(f"  acknowledged_at: {e}")
        
        db.session.commit()
        
        # Create default WarehouseSettings for existing hotels
        print("Creating default warehouse settings for hotels...")
        hotels = Hotel.query.all()
        for hotel in hotels:
            existing = WarehouseSettings.query.filter_by(hotel_id=hotel.id).first()
            if not existing:
                settings = WarehouseSettings(hotel_id=hotel.id)
                db.session.add(settings)
                print(f"  Created settings for hotel: {hotel.hotel_name}")
        
        db.session.commit()
        
        print("\nMigration completed successfully!")
        print("New tables created:")
        print("  - inventory_counts")
        print("  - warehouse_settings")
        print("\nNew columns added to transactions:")
        print("  - waste_reason, waste_reason_detail")
        print("  - reference_number, destination_department")
        print("  - requires_approval, approved_by_id, approved_at, approval_status")
        print("\nNew columns added to alerts:")
        print("  - hotel_id, related_transaction_id, related_count_id")
        print("  - threshold_value, actual_value, status")
        print("  - acknowledged_by_id, acknowledged_at")


if __name__ == '__main__':
    run_migration()
