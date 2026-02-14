#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Create Excel template for Pareto analysis testing
Required fields for accurate Pareto analysis:
- Item: item_code, item_name_fa, category
- Transaction: transaction_type='خرید', category, total_amount, transaction_date
"""

import pandas as pd
import random
from datetime import datetime, timedelta

# Sample items for testing
SAMPLE_ITEMS = [
    ('برنج', 'Rice', 'Food', 'کیلوگرم'),
    ('گوشت گوساله', 'Beef', 'Food', 'کیلوگرم'),
    ('مرغ', 'Chicken', 'Food', 'کیلوگرم'),
    ('شیر', 'Milk', 'Food', 'لیتر'),
    ('تخم مرغ', 'Eggs', 'Food', 'عدد'),
    ('شکر', 'Sugar', 'Food', 'کیلوگرم'),
    ('پنیر', 'Cheese', 'Food', 'کیلوگرم'),
    ('روغن', 'Oil', 'Food', 'لیتر'),
    ('ماست', 'Yogurt', 'Food', 'لیتر'),
    ('نان', 'Bread', 'Food', 'عدد'),
    ('سیب', 'Apple', 'Food', 'کیلوگرم'),
    ('موز', 'Banana', 'Food', 'کیلوگرم'),
    ('پیاز', 'Onion', 'Food', 'کیلوگرم'),
    ('سیر', 'Garlic', 'Food', 'کیلوگرم'),
    ('گوجه فرنگی', 'Tomato', 'Food', 'کیلوگرم'),
    ('سیب زمینی', 'Potato', 'Food', 'کیلوگرم'),
    ('خیار', 'Cucumber', 'Food', 'کیلوگرم'),
    ('هویج', 'Carrot', 'Food', 'کیلوگرم'),
    ('کاهو', 'Lettuce', 'Food', 'کیلوگرم'),
]

def create_pareto_test_excel(filename='pareto_test_data.xlsx', num_transactions=100):
    """
    Create Excel file with purchase transactions for Pareto analysis testing
    
    Required fields for Pareto analysis:
    - کد کالا (item_code): Unique identifier
    - نام کالا (item_name_fa): Item name in Persian
    - نوع تراکنش (transaction_type): Must be 'خرید' for Pareto
    - گروه (category): 'Food' or 'NonFood'
    - مقدار (quantity): Quantity purchased
    - قیمت واحد (unit_price): Price per unit
    - مبلغ کل (total_amount): quantity * unit_price (calculated)
    - تاریخ (transaction_date): Date of transaction
    """
    
    # Generate transactions
    transactions = []
    start_date = datetime.now() - timedelta(days=30)
    
    for i in range(num_transactions):
        item = random.choice(SAMPLE_ITEMS)
        item_name_fa, item_name_en, category, unit = item
        
        # Generate item code
        item_code = f"F{random.randint(1000, 9999)}"
        
        # Generate realistic amounts following Pareto distribution
        # 20% of items should have 80% of value
        if i < num_transactions * 0.2:  # Top 20%
            quantity = random.randint(50, 200)
            unit_price = random.randint(100000, 500000)  # High value
        else:  # Bottom 80%
            quantity = random.randint(10, 50)
            unit_price = random.randint(20000, 80000)  # Lower value
        
        total_amount = quantity * unit_price
        transaction_date = start_date + timedelta(days=random.randint(0, 30))
        
        transactions.append({
            'کد کالا': item_code,
            'نام کالا': item_name_fa,
            'نوع تراکنش': 'خرید',
            'گروه': category,
            'واحد': unit,
            'مقدار': quantity,
            'قیمت واحد (ریال)': unit_price,
            'مبلغ کل (ریال)': total_amount,
            'تاریخ': transaction_date.strftime('%Y-%m-%d'),
            'توضیحات': f'خرید {item_name_fa} از تأمین‌کننده'
        })
    
    # Create DataFrame
    df = pd.DataFrame(transactions)
    
    # Sort by total_amount descending (Pareto order)
    df = df.sort_values('مبلغ کل (ریال)', ascending=False).reset_index(drop=True)
    
    # Add row numbers
    df.insert(0, 'ردیف', range(1, len(df) + 1))
    
    # Calculate percentages
    total_amount = df['مبلغ کل (ریال)'].sum()
    df['درصد سهم'] = (df['مبلغ کل (ریال)'] / total_amount * 100).round(2)
    df['مبلغ تجمعی'] = df['مبلغ کل (ریال)'].cumsum()
    df['درصد تجمعی'] = (df['مبلغ تجمعی'] / total_amount * 100).round(2)
    
    # Add ABC classification
    df['کلاس'] = df['درصد تجمعی'].apply(
        lambda x: 'A' if x <= 80 else ('B' if x <= 95 else 'C')
    )
    
    # Save to Excel
    with pd.ExcelWriter(filename, engine='openpyxl') as writer:
        df.to_excel(writer, sheet_name='Purchase Transactions', index=False)
        
        # Add summary sheet
        summary_data = {
            'تعداد کل تراکنش‌ها': [len(df)],
            'مجموع مبلغ (ریال)': [total_amount],
            'تعداد اقلام کلاس A': [len(df[df['کلاس'] == 'A'])],
            'تعداد اقلام کلاس B': [len(df[df['کلاس'] == 'B'])],
            'تعداد اقلام کلاس C': [len(df[df['کلاس'] == 'C'])],
            'مبلغ کلاس A (ریال)': [df[df['کلاس'] == 'A']['مبلغ کل (ریال)'].sum()],
            'مبلغ کلاس B (ریال)': [df[df['کلاس'] == 'B']['مبلغ کل (ریال)'].sum()],
            'مبلغ کلاس C (ریال)': [df[df['کلاس'] == 'C']['مبلغ کل (ریال)'].sum()],
        }
        
        summary_df = pd.DataFrame(summary_data)
        summary_df.to_excel(writer, sheet_name='Summary', index=False)
        
        # Add instructions sheet
        instructions = [
            ['راهنمای استفاده از این فایل برای تحلیل پارتو'],
            [''],
            ['فیلدهای مورد نیاز برای تحلیل پارتو:'],
            ['1. کد کالا (item_code): شناسه یکتای کالا'],
            ['2. نام کالا (item_name_fa): نام فارسی کالا'],
            ['3. نوع تراکنش (transaction_type): باید "خرید" باشد'],
            ['4. گروه (category): "Food" یا "NonFood"'],
            ['5. مقدار (quantity): مقدار خرید'],
            ['6. قیمت واحد (unit_price): قیمت به ریال'],
            ['7. مبلغ کل (total_amount): مقدار × قیمت واحد'],
            ['8. تاریخ (transaction_date): تاریخ تراکنش (YYYY-MM-DD)'],
            [''],
            ['نکات مهم:'],
            ['- فایل باید فرمت .xlsx باشد'],
            ['- تاریخ‌ها باید فرمت YYYY-MM-DD داشته باشند'],
            ['- مبلغ کل باید محاسبه شده باشد (مقدار × قیمت)'],
            ['- برای تحلیل پارتو ۳۰ روزه، تاریخ‌ها باید در ۳۰ روز اخیر باشند'],
        ]
        
        instructions_df = pd.DataFrame(instructions)
        instructions_df.to_excel(writer, sheet_name='Instructions', index=False, header=False)
    
    print(f"✓ Excel file created: {filename}")
    print(f"✓ Total transactions: {len(df)}")
    print(f"✓ Total amount: {total_amount:,.0f} ریال")
    print(f"✓ Class A: {len(df[df['کلاس'] == 'A'])} items")
    print(f"✓ Class B: {len(df[df['کلاس'] == 'B'])} items")
    print(f"✓ Class C: {len(df[df['کلاس'] == 'C'])} items")
    
    return filename

if __name__ == '__main__':
    import os
    import sys
    
    # Add parent directory to path
    sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
    
    # Create test Excel file
    output_file = os.path.join(os.path.dirname(__file__), '..', 'pareto_test_data.xlsx')
    create_pareto_test_excel(output_file, num_transactions=100)
    
    print(f"\nFile saved to: {output_file}")
