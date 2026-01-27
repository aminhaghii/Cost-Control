"""
Waste Analysis Service - Waste tracking and analysis
"""
from datetime import datetime, date, timedelta
from decimal import Decimal
from sqlalchemy import func, extract
from models import db, Transaction, Item
from models.transaction import WASTE_REASONS
import logging

logger = logging.getLogger(__name__)


class WasteAnalysisService:
    """Service for waste analysis and reporting"""
    
    @staticmethod
    def get_waste_summary(hotel_id: int, start_date: date, end_date: date) -> dict:
        """Get waste summary for period"""
        # Total purchases
        total_purchase = db.session.query(func.sum(Transaction.total_amount)).filter(
            Transaction.hotel_id == hotel_id,
            Transaction.transaction_type == 'خرید',
            Transaction.transaction_date.between(start_date, end_date),
            Transaction.is_deleted == False,
            Transaction.is_opening_balance == False
        ).scalar() or Decimal(0)
        
        # Total waste
        total_waste = db.session.query(func.sum(Transaction.total_amount)).filter(
            Transaction.hotel_id == hotel_id,
            Transaction.transaction_type == 'ضایعات',
            Transaction.transaction_date.between(start_date, end_date),
            Transaction.is_deleted == False
        ).scalar() or Decimal(0)
        
        # Waste rate
        waste_rate = (float(total_waste) / float(total_purchase) * 100) if total_purchase else 0
        
        # Target rate (industry standard)
        target_rate = 3.0
        
        return {
            'total_purchase': float(total_purchase),
            'total_waste': float(total_waste),
            'waste_rate': round(waste_rate, 2),
            'target_rate': target_rate,
            'status': 'good' if waste_rate < 3 else ('warning' if waste_rate < 5 else 'critical'),
            'savings_potential': max(0, float(total_waste) - (float(total_purchase) * target_rate / 100))
        }
    
    @staticmethod
    def get_waste_by_reason(hotel_id: int, start_date: date, end_date: date) -> list:
        """Get waste breakdown by reason"""
        results = db.session.query(
            Transaction.waste_reason,
            func.sum(Transaction.total_amount).label('amount'),
            func.sum(Transaction.quantity).label('quantity'),
            func.count(Transaction.id).label('count')
        ).filter(
            Transaction.hotel_id == hotel_id,
            Transaction.transaction_type == 'ضایعات',
            Transaction.transaction_date.between(start_date, end_date),
            Transaction.is_deleted == False
        ).group_by(Transaction.waste_reason).all()
        
        total = sum(float(r[1] or 0) for r in results)
        
        return [{
            'reason': r[0] or 'other',
            'reason_label': WASTE_REASONS.get(r[0], 'سایر'),
            'amount': float(r[1] or 0),
            'quantity': float(r[2] or 0),
            'count': r[3],
            'percentage': round((float(r[1] or 0) / total * 100), 1) if total else 0
        } for r in results]
    
    @staticmethod
    def get_waste_by_category(hotel_id: int, start_date: date, end_date: date) -> list:
        """Get waste breakdown by category"""
        results = db.session.query(
            Transaction.category,
            func.sum(Transaction.total_amount).label('amount'),
            func.count(Transaction.id).label('count')
        ).filter(
            Transaction.hotel_id == hotel_id,
            Transaction.transaction_type == 'ضایعات',
            Transaction.transaction_date.between(start_date, end_date),
            Transaction.is_deleted == False
        ).group_by(Transaction.category).all()
        
        return [{
            'category': r[0],
            'amount': float(r[1] or 0),
            'count': r[2]
        } for r in results]
    
    @staticmethod
    def get_top_wasted_items(hotel_id: int, start_date: date, end_date: date,
                              limit: int = 10) -> list:
        """Get items with highest waste"""
        results = db.session.query(
            Item,
            func.sum(Transaction.total_amount).label('waste_amount'),
            func.sum(Transaction.quantity).label('waste_qty'),
            func.count(Transaction.id).label('waste_count')
        ).join(Transaction, Item.id == Transaction.item_id).filter(
            Transaction.hotel_id == hotel_id,
            Transaction.transaction_type == 'ضایعات',
            Transaction.transaction_date.between(start_date, end_date),
            Transaction.is_deleted == False
        ).group_by(Item.id).order_by(
            func.sum(Transaction.total_amount).desc()
        ).limit(limit).all()
        
        return [{
            'item': r[0],
            'waste_amount': float(r[1] or 0),
            'waste_quantity': float(r[2] or 0),
            'waste_count': r[3]
        } for r in results]
    
    @staticmethod
    def get_waste_trend(hotel_id: int, months: int = 6) -> list:
        """Get monthly waste trend"""
        trend = []
        
        for i in range(months - 1, -1, -1):
            # Calculate month boundaries
            target_date = date.today() - timedelta(days=i * 30)
            month_start = date(target_date.year, target_date.month, 1)
            if target_date.month == 12:
                month_end = date(target_date.year + 1, 1, 1) - timedelta(days=1)
            else:
                month_end = date(target_date.year, target_date.month + 1, 1) - timedelta(days=1)
            
            # Get waste for this month
            waste = db.session.query(func.sum(Transaction.total_amount)).filter(
                Transaction.hotel_id == hotel_id,
                Transaction.transaction_type == 'ضایعات',
                Transaction.transaction_date.between(month_start, month_end),
                Transaction.is_deleted == False
            ).scalar() or 0
            
            # Get purchases for this month
            purchase = db.session.query(func.sum(Transaction.total_amount)).filter(
                Transaction.hotel_id == hotel_id,
                Transaction.transaction_type == 'خرید',
                Transaction.transaction_date.between(month_start, month_end),
                Transaction.is_deleted == False,
                Transaction.is_opening_balance == False
            ).scalar() or 0
            
            rate = (float(waste) / float(purchase) * 100) if purchase else 0
            
            trend.append({
                'month': month_start.strftime('%Y-%m'),
                'month_label': month_start.strftime('%B %Y'),
                'waste_amount': float(waste),
                'purchase_amount': float(purchase),
                'waste_rate': round(rate, 2)
            })
        
        return trend
    
    @staticmethod
    def get_waste_by_department(hotel_id: int, start_date: date, end_date: date) -> list:
        """Get waste by destination department (for consumption that became waste)"""
        # This tracks which departments are generating most waste
        results = db.session.query(
            Transaction.destination_department,
            func.sum(Transaction.total_amount).label('amount'),
            func.count(Transaction.id).label('count')
        ).filter(
            Transaction.hotel_id == hotel_id,
            Transaction.transaction_type == 'ضایعات',
            Transaction.transaction_date.between(start_date, end_date),
            Transaction.is_deleted == False,
            Transaction.destination_department != None
        ).group_by(Transaction.destination_department).all()
        
        from models.transaction import DEPARTMENTS
        return [{
            'department': r[0],
            'department_label': DEPARTMENTS.get(r[0], r[0] or 'نامشخص'),
            'amount': float(r[1] or 0),
            'count': r[2]
        } for r in results]
    
    @staticmethod
    def get_waste_alerts(hotel_id: int, threshold_pct: float = 5.0) -> list:
        """Get items with waste rate above threshold"""
        # Last 30 days
        start_date = date.today() - timedelta(days=30)
        end_date = date.today()
        
        # Get purchase and waste per item
        purchase_subq = db.session.query(
            Transaction.item_id,
            func.sum(Transaction.total_amount).label('purchase_total')
        ).filter(
            Transaction.hotel_id == hotel_id,
            Transaction.transaction_type == 'خرید',
            Transaction.transaction_date.between(start_date, end_date),
            Transaction.is_deleted == False
        ).group_by(Transaction.item_id).subquery()
        
        waste_subq = db.session.query(
            Transaction.item_id,
            func.sum(Transaction.total_amount).label('waste_total')
        ).filter(
            Transaction.hotel_id == hotel_id,
            Transaction.transaction_type == 'ضایعات',
            Transaction.transaction_date.between(start_date, end_date),
            Transaction.is_deleted == False
        ).group_by(Transaction.item_id).subquery()
        
        # Join and calculate rate
        results = db.session.query(
            Item,
            purchase_subq.c.purchase_total,
            waste_subq.c.waste_total
        ).outerjoin(
            purchase_subq, Item.id == purchase_subq.c.item_id
        ).outerjoin(
            waste_subq, Item.id == waste_subq.c.item_id
        ).filter(
            Item.hotel_id == hotel_id,
            Item.is_active == True,
            waste_subq.c.waste_total != None
        ).all()
        
        alerts = []
        for item, purchase, waste in results:
            if purchase and waste:
                rate = float(waste) / float(purchase) * 100
                if rate >= threshold_pct:
                    alerts.append({
                        'item': item,
                        'purchase_amount': float(purchase),
                        'waste_amount': float(waste),
                        'waste_rate': round(rate, 2)
                    })
        
        return sorted(alerts, key=lambda x: x['waste_rate'], reverse=True)
