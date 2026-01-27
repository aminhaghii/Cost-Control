from . import db
from datetime import datetime

class Hotel(db.Model):
    __tablename__ = 'hotels'
    
    id = db.Column(db.Integer, primary_key=True)
    hotel_code = db.Column(db.String(20), unique=True, nullable=False)
    hotel_name = db.Column(db.String(100), nullable=False)
    hotel_name_en = db.Column(db.String(100), nullable=True)
    location = db.Column(db.String(100), nullable=True)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    items = db.relationship('Item', backref='hotel', lazy='dynamic')
    transactions = db.relationship('Transaction', backref='hotel', lazy='dynamic')
    
    def __repr__(self):
        return f'<Hotel {self.hotel_code}: {self.hotel_name}>'
