"""
Warehouse Settings Model - Per-hotel warehouse configuration
"""
from . import db
from datetime import datetime, date
from decimal import Decimal


class WarehouseSettings(db.Model):
    """Warehouse settings for each hotel"""
    __tablename__ = 'warehouse_settings'
    
    id = db.Column(db.Integer, primary_key=True)
    hotel_id = db.Column(db.Integer, db.ForeignKey('hotels.id'), nullable=False, unique=True, index=True)
    
    # Approval thresholds
    waste_approval_threshold = db.Column(db.Numeric(12, 2), default=500000)  # Rials
    adjustment_approval_threshold = db.Column(db.Numeric(12, 3), default=10)  # Units
    
    # Alert thresholds
    waste_alert_percentage = db.Column(db.Numeric(5, 2), default=5.0)  # Percentage
    variance_alert_percentage = db.Column(db.Numeric(5, 2), default=1.0)  # Percentage
    
    # Count frequency
    count_frequency_days = db.Column(db.Integer, default=30)
    last_full_count_date = db.Column(db.Date, nullable=True)
    
    # Notification settings
    notify_on_low_stock = db.Column(db.Boolean, default=True)
    notify_on_high_waste = db.Column(db.Boolean, default=True)
    notify_on_variance = db.Column(db.Boolean, default=True)
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationship
    hotel = db.relationship('Hotel', backref=db.backref('warehouse_settings', uselist=False))
    
    def __repr__(self):
        return f'<WarehouseSettings hotel_id={self.hotel_id}>'
    
    @classmethod
    def get_or_create(cls, hotel_id):
        """Get settings for hotel, create with defaults if not exists"""
        settings = cls.query.filter_by(hotel_id=hotel_id).first()
        if not settings:
            settings = cls(hotel_id=hotel_id)
            db.session.add(settings)
            db.session.commit()
        return settings
    
    def needs_count(self):
        """Check if inventory count is overdue"""
        if not self.last_full_count_date:
            return True
        days_since = (date.today() - self.last_full_count_date).days
        return days_since >= self.count_frequency_days
    
    def check_waste_approval_needed(self, waste_value):
        """Check if waste transaction needs approval"""
        threshold = float(self.waste_approval_threshold or 500000)
        return float(waste_value or 0) >= threshold
    
    def check_adjustment_approval_needed(self, quantity):
        """Check if adjustment needs approval"""
        threshold = float(self.adjustment_approval_threshold or 10)
        return abs(float(quantity or 0)) >= threshold
