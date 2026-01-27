import os
import secrets
from dotenv import load_dotenv

load_dotenv()

basedir = os.path.abspath(os.path.dirname(__file__))

class Config:
    # Security: Generate strong secret key if not provided
    SECRET_KEY = os.environ.get('SECRET_KEY') or secrets.token_hex(32)
    
    # Database
    SQLALCHEMY_DATABASE_URI = 'sqlite:///' + os.path.join(basedir, 'database', 'inventory.db')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # P1-1: SQLite optimizations for concurrency
    SQLALCHEMY_ENGINE_OPTIONS = {
        'connect_args': {
            'check_same_thread': False,
        },
        'pool_pre_ping': True,
    }
    
    # P0-8: Upload security
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB max file size
    UPLOAD_FOLDER = os.path.join(basedir, 'uploads')
    ALLOWED_EXTENSIONS = {'xlsx', 'xls'}
    
    # P0-6: Admin bootstrap (use ENV in production)
    ADMIN_INITIAL_PASSWORD = os.environ.get('ADMIN_INITIAL_PASSWORD')
    
    # CSRF Protection
    WTF_CSRF_ENABLED = True
    WTF_CSRF_TIME_LIMIT = 3600  # 1 hour CSRF token validity
    
    # Session Security
    SESSION_COOKIE_SECURE = os.environ.get('FLASK_ENV') == 'production'  # HTTPS only in production
    SESSION_COOKIE_HTTPONLY = True  # Prevent JavaScript access to session cookie
    SESSION_COOKIE_SAMESITE = 'Lax'  # Prevent CSRF via cross-site requests
    PERMANENT_SESSION_LIFETIME = 3600  # 1 hour session lifetime
    
    # Security Headers
    REMEMBER_COOKIE_SECURE = os.environ.get('FLASK_ENV') == 'production'
    REMEMBER_COOKIE_HTTPONLY = True
    REMEMBER_COOKIE_DURATION = 86400  # 1 day remember me
    
    # Password Security
    PASSWORD_MIN_LENGTH = 8
    PASSWORD_REQUIRE_DIGIT = True
    PASSWORD_REQUIRE_SPECIAL = False  # Can enable for stronger security
    
    # Rate Limiting
    RATELIMIT_DEFAULT = "200 per minute"
    RATELIMIT_STORAGE_URL = "memory://"
    
    # Login Security
    MAX_LOGIN_ATTEMPTS = 5  # Lock after 5 failed attempts
    LOGIN_LOCKOUT_DURATION = 300  # 5 minutes lockout
    
    JSON_AS_ASCII = False
