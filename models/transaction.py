from . import db
from datetime import datetime, date
from decimal import Decimal, ROUND_HALF_UP

# Transaction type constants
TRANSACTION_TYPES = {
    'purchase': 'خرید',
    'consumption': 'مصرف',
    'waste': 'ضایعات',
    'adjustment': 'اصلاحی'
}

# Direction mapping: +1 increases stock, -1 decreases stock
TRANSACTION_DIRECTION = {
    'خرید': 1,       # purchase increases stock
    'مصرف': -1,      # consumption decreases stock
    'ضایعات': -1,    # waste decreases stock
    'اصلاحی': 1      # adjustment can be +/- (use direction field)
}

# Warehouse Management Constants
WASTE_REASONS = {
    'expiry': 'تاریخ انقضا',
    'damage': 'خرابی/آسیب',
    'transport': 'آسیب حمل‌ونقل',
    'overproduction': 'تولید اضافی',
    'quality': 'کیفیت نامطلوب',
    'theft': 'سرقت/مفقودی',
    'other': 'سایر'
}

DEPARTMENTS = {
    'kitchen': 'آشپزخانه',
    'housekeeping': 'خانه‌داری',
    'restaurant': 'رستوران',
    'bar': 'بار',
    'banquet': 'تشریفات',
    'maintenance': 'تعمیرات',
    'admin': 'اداری',
    'other': 'سایر'
}

APPROVAL_STATUS = {
    'not_required': 'نیاز به تایید ندارد',
    'pending': 'در انتظار تایید',
    'approved': 'تایید شده',
    'rejected': 'رد شده'
}


class Transaction(db.Model):
    """
    Transaction model with P0-2/P0-3 consistency enforcement:
    - direction: +1 (increases stock) or -1 (decreases stock)
    - signed_quantity: ALWAYS = quantity * direction (computed, not stored independently)
    - quantity: ALWAYS positive, direction determines effect
    """
    __tablename__ = 'transactions'
    
    id = db.Column(db.Integer, primary_key=True)
    transaction_date = db.Column(db.Date, nullable=False, default=date.today, index=True)
    item_id = db.Column(db.Integer, db.ForeignKey('items.id'), nullable=False, index=True)
    transaction_type = db.Column(db.String(20), nullable=False, index=True)  # خرید، مصرف، ضایعات، اصلاحی
    category = db.Column(db.String(20), nullable=False)  # Food or NonFood
    hotel_id = db.Column(db.Integer, db.ForeignKey('hotels.id'), nullable=True, index=True)
    
    # P0-3: quantity is ALWAYS positive (>= 0)
    quantity = db.Column(db.Float, nullable=False)
    # P0-4: Money columns use Numeric for precision (12 digits, 2 decimal places)
    unit_price = db.Column(db.Numeric(12, 2), nullable=False, default=0)
    total_amount = db.Column(db.Numeric(12, 2), nullable=False, default=0)
    description = db.Column(db.Text, nullable=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    
    # P0-2: Stock integrity - direction determines stock effect
    # direction MUST be +1 or -1 (enforced by check constraint)
    direction = db.Column(db.Integer, nullable=False, default=1)
    # signed_quantity = quantity * direction (kept for query performance)
    signed_quantity = db.Column(db.Float, nullable=False, default=0)
    
    # P0-2: Import tracking fields
    is_opening_balance = db.Column(db.Boolean, default=False, index=True)
    source = db.Column(db.String(50), default='manual')  # manual, import, opening_import, adjustment
    import_batch_id = db.Column(db.Integer, db.ForeignKey('import_batches.id'), nullable=True, index=True)
    
    # P1-5: Unit normalization - store original unit and conversion factor
    unit = db.Column(db.String(20), nullable=True)  # Original unit from import
    conversion_factor_to_base = db.Column(db.Float, default=1.0)  # Factor to convert to item's base_unit
    
    # Soft delete support
    is_deleted = db.Column(db.Boolean, default=False)
    deleted_at = db.Column(db.DateTime, nullable=True)
    
    # ═══ Warehouse Management Fields ═══
    # Waste reason (required for waste transactions)
    waste_reason = db.Column(db.String(50), nullable=True)
    waste_reason_detail = db.Column(db.Text, nullable=True)
    
    # Reference number (invoice/receipt)
    reference_number = db.Column(db.String(100), nullable=True)
    
    # Destination department (for consumption)
    destination_department = db.Column(db.String(100), nullable=True)
    
    # Approval workflow
    requires_approval = db.Column(db.Boolean, default=False)
    approved_by_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    approved_at = db.Column(db.DateTime, nullable=True)
    approval_status = db.Column(db.String(20), default='not_required')
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    approved_by = db.relationship('User', foreign_keys=[approved_by_id], backref='approved_transactions')
    
    # P0-2: Check constraint for direction
    __table_args__ = (
        db.CheckConstraint('direction IN (1, -1)', name='ck_transaction_direction'),
        db.CheckConstraint('quantity >= 0', name='ck_transaction_quantity_positive'),
    )
    
    def __repr__(self):
        return f'<Transaction {self.id}: {self.transaction_type} - {self.total_amount}>'
    
    def calculate_signed_quantity(self):
        """
        P0-2: Centralized signed_quantity calculation
        This is the ONLY place where signed_quantity should be set.
        P1-FIX: Properly handles unit conversion factor lookup
        
        Rules:
        - quantity is always positive (abs value)
        - direction is determined by transaction_type (except for adjustments)
        - signed_quantity = quantity * direction * conversion_factor
        """
        from .item import Item
        
        # Ensure quantity is positive
        self.quantity = abs(self.quantity) if self.quantity else 0
        
        if self.transaction_type == 'اصلاحی':
            # For adjustments, direction is explicitly set (default +1)
            self.direction = self.direction if self.direction in (1, -1) else 1
        else:
            # For other types, derive direction from type
            self.direction = TRANSACTION_DIRECTION.get(self.transaction_type, 1)
        
        # P1-FIX: Properly determine conversion factor
        factor = self.conversion_factor_to_base
        
        if factor is None:
            # Try to get conversion factor from Item model
            if self.unit:
                factor = Item.get_conversion_factor(self.unit)
            
            # If still None, check if unit matches base unit (factor = 1.0)
            if factor is None:
                item = Item.query.get(self.item_id) if self.item_id else None
                if item:
                    base_unit = item.get_base_unit() if hasattr(item, 'get_base_unit') else item.unit
                    if self.unit == base_unit or self.unit is None:
                        factor = 1.0
                    else:
                        # P1-FIX: Raise error instead of silently defaulting to 1.0
                        raise ValueError(
                            f"Cannot determine conversion factor for unit '{self.unit}' to base unit '{base_unit}'. "
                            f"Please specify conversion_factor_to_base explicitly."
                        )
                else:
                    # No item context, default to 1.0 only if no unit specified
                    factor = 1.0
        
        self.conversion_factor_to_base = factor

        # P0-2 / Phase 3.1: signed_quantity ALWAYS in base units
        self.signed_quantity = self.quantity * factor * self.direction
        return self.signed_quantity
    
    @classmethod
    def create_transaction(cls, item_id, transaction_type, quantity, category, hotel_id, user_id,
                           unit_price=None, direction=None, description=None, source='manual', 
                           is_opening_balance=False, import_batch_id=None, unit=None, 
                           conversion_factor_to_base=None, price_override_reason=None, 
                           requires_approval=False):
        """
        P0-2/P0-3/P0-4: Centralized transaction creation
        Use this factory method instead of direct instantiation.
        Ensures money calculations use Decimal with proper rounding.
        
        PRICE CONTROL: Uses item's base price unless override is provided with approval
        
        BUG-VALIDATION-001: quantity must be > 0 (no negative or zero values allowed)
        """
        from .item import Item

        item = Item.query.get(item_id)
        if not item:
            raise ValueError(f"Item {item_id} not found")

        # BUG-VALIDATION-001: Enforce quantity > 0 at model layer
        if quantity is None or float(quantity) <= 0:
            raise ValueError(f"Quantity must be greater than zero, got: {quantity}")

        # PRICE CONTROL: Use item's base price unless override is provided
        if unit_price is not None:
            # Price override - check if user has permission
            from flask_login import current_user
            if current_user.role not in ['admin', 'manager', 'accountant']:
                raise ValueError("Only admin/manager/accountant can override item prices")
            
            if not price_override_reason:
                raise ValueError("Price override requires a reason")
            
            # Mark for approval if not admin
            if current_user.role != 'admin':
                requires_approval = True
            
            final_price = Decimal(str(unit_price))
        else:
            # Use item's base price
            final_price = item.unit_price or Decimal('0')

        # Ensure hotel consistency
        item_hotel_id = item.hotel_id
        if hotel_id is None:
            hotel_id = item_hotel_id
        elif item_hotel_id and hotel_id != item_hotel_id:
            raise ValueError("Transaction hotel_id must match item's hotel_id")

        # Determine direction
        if direction is not None:
            dir_value = 1 if direction > 0 else -1
        else:
            dir_value = TRANSACTION_DIRECTION.get(transaction_type, 1)
        
        # BUG-VALIDATION-001: quantity already validated > 0, convert to float
        qty = float(quantity)
        
        # Resolve unit + conversion factor (Phase 3.1: normalize to base unit)
        resolved_unit = unit or item.unit or item.get_base_unit()
        if conversion_factor_to_base is not None:
            factor = float(conversion_factor_to_base)
        else:
            factor = Item.get_conversion_factor(resolved_unit)

        if factor is None:
            raise ValueError(f"Cannot convert unit '{resolved_unit}' to base unit for item {item_id}")

        # P0-4: Use Decimal for money calculations
        price = final_price.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        total = (Decimal(str(qty)) * price).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        signed_base_quantity = qty * factor * dir_value
        
        tx = cls(
            item_id=item_id,
            transaction_type=transaction_type,
            category=category or item.category,
            hotel_id=hotel_id,
            user_id=user_id,
            quantity=qty,
            direction=dir_value,
            signed_quantity=signed_base_quantity,
            unit_price=price,
            total_amount=total,
            unit=resolved_unit,
            conversion_factor_to_base=factor,
            description=description,
            source=source,
            is_opening_balance=is_opening_balance,
            import_batch_id=import_batch_id,
            transaction_date=date.today(),
            requires_approval=requires_approval
        )
        return tx
    
    @staticmethod
    def calculate_total_amount(quantity, unit_price):
        """
        P0-4: Helper to calculate total_amount with proper Decimal rounding
        """
        qty = Decimal(str(abs(quantity) if quantity else 0))
        price = Decimal(str(unit_price or 0))
        return (qty * price).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    
    @staticmethod
    def get_stock_for_item(item_id):
        """Calculate current stock from sum of signed_quantity"""
        from sqlalchemy import func
        result = db.session.query(
            func.coalesce(func.sum(Transaction.signed_quantity), 0)
        ).filter(
            Transaction.item_id == item_id,
            Transaction.is_deleted != True
        ).scalar()
        return float(result or 0)
