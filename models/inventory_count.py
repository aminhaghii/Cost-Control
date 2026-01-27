"""
Inventory Count Model - Physical stock counting and variance tracking
"""
from . import db
from datetime import datetime, date
from decimal import Decimal

# Variance reasons for physical count discrepancies
VARIANCE_REASONS = {
    'counting_error': 'خطای شمارش قبلی',
    'unrecorded_consumption': 'مصرف ثبت‌نشده',
    'unrecorded_waste': 'ضایعات ثبت‌نشده',
    'theft': 'سرقت/مفقودی',
    'unit_conversion': 'خطای تبدیل واحد',
    'data_entry': 'خطای ورود اطلاعات',
    'system_bug': 'خطای سیستم',
    'other': 'سایر'
}

COUNT_STATUS = {
    'pending': 'در انتظار بررسی',
    'investigating': 'در حال بررسی',
    'resolved': 'حل شده',
    'adjusted': 'اصلاح شده'
}


class InventoryCount(db.Model):
    """Physical inventory count for stock verification"""
    __tablename__ = 'inventory_counts'
    
    id = db.Column(db.Integer, primary_key=True)
    
    # Location and item
    hotel_id = db.Column(db.Integer, db.ForeignKey('hotels.id'), nullable=False, index=True)
    item_id = db.Column(db.Integer, db.ForeignKey('items.id'), nullable=False, index=True)
    
    # Who and when
    counted_by_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    count_date = db.Column(db.Date, nullable=False, default=date.today, index=True)
    
    # Key numbers
    system_quantity = db.Column(db.Numeric(12, 3), nullable=False)
    physical_quantity = db.Column(db.Numeric(12, 3), nullable=False)
    variance = db.Column(db.Numeric(12, 3), nullable=False)
    variance_percentage = db.Column(db.Numeric(5, 2), nullable=True)
    
    # Variance explanation
    variance_reason = db.Column(db.String(50), nullable=True)
    variance_notes = db.Column(db.Text, nullable=True)
    
    # Status tracking
    status = db.Column(db.String(20), default='pending', index=True)
    
    # Adjustment transaction (if created)
    adjustment_transaction_id = db.Column(db.Integer, db.ForeignKey('transactions.id'), nullable=True)
    
    # Review
    reviewed_by_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    reviewed_at = db.Column(db.DateTime, nullable=True)
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    hotel = db.relationship('Hotel', backref='inventory_counts')
    item = db.relationship('Item', backref='inventory_counts')
    counted_by = db.relationship('User', foreign_keys=[counted_by_id], backref='counts_performed')
    reviewed_by = db.relationship('User', foreign_keys=[reviewed_by_id], backref='counts_reviewed')
    adjustment_transaction = db.relationship('Transaction', foreign_keys=[adjustment_transaction_id])
    
    def __repr__(self):
        return f'<InventoryCount {self.id}: {self.item_id} variance={self.variance}>'
    
    @property
    def has_variance(self):
        """Check if there's a significant variance"""
        return abs(float(self.variance or 0)) > 0.001
    
    @property
    def variance_status(self):
        """Get variance severity"""
        pct = abs(float(self.variance_percentage or 0))
        if pct == 0:
            return 'ok'
        elif pct < 1:
            return 'minor'
        elif pct < 5:
            return 'warning'
        else:
            return 'critical'
    
    @classmethod
    def create_count(cls, hotel_id, item_id, physical_quantity, user_id, count_date=None):
        """Factory method to create a new inventory count"""
        from .item import Item
        
        item = Item.query.get(item_id)
        if not item:
            raise ValueError(f"Item {item_id} not found")
        
        system_qty = Decimal(str(item.current_stock or 0))
        physical_qty = Decimal(str(physical_quantity))
        variance = physical_qty - system_qty
        
        if system_qty != 0:
            variance_pct = (variance / system_qty * 100).quantize(Decimal('0.01'))
        else:
            variance_pct = Decimal('100.00') if variance != 0 else Decimal('0.00')
        
        count = cls(
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
        
        return count
