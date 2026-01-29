import os
import secrets
import logging
from dotenv import load_dotenv

load_dotenv()

basedir = os.path.abspath(os.path.dirname(__file__))

# P2-FIX: Determine environment safely
FLASK_ENV = os.environ.get('FLASK_ENV', 'production')  # Default to production (secure)
IS_PRODUCTION = FLASK_ENV == 'production'
IS_DEVELOPMENT = FLASK_ENV == 'development'

class Config:
    # P2-FIX: Security warning if SECRET_KEY not set in production
    _env_secret_key = os.environ.get('SECRET_KEY')
    if IS_PRODUCTION and not _env_secret_key:
        logging.warning(
            "⚠️ WARNING: SECRET_KEY not set in production environment! "
            "Sessions will be invalidated on server restart. "
            "Set SECRET_KEY environment variable for persistent sessions."
        )
    SECRET_KEY = _env_secret_key or secrets.token_hex(32)
    
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
    
    # P2-FIX: Session Security - Secure by Default
    # Only disable secure cookie in explicit development mode
    SESSION_COOKIE_SECURE = not IS_DEVELOPMENT  # True unless explicitly in development
    SESSION_COOKIE_HTTPONLY = True  # Prevent JavaScript access to session cookie
    # BUG #27 FIX: Use Strict in production to prevent CSRF via cross-site requests
    SESSION_COOKIE_SAMESITE = 'Strict' if IS_PRODUCTION else 'Lax'
    PERMANENT_SESSION_LIFETIME = 3600  # 1 hour session lifetime
    
    # Security Headers
    REMEMBER_COOKIE_SECURE = not IS_DEVELOPMENT  # True unless explicitly in development
    REMEMBER_COOKIE_HTTPONLY = True
    REMEMBER_COOKIE_DURATION = 86400  # 1 day remember me
    
    # Password Security
    PASSWORD_MIN_LENGTH = 8
    PASSWORD_REQUIRE_DIGIT = True
    PASSWORD_REQUIRE_SPECIAL = False  # Can enable for stronger security
    
    # P2-FIX: Rate Limiting - Use Redis in production if available
    RATELIMIT_DEFAULT = "200 per minute"
    RATELIMIT_STORAGE_URL = os.environ.get('REDIS_URL', 'memory://')  # Configurable via env
    
    # Login Security
    MAX_LOGIN_ATTEMPTS = 5  # Lock after 5 failed attempts
    LOGIN_LOCKOUT_DURATION = 300  # 5 minutes lockout (in seconds)
    
    JSON_AS_ASCII = False
