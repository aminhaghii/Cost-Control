"""
Warehouse Service - Core warehouse management operations
"""
from datetime import datetime, date, timedelta
from decimal import Decimal
from sqlalchemy import func
from models import db, Transaction, Item, Alert, WarehouseSettings, InventoryCount
from models.transaction import WASTE_REASONS, DEPARTMENTS
from services.hotel_scope_service import user_can_access_hotel, get_allowed_hotel_ids
import logging

logger = logging.getLogger(__name__)


class WarehouseService:
    """Core warehouse management service"""
    
    @staticmethod
    def get_warehouse_dashboard(hotel_id: int, user) -> dict:
        """Get complete warehouse dashboard data"""
        if not user_can_access_hotel(user, hotel_id):
            raise PermissionError("دسترسی غیرمجاز به این هتل")
        
        settings = WarehouseSettings.get_or_create(hotel_id)
        
        # Summary stats
        items = Item.query.filter_by(hotel_id=hotel_id, is_active=True).all()
        total_items = len(items)
        
        # Calculate total value from last known price
        total_value = 0
        for item in items:
            # Fallback chain: last purchase -> any transaction with price -> 0
            last_price_tx = Transaction.query.filter(
                Transaction.item_id == item.id,
                Transaction.unit_price > 0,
                Transaction.is_deleted == False
            ).order_by(Transaction.transaction_date.desc()).first()
            
            if last_price_tx and item.current_stock:
                total_value += float(item.current_stock) * float(last_price_tx.unit_price)
        
        low_stock_count = sum(1 for i in items if (i.current_stock or 0) <= (i.min_stock or 0))
        high_stock_count = sum(1 for i in items if i.max_stock and (i.current_stock or 0) >= i.max_stock)
        
        # Pending approvals
        pending_approvals = Transaction.query.filter_by(
            hotel_id=hotel_id,
            approval_status='pending',
            is_deleted=False
        ).count()
        
        # Active alerts
        active_alerts = Alert.query.filter_by(
            hotel_id=hotel_id,
            status='active'
        ).order_by(Alert.created_at.desc()).limit(10).all()
        
        # Recent movements
        recent_movements = Transaction.query.filter_by(
            hotel_id=hotel_id,
            is_deleted=False
        ).order_by(Transaction.created_at.desc()).limit(10).all()
        
        # Waste rate (last 30 days)
        waste_summary = WarehouseService.get_waste_rate(hotel_id, days=30)
        
        # Items needing count
        items_needing_count = WarehouseService.get_items_needing_count(hotel_id, settings.count_frequency_days)
        
        return {
            'summary': {
                'total_items': total_items,
                'total_value': total_value,
                'low_stock_count': low_stock_count,
                'high_stock_count': high_stock_count,
                'pending_approvals': pending_approvals,
            },
            'alerts': active_alerts,
            'recent_movements': recent_movements,
            'waste_rate': waste_summary.get('waste_rate', 0),
            'items_needing_count': items_needing_count[:5],
            'settings': settings
        }
    
    @staticmethod
    def get_stock_status(hotel_id: int, category: str = None) -> list:
        """Get stock status for all items"""
        query = Item.query.filter_by(hotel_id=hotel_id, is_active=True)
        if category:
            query = query.filter_by(category=category)
        
        items = query.order_by(Item.item_name_fa).all()
        result = []
        
        for item in items:
            stock = float(item.current_stock or 0)
            min_stock = float(item.min_stock or 0)
            max_stock = float(item.max_stock or 0) if item.max_stock else None
            
            if stock <= min_stock:
                status = 'low'
            elif max_stock and stock >= max_stock:
                status = 'high'
            else:
                status = 'normal'
            
            # Calculate days on hand
            days_on_hand = WarehouseService.calculate_days_on_hand(item)
            
            result.append({
                'item': item,
                'status': status,
                'days_on_hand': days_on_hand,
                'stock_percentage': (stock / max_stock * 100) if max_stock else None
            })
        
        return result
    
    @staticmethod
    def calculate_days_on_hand(item) -> int:
        """Calculate how many days current stock will last based on avg consumption"""
        # Get average daily consumption (last 30 days)
        thirty_days_ago = date.today() - timedelta(days=30)
        
        consumption = db.session.query(func.sum(Transaction.quantity)).filter(
            Transaction.item_id == item.id,
            Transaction.transaction_type == 'مصرف',
            Transaction.transaction_date >= thirty_days_ago,
            Transaction.is_deleted == False
        ).scalar() or 0
        
        avg_daily = float(consumption) / 30 if consumption else 0
        
        if avg_daily <= 0:
            return 999  # No consumption, infinite days
        
        return int(float(item.current_stock or 0) / avg_daily)
    
    @staticmethod
    def get_movements(hotel_id: int, item_id: int = None, 
                      start_date: date = None, end_date: date = None,
                      movement_type: str = None, limit: int = 100) -> list:
        """Get movement history with filters"""
        query = Transaction.query.filter_by(hotel_id=hotel_id, is_deleted=False)
        
        if item_id:
            query = query.filter_by(item_id=item_id)
        if start_date:
            query = query.filter(Transaction.transaction_date >= start_date)
        if end_date:
            query = query.filter(Transaction.transaction_date <= end_date)
        if movement_type:
            query = query.filter_by(transaction_type=movement_type)
        
        return query.order_by(Transaction.created_at.desc()).limit(limit).all()
    
    @staticmethod
    def get_waste_rate(hotel_id: int, days: int = 30) -> dict:
        """Calculate waste rate for period"""
        start_date = date.today() - timedelta(days=days)
        
        # Total purchases
        total_purchase = db.session.query(func.sum(Transaction.total_amount)).filter(
            Transaction.hotel_id == hotel_id,
            Transaction.transaction_type == 'خرید',
            Transaction.transaction_date >= start_date,
            Transaction.is_deleted == False,
            Transaction.is_opening_balance == False
        ).scalar() or Decimal(0)
        
        # Total waste
        total_waste = db.session.query(func.sum(Transaction.total_amount)).filter(
            Transaction.hotel_id == hotel_id,
            Transaction.transaction_type == 'ضایعات',
            Transaction.transaction_date >= start_date,
            Transaction.is_deleted == False
        ).scalar() or Decimal(0)
        
        waste_rate = (float(total_waste) / float(total_purchase) * 100) if total_purchase else 0
        
        return {
            'total_purchase': float(total_purchase),
            'total_waste': float(total_waste),
            'waste_rate': round(waste_rate, 2),
            'status': 'good' if waste_rate < 3 else ('warning' if waste_rate < 5 else 'critical')
        }
    
    @staticmethod
    def get_items_needing_count(hotel_id: int, days_threshold: int = 30) -> list:
        """Get items that need physical count"""
        cutoff_date = date.today() - timedelta(days=days_threshold)
        
        # Subquery for last count date per item
        subquery = db.session.query(
            InventoryCount.item_id,
            func.max(InventoryCount.count_date).label('last_count')
        ).filter_by(hotel_id=hotel_id).group_by(InventoryCount.item_id).subquery()
        
        # Items never counted or not counted recently
        items = Item.query.filter_by(hotel_id=hotel_id, is_active=True).outerjoin(
            subquery, Item.id == subquery.c.item_id
        ).filter(
            (subquery.c.last_count == None) | (subquery.c.last_count < cutoff_date)
        ).all()
        
        return items
    
    @staticmethod
    def get_pending_approvals(hotel_id: int) -> list:
        """Get transactions pending approval"""
        return Transaction.query.filter(
            Transaction.hotel_id == hotel_id,
            Transaction.requires_approval == True,
            Transaction.approval_status == 'pending',
            Transaction.is_deleted == False
        ).order_by(Transaction.created_at.desc()).all()
    
    @staticmethod
    def approve_transaction(transaction_id: int, approver_id: int) -> Transaction:
        """Approve a pending transaction and update stock"""
        tx = Transaction.query.get_or_404(transaction_id)
        
        if tx.approval_status != 'pending':
            raise ValueError("این تراکنش در انتظار تایید نیست")
        
        # Update approval fields
        tx.approval_status = 'approved'
        tx.approved_by_id = approver_id
        tx.approved_at = datetime.utcnow()
        
        # NOW update stock
        item = Item.query.get(tx.item_id)
        if item:
            item.current_stock = (item.current_stock or 0) + tx.signed_quantity
            # Check and create stock alerts (now that stock is updated)
            from routes.transactions import check_and_create_stock_alert
            check_and_create_stock_alert(item)
        
        # Resolve related alert
        Alert.query.filter_by(
            related_transaction_id=transaction_id,
            alert_type='pending_approval',
            status='active'
        ).update({
            'status': 'resolved',
            'is_resolved': True,
            'resolved_at': datetime.utcnow(),
            'acknowledged_by_id': approver_id,
            'acknowledged_at': datetime.utcnow()
        })
        
        db.session.commit()
        logger.info(f"Transaction {transaction_id} approved by user {approver_id}")
        
        return tx
    
    @staticmethod
    def reject_transaction(transaction_id: int, approver_id: int, reason: str = None) -> Transaction:
        """Reject a pending transaction - stock NOT updated"""
        tx = Transaction.query.get_or_404(transaction_id)
        
        if tx.approval_status != 'pending':
            raise ValueError("این تراکنش در انتظار تایید نیست")
        
        # Update approval fields
        tx.approval_status = 'rejected'
        tx.approved_by_id = approver_id
        tx.approved_at = datetime.utcnow()
        
        # Soft delete the transaction
        tx.is_deleted = True
        tx.deleted_at = datetime.utcnow()
        
        if reason:
            tx.description = (tx.description or '') + f' [رد شده: {reason}]'
        
        # Resolve related alert
        Alert.query.filter_by(
            related_transaction_id=transaction_id,
            alert_type='pending_approval',
            status='active'
        ).update({
            'status': 'resolved',
            'is_resolved': True,
            'resolved_at': datetime.utcnow(),
            'acknowledged_by_id': approver_id,
            'acknowledged_at': datetime.utcnow()
        })
        
        db.session.commit()
        logger.info(f"Transaction {transaction_id} rejected by user {approver_id}: {reason}")
        
        return tx
    
    @staticmethod
    def check_and_create_alerts(hotel_id: int):
        """Check thresholds and create alerts"""
        items = Item.query.filter_by(hotel_id=hotel_id, is_active=True).all()
        settings = WarehouseSettings.get_or_create(hotel_id)
        
        for item in items:
            stock = float(item.current_stock or 0)
            min_stock = float(item.min_stock or 0)
            max_stock = float(item.max_stock or 0) if item.max_stock else None
            
            # Low stock alert
            if stock <= min_stock and settings.notify_on_low_stock:
                Alert.create_if_not_exists(
                    hotel_id=hotel_id,
                    alert_type='low_stock',
                    item_id=item.id,
                    message=f'موجودی {item.item_name_fa} کمتر از حد مجاز است ({stock:.2f} از {min_stock:.2f})',
                    severity='warning',
                    threshold_value=Decimal(str(min_stock)),
                    actual_value=Decimal(str(stock))
                )
            
            # High stock alert
            if max_stock and stock >= max_stock:
                Alert.create_if_not_exists(
                    hotel_id=hotel_id,
                    alert_type='high_stock',
                    item_id=item.id,
                    message=f'موجودی {item.item_name_fa} بیشتر از حد مجاز است ({stock:.2f} از {max_stock:.2f})',
                    severity='info',
                    threshold_value=Decimal(str(max_stock)),
                    actual_value=Decimal(str(stock))
                )
        
        db.session.commit()
    
    @staticmethod
    def check_waste_approval_needed(hotel_id: int, waste_value: float) -> bool:
        """Check if waste transaction needs approval"""
        settings = WarehouseSettings.get_or_create(hotel_id)
        return settings.check_waste_approval_needed(waste_value)
    
    @staticmethod
    def validate_stock_for_consumption(item, quantity: float) -> tuple:
        """Validate if there's enough stock for consumption"""
        current_stock = float(item.current_stock or 0)
        if quantity > current_stock:
            return False, f'موجودی کافی نیست. موجودی فعلی: {current_stock:.2f} {item.unit}'
        return True, None
