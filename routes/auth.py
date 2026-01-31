from flask import Blueprint, render_template, redirect, url_for, flash, request, session, current_app
from flask_login import login_user, logout_user, login_required, current_user
from models import db, User, AuditLog
from datetime import datetime, timedelta, timezone
import logging

# BUG-FIX #3: Import database-backed rate limiting
from services.rate_limit_service import LoginAttempt

# BUG #31 FIX: Apply rate limiting to login endpoint if limiter is available
try:
    from app import limiter
except ImportError:
    limiter = None

logger = logging.getLogger(__name__)

auth_bp = Blueprint('auth', __name__, url_prefix='/auth')

@auth_bp.route('/login', methods=['GET', 'POST'])
@limiter.limit("10 per minute") if limiter else (lambda f: f)
def login():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard.index'))
    
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        remember = request.form.get('remember', False)
        
        if not username or not password:
            flash('لطفاً نام کاربری و رمز عبور را وارد کنید', 'danger')
            return render_template('auth/login.html')
        
        # BUG-FIX #3: Use database-backed rate limiting
        identifier = f"{username}:{request.remote_addr}"
        
        if LoginAttempt.is_locked(identifier):
            logger.warning(f'Login attempt blocked for locked identifier: {identifier}')
            flash('حساب شما به دلیل تلاش‌های ناموفق متعدد موقتاً قفل شده است. لطفاً ۵ دقیقه صبر کنید.', 'danger')
            return render_template('auth/login.html')
        
        user = User.query.filter_by(username=username).first()
        
        if user and user.check_password(password):
            if not user.is_active:
                flash('حساب کاربری شما غیرفعال است', 'danger')
                # Log failed login attempt (inactive account)
                AuditLog.log(
                    user=user,
                    action=AuditLog.ACTION_LOGIN_FAILED,
                    resource_type=AuditLog.RESOURCE_USER,
                    resource_id=user.id,
                    resource_name=user.username,
                    description='تلاش ورود با حساب غیرفعال',
                    request=request
                )
                db.session.commit()
                return render_template('auth/login.html')
            
            # Check if account is locked
            if user.is_locked():
                flash('حساب شما موقتاً قفل شده است. لطفاً ۱۵ دقیقه صبر کنید.', 'danger')
                return render_template('auth/login.html')
            
            # Check if 2FA is enabled
            if user.is_2fa_enabled:
                # Store user info in session for 2FA verification
                session['pending_2fa_user_id'] = user.id
                session['pending_2fa_remember'] = bool(remember)
                session['pending_2fa_next'] = request.args.get('next')
                return redirect(url_for('security.verify_2fa'))
            
            login_user(user, remember=remember)
            user.last_login = datetime.now(timezone.utc)
            user.clear_failed_logins()
            LoginAttempt.clear_attempts(identifier)  # BUG-FIX #3
            
            # Log successful login
            AuditLog.log(
                user=user,
                action=AuditLog.ACTION_LOGIN,
                resource_type=AuditLog.RESOURCE_USER,
                resource_id=user.id,
                resource_name=user.username,
                description=f'ورود موفق کاربر {user.username}',
                request=request
            )
            db.session.commit()
            
            # Check if password change is required
            if user.must_change_password:
                flash('لطفاً رمز عبور خود را تغییر دهید', 'warning')
                return redirect(url_for('security.change_password'))
            
            flash('خوش آمدید!', 'success')
            
            # Bug #12: Prevent Open Redirect vulnerability
            next_page = request.args.get('next')
            if next_page and next_page.startswith('/') and not next_page.startswith('//'):
                return redirect(next_page)
            return redirect(url_for('dashboard.index'))
        else:
            # BUG-FIX #3: Record failed attempt in database
            is_locked, remaining = LoginAttempt.record_failed_attempt(identifier)
            
            logger.warning(f'Failed login attempt for user: {username}')
            
            # Log failed login attempt and update user lockout
            if user:
                user.record_failed_login()
                AuditLog.log(
                    user=user,
                    action=AuditLog.ACTION_LOGIN_FAILED,
                    resource_type=AuditLog.RESOURCE_USER,
                    resource_id=user.id,
                    resource_name=username,
                    description=f'رمز عبور اشتباه (تلاش {user.failed_login_attempts})',
                    request=request
                )
                db.session.commit()
            
            if is_locked:
                flash('حساب شما به دلیل تلاش‌های ناموفق قفل شد. لطفاً ۵ دقیقه صبر کنید.', 'danger')
            else:
                flash(f'نام کاربری یا رمز عبور اشتباه است. {remaining} تلاش باقی‌مانده.', 'danger')
    
    return render_template('auth/login.html')

@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    """
    Public registration is DISABLED for security.
    Only admins can create new users via admin panel.
    This route now redirects to login with a message.
    """
    flash('ثبت‌نام عمومی غیرفعال است. برای دریافت حساب کاربری با مدیر سیستم تماس بگیرید.', 'warning')
    return redirect(url_for('auth.login'))

@auth_bp.route('/register-disabled', methods=['GET', 'POST'])
def register_disabled():
    """Route disabled for security - redirecting to login"""
    flash('ثبت‌نام مستقیم غیرفعال است', 'warning')
    return redirect(url_for('auth.login'))
    
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '')
        confirm_password = request.form.get('confirm_password', '')
        full_name = request.form.get('full_name', '').strip()
        role = request.form.get('role', 'staff')
        
        errors = []
        
        if not username or len(username) < 3:
            errors.append('نام کاربری باید حداقل 3 کاراکتر باشد')
        
        if not email or '@' not in email:
            errors.append('ایمیل معتبر وارد کنید')
        
        # Bug #13: Stronger password policy
        if not password or len(password) < 8:
            errors.append('رمز عبور باید حداقل 8 کاراکتر باشد')
        elif not any(c.isdigit() for c in password):
            errors.append('رمز عبور باید حداقل یک عدد داشته باشد')
        
        if password != confirm_password:
            errors.append('رمز عبور و تکرار آن مطابقت ندارند')
        
        if User.query.filter_by(username=username).first():
            errors.append('این نام کاربری قبلاً ثبت شده است')
        
        if User.query.filter_by(email=email).first():
            errors.append('این ایمیل قبلاً ثبت شده است')
        
        if role not in ['admin', 'manager', 'staff']:
            errors.append('نقش کاربری نامعتبر است')
        
        if errors:
            for error in errors:
                flash(error, 'danger')
            return render_template('auth/register.html')
        
        user = User(
            username=username,
            email=email,
            full_name=full_name,
            role=role
        )
        user.set_password(password)
        
        db.session.add(user)
        db.session.commit()
        
        flash('ثبت‌نام با موفقیت انجام شد. اکنون وارد شوید.', 'success')
        return redirect(url_for('auth.login'))
    
    return render_template('auth/register.html')

@auth_bp.route('/logout')
@login_required
def logout():
    # Log logout action before logging out
    AuditLog.log(
        user=current_user,
        action=AuditLog.ACTION_LOGOUT,
        resource_type=AuditLog.RESOURCE_USER,
        resource_id=current_user.id,
        resource_name=current_user.username,
        description=f'خروج کاربر {current_user.username}',
        request=request
    )
    db.session.commit()
    
    logout_user()
    flash('با موفقیت خارج شدید', 'info')
    return redirect(url_for('auth.login'))
