from . import db
from datetime import datetime

# Alert types for warehouse management
ALERT_TYPES = {
    'low_stock': 'موجودی کم',
    'high_stock': 'موجودی زیاد',
    'high_waste': 'ضایعات بالا',
    'variance_detected': 'مغایرت موجودی',
    'pending_approval': 'در انتظار تایید',
    'count_overdue': 'تاخیر در شمارش',
    'expiry_warning': 'هشدار انقضا'
}

ALERT_STATUS = {
    'active': 'فعال',
    'acknowledged': 'مشاهده شده',
    'resolved': 'حل شده',
    'ignored': 'نادیده گرفته شده'
}


class Alert(db.Model):
    __tablename__ = 'alerts'
    
    id = db.Column(db.Integer, primary_key=True)
    hotel_id = db.Column(db.Integer, db.ForeignKey('hotels.id'), nullable=True, index=True)
    alert_type = db.Column(db.String(50), nullable=False, index=True)
    message = db.Column(db.Text, nullable=False)
    severity = db.Column(db.String(20), default='warning')  # info, warning, danger
    
    # Related entities
    item_id = db.Column(db.Integer, db.ForeignKey('items.id'), nullable=True, index=True)
    related_transaction_id = db.Column(db.Integer, db.ForeignKey('transactions.id'), nullable=True)
    related_count_id = db.Column(db.Integer, db.ForeignKey('inventory_counts.id'), nullable=True)
    
    # Threshold values
    threshold_value = db.Column(db.Numeric(12, 3), nullable=True)
    actual_value = db.Column(db.Numeric(12, 3), nullable=True)
    
    # Status tracking
    status = db.Column(db.String(20), default='active', index=True)
    is_resolved = db.Column(db.Boolean, default=False)
    resolved_at = db.Column(db.DateTime, nullable=True)
    
    # Acknowledgement
    acknowledged_by_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    acknowledged_at = db.Column(db.DateTime, nullable=True)
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    hotel = db.relationship('Hotel', backref='alerts')
    item = db.relationship('Item', backref='alerts')
    related_transaction = db.relationship('Transaction', foreign_keys=[related_transaction_id])
    acknowledged_by = db.relationship('User', foreign_keys=[acknowledged_by_id])
    
    def __repr__(self):
        return f'<Alert {self.id}: {self.alert_type}>'
    
    @classmethod
    def create_if_not_exists(cls, hotel_id, alert_type, item_id=None, message=None,
                              severity='warning', threshold_value=None, actual_value=None,
                              related_transaction_id=None, related_count_id=None):
        """Create alert only if similar active alert doesn't exist"""
        existing = cls.query.filter_by(
            hotel_id=hotel_id,
            alert_type=alert_type,
            item_id=item_id,
            status='active'
        ).first()
        
        if existing:
            return existing
        
        alert = cls(
            hotel_id=hotel_id,
            alert_type=alert_type,
            item_id=item_id,
            message=message or ALERT_TYPES.get(alert_type, alert_type),
            severity=severity,
            threshold_value=threshold_value,
            actual_value=actual_value,
            related_transaction_id=related_transaction_id,
            related_count_id=related_count_id
        )
        db.session.add(alert)
        return alert
    
    def acknowledge(self, user_id):
        """Mark alert as acknowledged"""
        self.status = 'acknowledged'
        self.acknowledged_by_id = user_id
        self.acknowledged_at = datetime.utcnow()
    
    def resolve(self):
        """Mark alert as resolved"""
        self.status = 'resolved'
        self.is_resolved = True
        self.resolved_at = datetime.utcnow()
