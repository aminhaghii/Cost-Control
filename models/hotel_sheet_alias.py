"""
HotelSheetAlias Model - P1-4
Maps Excel sheet names to hotels for import automation
"""

from . import db
from datetime import datetime


class HotelSheetAlias(db.Model):
    """
    P1-4: Map Excel sheet names to hotels
    Replaces hardcoded sheet-to-hotel mapping in data_importer
    """
    __tablename__ = 'hotel_sheet_aliases'
    
    id = db.Column(db.Integer, primary_key=True)
    hotel_id = db.Column(db.Integer, db.ForeignKey('hotels.id'), nullable=False)
    alias_text = db.Column(db.String(100), nullable=False, unique=True, index=True)
    description = db.Column(db.String(255))
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    created_by_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    
    # Relationships
    hotel = db.relationship('Hotel', backref='sheet_aliases')
    created_by = db.relationship('User', backref='created_aliases')
    
    def __repr__(self):
        return f'<HotelSheetAlias {self.alias_text} -> Hotel {self.hotel_id}>'
    
    def to_dict(self):
        return {
            'id': self.id,
            'hotel_id': self.hotel_id,
            'alias_text': self.alias_text,
            'description': self.description,
            'is_active': self.is_active,
            'hotel_name': self.hotel.hotel_name if self.hotel else None
        }
    
    @classmethod
    def get_hotel_for_sheet(cls, sheet_name):
        """
        Get hotel ID for a sheet name (case-insensitive)
        
        Args:
            sheet_name: Excel sheet name
        
        Returns:
            Hotel ID or None
        """
        # Try exact match first
        alias = cls.query.filter(
            cls.alias_text == sheet_name,
            cls.is_active == True
        ).first()
        
        if alias:
            return alias.hotel_id
        
        # Try case-insensitive match
        alias = cls.query.filter(
            db.func.lower(cls.alias_text) == sheet_name.lower(),
            cls.is_active == True
        ).first()
        
        return alias.hotel_id if alias else None
    
    @classmethod
    def create_alias(cls, hotel_id, alias_text, description=None, created_by_id=None):
        """
        Create a new sheet alias
        
        Args:
            hotel_id: Hotel ID
            alias_text: Sheet name to map
            description: Optional description
            created_by_id: User who created this
        
        Returns:
            HotelSheetAlias object
        """
        alias = cls(
            hotel_id=hotel_id,
            alias_text=alias_text,
            description=description,
            created_by_id=created_by_id
        )
        db.session.add(alias)
        db.session.commit()
        return alias
    
    @classmethod
    def get_all_mappings(cls):
        """
        Get all active mappings as a dict
        
        Returns:
            Dict of {alias_text.lower(): hotel_id}
        """
        aliases = cls.query.filter_by(is_active=True).all()
        return {a.alias_text.lower(): a.hotel_id for a in aliases}
