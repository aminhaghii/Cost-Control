import os
import sys
import pandas as pd
from datetime import datetime
from math import isnan

# Add current directory to path so app can be imported
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app import create_app
from models import db, Item, Transaction, Hotel, User

app = create_app()

with app.app_context():
    print("Starting data injection process...")

    # Ensure a hotel exists
    hotel = Hotel.query.first()
    if not hotel:
        print("No Hotel found! Creating test Hotel...")
        hotel = Hotel(hotel_name="Test Hotel", hotel_code="TEST", subscription_status='active', db_name='default')
        db.session.add(hotel)
        db.session.commit()
    print(f"Using Hotel: {hotel.hotel_name} (ID: {hotel.id})")

    # Ensure an admin user exists
    user = User.query.filter_by(role='admin').first()
    if not user:
        print("No admin User found! Creating 'admin' user...")
        user = User(username='admin', email='test@pareto.com', role='admin', hotel_id=hotel.id)
        user.set_password('admin123')
        db.session.add(user)
        db.session.commit()
    print(f"Using User: {user.username} (ID: {user.id})")

    # Clear existing data
    print("Deleting ALL existing transactions and items for a clean slate...")
    Transaction.query.delete()
    Item.query.delete()
    db.session.commit()

    print("Loading test dataset 'sample_strategy_data.xlsx'...")
    try:
        df = pd.read_excel('sample_strategy_data.xlsx')
    except Exception as e:
        print(f"Error reading Excel file: {e}")
        sys.exit(1)

    print("Populating initial Item database...")
    items_created = {} # Maps code -> id
    
    # Get unique items to create them
    unique_items = df.drop_duplicates(subset=[df.columns[0]])
    for _, row in unique_items.iterrows():
        item_code = str(row.iloc[0])
        item_name = str(row.iloc[1])
        category = str(row.iloc[3])
        unit = str(row.iloc[8])

        itm = Item(
            hotel_id=hotel.id,
            item_code=item_code,
            item_name_fa=item_name,
            category=category,
            unit=unit,
            base_unit=unit,
            unit_price=0.0,
            current_stock=0 # Will be calculated after inserting all
        )
        db.session.add(itm)
        db.session.flush() # flush to get the ID
        items_created[item_code] = itm.id
    
    db.session.commit()
    print(f"Successfully created {len(items_created)} distinct items.")

    print("Populating transactions...")
    txs = []
    
    # Track inventory dynamically
    stock_map = {itm_id: 0.0 for itm_id in items_created.values()}

    for index, row in df.iterrows():
        item_code = str(row.iloc[0])
        tx_type = str(row.iloc[2]) # خرید یا مصرف
        category = str(row.iloc[3])
        
        # Parse numbers safely
        u_price = row.iloc[4]
        unit_price = float(u_price) if not isnan(float(u_price)) else 0.0
        
        qty = row.iloc[5]
        quantity = float(qty) if not isnan(float(qty)) else 0.0
        
        amt = row.iloc[6]
        amount = float(amt) if not isnan(float(amt)) else 0.0
        
        date_val = row.iloc[7] 
        # Excel date might be string or proper datetime. Handle safely
        if isinstance(date_val, str):
            tx_date = datetime.strptime(date_val.split(' ')[0], '%Y-%m-%d').date()
        else:
            tx_date = date_val.date() if hasattr(date_val, 'date') else date_val

        unit = str(row.iloc[8])
        item_id = items_created[item_code]

        direction = 1 if tx_type == 'خرید' else -1
        signed_quantity = quantity * direction
        
        # update stock map
        stock_map[item_id] += signed_quantity

        # Create Transaction instance
        tx = Transaction(
            hotel_id=hotel.id,
            item_id=item_id,
            user_id=user.id,
            transaction_type=tx_type,
            category=category,
            quantity=quantity,
            direction=direction,
            signed_quantity=signed_quantity,
            unit_price=unit_price,
            total_amount=amount,
            transaction_date=tx_date,
            unit=unit,
            source='manual',
            is_opening_balance=False,
            is_deleted=False
        )
        txs.append(tx)

    # Bulk insert for speed
    db.session.bulk_save_objects(txs)
    db.session.commit()
    
    print(f"Successfully inserted {len(txs)} transactions.")

    print("Updating current stock for all items...")
    # Update item stock limits based on real cumulative logic
    for itm_id, f_stock in stock_map.items():
        itm = Item.query.get(itm_id)
        # Fix negative stocks that might occur since the sample data is blind
        final_stock = f_stock if f_stock > 0 else 0
        itm.current_stock = final_stock
    db.session.commit()
    print("Stock limits updated.")

    print("✅ DATABASE INJECTION COMPLETE!")
