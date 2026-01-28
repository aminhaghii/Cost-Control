#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Full Database Seed Script - Clears data and loads 1600+ items from Excel
"""

import os, sys, random
from datetime import date, timedelta
from decimal import Decimal

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd
from app import create_app
from models import db
from models.item import Item
from models.transaction import Transaction, WASTE_REASONS, DEPARTMENTS
from models.alert import Alert
from models.chat_history import ChatHistory
from models.hotel import Hotel
from models.user import User
from models.inventory_count import InventoryCount

HOTEL_MAPPING = {
    'biston': 'هتل بیستون',
    'biston 2': 'هتل بیستون ۲', 
    'zagroos ghazaei': 'هتل زاگرس غذایی',
    'zagros Behdashti': 'هتل زاگرس بهداشتی',
    'Abdarmani': 'آبدرمانی',
    'sarein': 'هتل سرعین',
    'kandovan malzumat': 'هتل کندوان ملزومات',
    'kandovan eng': 'هتل کندوان مهندسی',
    'kandovan Drink': 'هتل کندوان نوشیدنی',
}

CATEGORY_MAPPING = {
    'biston': 'Food', 'biston 2': 'NonFood',
    'zagroos ghazaei': 'Food', 'zagros Behdashti': 'NonFood',
    'Abdarmani': 'Food', 'sarein': 'Food',
    'kandovan malzumat': 'NonFood', 'kandovan eng': 'NonFood',
    'kandovan Drink': 'Food',
}

def clear_all_data():
    print("🗑️  پاک کردن داده‌های قبلی...")
    db.session.query(ChatHistory).delete()
    db.session.query(InventoryCount).delete()
    db.session.query(Alert).delete()
    db.session.query(Transaction).delete()
    db.session.query(Item).delete()
    db.session.commit()
    print("✅ همه داده‌ها پاک شد")

def ensure_hotels():
    hotels = {}
    for sheet, name in HOTEL_MAPPING.items():
        h = Hotel.query.filter_by(hotel_name=name).first()
        if not h:
            h = Hotel(hotel_name=name, hotel_code=sheet[:10])
            db.session.add(h)
            db.session.flush()
        hotels[sheet] = h
    db.session.commit()
    return hotels

def load_items(excel_path, hotels):
    print(f"📥 خواندن Excel...")
    df_all = pd.read_excel(excel_path, sheet_name=None)
    
    items_created = 0
    code_counter = 1
    
    for sheet, df in df_all.items():
        if sheet == 'تحلیل جامع': continue
        hotel = hotels.get(sheet)
        if not hotel: continue
        
        category = CATEGORY_MAPPING.get(sheet, 'Food')
        
        # Find columns
        name_col = next((c for c in df.columns if any(x in str(c) for x in ['شرح', 'نام کالا'])), None)
        unit_col = next((c for c in df.columns if 'واحد' in str(c)), None)
        stock_col = next((c for c in df.columns if 'موجودی' in str(c)), None)
        
        if not name_col: continue
        
        for _, row in df.iterrows():
            item_name = str(row.get(name_col, '')).strip()
            if not item_name or item_name == 'nan' or len(item_name) < 2: continue
            if any(x in item_name for x in ['ردیف', 'شرح', 'نام', 'جمع']): continue
            
            unit = str(row.get(unit_col, 'عدد')).strip() if unit_col else 'عدد'
            if unit == 'nan': unit = 'عدد'
            
            try:
                stock = float(row.get(stock_col, 50)) if stock_col else random.randint(20, 100)
            except: stock = random.randint(20, 100)
            
            prefix = 'F' if category == 'Food' else 'NF'
            item = Item(
                item_code=f"{prefix}{code_counter:04d}",
                item_name_fa=item_name,
                category=category,
                unit=unit,
                hotel_id=hotel.id,
                unit_price=Decimal(str(random.randint(50000, 2000000))),
                min_stock=max(5, int(stock * 0.2)),
                max_stock=max(20, int(stock * 2)),
                current_stock=stock,
                is_active=True
            )
            db.session.add(item)
            code_counter += 1
            items_created += 1
        
        db.session.commit()
        print(f"  ✅ {sheet}: loaded")
    
    return items_created

def generate_transactions(days=30):
    print(f"📊 ایجاد تراکنش‌ها...")
    items = Item.query.filter_by(is_active=True).all()
    user = User.query.filter_by(username='admin').first()
    if not user: return 0
    
    count = 0
    for d in range(days, 0, -1):
        trans_date = date.today() - timedelta(days=d)
        for item in random.sample(items, min(len(items), random.randint(15, 40))):
            ttype = random.choices(['خرید', 'مصرف', 'ضایعات'], weights=[0.4, 0.5, 0.1])[0]
            qty = random.uniform(5, 50) if ttype == 'خرید' else random.uniform(1, 20)
            direction = 1 if ttype == 'خرید' else -1
            
            tx = Transaction(
                transaction_date=trans_date,
                item_id=item.id,
                transaction_type=ttype,
                category=item.category,
                hotel_id=item.hotel_id,
                quantity=qty,
                unit_price=item.unit_price,
                total_amount=Decimal(str(qty)) * item.unit_price,
                user_id=user.id,
                direction=direction,
                signed_quantity=qty * direction,
                waste_reason='expiry' if ttype == 'ضایعات' else None
            )
            db.session.add(tx)
            count += 1
    
    db.session.commit()
    return count

def main():
    app = create_app()
    excel_path = r'c:\Users\aminh\OneDrive\Desktop\pareto\گزارش_تحلیلی_جامع.xlsx'
    
    with app.app_context():
        clear_all_data()
        hotels = ensure_hotels()
        items = load_items(excel_path, hotels)
        print(f"✅ {items} کالا ایجاد شد")
        
        txs = generate_transactions(30)
        print(f"✅ {txs} تراکنش ایجاد شد")
        
        print("\n🎉 بارگذاری کامل شد!")

if __name__ == '__main__':
    main()
