"""
Migration script to add unit_price column to items table
"""
from app import app, db
from sqlalchemy import text

def add_unit_price_column():
    with app.app_context():
        try:
            # Add the unit_price column
            with db.engine.connect() as conn:
                conn.execute(text('ALTER TABLE items ADD COLUMN unit_price NUMERIC(12, 2) DEFAULT 0 NOT NULL'))
                conn.commit()
            print('✅ Column unit_price added successfully to items table')
        except Exception as e:
            if 'duplicate column name' in str(e).lower():
                print('⚠️  Column unit_price already exists')
            else:
                print(f'❌ Error: {e}')
                raise

if __name__ == '__main__':
    add_unit_price_column()
