"""
Inventory Count Service - Physical stock counting operations
"""
from datetime import datetime, date, timedelta
from decimal import Decimal
from sqlalchemy import func
from models import db, Transaction, Item, Alert, InventoryCount, WarehouseSettings
from models.inventory_count import VARIANCE_REASONS
import logging

logger = logging.getLogger(__name__)


class InventoryCountService:
    """Service for physical inventory counting"""
    
    @staticmethod
    def create_count(hotel_id: int, item_id: int, physical_quantity: float,
                     user_id: int, count_date: date = None) -> InventoryCount:
        """Create a new inventory count"""
        item = Item.query.get_or_404(item_id)
        
        if item.hotel_id != hotel_id:
            raise ValueError("کالا متعلق به این هتل نیست")
        
        system_qty = Decimal(str(item.current_stock or 0))
        physical_qty = Decimal(str(physical_quantity))
        variance = physical_qty - system_qty
        
        if system_qty != 0:
            variance_pct = (variance / system_qty * 100).quantize(Decimal('0.01'))
        else:
            variance_pct = Decimal('100.00') if variance != 0 else Decimal('0.00')
        
        count = InventoryCount(
            hotel_id=hotel_id,
            item_id=item_id,
            counted_by_id=user_id,
            count_date=count_date or date.today(),
            system_quantity=system_qty,
            physical_quantity=physical_qty,
            variance=variance,
            variance_percentage=variance_pct,
            status='pending' if abs(variance) > Decimal('0.001') else 'resolved'
        )
        
        db.session.add(count)
        db.session.commit()
        
        # Create alert if significant variance
        settings = WarehouseSettings.get_or_create(hotel_id)
        if abs(float(variance_pct)) > float(settings.variance_alert_percentage or 1):
            Alert.create_if_not_exists(
                hotel_id=hotel_id,
                alert_type='variance_detected',
                item_id=item_id,
                related_count_id=count.id,
                message=f'مغایرت {abs(float(variance_pct)):.1f}% در {item.item_name_fa}',
                severity='warning' if abs(float(variance_pct)) < 5 else 'danger',
                threshold_value=Decimal('0'),
                actual_value=variance
            )
            db.session.commit()
        
        logger.info(f"Inventory count created: item={item_id}, variance={variance}")
        return count
    
    @staticmethod
    def create_bulk_count(hotel_id: int, counts_data: list, user_id: int,
                          count_date: date = None) -> list:
        """Create multiple inventory counts at once"""
        results = []
        for data in counts_data:
            try:
                count = InventoryCountService.create_count(
                    hotel_id=hotel_id,
                    item_id=data['item_id'],
                    physical_quantity=data['physical_quantity'],
                    user_id=user_id,
                    count_date=count_date
                )
                results.append({'success': True, 'count': count})
            except Exception as e:
                results.append({'success': False, 'error': str(e), 'item_id': data.get('item_id')})
        
        return results
    
    @staticmethod
    def get_pending_counts(hotel_id: int) -> list:
        """Get unresolved counts"""
        return InventoryCount.query.filter(
            InventoryCount.hotel_id == hotel_id,
            InventoryCount.status.in_(['pending', 'investigating'])
        ).order_by(InventoryCount.count_date.desc()).all()
    
    @staticmethod
    def get_recent_counts(hotel_id: int, days: int = 30, limit: int = 50) -> list:
        """Get recent counts"""
        cutoff = date.today() - timedelta(days=days)
        return InventoryCount.query.filter(
            InventoryCount.hotel_id == hotel_id,
            InventoryCount.count_date >= cutoff
        ).order_by(InventoryCount.count_date.desc()).limit(limit).all()
    
    @staticmethod
    def resolve_count(count_id: int, reason: str, notes: str, user_id: int) -> InventoryCount:
        """Resolve count without adjustment (accept variance as-is)"""
        count = InventoryCount.query.get_or_404(count_id)
        
        if count.status in ['resolved', 'adjusted']:
            raise ValueError("این شمارش قبلاً پردازش شده است")
        
        count.status = 'resolved'
        count.variance_reason = reason
        count.variance_notes = notes
        count.reviewed_by_id = user_id
        count.reviewed_at = datetime.utcnow()
        
        # Resolve related alert
        Alert.query.filter_by(
            related_count_id=count_id,
            status='active'
        ).update({'status': 'resolved', 'is_resolved': True, 'resolved_at': datetime.utcnow()})
        
        db.session.commit()
        logger.info(f"Count {count_id} resolved without adjustment")
        
        return count
    
    @staticmethod
    def resolve_with_adjustment(count_id: int, reason: str, notes: str,
                                 user_id: int, approver_id: int = None) -> Transaction:
        """Create adjustment transaction to fix variance"""
        count = InventoryCount.query.get_or_404(count_id)
        
        if count.status in ['resolved', 'adjusted']:
            raise ValueError("این شمارش قبلاً پردازش شده است")
        
        if float(count.variance) == 0:
            raise ValueError("مغایرتی برای اصلاح وجود ندارد")
        
        item = Item.query.get(count.item_id)
        variance = float(count.variance)
        
        # Create adjustment transaction
        tx = Transaction.create_transaction(
            item_id=count.item_id,
            hotel_id=count.hotel_id,
            user_id=user_id,
            transaction_type='اصلاحی',
            quantity=abs(variance),
            direction=1 if variance > 0 else -1,
            unit_price=Decimal('0'),
            description=f'اصلاحی شمارش #{count.id}: {notes}',
            source='inventory_count'
        )
        
        # Check if approval needed
        settings = WarehouseSettings.get_or_create(count.hotel_id)
        if settings.check_adjustment_approval_needed(abs(variance)):
            tx.requires_approval = True
            tx.approval_status = 'pending'
            
            # Create approval alert
            Alert.create_if_not_exists(
                hotel_id=count.hotel_id,
                alert_type='pending_approval',
                item_id=count.item_id,
                related_transaction_id=tx.id,
                message=f'اصلاحی {abs(variance):.2f} واحد {item.item_name_fa} نیاز به تایید دارد',
                severity='warning'
            )
        else:
            # Update stock immediately
            item.current_stock = (item.current_stock or 0) + tx.signed_quantity
            tx.approval_status = 'not_required'
            if approver_id:
                tx.approved_by_id = approver_id
                tx.approved_at = datetime.utcnow()
        
        # Update count
        count.status = 'adjusted'
        count.variance_reason = reason
        count.variance_notes = notes
        count.adjustment_transaction_id = tx.id
        count.reviewed_by_id = approver_id or user_id
        count.reviewed_at = datetime.utcnow()
        
        # Resolve related alert
        Alert.query.filter_by(
            related_count_id=count_id,
            status='active'
        ).update({'status': 'resolved', 'is_resolved': True, 'resolved_at': datetime.utcnow()})
        
        db.session.add(tx)
        db.session.commit()
        
        logger.info(f"Count {count_id} resolved with adjustment transaction {tx.id}")
        return tx
    
    @staticmethod
    def get_items_needing_count(hotel_id: int, days_threshold: int = 30) -> list:
        """Get items that haven't been counted recently"""
        cutoff_date = date.today() - timedelta(days=days_threshold)
        
        # Subquery for last count date
        subquery = db.session.query(
            InventoryCount.item_id,
            func.max(InventoryCount.count_date).label('last_count')
        ).filter_by(hotel_id=hotel_id).group_by(InventoryCount.item_id).subquery()
        
        # Items never counted or not counted recently
        items = Item.query.filter_by(hotel_id=hotel_id, is_active=True).outerjoin(
            subquery, Item.id == subquery.c.item_id
        ).filter(
            (subquery.c.last_count == None) | (subquery.c.last_count < cutoff_date)
        ).order_by(Item.item_name_fa).all()
        
        # Add days since last count
        result = []
        for item in items:
            last_count = db.session.query(func.max(InventoryCount.count_date)).filter_by(
                item_id=item.id
            ).scalar()
            
            days_since = (date.today() - last_count).days if last_count else None
            result.append({
                'item': item,
                'last_count_date': last_count,
                'days_since_count': days_since
            })
        
        return result
    
    @staticmethod
    def get_variance_summary(hotel_id: int, days: int = 30) -> dict:
        """Get summary of variances"""
        cutoff = date.today() - timedelta(days=days)
        
        counts = InventoryCount.query.filter(
            InventoryCount.hotel_id == hotel_id,
            InventoryCount.count_date >= cutoff
        ).all()
        
        if not counts:
            return {'total_counts': 0, 'with_variance': 0, 'avg_variance_pct': 0}
        
        total = len(counts)
        with_variance = sum(1 for c in counts if c.has_variance)
        avg_variance = sum(abs(float(c.variance_percentage or 0)) for c in counts) / total
        
        # By reason
        by_reason = {}
        for c in counts:
            if c.variance_reason:
                reason = c.variance_reason
                if reason not in by_reason:
                    by_reason[reason] = {'count': 0, 'total_variance': 0}
                by_reason[reason]['count'] += 1
                by_reason[reason]['total_variance'] += abs(float(c.variance or 0))
        
        return {
            'total_counts': total,
            'with_variance': with_variance,
            'variance_rate': (with_variance / total * 100) if total else 0,
            'avg_variance_pct': round(avg_variance, 2),
            'by_reason': by_reason
        }
