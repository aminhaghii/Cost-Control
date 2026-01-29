from . import db
from datetime import datetime
from urllib.parse import urlparse, parse_qs, urlencode

class AuditLog(db.Model):
    """
    Audit Log Model - Records all user activities in the system
    Used by admin to track all changes and actions
    """
    __tablename__ = 'audit_logs'
    
    id = db.Column(db.Integer, primary_key=True)
    
    # Who performed the action
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    username = db.Column(db.String(80), nullable=False)  # Stored for historical reference
    user_role = db.Column(db.String(20), nullable=False)
    
    # What action was performed
    action = db.Column(db.String(50), nullable=False)  # create, update, delete, login, logout, view, export
    
    # On what resource
    resource_type = db.Column(db.String(50), nullable=False)  # transaction, item, user, report, etc.
    resource_id = db.Column(db.Integer, nullable=True)
    resource_name = db.Column(db.String(200), nullable=True)  # Human readable name
    
    # Details of the change
    old_values = db.Column(db.Text, nullable=True)  # JSON string of old values
    new_values = db.Column(db.Text, nullable=True)  # JSON string of new values
    description = db.Column(db.Text, nullable=True)  # Human readable description
    
    # Request metadata
    ip_address = db.Column(db.String(50), nullable=True)
    user_agent = db.Column(db.String(500), nullable=True)
    
    # Timestamp
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    
    # Relationships
    user = db.relationship('User', backref=db.backref('audit_logs', lazy='dynamic'))
    
    # Action types constants
    ACTION_CREATE = 'create'
    ACTION_UPDATE = 'update'
    ACTION_DELETE = 'delete'
    ACTION_LOGIN = 'login'
    ACTION_LOGOUT = 'logout'
    ACTION_LOGIN_FAILED = 'login_failed'
    ACTION_VIEW = 'view'
    ACTION_EXPORT = 'export'
    ACTION_PASSWORD_CHANGE = 'password_change'
    ACTION_ROLE_CHANGE = 'role_change'
    
    # Resource types constants
    RESOURCE_USER = 'user'
    RESOURCE_ITEM = 'item'
    RESOURCE_TRANSACTION = 'transaction'
    RESOURCE_REPORT = 'report'
    RESOURCE_SYSTEM = 'system'
    RESOURCE_ALERT = 'alert'
    
    # Action labels in Persian
    ACTION_LABELS = {
        'create': 'ایجاد',
        'update': 'ویرایش',
        'delete': 'حذف',
        'login': 'ورود',
        'logout': 'خروج',
        'login_failed': 'تلاش ناموفق ورود',
        'view': 'مشاهده',
        'export': 'خروجی گرفتن',
        'password_change': 'تغییر رمز عبور',
        'role_change': 'تغییر نقش'
    }
    
    RESOURCE_LABELS = {
        'user': 'کاربر',
        'item': 'کالا',
        'transaction': 'تراکنش',
        'report': 'گزارش',
        'system': 'سیستم',
        'alert': 'هشدار'
    }
    
    @property
    def action_label(self):
        return self.ACTION_LABELS.get(self.action, self.action)
    
    @property
    def resource_label(self):
        return self.RESOURCE_LABELS.get(self.resource_type, self.resource_type)
    
    @classmethod
    def log(cls, user, action, resource_type, resource_id=None, resource_name=None,
            old_values=None, new_values=None, description=None, request=None):
        """
        Create a new audit log entry
        
        Args:
            user: Current user object
            action: Action type (create, update, delete, etc.)
            resource_type: Type of resource (user, item, transaction, etc.)
            resource_id: ID of the affected resource
            resource_name: Human readable name of the resource
            old_values: Dict of old values (will be converted to JSON)
            new_values: Dict of new values (will be converted to JSON)
            description: Human readable description
            request: Flask request object for IP and user agent
        """
        import json
        
        log_entry = cls(
            user_id=user.id if user else None,
            username=user.username if user else 'system',
            user_role=user.role if user else 'system',
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            resource_name=resource_name,
            old_values=json.dumps(old_values, ensure_ascii=False, default=str) if old_values else None,
            new_values=json.dumps(new_values, ensure_ascii=False, default=str) if new_values else None,
            description=description
        )
        
        if request:
            log_entry.ip_address = request.remote_addr
            log_entry.user_agent = request.user_agent.string[:500] if request.user_agent else None
            if request.url:
                sanitized_url = cls._sanitize_request_url(request.url)
                if description:
                    log_entry.description = f"{description} | URL: {sanitized_url}"
                else:
                    log_entry.description = f"URL: {sanitized_url}"
        
        db.session.add(log_entry)
        # Note: Commit should be done by the calling code
        
        return log_entry

    @staticmethod
    def _sanitize_request_url(url):
        """BUG #34 FIX: Remove sensitive query parameters from URLs before logging."""
        parsed = urlparse(url)
        query_params = parse_qs(parsed.query)

        # Remove sensitive parameters
        sensitive_keys = {'password', 'token', 'api_key', 'secret'}
        for key in list(query_params.keys()):
            if key.lower() in sensitive_keys:
                query_params.pop(key, None)

        sanitized_query = urlencode(query_params, doseq=True)
        return parsed._replace(query=sanitized_query).geturl()
    
    def get_old_values_dict(self):
        """Parse old_values JSON string to dict"""
        import json
        if self.old_values:
            try:
                return json.loads(self.old_values)
            except:
                return {}
        return {}
    
    def get_new_values_dict(self):
        """Parse new_values JSON string to dict"""
        import json
        if self.new_values:
            try:
                return json.loads(self.new_values)
            except:
                return {}
        return {}
    
    def __repr__(self):
        return f'<AuditLog {self.action} {self.resource_type} by {self.username}>'
