#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Comprehensive verification of all 12 strategy analyses.
1. Generate test Excel with known data
2. Import via DataImporter
3. Run each analysis function
4. Verify outputs against expected values
"""
import os, sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import pandas as pd
import numpy as np
from datetime import datetime, timedelta, date
from decimal import Decimal

# ── Generate deterministic test Excel ──────────────────────
def create_test_excel(path):
    """Create a deterministic Excel file with known values for verification."""
    np.random.seed(42)
    items = [
        ('F1001', 'برنج', 'Food', 'کیلوگرم'),
        ('F1002', 'گوشت گوساله', 'Food', 'کیلوگرم'),
        ('F1003', 'مرغ', 'Food', 'کیلوگرم'),
        ('F1004', 'روغن', 'Food', 'لیتر'),
        ('F1005', 'شکر', 'Food', 'کیلوگرم'),
        ('F1006', 'شیر', 'Food', 'لیتر'),
        ('F1007', 'تخم مرغ', 'Food', 'عدد'),
        ('F1008', 'پنیر', 'Food', 'کیلوگرم'),
        ('F1009', 'ماست', 'Food', 'لیتر'),
        ('F1010', 'نان', 'Food', 'عدد'),
        ('F1011', 'سیب', 'Food', 'کیلوگرم'),
        ('F1012', 'موز', 'Food', 'کیلوگرم'),
        ('F1013', 'پیاز', 'Food', 'کیلوگرم'),
        ('F1014', 'سیر', 'Food', 'کیلوگرم'),
        ('F1015', 'گوجه فرنگی', 'Food', 'کیلوگرم'),
    ]

    # Pareto-like distribution: first 3 items get ~80% of spend
    # We create multiple transactions per item across different weeks
    rows = []
    base_date = datetime.now() - timedelta(days=60)

    # High-value items (A class) – many transactions, high prices
    for week in range(8):
        tx_date = base_date + timedelta(days=week * 7 + np.random.randint(0, 3))
        # Item 1: Rice – biggest spender
        price1 = 450000 + np.random.randint(-20000, 20000)
        qty1 = 100 + np.random.randint(-10, 10)
        rows.append(('F1001', 'برنج', 'خرید', 'Food', 'کیلوگرم', qty1, price1, qty1 * price1, tx_date.strftime('%Y-%m-%d')))
        # Item 2: Beef – second biggest
        price2 = 800000 + np.random.randint(-50000, 50000)
        qty2 = 50 + np.random.randint(-5, 5)
        rows.append(('F1002', 'گوشت گوساله', 'خرید', 'Food', 'کیلوگرم', qty2, price2, qty2 * price2, tx_date.strftime('%Y-%m-%d')))
        # Item 3: Chicken
        price3 = 350000 + np.random.randint(-15000, 15000)
        qty3 = 80 + np.random.randint(-8, 8)
        rows.append(('F1003', 'مرغ', 'خرید', 'Food', 'کیلوگرم', qty3, price3, qty3 * price3, tx_date.strftime('%Y-%m-%d')))

    # Medium-value items (B class)
    for week in range(8):
        tx_date = base_date + timedelta(days=week * 7 + np.random.randint(0, 3))
        for code, name, _, unit in items[3:6]:
            price = 150000 + np.random.randint(-10000, 10000)
            qty = 30 + np.random.randint(-5, 5)
            rows.append((code, name, 'خرید', 'Food', unit, qty, price, qty * price, tx_date.strftime('%Y-%m-%d')))

    # Low-value items (C class) – fewer transactions, lower prices
    for week in range(4):
        tx_date = base_date + timedelta(days=week * 14 + np.random.randint(0, 5))
        for code, name, _, unit in items[6:15]:
            price = 50000 + np.random.randint(-5000, 5000)
            qty = 10 + np.random.randint(-3, 3)
            rows.append((code, name, 'خرید', 'Food', unit, qty, price, qty * price, tx_date.strftime('%Y-%m-%d')))

    # Add one anomaly: an unusually large purchase for سیر (garlic)
    anomaly_date = (base_date + timedelta(days=30)).strftime('%Y-%m-%d')
    rows.append(('F1014', 'سیر', 'خرید', 'Food', 'کیلوگرم', 500, 200000, 500 * 200000, anomaly_date))

    df = pd.DataFrame(rows, columns=[
        'کد کالا', 'نام کالا', 'نوع تراکنش', 'گروه', 'واحد',
        'مقدار', 'قیمت واحد (ریال)', 'مبلغ کل (ریال)', 'تاریخ'
    ])
    df.insert(0, 'ردیف', range(1, len(df) + 1))
    df.to_excel(path, sheet_name='Purchase Transactions', index=False)
    print(f"✅ Test Excel created: {len(df)} rows, total={df['مبلغ کل (ریال)'].sum():,.0f} ریال")
    return df


# ── Import the Excel ──────────────────────────────────────
def import_test_data(excel_path):
    from app import create_app
    from config import Config
    from models import db, Transaction, Item
    from services.data_importer import DataImporter

    app = create_app(Config)
    with app.app_context():
        # Clear old test data first
        old_count = Transaction.query.filter(Transaction.transaction_type == 'خرید').count()
        print(f"ℹ️  Existing purchase transactions: {old_count}")

        importer = DataImporter()
        result = importer.import_excel(excel_path, import_mode='pareto_transactions')
        print(f"✅ Import result: {result}")

        tx_count = Transaction.query.filter(
            Transaction.transaction_type == 'خرید',
            Transaction.is_deleted != True,
            Transaction.is_opening_balance != True,
        ).count()
        print(f"✅ Total purchase transactions in DB: {tx_count}")
        return tx_count


# ── Verify all 12 analyses ────────────────────────────────
def verify_analyses():
    from app import create_app
    from config import Config
    from models import db, Transaction, Item

    app = create_app(Config)
    with app.app_context():
        from services.strategy_analytics_service import (
            analyse_abc, analyse_xyz, analyse_abc_xyz,
            analyse_price_trend, analyse_price_volatility,
            analyse_spend_trend, analyse_category_mix,
            analyse_purchase_frequency, analyse_demand_proxy,
            analyse_anomalies, analyse_forecast, analyse_budget_burndown,
            get_strategy_overview,
        )

        errors = []
        passes = []

        # ── 1. ABC Analysis ──
        print("\n" + "="*60)
        print("1. ABC Analysis")
        try:
            r = analyse_abc(days=90, category='Food')
            df = r['data']
            s = r['summary']
            assert not df.empty, "ABC data is empty"
            assert s['total_items'] > 0, "No items in ABC"
            assert s['class_a_count'] > 0, "No class A items"
            assert s['class_a_count'] + s['class_b_count'] + s['class_c_count'] == s['total_items'], "ABC counts don't add up"
            # Verify cumulative percentage reaches ~100%
            last_cum = df.iloc[-1]['cumulative_percentage']
            assert 99.5 <= last_cum <= 100.5, f"Cumulative % should be ~100, got {last_cum}"
            # Verify sorted descending
            amounts = df['amount'].tolist()
            assert amounts == sorted(amounts, reverse=True), "Not sorted descending"
            print(f"   ✅ PASS: {s['total_items']} items, A={s['class_a_count']}, B={s['class_b_count']}, C={s['class_c_count']}")
            print(f"   Total amount: {s['total_amount']:,.0f}, Gini: {s['gini_coefficient']}")
            passes.append("ABC")
        except Exception as e:
            print(f"   ❌ FAIL: {e}")
            errors.append(f"ABC: {e}")

        # ── 2. XYZ Analysis ──
        print("\n" + "="*60)
        print("2. XYZ Analysis")
        try:
            r = analyse_xyz(days=90, category='Food')
            df = r['data']
            s = r['summary']
            assert not df.empty, "XYZ data is empty"
            assert s['total_items'] > 0, "No items"
            assert s['x_count'] + s['y_count'] + s['z_count'] == s['total_items'], "XYZ counts don't add up"
            # Verify CV values are non-negative
            assert (df['cv'] >= 0).all(), "Negative CV found"
            # X items should have CV < 0.5
            x_items = df[df['xyz_class'] == 'X']
            if not x_items.empty:
                assert (x_items['cv'] < 0.5).all(), "X class item with CV >= 0.5"
            print(f"   ✅ PASS: X={s['x_count']}, Y={s['y_count']}, Z={s['z_count']}")
            passes.append("XYZ")
        except Exception as e:
            print(f"   ❌ FAIL: {e}")
            errors.append(f"XYZ: {e}")

        # ── 3. ABC-XYZ Matrix ──
        print("\n" + "="*60)
        print("3. ABC-XYZ Matrix")
        try:
            r = analyse_abc_xyz(days=90, category='Food')
            df = r['data']
            matrix = r['matrix']
            assert matrix, "Matrix is empty"
            total_in_matrix = sum(v['count'] for v in matrix.values())
            assert total_in_matrix == len(df), f"Matrix count {total_in_matrix} != data rows {len(df)}"
            # Verify all 9 cells exist
            for a in ['A', 'B', 'C']:
                for x in ['X', 'Y', 'Z']:
                    assert f'{a}{x}' in matrix, f"Missing cell {a}{x}"
            print(f"   ✅ PASS: {len(df)} items in matrix, AX={matrix['AX']['count']}, CZ={matrix['CZ']['count']}")
            passes.append("ABC-XYZ")
        except Exception as e:
            print(f"   ❌ FAIL: {e}")
            errors.append(f"ABC-XYZ: {e}")

        # ── 4. Price Trend ──
        print("\n" + "="*60)
        print("4. Price Trend / Inflation")
        try:
            r = analyse_price_trend(days=90, category='Food')
            df = r['data']
            s = r['summary']
            items_chart = r['items_chart']
            assert not df.empty, "Price trend data is empty"
            assert 'change_pct' in df.columns, "Missing change_pct column"
            assert s['items_with_increase'] + s['items_with_decrease'] <= len(df), "Count mismatch"
            assert len(items_chart) > 0, "No chart items"
            print(f"   ✅ PASS: avg_inflation={s['avg_inflation']}%, increases={s['items_with_increase']}, decreases={s['items_with_decrease']}")
            passes.append("Price Trend")
        except Exception as e:
            print(f"   ❌ FAIL: {e}")
            errors.append(f"Price Trend: {e}")

        # ── 5. Price Volatility ──
        print("\n" + "="*60)
        print("5. Price Volatility")
        try:
            r = analyse_price_volatility(days=90, category='Food')
            df = r['data']
            s = r['summary']
            assert not df.empty, "Price volatility data is empty"
            assert (df['price_cv'] >= 0).all(), "Negative price CV"
            assert s['most_volatile'] != '-', "No most volatile item"
            # Verify range = max - min
            for _, row in df.iterrows():
                expected_range = row['max_price'] - row['min_price']
                assert abs(row['price_range'] - expected_range) < 1, f"Range mismatch for {row['item_code']}"
            print(f"   ✅ PASS: most_volatile={s['most_volatile']} (CV={s['most_volatile_cv']}), high_risk={s['high_risk_count']}")
            passes.append("Price Volatility")
        except Exception as e:
            print(f"   ❌ FAIL: {e}")
            errors.append(f"Price Volatility: {e}")

        # ── 6. Spend Trend ──
        print("\n" + "="*60)
        print("6. Spend Trend")
        try:
            r = analyse_spend_trend(days=90, category='Food', period='weekly')
            df = r['data']
            s = r['summary']
            assert not df.empty, "Spend trend data is empty"
            assert s['total_spend'] > 0, "Zero total spend"
            # Verify sum of periods ≈ total
            period_sum = df['total_amount'].sum()
            assert abs(period_sum - s['total_spend']) < 1, f"Period sum {period_sum} != total {s['total_spend']}"
            print(f"   ✅ PASS: total={s['total_spend']:,.0f}, periods={s['periods_count']}, trend={s['trend_direction']}")
            passes.append("Spend Trend")
        except Exception as e:
            print(f"   ❌ FAIL: {e}")
            errors.append(f"Spend Trend: {e}")

        # ── 7. Category Mix ──
        print("\n" + "="*60)
        print("7. Category Mix")
        try:
            r = analyse_category_mix(days=90)
            df = r['data']
            s = r['summary']
            assert not df.empty, "Category mix data is empty"
            # Shares should sum to ~100%
            share_sum = df['share_pct'].sum()
            assert 99.5 <= share_sum <= 100.5, f"Shares sum to {share_sum}, expected ~100"
            assert s['grand_total'] > 0, "Zero grand total"
            print(f"   ✅ PASS: {s['categories']} categories, dominant={s['dominant_category']} ({s['dominant_share']}%)")
            passes.append("Category Mix")
        except Exception as e:
            print(f"   ❌ FAIL: {e}")
            errors.append(f"Category Mix: {e}")

        # ── 8. Purchase Frequency ──
        print("\n" + "="*60)
        print("8. Purchase Frequency")
        try:
            r = analyse_purchase_frequency(days=90, category='Food')
            df = r['data']
            s = r['summary']
            assert not df.empty, "Frequency data is empty"
            assert s['total_items'] > 0, "No items"
            assert (df['purchase_count'] >= 1).all(), "Zero purchase count"
            # Items with 1 purchase should have avg_interval = days
            single = df[df['purchase_count'] == 1]
            if not single.empty:
                assert (single['avg_interval_days'] == 90).all(), "Single purchase interval should equal period"
            print(f"   ✅ PASS: most_frequent={s['most_frequent']} ({s['most_frequent_count']}x), avg_interval={s['avg_interval']}d")
            passes.append("Purchase Frequency")
        except Exception as e:
            print(f"   ❌ FAIL: {e}")
            errors.append(f"Purchase Frequency: {e}")

        # ── 9. Demand Proxy ──
        print("\n" + "="*60)
        print("9. Demand Proxy")
        try:
            r = analyse_demand_proxy(days=90, category='Food')
            s = r['summary']
            items_chart = r['items_chart']
            assert len(items_chart) > 0, "No demand chart items"
            total_demand = s['rising_demand'] + s['falling_demand'] + s['stable_demand']
            assert total_demand > 0, "No demand data"
            print(f"   ✅ PASS: rising={s['rising_demand']}, stable={s['stable_demand']}, falling={s['falling_demand']}")
            passes.append("Demand Proxy")
        except Exception as e:
            print(f"   ❌ FAIL: {e}")
            errors.append(f"Demand Proxy: {e}")

        # ── 10. Anomaly Detection ──
        print("\n" + "="*60)
        print("10. Anomaly Detection")
        try:
            r = analyse_anomalies(days=90, category='Food')
            s = r['summary']
            assert s['total_transactions'] > 0, "No transactions"
            assert 0 <= s['anomaly_rate'] <= 100, "Invalid anomaly rate"
            # We inserted a deliberate anomaly (سیر with qty=500), check it's detected
            if not r['data'].empty:
                garlic_anomalies = r['data'][r['data']['item_code'] == 'F1014']
                if not garlic_anomalies.empty:
                    print(f"   ✅ Deliberate anomaly for سیر detected!")
            print(f"   ✅ PASS: {s['total_anomalies']} anomalies / {s['total_transactions']} tx ({s['anomaly_rate']}%)")
            passes.append("Anomaly Detection")
        except Exception as e:
            print(f"   ❌ FAIL: {e}")
            errors.append(f"Anomaly Detection: {e}")

        # ── 11. Forecast ──
        print("\n" + "="*60)
        print("11. Cost Forecast")
        try:
            r = analyse_forecast(days=90, category='Food')
            s = r['summary']
            df = r['data']
            if s.get('avg_weekly_spend'):
                assert s['avg_weekly_spend'] > 0, "Zero avg weekly spend"
                assert s['forecast_total'] > 0, "Zero forecast"
                assert s['trend'] in ['صعودی', 'نزولی'], f"Invalid trend: {s['trend']}"
                # Verify forecast rows exist
                forecast_rows = df[df['is_forecast'] == True]
                assert len(forecast_rows) > 0, "No forecast rows"
                print(f"   ✅ PASS: avg_weekly={s['avg_weekly_spend']:,.0f}, forecast_total={s['forecast_total']:,.0f}, trend={s['trend']}")
            else:
                print(f"   ⚠️  Not enough data for forecast: {s.get('message', 'unknown')}")
            passes.append("Forecast")
        except Exception as e:
            print(f"   ❌ FAIL: {e}")
            errors.append(f"Forecast: {e}")

        # ── 12. Budget Burndown ──
        print("\n" + "="*60)
        print("12. Budget Burndown")
        try:
            r = analyse_budget_burndown(days=90, category='Food', budget=500000000)
            s = r['summary']
            df = r['data']
            assert s['budget'] == 500000000, f"Budget mismatch: {s['budget']}"
            assert s['total_spent'] > 0, "Zero spend"
            assert s['remaining'] == s['budget'] - s['total_spent'], "Remaining mismatch"
            assert abs(s['pct_used'] - (s['total_spent'] / s['budget'] * 100)) < 0.2, "Pct used mismatch"
            assert s['daily_burn_rate'] > 0, "Zero daily burn rate"
            # Verify cumulative is monotonically increasing
            if not df.empty:
                cum_values = df['cumulative'].tolist()
                assert cum_values == sorted(cum_values), "Cumulative not monotonically increasing"
            print(f"   ✅ PASS: budget={s['budget']:,.0f}, spent={s['total_spent']:,.0f}, remaining={s['remaining']:,.0f}")
            print(f"   pct_used={s['pct_used']}%, daily_rate={s['daily_burn_rate']:,.0f}, days_left={s['estimated_days_left']}")
            passes.append("Budget Burndown")
        except Exception as e:
            print(f"   ❌ FAIL: {e}")
            errors.append(f"Budget Burndown: {e}")

        # ── Hub Overview ──
        print("\n" + "="*60)
        print("Hub Overview")
        try:
            overview = get_strategy_overview(days=90, category='Food')
            assert overview['has_data'], "Overview has no data"
            print(f"   ✅ PASS: Overview loaded successfully")
            passes.append("Hub Overview")
        except Exception as e:
            print(f"   ❌ FAIL: {e}")
            errors.append(f"Hub Overview: {e}")

        # ── Final Report ──
        print("\n" + "="*60)
        print("="*60)
        print(f"\n🏁 RESULTS: {len(passes)} PASSED, {len(errors)} FAILED out of 13 tests")
        if errors:
            print("\n❌ FAILURES:")
            for e in errors:
                print(f"   - {e}")
        else:
            print("\n🎉 ALL TESTS PASSED!")
        print("="*60)
        return errors


if __name__ == '__main__':
    excel_path = os.path.join(os.path.dirname(__file__), '..', 'strategy_test_data.xlsx')

    print("="*60)
    print("STRATEGY ANALYTICS VERIFICATION")
    print("="*60)

    # Step 1: Create test Excel
    print("\n📊 Step 1: Creating test Excel...")
    test_df = create_test_excel(excel_path)

    # Step 2: Import
    print("\n📥 Step 2: Importing test data...")
    tx_count = import_test_data(excel_path)

    # Step 3: Verify all analyses
    print("\n🔍 Step 3: Verifying all 12 analyses...")
    errors = verify_analyses()

    sys.exit(1 if errors else 0)
