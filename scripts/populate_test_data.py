#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Comprehensive Test Data Population Script
==========================================
This script populates the database with realistic, complete test data across all modules:
- Hotels
- Items (Food & Non-Food categories)
- Transactions (Purchase, Consumption, Waste, Adjustment)
- Inventory Counts
- Alerts
- Users

Usage:
    python scripts/populate_test_data.py
"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import create_app
from models import db, User, Hotel, Item, Transaction, InventoryCount, Alert, WarehouseSettings
from datetime import datetime, date, timedelta
from decimal import Decimal
import random

app = create_app()

# Test data configuration
TARGET_ITEM_COUNT = 500
HISTORY_DAYS = 365
TARGET_TRANSACTION_COUNT = 5000  # هدف تعداد تراکنش
CATEGORIES = ['Food', 'Beverage', 'Cleaning', 'Office', 'Equipment', 'Maintenance']

FOOD_ITEMS = [
    ('برنج', 'Rice', 'کیلوگرم', 'Food'),
    ('گوشت گوساله', 'Beef', 'کیلوگرم', 'Food'),
    ('مرغ', 'Chicken', 'کیلوگرم', 'Food'),
    ('ماهی', 'Fish', 'کیلوگرم', 'Food'),
    ('پیاز', 'Onion', 'کیلوگرم', 'Food'),
    ('گوجه فرنگی', 'Tomato', 'کیلوگرم', 'Food'),
    ('سیب زمینی', 'Potato', 'کیلوگرم', 'Food'),
    ('روغن مایع', 'Cooking Oil', 'لیتر', 'Food'),
    ('شکر', 'Sugar', 'کیلوگرم', 'Food'),
    ('نمک', 'Salt', 'کیلوگرم', 'Food'),
    ('آرد', 'Flour', 'کیلوگرم', 'Food'),
    ('تخم مرغ', 'Eggs', 'عدد', 'Food'),
    ('شیر', 'Milk', 'لیتر', 'Food'),
    ('ماست', 'Yogurt', 'کیلوگرم', 'Food'),
    ('پنیر', 'Cheese', 'کیلوگرم', 'Food'),
]

BEVERAGE_ITEMS = [
    ('آب معدنی', 'Mineral Water', 'بطری', 'Beverage'),
    ('نوشابه', 'Soft Drink', 'قوطی', 'Beverage'),
    ('آب میوه', 'Juice', 'لیتر', 'Beverage'),
    ('چای', 'Tea', 'کیلوگرم', 'Beverage'),
    ('قهوه', 'Coffee', 'کیلوگرم', 'Beverage'),
]

CLEANING_ITEMS = [
    ('مایع ظرفشویی', 'Dish Soap', 'لیتر', 'Cleaning'),
    ('پودر لباسشویی', 'Laundry Detergent', 'کیلوگرم', 'Cleaning'),
    ('وایتکس', 'Bleach', 'لیتر', 'Cleaning'),
    ('دستمال کاغذی', 'Paper Towel', 'رول', 'Cleaning'),
    ('کیسه زباله', 'Garbage Bag', 'بسته', 'Cleaning'),
]

OFFICE_ITEMS = [
    ('کاغذ A4', 'A4 Paper', 'بسته', 'Office'),
    ('خودکار', 'Pen', 'عدد', 'Office'),
    ('مداد', 'Pencil', 'عدد', 'Office'),
    ('پوشه', 'Folder', 'عدد', 'Office'),
]

EQUIPMENT_ITEMS = [
    ('چاقو آشپزخانه', 'Kitchen Knife', 'عدد', 'Equipment'),
    ('قابلمه', 'Pot', 'عدد', 'Equipment'),
    ('ماهیتابه', 'Pan', 'عدد', 'Equipment'),
]

MAINTENANCE_ITEMS = [
    ('لامپ LED', 'LED Bulb', 'عدد', 'Maintenance'),
    ('باتری', 'Battery', 'عدد', 'Maintenance'),
]

BASE_ITEMS = FOOD_ITEMS + BEVERAGE_ITEMS + CLEANING_ITEMS + OFFICE_ITEMS + EQUIPMENT_ITEMS + MAINTENANCE_ITEMS


def build_item_catalog(target_count: int):
    """Expand base items catalog to reach target count"""
    extended = list(BASE_ITEMS)
    if len(extended) >= target_count:
        return extended[:target_count]

    suffix = 1
    while len(extended) < target_count:
        for name_fa, name_en, unit, category in BASE_ITEMS:
            suffix += 1
            new_name_fa = f"{name_fa} #{suffix}"
            new_name_en = f"{name_en} #{suffix}"
            extended.append((new_name_fa, new_name_en, unit, category))
            if len(extended) >= target_count:
                break

    return extended


ALL_ITEMS = build_item_catalog(TARGET_ITEM_COUNT)

TRANSACTION_TYPES = ['خرید', 'مصرف', 'ضایعات', 'اصلاحی']
WASTE_REASONS = ['تاریخ انقضا', 'خرابی/آسیب', 'آسیب حمل‌ونقل', 'کیفیت نامطلوب', 'سایر']
DEPARTMENTS = ['آشپزخانه', 'رستوران', 'خانه‌داری', 'اداری', 'نگهبانی', 'تعمیرات']
APPROVAL_STATUSES = ['not_required', 'pending', 'approved', 'rejected']


def create_test_users():
    """Create test users"""
    print("Creating test users...")
    
    # Admin user
    admin = User.query.filter_by(username='admin').first()
    if not admin:
        admin = User(
            username='admin',
            email='admin@hotel.local',
            full_name='مدیر سیستم',
            role='admin',
            is_active=True
        )
        admin.set_password('admin123')
        db.session.add(admin)
    
    # Manager user
    manager = User.query.filter_by(username='manager').first()
    if not manager:
        manager = User(
            username='manager',
            email='manager@hotel.local',
            full_name='مدیر انبار',
            role='manager',
            is_active=True
        )
        manager.set_password('manager123')
        db.session.add(manager)
    
    # Staff user
    staff = User.query.filter_by(username='staff').first()
    if not staff:
        staff = User(
            username='staff',
            email='staff@hotel.local',
            full_name='کارمند انبار',
            role='staff',
            is_active=True
        )
        staff.set_password('staff123')
        db.session.add(staff)
    
    db.session.commit()
    print(f"✓ Created {User.query.count()} users")
    return admin, manager, staff


def create_test_hotel():
    """Create test hotel"""
    print("Creating test hotel...")
    
    hotel = Hotel.query.filter_by(hotel_code='MAIN').first()
    if not hotel:
        hotel = Hotel(
            hotel_code='MAIN',
            hotel_name='هتل اصلی',
            is_active=True
        )
        db.session.add(hotel)
        db.session.commit()
    
    # Create warehouse settings
    settings = WarehouseSettings.get_or_create(hotel.id)
    settings.low_stock_percentage = 20
    settings.variance_alert_percentage = 5
    settings.adjustment_approval_threshold = 10
    db.session.commit()
    
    print(f"✓ Created hotel: {hotel.hotel_name}")
    return hotel


def create_test_items(hotel):
    """Create comprehensive test items"""
    print("Creating test items...")
    
    items = []
    for idx, (name_fa, name_en, unit, category) in enumerate(ALL_ITEMS, start=1):
        item_code = f'ITM{idx:04d}'
        
        existing = Item.query.filter_by(item_code=item_code).first()
        if existing:
            items.append(existing)
            continue
        
        # Set realistic min/max stock based on category
        if category == 'Food':
            min_stock = random.randint(10, 50)
            max_stock = random.randint(100, 500)
        elif category == 'Beverage':
            min_stock = random.randint(20, 100)
            max_stock = random.randint(200, 1000)
        elif category == 'Cleaning':
            min_stock = random.randint(5, 20)
            max_stock = random.randint(50, 200)
        else:
            min_stock = random.randint(5, 15)
            max_stock = random.randint(30, 100)
        
        item = Item(
            item_code=item_code,
            item_name_fa=name_fa,
            item_name_en=name_en,
            category=category,
            unit=unit,
            hotel_id=hotel.id,
            min_stock=min_stock,
            max_stock=max_stock,
            current_stock=0,
            is_active=True
        )
        db.session.add(item)
        items.append(item)
    
    db.session.commit()
    print(f"✓ Created {len(items)} items across {len(CATEGORIES)} categories")
    return items


def create_test_transactions(hotel, items, users):
    """Create realistic transaction history with comprehensive field coverage"""
    print(f"Creating {TARGET_TRANSACTION_COUNT} test transactions with full field coverage...")
    
    admin, manager, staff = users
    start_date = date.today() - timedelta(days=HISTORY_DAYS)
    transaction_count = 0
    
    # Calculate transactions per item to reach target
    transactions_per_item = TARGET_TRANSACTION_COUNT // len(items)
    
    for item in items:
        # Price based on category
        if item.category == 'Food':
            base_price = random.randint(50000, 500000)
        elif item.category == 'Beverage':
            base_price = random.randint(10000, 100000)
        elif item.category == 'Equipment':
            base_price = random.randint(200000, 2000000)
        else:
            base_price = random.randint(20000, 200000)
        
        # Initial stock purchase
        initial_qty = random.randint(int(item.max_stock * 0.5), int(item.max_stock * 1.5))
        tx = Transaction.create_transaction(
            item_id=item.id,
            hotel_id=hotel.id,
            user_id=admin.id,
            transaction_type='خرید',
            quantity=initial_qty,
            category=item.category,
            direction=1,
            unit_price=Decimal(str(base_price)),
            description='موجودی اولیه',
            allow_price_override=True
        )
        db.session.add(tx)
        tx.transaction_date = start_date
        tx.reference_number = f"INV-{random.randint(1000, 9999)}"
        item.current_stock = initial_qty
        transaction_count += 1
        
        # Generate distributed transactions over the year
        current_stock = initial_qty
        item_transactions = 0
        
        while item_transactions < transactions_per_item and transaction_count < TARGET_TRANSACTION_COUNT:
            # Random date within the year
            days_offset = random.randint(1, HISTORY_DAYS - 1)
            current_date = start_date + timedelta(days=days_offset)
            
            # Transaction type with realistic distribution
            tx_type = random.choices(
                ['خرید', 'مصرف', 'ضایعات', 'اصلاحی'],
                weights=[25, 55, 10, 10]
            )[0]
                
            if tx_type == 'خرید':
                # Purchase: restock when low or random purchase
                qty = random.randint(int(item.max_stock * 0.2), int(item.max_stock * 0.8))
                price = Decimal(str(base_price * random.uniform(0.85, 1.15)))
                
                tx = Transaction.create_transaction(
                    item_id=item.id,
                    hotel_id=hotel.id,
                    user_id=random.choice([admin, manager]).id,
                    transaction_type='خرید',
                    quantity=qty,
                    category=item.category,
                    direction=1,
                    unit_price=price,
                    description=f'خرید {item.item_name_fa}',
                    allow_price_override=True,
                    price_override_reason='تغییر قیمت بازار' if random.random() > 0.7 else None
                )
                db.session.add(tx)
                tx.transaction_date = current_date
                tx.reference_number = f"PO-{random.randint(10000, 99999)}"
                # Approval workflow for large purchases
                if qty > item.max_stock * 0.6:
                    tx.requires_approval = True
                    tx.approval_status = random.choice(['approved', 'pending'])
                    if tx.approval_status == 'approved':
                        tx.approved_by_id = admin.id
                        tx.approved_at = current_date
                current_stock += qty
                transaction_count += 1
                item_transactions += 1
                
            elif tx_type == 'مصرف':
                # Consumption: realistic usage
                if current_stock > 0:
                    max_consume = min(current_stock, int(item.max_stock * 0.15))
                    qty = random.randint(1, max(1, max_consume))
                    
                    tx = Transaction.create_transaction(
                        item_id=item.id,
                        hotel_id=hotel.id,
                        user_id=random.choice([manager, staff]).id,
                        transaction_type='مصرف',
                        quantity=qty,
                        category=item.category,
                        direction=-1,
                        unit_price=Decimal('0'),
                        description=f'مصرف {item.item_name_fa} - {random.choice(DEPARTMENTS)}'
                    )
                    db.session.add(tx)
                    tx.transaction_date = current_date
                    tx.destination_department = random.choice(DEPARTMENTS)
                    current_stock -= qty
                    transaction_count += 1
                    item_transactions += 1
                
            elif tx_type == 'ضایعات':
                # Waste: with detailed reason
                if current_stock > 0:
                    max_waste = min(current_stock, int(item.max_stock * 0.08))
                    qty = random.randint(1, max(1, max_waste))
                    waste_reason = random.choice(WASTE_REASONS)
                    
                    tx = Transaction.create_transaction(
                        item_id=item.id,
                        hotel_id=hotel.id,
                        user_id=random.choice([manager, staff]).id,
                        transaction_type='ضایعات',
                        quantity=qty,
                        category=item.category,
                        direction=-1,
                        unit_price=Decimal('0'),
                        description=f'ضایعات {item.item_name_fa} - {waste_reason}'
                    )
                    db.session.add(tx)
                    tx.transaction_date = current_date
                    tx.waste_reason = waste_reason
                    tx.waste_reason_detail = f'جزئیات: {waste_reason} - بررسی شده توسط {random.choice(["مدیر", "سرپرست", "کنترل کیفیت"])}'
                    # Large waste needs approval
                    if qty > item.max_stock * 0.05:
                        tx.requires_approval = True
                        tx.approval_status = random.choice(['approved', 'pending', 'rejected'])
                        if tx.approval_status == 'approved':
                            tx.approved_by_id = manager.id
                            tx.approved_at = current_date
                    current_stock -= qty
                    transaction_count += 1
                    item_transactions += 1
            
            elif tx_type == 'اصلاحی':
                # Adjustment: correction transactions
                if current_stock > 0:
                    # Random adjustment (can be positive or negative)
                    adjustment_direction = random.choice([1, -1])
                    max_adjustment = min(current_stock if adjustment_direction == -1 else item.max_stock, 
                                       int(item.max_stock * 0.1))
                    qty = random.randint(1, max(1, max_adjustment))
                    
                    tx = Transaction.create_transaction(
                        item_id=item.id,
                        hotel_id=hotel.id,
                        user_id=random.choice([admin, manager]).id,
                        transaction_type='اصلاحی',
                        quantity=qty,
                        category=item.category,
                        direction=adjustment_direction,
                        unit_price=Decimal('0'),
                        description=f'اصلاح موجودی {item.item_name_fa} - {"افزایش" if adjustment_direction == 1 else "کاهش"}'
                    )
                    db.session.add(tx)
                    tx.transaction_date = current_date
                    # Adjustments always need approval
                    tx.requires_approval = True
                    tx.approval_status = random.choice(['approved', 'pending'])
                    if tx.approval_status == 'approved':
                        tx.approved_by_id = admin.id
                        tx.approved_at = current_date
                    current_stock += (qty * adjustment_direction)
                    transaction_count += 1
                    item_transactions += 1
        
        # Update final stock
        item.current_stock = max(0, current_stock)
    
    db.session.commit()
    print(f"✓ Created {transaction_count} transactions over {HISTORY_DAYS} days")


def create_test_inventory_counts(hotel, items, users):
    """Create inventory count records"""
    print("Creating inventory counts...")
    
    admin, manager, staff = users
    count_records = 0
    
    # Create counts for random items (30% of items)
    sample_size = max(1, int(len(items) * 0.3))
    sample_items = random.sample(items, k=sample_size)
    
    for item in sample_items:
        # Count from 7 days ago
        count_date = date.today() - timedelta(days=7)
        
        # Simulate small variance (±5%)
        system_qty = item.current_stock
        variance_pct = random.uniform(-0.05, 0.05)
        physical_qty = max(0, system_qty + (system_qty * variance_pct))
        
        count = InventoryCount(
            hotel_id=hotel.id,
            item_id=item.id,
            counted_by_id=random.choice([manager, staff]).id,
            count_date=count_date,
            system_quantity=Decimal(str(system_qty)),
            physical_quantity=Decimal(str(physical_qty)),
            variance=Decimal(str(physical_qty - system_qty)),
            variance_percentage=Decimal(str(variance_pct * 100)),
            status='resolved' if abs(variance_pct) < 0.02 else 'pending'
        )
        db.session.add(count)
        count_records += 1
    
    db.session.commit()
    print(f"✓ Created {count_records} inventory count records")


def create_test_alerts(hotel, items):
    """Create realistic alerts"""
    print("Creating alerts...")
    
    alert_count = 0
    
    for item in items:
        # Low stock alert
        if item.current_stock < item.min_stock:
            Alert.create_if_not_exists(
                hotel_id=hotel.id,
                alert_type='low_stock',
                item_id=item.id,
                message=f'موجودی {item.item_name_fa} کمتر از حد مجاز است',
                severity='warning',
                threshold_value=Decimal(str(item.min_stock)),
                actual_value=Decimal(str(item.current_stock))
            )
            alert_count += 1
        
        # High stock alert (overstocking)
        elif item.current_stock > item.max_stock:
            Alert.create_if_not_exists(
                hotel_id=hotel.id,
                alert_type='high_stock',
                item_id=item.id,
                message=f'موجودی {item.item_name_fa} بیش از حد مجاز است',
                severity='info',
                threshold_value=Decimal(str(item.max_stock)),
                actual_value=Decimal(str(item.current_stock))
            )
            alert_count += 1
    
    db.session.commit()
    print(f"✓ Created {alert_count} alerts")


def main():
    """Main population function"""
    print("="*60)
    print("Starting Comprehensive Test Data Population")
    print("="*60)
    
    with app.app_context():
        try:
            # Create users
            users = create_test_users()
            
            # Create hotel
            hotel = create_test_hotel()
            
            # Create items
            items = create_test_items(hotel)
            
            # Create transactions (this will take a moment)
            create_test_transactions(hotel, items, users)
            
            # Create inventory counts
            create_test_inventory_counts(hotel, items, users)
            
            # Create alerts
            create_test_alerts(hotel, items)
            
            print("="*60)
            print("✓ Test Data Population Complete!")
            print("="*60)
            print("\nDatabase Summary:")
            print(f"  Users: {User.query.count()}")
            print(f"  Hotels: {Hotel.query.count()}")
            print(f"  Items: {Item.query.count()}")
            print(f"  Transactions: {Transaction.query.filter_by(is_deleted=False).count()}")
            print(f"  Inventory Counts: {InventoryCount.query.count()}")
            print(f"  Active Alerts: {Alert.query.filter_by(status='active').count()}")
            print("\nTest Credentials:")
            print("  Admin: admin / admin123")
            print("  Manager: manager / manager123")
            print("  Staff: staff / staff123")
            print("="*60)
            
        except Exception as e:
            print(f"\n✗ Error during population: {e}")
            import traceback
            traceback.print_exc()
            db.session.rollback()
            return 1
    
    return 0


if __name__ == '__main__':
    sys.exit(main())
