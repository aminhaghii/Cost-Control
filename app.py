#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Hotel Inventory Pareto Analysis System
Flask Application Entry Point
"""

import os
import logging
from datetime import datetime
from flask import Flask, redirect, url_for, jsonify
from flask_login import LoginManager
from flask_wtf.csrf import CSRFProtect
from sqlalchemy import event
from sqlalchemy.engine import Engine
from config import Config
from models import db, User
from routes import register_blueprints
from utils.timezone import IRAN_TZ, get_iran_now

# Custom logging formatter with Iran timezone
class IranTimezoneFormatter(logging.Formatter):
    def formatTime(self, record, datefmt=None):
        dt = datetime.fromtimestamp(record.created, tz=IRAN_TZ)
        if datefmt:
            return dt.strftime(datefmt)
        return dt.strftime('%Y-%m-%d %H:%M:%S')
    
    def format(self, record):
        record.iran_time = datetime.fromtimestamp(record.created, tz=IRAN_TZ).strftime('%Y-%m-%d %H:%M:%S')
        return super().format(record)

# Configure logging with Iran timezone
formatter = IranTimezoneFormatter(
    '%(iran_time)s [Iran] - %(name)s - %(levelname)s - %(message)s'
)

console_handler = logging.StreamHandler()
console_handler.setFormatter(formatter)

file_handler = logging.FileHandler('app.log', encoding='utf-8')
file_handler.setFormatter(formatter)

logging.basicConfig(
    level=logging.INFO,
    handlers=[console_handler, file_handler]
)
logger = logging.getLogger(__name__)

# Global CSRF instance for reuse in other modules (e.g., chat API exemptions)
csrf = CSRFProtect()

# BUG #15 FIX: Rate limiter - required for production
limiter = None
try:
    from flask_limiter import Limiter
    from flask_limiter.util import get_remote_address
    limiter = Limiter(key_func=get_remote_address, default_limits=["200 per minute"])
except ImportError:
    logger.warning("flask-limiter not installed. Rate limiting disabled.")
    # BUG #15 FIX: In production, limiter is required
    import os
    if os.environ.get('FLASK_ENV') == 'production':
        raise RuntimeError("flask-limiter is required for production deployment. Install with: pip install flask-limiter")

def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)
    
    db_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'database')
    if not os.path.exists(db_dir):
        os.makedirs(db_dir)
    
    exports_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'exports')
    if not os.path.exists(exports_dir):
        os.makedirs(exports_dir)
    
    db.init_app(app)
    
    # P1-1: SQLite pragmas for WAL mode and better concurrency
    @event.listens_for(Engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA busy_timeout=5000")
        cursor.execute("PRAGMA synchronous=NORMAL")
        cursor.execute("PRAGMA cache_size=-64000")  # 64MB cache
        cursor.close()
    
    csrf.init_app(app)
    
    # Initialize rate limiter if available
    if limiter:
        limiter.init_app(app)
        logger.info("Rate limiting enabled: 200 requests/minute")
    
    login_manager = LoginManager()
    login_manager.init_app(app)
    login_manager.login_view = 'auth.login'
    login_manager.login_message = 'لطفاً برای دسترسی به این صفحه وارد شوید'
    login_manager.login_message_category = 'warning'
    
    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))
    
    register_blueprints(app)

    # P0-5: Chat endpoints are NO LONGER exempt from CSRF
    # All POST endpoints require CSRF token for session-based authentication
    # The chat templates must include {{ csrf_token() }} in AJAX calls
    
    @app.route('/favicon.ico')
    def favicon():
        return '', 204
    
    @app.template_filter('format_number')
    def format_number(value):
        try:
            return "{:,.0f}".format(float(value))
        except (ValueError, TypeError):
            return value
    
    @app.context_processor
    def utility_processor():
        def format_currency(amount):
            try:
                return "{:,.0f}".format(float(amount))
            except (ValueError, TypeError):
                return "0"
        return dict(format_currency=format_currency)
    
    # Security Headers - Protect against common attacks
    # P0-6: Updated security headers with proper conditions
    @app.after_request
    def add_security_headers(response):
        # Prevent clickjacking
        response.headers['X-Frame-Options'] = 'SAMEORIGIN'
        # Prevent MIME type sniffing
        response.headers['X-Content-Type-Options'] = 'nosniff'
        
        # P0-6: REMOVED X-XSS-Protection (deprecated, rely on CSP instead)
        # response.headers['X-XSS-Protection'] = '1; mode=block'  # REMOVED
        
        # Referrer policy
        response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
        
        # Content Security Policy (CSP) - primary XSS protection
        response.headers['Content-Security-Policy'] = (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline' 'unsafe-eval' https://cdn.jsdelivr.net https://cdnjs.cloudflare.com https://code.jquery.com; "
            "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net https://cdnjs.cloudflare.com https://fonts.googleapis.com; "
            "font-src 'self' https://cdn.jsdelivr.net https://cdnjs.cloudflare.com https://fonts.gstatic.com; "
            "img-src 'self' data: blob:; "
            "connect-src 'self' https://cdn.jsdelivr.net https://cdnjs.cloudflare.com; "
            "frame-ancestors 'self';"
        )
        # Permissions Policy
        response.headers['Permissions-Policy'] = 'geolocation=(), microphone=(), camera=()'
        
        # P0-6: HSTS only when HTTPS is actually enabled (SESSION_COOKIE_SECURE=True)
        # This should only be set in production behind TLS
        if app.config.get('SESSION_COOKIE_SECURE') and app.config.get('PREFERRED_URL_SCHEME') == 'https':
            response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'
        
        # Cache control for sensitive pages
        if 'text/html' in response.content_type:
            response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
            response.headers['Pragma'] = 'no-cache'
        return response
    
    return app

app = create_app()

if __name__ == '__main__':
    # BUG-003 Fix: Debug should be False by default, only True in development
    import os
    flask_env = os.environ.get('FLASK_ENV', 'production')
    debug_mode = flask_env == 'development'
    
    # Display current Iran time at startup
    iran_time = get_iran_now()
    
    print("\n" + "="*60)
    print("Hotel Inventory Management - Pareto Analysis")
    print("="*60)
    print(f"\nEnvironment: {flask_env}")
    print(f"Debug Mode: {debug_mode}")
    print(f"System Timezone: Iran (UTC+03:30)")
    print(f"Current Iran Time: {iran_time.strftime('%Y-%m-%d %H:%M:%S')}")
    print("\nAccess URL: http://localhost:8084")
    print("\nServer is running...")
    print("="*60 + "\n")
    
    # Log security-relevant config (without exposing secrets)
    logger.info(f"Application starting in {flask_env} mode")
    logger.info(f"Debug mode: {debug_mode}")
    logger.info(f"CSRF protection: {app.config.get('WTF_CSRF_ENABLED', False)}")
    logger.info(f"System timezone set to Iran (UTC+03:30) - Current time: {iran_time.strftime('%Y-%m-%d %H:%M:%S')}")
    
    app.run(host='0.0.0.0', port=8084, debug=debug_mode)
