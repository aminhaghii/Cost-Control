from . import db
from datetime import datetime


class UserHotel(db.Model):
    """Association table for User-Hotel many-to-many with role"""
    __tablename__ = 'user_hotels'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    hotel_id = db.Column(db.Integer, db.ForeignKey('hotels.id'), nullable=False)
    role = db.Column(db.String(20), default='viewer')  # viewer, editor, manager
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    created_by_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    
    __table_args__ = (
        db.UniqueConstraint('user_id', 'hotel_id', name='uq_user_hotel'),
    )
    
    # Relationships
    user = db.relationship('User', foreign_keys=[user_id], backref='hotel_assignments')
    hotel = db.relationship('Hotel', backref='user_assignments')
    created_by = db.relationship('User', foreign_keys=[created_by_id])
    
    def __repr__(self):
        return f'<UserHotel user={self.user_id} hotel={self.hotel_id} role={self.role}>'
