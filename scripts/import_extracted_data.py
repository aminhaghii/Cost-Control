#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Import items from extracted_data.txt to database
"""

import os
import sys
import re
from decimal import Decimal
from datetime import date, timedelta
import random

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import create_app
from models import db, Item, Transaction, Hotel, User

def parse_extracted_data(file_path):
    """Parse extracted_data.txt and extract item information"""
    items = []
    
    with open(file_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    
    for line in lines:
        # Look for data lines starting with "سطر X:" and containing |
        if line.startswith('سطر') and '|' in line:
            # Remove "سطر X: " prefix
            line = re.sub(r'^سطر \d+:\s*', '', line)
            
            parts = [p.strip() for p in line.split('|')]
            
            # Skip header rows
            if len(parts) < 3:
                continue
            if parts[0] in ['ردیف', 'نام کالا', '']:
                continue
            
            try:
                # Try to parse first column as number (row number)
                int(parts[0])
                
                if len(parts) >= 3:
                    name = parts[1]
                    unit = parts[2]
                    
                    # Skip empty names or placeholders
                    if not name or name == '--' or name.strip() == '':
                        continue
                    
                    # Extract price (usually last column with numeric value)
                    price = 0
                    for i in range(len(parts)-1, 2, -1):
                        try:
                            price_str = parts[i].replace(',', '').replace(' ', '').strip()
                            if price_str and price_str != '--' and price_str != 'خریداری توسط شرکت' and price_str != '':
                                price = float(price_str)
                                if price > 0:
                                    break
                        except:
                            continue
                    
                    # Extract stock (usually around column 6-7)
                    stock = 0
                    if len(parts) > 6:
                        try:
                            stock_str = parts[6].replace(',', '').replace(' ', '').strip()
                            if stock_str and stock_str != '--' and stock_str != 'کمتر از یک ماه' and stock_str != '':
                                stock = float(stock_str)
                        except:
                            pass
                    
                    items.append({
                        'name': name,
                        'unit': unit,
                        'price': price,
                        'stock': abs(stock) if stock else 0
                    })
            except (ValueError, IndexError):
                continue
    
    return items

def import_items():
    """Import items to database"""
    app = create_app()
    
    with app.app_context():
        # Get or create hotel
        hotel = Hotel.query.filter_by(hotel_code='MAIN').first()
        if not hotel:
            hotel = Hotel(
                hotel_code='MAIN',
                hotel_name='هتل اصلی',
                is_active=True
            )
            db.session.add(hotel)
            db.session.commit()
        
        hotel_id = hotel.id
        
        # Get admin user
        admin = User.query.filter_by(username='admin').first()
        if not admin:
            print("Error: Admin user not found. Run init_db.py first.")
            return
        
        # Parse data file
        data_file = os.path.join(os.path.dirname(__file__), '..', 'reports', 'Pareto', 'extracted_data.txt')
        if not os.path.exists(data_file):
            print(f"Error: File not found: {data_file}")
            return
        
        print(f"Parsing {data_file}...")
        parsed_items = parse_extracted_data(data_file)
        print(f"Found {len(parsed_items)} items")
        
        # Determine category based on keywords
        food_keywords = ['برنج', 'گوشت', 'مرغ', 'ماهی', 'پنیر', 'ماست', 'کره', 'شیر', 'تخم', 'نان', 
                        'آرد', 'شکر', 'نمک', 'روغن', 'زیتون', 'سوسیس', 'کالباس', 'عسل', 'مربا',
                        'چای', 'قهوه', 'نوشابه', 'آب', 'دوغ', 'شربت', 'عدس', 'لوبیا', 'نخود',
                        'سبزی', 'گوجه', 'پیاز', 'سیب', 'پرتقال', 'موز', 'خیار', 'کاهو', 'فلفل',
                        'سیر', 'هویج', 'زعفران', 'زرشک', 'خرما', 'کشمش', 'بستنی', 'کیک', 'بیسکوئیت']
        
        imported_count = 0
        skipped_count = 0
        
        # Get max existing item code globally to avoid conflicts
        max_food_code = db.session.query(db.func.max(Item.item_code)).filter(
            Item.item_code.like('F%')
        ).scalar()
        max_nonfood_code = db.session.query(db.func.max(Item.item_code)).filter(
            Item.item_code.like('NF%')
        ).scalar()
        
        food_counter = 1
        nonfood_counter = 1
        
        if max_food_code:
            try:
                food_counter = int(max_food_code[1:]) + 1
            except:
                pass
        
        if max_nonfood_code:
            try:
                nonfood_counter = int(max_nonfood_code[2:]) + 1
            except:
                pass
        
        with db.session.no_autoflush:
            for item_data in parsed_items:
                name = item_data['name']
                
                # Check if item already exists by name
                existing = Item.query.filter_by(
                    hotel_id=hotel_id,
                    item_name_fa=name
                ).first()
                
                if existing:
                    skipped_count += 1
                    continue
                
                # Determine category
                category = 'NonFood'
                for keyword in food_keywords:
                    if keyword in name:
                        category = 'Food'
                        break
                
                # Generate unique item code
                if category == 'Food':
                    item_code = f"F{food_counter:04d}"
                    food_counter += 1
                else:
                    item_code = f"NF{nonfood_counter:04d}"
                    nonfood_counter += 1
                
                # Create item
                item = Item(
                    hotel_id=hotel_id,
                    item_code=item_code,
                    item_name_fa=name,
                    category=category,
                    unit=item_data['unit'],
                    current_stock=Decimal(str(item_data['stock'])),
                    min_stock=Decimal('10'),
                    max_stock=Decimal('500'),
                    is_active=True
                )
                
                db.session.add(item)
                imported_count += 1
                
                if imported_count % 50 == 0:
                    try:
                        db.session.flush()
                        print(f"Imported {imported_count} items...")
                    except Exception as e:
                        print(f"Error at item {imported_count}: {e}")
                        db.session.rollback()
                        break
        
        db.session.commit()
        print(f"\n✅ Import completed:")
        print(f"   - Imported: {imported_count} items")
        print(f"   - Skipped (duplicates): {skipped_count} items")
        
        # Create sample transactions
        print("\nCreating sample transactions...")
        create_sample_transactions(hotel_id, admin.id)

def create_sample_transactions(hotel_id, user_id):
    """Create sample transactions for history"""
    items = Item.query.filter_by(hotel_id=hotel_id, is_active=True).limit(50).all()
    
    if not items:
        print("No items found to create transactions")
        return
    
    transaction_types = ['خرید', 'مصرف', 'ضایعات']
    type_weights = [0.6, 0.3, 0.1]
    
    transactions_count = 0
    
    # Create transactions for last 30 days
    for days_ago in range(30, -1, -1):
        trans_date = date.today() - timedelta(days=days_ago)
        
        # Random 3-8 transactions per day
        daily_count = random.randint(3, 8)
        
        for _ in range(daily_count):
            item = random.choice(items)
            trans_type = random.choices(transaction_types, weights=type_weights)[0]
            
            # Random price based on typical ranges
            if 'برنج' in item.item_name_fa or 'گوشت' in item.item_name_fa:
                unit_price = random.randint(1000000, 5000000)
            elif 'نوشابه' in item.item_name_fa or 'آب' in item.item_name_fa:
                unit_price = random.randint(50000, 300000)
            else:
                unit_price = random.randint(100000, 2000000)
            
            # Random quantity
            if trans_type == 'خرید':
                quantity = round(random.uniform(5, 30), 2)
            elif trans_type == 'مصرف':
                quantity = round(random.uniform(1, 15), 2)
            else:  # ضایعات
                quantity = round(random.uniform(0.5, 5), 2)
            
            total_amount = Decimal(str(quantity)) * Decimal(str(unit_price))
            
            transaction = Transaction(
                hotel_id=hotel_id,
                transaction_date=trans_date,
                item_id=item.id,
                transaction_type=trans_type,
                category=item.category,
                quantity=Decimal(str(quantity)),
                unit_price=Decimal(str(unit_price)),
                total_amount=total_amount,
                user_id=user_id,
                is_opening_balance=False
            )
            
            db.session.add(transaction)
            transactions_count += 1
    
    db.session.commit()
    print(f"✅ Created {transactions_count} sample transactions")

if __name__ == '__main__':
    import_items()
