#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Database initialization script with seed data
Run this script to create tables and add sample data
"""

import os
import sys
from datetime import date, timedelta
import random

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import create_app
from models import db, User, Item, Transaction, Alert

def init_database():
    app = create_app()
    
    with app.app_context():
        db.drop_all()
        db.create_all()
        print("Database tables created.")
        
        admin = User(
            username='admin',
            email='admin@hotel.com',
            full_name='مدیر سیستم'
        )
        admin.set_password('admin')
        db.session.add(admin)
        
        user1 = User(
            username='user1',
            email='user1@hotel.com',
            full_name='کاربر تست'
        )
        user1.set_password('1234')
        db.session.add(user1)
        
        db.session.commit()
        print("Users created (admin/admin, user1/1234)")
        
        # فهرست کامل‌تر اقلام غذایی (Food)
        food_items = [
            ('F001', 'برنج ایرانی', 'کیلوگرم', 100, 500),
            ('F002', 'روغن مایع', 'لیتر', 50, 200),
            ('F003', 'گوشت گوساله', 'کیلوگرم', 30, 120),
            ('F004', 'مرغ', 'کیلوگرم', 50, 180),
            ('F005', 'تخم مرغ', 'عدد', 200, 1200),
            ('F006', 'ماهی قزل‌آلا', 'کیلوگرم', 20, 90),
            ('F007', 'پنیر', 'کیلوگرم', 30, 120),
            ('F008', 'ماست', 'کیلوگرم', 50, 220),
            ('F009', 'کره', 'کیلوگرم', 20, 100),
            ('F010', 'شیر', 'لیتر', 100, 400),
            ('F011', 'نان', 'عدد', 100, 800),
            ('F012', 'آرد', 'کیلوگرم', 50, 250),
            ('F013', 'شکر', 'کیلوگرم', 50, 250),
            ('F014', 'نمک', 'کیلوگرم', 20, 120),
            ('F015', 'فلفل سیاه', 'گرم', 500, 2500),
            ('F016', 'زعفران', 'گرم', 50, 300),
            ('F017', 'گوجه‌فرنگی', 'کیلوگرم', 30, 150),
            ('F018', 'پیاز', 'کیلوگرم', 50, 200),
            ('F019', 'سیب‌زمینی', 'کیلوگرم', 50, 220),
            ('F020', 'هویج', 'کیلوگرم', 30, 120),
            ('F021', 'قارچ', 'کیلوگرم', 20, 80),
            ('F022', 'کاهو', 'عدد', 30, 120),
            ('F023', 'خیار', 'کیلوگرم', 30, 140),
            ('F024', 'فلفل دلمه‌ای', 'کیلوگرم', 20, 100),
            ('F025', 'سیر', 'کیلوگرم', 10, 60),
            ('F026', 'لیمو ترش', 'کیلوگرم', 20, 100),
            ('F027', 'پرتقال', 'کیلوگرم', 40, 200),
            ('F028', 'سیب', 'کیلوگرم', 40, 200),
            ('F029', 'موز', 'کیلوگرم', 30, 150),
            ('F030', 'نوشابه قوطی', 'عدد', 100, 800),
            ('F031', 'آب معدنی', 'بطری', 200, 1200),
            ('F032', 'چای ایرانی', 'گرم', 500, 2500),
            ('F033', 'قهوه ترک', 'گرم', 300, 1800),
            ('F034', 'پاستا', 'کیلوگرم', 40, 200),
            ('F035', 'کنسرو تن ماهی', 'عدد', 60, 300),
            ('F036', 'عدس', 'کیلوگرم', 40, 200),
            ('F037', 'لوبیا چیتی', 'کیلوگرم', 40, 200),
            ('F038', 'نخود', 'کیلوگرم', 40, 200),
            ('F039', 'ذرت شیرین', 'کیلوگرم', 20, 120),
            ('F040', 'رب گوجه‌فرنگی', 'گرم', 500, 3000),
        ]
        
        # فهرست کامل‌تر اقلام غیرغذایی (NonFood)
        nonfood_items = [
            ('NF001', 'دستمال کاغذی', 'بسته', 120, 600),
            ('NF002', 'مایع ظرفشویی', 'لیتر', 60, 250),
            ('NF003', 'پودر رختشویی', 'کیلوگرم', 40, 160),
            ('NF004', 'شامپو', 'لیتر', 60, 180),
            ('NF005', 'صابون', 'عدد', 150, 700),
            ('NF006', 'اسفنج', 'عدد', 60, 250),
            ('NF007', 'دستکش', 'جفت', 120, 400),
            ('NF008', 'سطل زباله', 'عدد', 15, 60),
            ('NF009', 'کیسه زباله', 'بسته', 150, 700),
            ('NF010', 'جاروبرقی', 'عدد', 5, 12),
            ('NF011', 'مایع دستشویی', 'لیتر', 80, 250),
            ('NF012', 'حوله یکبار مصرف', 'بسته', 80, 300),
            ('NF013', 'دستمال مرطوب', 'بسته', 80, 300),
            ('NF014', 'ژل ضدعفونی', 'میلی‌لیتر', 500, 2500),
            ('NF015', 'شوینده چندمنظوره', 'لیتر', 60, 200),
            ('NF016', 'سفیدکننده', 'لیتر', 50, 180),
            ('NF017', 'شیشه‌شوی', 'لیتر', 60, 200),
            ('NF018', 'قرص کلر استخر', 'عدد', 20, 80),
            ('NF019', 'فویل آلومینیوم', 'رول', 40, 200),
            ('NF020', 'سلفون', 'رول', 50, 220),
            ('NF021', 'لیوان یکبار مصرف', 'بسته', 100, 500),
            ('NF022', 'کارد و چنگال یکبار مصرف', 'بسته', 80, 400),
            ('NF023', 'دستمال سفره', 'بسته', 120, 600),
            ('NF024', 'باتری قلمی', 'بسته', 40, 200),
            ('NF025', 'لامپ LED', 'عدد', 20, 120),
            ('NF026', 'فیلتر تصفیه آب', 'عدد', 10, 60),
            ('NF027', 'کیت تست PH آب', 'عدد', 10, 40),
            ('NF028', 'چمن مصنوعی (متراژ)', 'متر', 5, 30),
            ('NF029', 'پادری هتلی', 'عدد', 10, 50),
            ('NF030', 'گلدان تزیینی', 'عدد', 10, 40),
        ]
        
        all_items = []
        for code, name, unit, min_s, max_s in food_items:
            item = Item(
                item_code=code,
                item_name_fa=name,
                category='Food',
                unit=unit,
                min_stock=min_s,
                max_stock=max_s,
                current_stock=random.randint(min_s, max_s)
            )
            db.session.add(item)
            all_items.append(item)
        
        for code, name, unit, min_s, max_s in nonfood_items:
            item = Item(
                item_code=code,
                item_name_fa=name,
                category='NonFood',
                unit=unit,
                min_stock=min_s,
                max_stock=max_s,
                current_stock=random.randint(min_s, max_s)
            )
            db.session.add(item)
            all_items.append(item)
        
        db.session.commit()
        print(f"{len(all_items)} items created")
        
        transaction_types = ['خرید', 'مصرف', 'ضایعات']
        type_weights = [0.6, 0.35, 0.05]
        
        price_ranges = {
            # Food
            'F001': (450000, 550000),
            'F002': (180000, 220000),
            'F003': (2500000, 3600000),
            'F004': (450000, 700000),
            'F005': (4000, 7000),
            'F006': (800000, 1300000),
            'F007': (350000, 480000),
            'F008': (80000, 140000),
            'F009': (400000, 520000),
            'F010': (45000, 75000),
            'F011': (5000, 12000),
            'F012': (80000, 140000),
            'F013': (70000, 110000),
            'F014': (15000, 30000),
            'F015': (200, 500),
            'F016': (15000, 30000),
            'F017': (50000, 110000),
            'F018': (30000, 70000),
            'F019': (40000, 90000),
            'F020': (40000, 80000),
            'F021': (120000, 220000),
            'F022': (20000, 60000),
            'F023': (30000, 70000),
            'F024': (80000, 150000),
            'F025': (120000, 240000),
            'F026': (90000, 170000),
            'F027': (50000, 120000),
            'F028': (50000, 130000),
            'F029': (60000, 160000),
            'F030': (12000, 25000),
            'F031': (5000, 15000),
            'F032': (120000, 240000),
            'F033': (300000, 600000),
            'F034': (80000, 160000),
            'F035': (60000, 140000),
            'F036': (90000, 180000),
            'F037': (90000, 180000),
            'F038': (80000, 160000),
            'F039': (60000, 140000),
            'F040': (90000, 180000),
            # NonFood
            'NF001': (25000, 50000),
            'NF002': (80000, 140000),
            'NF003': (150000, 260000),
            'NF004': (100000, 190000),
            'NF005': (10000, 30000),
            'NF006': (8000, 18000),
            'NF007': (15000, 35000),
            'NF008': (50000, 120000),
            'NF009': (30000, 70000),
            'NF010': (5000000, 8500000),
            'NF011': (70000, 140000),
            'NF012': (60000, 140000),
            'NF013': (60000, 140000),
            'NF014': (40000, 100000),
            'NF015': (90000, 180000),
            'NF016': (70000, 160000),
            'NF017': (70000, 150000),
            'NF018': (150000, 350000),
            'NF019': (60000, 140000),
            'NF020': (60000, 150000),
            'NF021': (30000, 80000),
            'NF022': (40000, 100000),
            'NF023': (30000, 90000),
            'NF024': (50000, 140000),
            'NF025': (70000, 180000),
            'NF026': (150000, 350000),
            'NF027': (120000, 280000),
            'NF028': (200000, 500000),
            'NF029': (150000, 350000),
            'NF030': (120000, 300000),
        }
        
        transactions_count = 0
        for days_ago in range(60, -1, -1):
            trans_date = date.today() - timedelta(days=days_ago)
            
            daily_transactions = random.randint(5, 15)
            
            for _ in range(daily_transactions):
                item = random.choice(all_items)
                trans_type = random.choices(transaction_types, weights=type_weights)[0]
                
                price_range = price_ranges.get(item.item_code, (10000, 100000))
                unit_price = random.randint(price_range[0], price_range[1])
                
                if trans_type == 'خرید':
                    quantity = random.uniform(5, 50)
                elif trans_type == 'مصرف':
                    quantity = random.uniform(1, 20)
                else:
                    quantity = random.uniform(0.5, 5)
                
                quantity = round(quantity, 2)
                total_amount = quantity * unit_price
                
                transaction = Transaction(
                    transaction_date=trans_date,
                    item_id=item.id,
                    transaction_type=trans_type,
                    category=item.category,
                    quantity=quantity,
                    unit_price=unit_price,
                    total_amount=total_amount,
                    user_id=random.choice([1, 2])
                )
                db.session.add(transaction)
                transactions_count += 1
        
        db.session.commit()
        print(f"{transactions_count} transactions created")
        
        alerts = [
            Alert(
                alert_type='low_stock',
                item_id=1,
                message='موجودی برنج ایرانی کم است',
                severity='warning'
            ),
            Alert(
                alert_type='high_waste',
                item_id=3,
                message='ضایعات گوشت گوساله در هفته گذشته بالا بوده',
                severity='danger'
            ),
            Alert(
                alert_type='price_increase',
                item_id=6,
                message='قیمت ماهی قزل‌آلا 15% افزایش یافته',
                severity='info'
            ),
        ]
        
        for alert in alerts:
            db.session.add(alert)
        
        db.session.commit()
        print(f"{len(alerts)} alerts created")
        
        print("\n" + "="*50)
        print("Database seeding completed successfully.")
        print("="*50)
        print("\nLogin info:")
        print("   Admin user: admin / admin")
        print("   Test user: user1 / 1234")
        print("\nRun the system with:")
        print("   python app.py")

if __name__ == '__main__':
    init_database()
