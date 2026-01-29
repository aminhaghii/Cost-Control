from . import db
from datetime import datetime


# P1-5: Standard base units for normalization
BASE_UNITS = {
    'weight': 'کیلوگرم',  # kg
    'volume': 'لیتر',     # liter
    'count': 'عدد',       # piece
    'length': 'متر',      # meter
}

# P1-5: Unit conversion factors to base unit
UNIT_CONVERSIONS = {
    # Weight -> کیلوگرم (kg)
    'کیلوگرم': ('weight', 1.0),
    'کیلو': ('weight', 1.0),
    'گرم': ('weight', 0.001),
    # Volume -> لیتر
    'لیتر': ('volume', 1.0),
    'گالن': ('volume', 3.785),
    # Count -> عدد
    'عدد': ('count', 1.0),
    'بسته': ('count', 1.0),
    'قوطی': ('count', 1.0),
    'شیشه': ('count', 1.0),
    'جفت': ('count', 2.0),
    'دست': ('count', 1.0),
    'رول': ('count', 1.0),
    # Length -> متر
    'متر': ('length', 1.0),
}


class Item(db.Model):
    """
    Item model with P1-5 unit normalization support
    BUG #40 FIX: Added constraint to prevent negative stock
    """
    __tablename__ = 'items'
    
    id = db.Column(db.Integer, primary_key=True)
    item_code = db.Column(db.String(20), unique=True, nullable=False)
    item_name_fa = db.Column(db.String(100), nullable=False)
    item_name_en = db.Column(db.String(100), nullable=True)
    category = db.Column(db.String(20), nullable=False, index=True)  # Food or NonFood
    
    # P1-5: Unit normalization
    unit = db.Column(db.String(20), nullable=False)  # Display unit (کیلوگرم، لیتر، عدد)
    base_unit = db.Column(db.String(20), nullable=True)  # Normalized base unit
    
    hotel_id = db.Column(db.Integer, db.ForeignKey('hotels.id'), nullable=True, index=True)
    
    # Price control: Base unit price set by admin/accountant
    unit_price = db.Column(db.Numeric(12, 2), nullable=False, default=0)
    
    min_stock = db.Column(db.Float, default=0)
    max_stock = db.Column(db.Float, default=0)
    current_stock = db.Column(db.Float, default=0)  # In base_unit
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # BUG #40 FIX: Prevent negative stock at database level
    __table_args__ = (
        db.CheckConstraint('current_stock >= 0', name='ck_item_stock_non_negative'),
    )
    
    transactions = db.relationship('Transaction', backref='item', lazy='dynamic')
    
    def __repr__(self):
        return f'<Item {self.item_code}: {self.item_name_fa}>'
    
    def get_base_unit(self):
        """
        P1-5: Get the base unit for this item
        """
        if self.base_unit:
            return self.base_unit
        
        # Derive from unit
        if self.unit in UNIT_CONVERSIONS:
            unit_type, _ = UNIT_CONVERSIONS[self.unit]
            return BASE_UNITS.get(unit_type, self.unit)
        
        return self.unit
    
    @staticmethod
    def get_conversion_factor(from_unit, to_unit=None):
        """
        P1-5: Get conversion factor between units
        BUG-FIX #1 & #14: Raise error for unknown units instead of defaulting to 1.0
        
        Args:
            from_unit: Source unit
            to_unit: Target unit (if None, converts to base unit)
        
        Returns:
            Conversion factor
        
        Raises:
            ValueError: If from_unit is not recognized or units are incompatible
        """
        import logging
        logger = logging.getLogger(__name__)
        
        if from_unit not in UNIT_CONVERSIONS:
            # BUG-FIX #1 & #14: Log and raise error instead of defaulting to 1.0
            logger.warning(
                f"Unknown unit '{from_unit}' encountered in conversion. "
                f"Valid units: {', '.join(list(UNIT_CONVERSIONS.keys())[:10])}..."
            )
            raise ValueError(f"Unknown unit: '{from_unit}'. Valid units: {', '.join(UNIT_CONVERSIONS.keys())}")
        
        from_type, from_factor = UNIT_CONVERSIONS[from_unit]
        
        if to_unit is None:
            # Convert to base unit
            return from_factor
        
        if to_unit not in UNIT_CONVERSIONS:
            logger.warning(f"Unknown target unit '{to_unit}' in conversion")
            raise ValueError(f"Unknown target unit: '{to_unit}'")
        
        to_type, to_factor = UNIT_CONVERSIONS[to_unit]
        
        # BUG #3 FIX: Check for zero division
        if to_factor == 0:
            logger.error(f"Invalid zero conversion factor for unit: {to_unit}")
            raise ValueError(f"Invalid zero conversion factor for unit: {to_unit}")
        
        if from_type != to_type:
            logger.error(f"Incompatible unit types: {from_type} vs {to_type} ({from_unit} -> {to_unit})")
            raise ValueError(f"Cannot convert between incompatible unit types: {from_type} vs {to_type}")
        
        return from_factor / to_factor
