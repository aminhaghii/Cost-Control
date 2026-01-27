from . import db
from datetime import datetime


class ImportBatch(db.Model):
    """
    Track import batches to ensure idempotency and auditability
    
    P0-1 Fix: 
    - file_hash is NOT unique (allows multiple batches for same file in replace mode)
    - is_active flag determines which batch is current
    - Only ONE active batch per file_hash (enforced by unique constraint)
    """
    __tablename__ = 'import_batches'
    
    id = db.Column(db.Integer, primary_key=True)
    filename = db.Column(db.String(255), nullable=False)
    file_hash = db.Column(db.String(64), nullable=False, index=True)  # SHA256 - NOT unique
    file_size = db.Column(db.Integer)
    sheet_name = db.Column(db.String(100))
    hotel_id = db.Column(db.Integer, db.ForeignKey('hotels.id'), nullable=True)
    uploaded_by_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    
    # P0-1: is_active flag for replace-mode support
    is_active = db.Column(db.Boolean, default=True, nullable=False, index=True)
    
    status = db.Column(db.String(20), default='completed')  # pending, completed, replaced, failed
    items_created = db.Column(db.Integer, default=0)
    items_updated = db.Column(db.Integer, default=0)
    transactions_created = db.Column(db.Integer, default=0)
    errors_count = db.Column(db.Integer, default=0)
    error_details = db.Column(db.Text)  # JSON: [{row: 5, error: "..."}]
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    replaced_at = db.Column(db.DateTime, nullable=True)
    
    # P0-1: Track which batch this one replaces
    replaces_batch_id = db.Column(db.Integer, db.ForeignKey('import_batches.id'), nullable=True)
    replaced_by_id = db.Column(db.Integer, db.ForeignKey('import_batches.id'), nullable=True)
    
    # Relationships
    hotel = db.relationship('Hotel', backref='import_batches')
    uploaded_by = db.relationship('User', foreign_keys=[uploaded_by_id], backref='import_batches')
    transactions = db.relationship('Transaction', backref='import_batch', lazy='dynamic')
    
    # Self-referential relationships for replace tracking
    # replaced_by: The batch that replaced this one
    replaced_by_rel = db.relationship('ImportBatch', 
                                      foreign_keys=[replaced_by_id],
                                      remote_side='ImportBatch.id',
                                      uselist=False)
    # replaces: The batch this one replaces
    replaces_rel = db.relationship('ImportBatch',
                                   foreign_keys=[replaces_batch_id],
                                   remote_side='ImportBatch.id',
                                   uselist=False)
    
    def to_dict(self):
        return {
            'id': self.id,
            'filename': self.filename,
            'file_hash': self.file_hash[:8] + '...',  # Truncated for display
            'hotel_id': self.hotel_id,
            'status': self.status,
            'items_created': self.items_created,
            'items_updated': self.items_updated,
            'transactions_created': self.transactions_created,
            'errors_count': self.errors_count,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }
