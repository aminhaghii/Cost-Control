from . import db
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import UserMixin
from datetime import datetime, timedelta, timezone
import pyotp
import secrets

# Role hierarchy: admin > manager > staff
ROLES = {
    'admin': 3,      # Full access to everything
    'manager': 2,    # Can manage items, view reports, manage staff
    'staff': 1       # Basic access: add transactions, view own data
}

ROLE_LABELS = {
    'admin': 'مدیر سیستم',
    'manager': 'مدیر انبار',
    'staff': 'کارمند'
}

class User(UserMixin, db.Model):
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    full_name = db.Column(db.String(100), nullable=True)
    role = db.Column(db.String(20), default='staff', nullable=False)  # roles: admin, manager, staff
    department = db.Column(db.String(100), nullable=True)  # بخش/واحد
    phone = db.Column(db.String(20), nullable=True)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    last_login = db.Column(db.DateTime, nullable=True)
    created_by_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    
    # Two-Factor Authentication (2FA)
    totp_secret = db.Column(db.String(32), nullable=True)  # TOTP secret key
    is_2fa_enabled = db.Column(db.Boolean, default=False)
    
    # Password Security
    password_changed_at = db.Column(db.DateTime, nullable=True)
    must_change_password = db.Column(db.Boolean, default=False)
    
    # Security tracking
    failed_login_attempts = db.Column(db.Integer, default=0)
    locked_until = db.Column(db.DateTime, nullable=True)
    last_failed_login = db.Column(db.DateTime, nullable=True)
    password_history = db.Column(db.Text, nullable=True)  # JSON list of previous password hashes
    
    # Relationships
    transactions = db.relationship('Transaction', backref='user', lazy='dynamic', foreign_keys='Transaction.user_id')
    created_by = db.relationship('User', remote_side=[id], backref='created_users')
    
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
        self.password_changed_at = datetime.now(timezone.utc)
    
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)
    
    # 2FA Methods
    def generate_totp_secret(self):
        """Generate a new TOTP secret for 2FA"""
        self.totp_secret = pyotp.random_base32()
        return self.totp_secret
    
    def get_totp_uri(self):
        """Get the TOTP URI for QR code generation"""
        if not self.totp_secret:
            self.generate_totp_secret()
        return pyotp.totp.TOTP(self.totp_secret).provisioning_uri(
            name=self.email,
            issuer_name="سیستم موجودی هتل"
        )
    
    def verify_totp(self, token):
        """Verify a TOTP token"""
        if not self.totp_secret:
            return False
        totp = pyotp.TOTP(self.totp_secret)
        return totp.verify(token, valid_window=1)  # Allow 1 window (30 sec) tolerance
    
    def enable_2fa(self):
        """Enable 2FA for this user"""
        if not self.totp_secret:
            self.generate_totp_secret()
        self.is_2fa_enabled = True
    
    def disable_2fa(self):
        """Disable 2FA for this user"""
        self.is_2fa_enabled = False
        self.totp_secret = None
    
    # Account lockout methods
    def is_locked(self):
        """Check if account is locked"""
        if self.locked_until:
            # Handle both naive and aware datetimes
            now = datetime.now(timezone.utc)
            locked_until = self.locked_until
            if locked_until.tzinfo is None:
                locked_until = locked_until.replace(tzinfo=timezone.utc)
            if locked_until > now:
                return True
        return False
    
    def record_failed_login(self):
        """
        Record a failed login attempt
        P2-FIX: Use config value for lockout duration instead of hardcoded 15 minutes
        """
        self.failed_login_attempts = (self.failed_login_attempts or 0) + 1
        self.last_failed_login = datetime.now(timezone.utc)
        
        # P2-FIX: Get config values from app config
        try:
            from flask import current_app
            max_attempts = current_app.config.get('MAX_LOGIN_ATTEMPTS', 5)
            lockout_seconds = current_app.config.get('LOGIN_LOCKOUT_DURATION', 300)
        except RuntimeError:
            # Outside app context, use defaults
            max_attempts = 5
            lockout_seconds = 300  # 5 minutes
        
        # Lock account after max failed attempts
        if self.failed_login_attempts >= max_attempts:
            from datetime import timedelta
            # BUG #20 FIX: Admin accounts should have LONGER lock, not shorter
            # Exponential backoff for repeated failures
            if self.is_admin():
                multiplier = min(self.failed_login_attempts - max_attempts + 1, 10)
                lockout_seconds = lockout_seconds * multiplier  # 5min, 10min, 15min, ...
            self.locked_until = datetime.now(timezone.utc) + timedelta(seconds=lockout_seconds)
    
    def clear_failed_logins(self):
        """Clear failed login attempts on successful login"""
        self.failed_login_attempts = 0
        self.locked_until = None
        self.last_failed_login = None
    
    # Role checking methods
    def is_admin(self):
        return self.role == 'admin'
    
    def is_manager(self):
        return self.role in ['admin', 'manager']
    
    def is_staff(self):
        return self.role in ['admin', 'manager', 'staff']
    
    def has_role(self, role):
        """Check if user has at least the specified role level"""
        return ROLES.get(self.role, 0) >= ROLES.get(role, 0)
    
    def can_manage_users(self):
        """Only admin can manage users"""
        return self.role == 'admin'
    
    def can_manage_items(self):
        """Admin and manager can manage items"""
        return self.role in ['admin', 'manager']
    
    def can_view_logs(self):
        """Only admin can view audit logs"""
        return self.role == 'admin'
    
    def can_edit_user(self, target_user):
        """Check if current user can edit target user"""
        if self.role == 'admin':
            return True
        if self.role == 'manager' and target_user.role == 'staff':
            return True
        return self.id == target_user.id  # Can edit own profile
    
    @property
    def role_label(self):
        return ROLE_LABELS.get(self.role, self.role)
    
    def __repr__(self):
        return f'<User {self.username}>'
