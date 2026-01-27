from models import db, Transaction, Item
from sqlalchemy import func
from datetime import date, timedelta
from decimal import Decimal
import pandas as pd
from services.hotel_scope_service import get_allowed_hotel_ids
from utils.decimal_utils import to_decimal

class ABCService:
    
    def get_abc_classification(self, mode='خرید', category='Food', days=30, 
                               hotel_ids=None, user=None, exclude_opening=True):
        """
        Get items classified by ABC with recommendations
        P0-4: Only use purchase transactions, exclude opening balances
        P0-3: Apply hotel scoping
        """
        start_date = date.today() - timedelta(days=days)
        
        query = db.session.query(
            Item.id,
            Item.item_code,
            Item.item_name_fa,
            Item.unit,
            func.sum(Transaction.total_amount).label('total_amount'),
            func.sum(Transaction.quantity).label('total_quantity')
        ).join(Transaction).filter(
            Transaction.transaction_type == mode,
            Transaction.category == category,
            Transaction.transaction_date >= start_date,
            Transaction.is_deleted != True  # P0-1: Exclude soft-deleted
        )
        
        # P0-4: Exclude opening balances from spend reports
        if exclude_opening:
            query = query.filter(Transaction.is_opening_balance != True)
        
        # P0-3: Apply hotel scoping
        if user:
            allowed = get_allowed_hotel_ids(user)
            if allowed is not None:  # None means admin (all hotels)
                query = query.filter(Item.hotel_id.in_(allowed))
        elif hotel_ids:
            query = query.filter(Item.hotel_id.in_(hotel_ids))
        
        query = query.group_by(Item.id).order_by(func.sum(Transaction.total_amount).desc())
        
        results = query.all()
        
        if not results:
            return {'A': [], 'B': [], 'C': []}
        
        # Bug #18: Filter out NULL/None values and negative amounts
        normalized_results = []
        for r in results:
            amount_dec = to_decimal(r.total_amount)
            qty = to_decimal(r.total_quantity, quantize=None) if r.total_quantity is not None else Decimal('0')
            if amount_dec <= 0:
                continue
            normalized_results.append({
                'item_code': r.item_code,
                'item_name': r.item_name_fa,
                'unit': r.unit,
                'amount_dec': amount_dec,
                'quantity': float(qty) if qty is not None else 0
            })
        
        if not normalized_results:
            return {'A': [], 'B': [], 'C': []}
        
        total_amount_dec = sum((r['amount_dec'] for r in normalized_results), Decimal('0.00'))
        cumulative_dec = Decimal('0.00')
        classified = {'A': [], 'B': [], 'C': []}
        
        for row in normalized_results:
            amount_dec = row['amount_dec']
            cumulative_dec += amount_dec
            if total_amount_dec > 0:
                percentage = (amount_dec / total_amount_dec) * Decimal('100')
                cumulative_percentage = (cumulative_dec / total_amount_dec) * Decimal('100')
            else:
                percentage = Decimal('0')
                cumulative_percentage = Decimal('0')
            
            # ABC Classification (Industry Standard - Strict Threshold)
            # Based on cumulative percentage AFTER adding the item
            # Class A: cumulative ≤ 80%
            # Class B: 80% < cumulative ≤ 95%
            # Class C: cumulative > 95%
            if cumulative_percentage <= Decimal('80'):
                abc_class = 'A'
            elif cumulative_percentage <= Decimal('95'):
                abc_class = 'B'
            else:
                abc_class = 'C'
            
            # Bug #17: Better precision for small percentages
            if Decimal('0') < percentage < Decimal('0.01'):
                percentage_display = 0.01
            else:
                percentage_display = float(percentage.quantize(Decimal('0.01')))
            
            item_data = {
                'item_code': row['item_code'],
                'item_name': row['item_name'],
                'unit': row['unit'],
                'total_amount': float(amount_dec),
                'total_quantity': row['quantity'],
                'percentage': percentage_display,
                'percentage_exact': float(percentage.quantize(Decimal('0.0001'))),
                'cumulative_percentage': float(cumulative_percentage.quantize(Decimal('0.01')))
            }
            
            classified[abc_class].append(item_data)
        
        return classified
    
    def get_recommendations(self, abc_class):
        """
        Get management recommendations for each ABC class
        """
        recommendations = {
            'A': {
                'title': 'کلاس A: اقلام حیاتی',
                'subtitle': '80% ارزش کل',
                'color': 'success',
                'icon': '✅',
                'actions': [
                    'کنترل روزانه موجودی',
                    'سفارش‌گذاری دقیق با پیش‌بینی',
                    'تأمین‌کننده بکاپ داشته باشید',
                    'بررسی قیمت‌ها به صورت هفتگی',
                    'ذخیره ایمنی بالا'
                ]
            },
            'B': {
                'title': 'کلاس B: اقلام مهم',
                'subtitle': '15% ارزش کل',
                'color': 'warning',
                'icon': '⚠️',
                'actions': [
                    'کنترل هفتگی موجودی',
                    'سفارش‌گذاری معمولی',
                    'بررسی ماهانه قیمت‌ها',
                    'ذخیره ایمنی متوسط'
                ]
            },
            'C': {
                'title': 'کلاس C: اقلام معمولی',
                'subtitle': '5% ارزش کل',
                'color': 'secondary',
                'icon': '⚪',
                'actions': [
                    'کنترل ماهانه موجودی',
                    'سفارش انبوه',
                    'حداقل ذخیره ایمنی',
                    'امکان جایگزینی آسان'
                ]
            }
        }
        
        return recommendations.get(abc_class, recommendations['C'])
