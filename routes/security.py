"""
Security routes for 2FA, password management, and account security
"""
from flask import Blueprint, render_template, redirect, url_for, flash, request, session, send_file
from flask_login import login_required, current_user
from models import db, User, AuditLog
from datetime import datetime, timedelta, timezone
import io
import qrcode
import base64

security_bp = Blueprint('security', __name__, url_prefix='/security')

# P2-FIX: Import limiter for rate limiting (initialized in app.py)
def get_limiter():
    """Get the rate limiter instance from app module"""
    try:
        from app import limiter
        return limiter
    except ImportError:
        return None


@security_bp.route('/2fa/setup', methods=['GET', 'POST'])
@login_required
def setup_2fa():
    """Setup Two-Factor Authentication"""
    if current_user.is_2fa_enabled:
        flash('احراز هویت دو مرحله‌ای قبلاً فعال شده است', 'info')
        return redirect(url_for('security.security_settings'))
    
    if request.method == 'POST':
        token = request.form.get('token', '').strip()
        
        if not token:
            flash('لطفاً کد تأیید را وارد کنید', 'danger')
            return redirect(url_for('security.setup_2fa'))
        
        if current_user.verify_totp(token):
            current_user.enable_2fa()
            db.session.commit()
            
            # Log 2FA enable
            AuditLog.log(
                user=current_user,
                action='2FA_ENABLED',
                resource_type=AuditLog.RESOURCE_USER,
                resource_id=current_user.id,
                resource_name=current_user.username,
                description='احراز هویت دو مرحله‌ای فعال شد',
                request=request
            )
            db.session.commit()
            
            flash('احراز هویت دو مرحله‌ای با موفقیت فعال شد', 'success')
            return redirect(url_for('security.security_settings'))
        else:
            flash('کد تأیید اشتباه است. لطفاً دوباره تلاش کنید', 'danger')
    
    # Generate new secret if not exists
    if not current_user.totp_secret:
        current_user.generate_totp_secret()
        db.session.commit()
    
    # Generate QR code
    totp_uri = current_user.get_totp_uri()
    qr = qrcode.QRCode(version=1, box_size=10, border=5)
    qr.add_data(totp_uri)
    qr.make(fit=True)
    
    img = qr.make_image(fill_color="black", back_color="white")
    buffer = io.BytesIO()
    img.save(buffer, format='PNG')
    buffer.seek(0)
    qr_code_base64 = base64.b64encode(buffer.getvalue()).decode()
    
    return render_template('security/setup_2fa.html', 
                         qr_code=qr_code_base64,
                         secret=current_user.totp_secret)


@security_bp.route('/2fa/disable', methods=['POST'])
@login_required
def disable_2fa():
    """Disable Two-Factor Authentication"""
    password = request.form.get('password', '')
    
    if not current_user.check_password(password):
        flash('رمز عبور اشتباه است', 'danger')
        return redirect(url_for('security.security_settings'))
    
    current_user.disable_2fa()
    db.session.commit()
    
    # Log 2FA disable
    AuditLog.log(
        user=current_user,
        action='2FA_DISABLED',
        resource_type=AuditLog.RESOURCE_USER,
        resource_id=current_user.id,
        resource_name=current_user.username,
        description='احراز هویت دو مرحله‌ای غیرفعال شد',
        request=request
    )
    db.session.commit()
    
    flash('احراز هویت دو مرحله‌ای غیرفعال شد', 'success')
    return redirect(url_for('security.security_settings'))


@security_bp.route('/2fa/verify', methods=['GET', 'POST'])
def verify_2fa():
    """
    Verify 2FA token during login
    P2-FIX: Rate limited to prevent brute-force attacks on TOTP codes
    """
    user_id = session.get('pending_2fa_user_id')
    if not user_id:
        return redirect(url_for('auth.login'))
    
    user = User.query.get(user_id)
    if not user:
        session.pop('pending_2fa_user_id', None)
        return redirect(url_for('auth.login'))
    
    if request.method == 'POST':
        # P2-FIX: Apply rate limiting to POST requests only (5 attempts per minute)
        limiter = get_limiter()
        if limiter:
            try:
                # Check rate limit manually for this specific endpoint
                from flask import current_app
                key = f"2fa_verify:{request.remote_addr}"
                
                # Use in-memory tracking as fallback
                from datetime import timedelta
                attempts_key = f'2fa_attempts_{request.remote_addr}'
                attempts_time_key = f'2fa_attempts_time_{request.remote_addr}'
                
                current_attempts = session.get(attempts_key, 0)
                last_attempt_time = session.get(attempts_time_key)
                
                # Reset counter if more than 1 minute has passed
                if last_attempt_time:
                    from datetime import datetime as dt
                    if isinstance(last_attempt_time, str):
                        last_attempt_time = dt.fromisoformat(last_attempt_time)
                    if (datetime.now(timezone.utc) - last_attempt_time.replace(tzinfo=timezone.utc)) > timedelta(minutes=1):
                        current_attempts = 0
                
                if current_attempts >= 5:
                    flash('تعداد تلاش‌های شما بیش از حد مجاز است. لطفاً یک دقیقه صبر کنید.', 'danger')
                    return render_template('security/verify_2fa.html'), 429
                
                # Increment attempt counter
                session[attempts_key] = current_attempts + 1
                session[attempts_time_key] = datetime.now(timezone.utc).isoformat()
                
            except Exception:
                pass  # Don't block login if rate limiting fails
        
        token = request.form.get('token', '').strip()
        
        if user.verify_totp(token):
            from flask_login import login_user
            login_user(user, remember=session.get('pending_2fa_remember', False))
            user.last_login = datetime.now(timezone.utc)
            user.clear_failed_logins()
            
            # Log successful 2FA login
            AuditLog.log(
                user=user,
                action=AuditLog.ACTION_LOGIN,
                resource_type=AuditLog.RESOURCE_USER,
                resource_id=user.id,
                resource_name=user.username,
                description='ورود موفق با احراز هویت دو مرحله‌ای',
                request=request
            )
            db.session.commit()
            
            # Clear session data including rate limit counters
            session.pop('pending_2fa_user_id', None)
            session.pop('pending_2fa_remember', None)
            session.pop(f'2fa_attempts_{request.remote_addr}', None)
            session.pop(f'2fa_attempts_time_{request.remote_addr}', None)
            
            flash('خوش آمدید!', 'success')
            next_page = session.pop('pending_2fa_next', None)
            if next_page and next_page.startswith('/') and not next_page.startswith('//'):
                return redirect(next_page)
            return redirect(url_for('dashboard.index'))
        else:
            flash('کد تأیید اشتباه است', 'danger')
    
    return render_template('security/verify_2fa.html')


@security_bp.route('/change-password', methods=['GET', 'POST'])
@login_required
def change_password():
    """Change password"""
    if request.method == 'POST':
        current_password = request.form.get('current_password', '')
        new_password = request.form.get('new_password', '')
        confirm_password = request.form.get('confirm_password', '')
        
        errors = []
        
        if not current_user.check_password(current_password):
            errors.append('رمز عبور فعلی اشتباه است')
        
        if len(new_password) < 8:
            errors.append('رمز عبور جدید باید حداقل ۸ کاراکتر باشد')
        
        if not any(c.isdigit() for c in new_password):
            errors.append('رمز عبور جدید باید حداقل یک عدد داشته باشد')
        
        if not any(c.isupper() for c in new_password):
            errors.append('رمز عبور جدید باید حداقل یک حرف بزرگ داشته باشد')
        
        if new_password != confirm_password:
            errors.append('رمز عبور جدید و تکرار آن مطابقت ندارند')
        
        if current_password == new_password:
            errors.append('رمز عبور جدید نباید با رمز عبور فعلی یکسان باشد')
        
        if errors:
            for error in errors:
                flash(error, 'danger')
            return render_template('security/change_password.html')
        
        current_user.set_password(new_password)
        current_user.must_change_password = False
        db.session.commit()
        
        # Log password change
        AuditLog.log(
            user=current_user,
            action='PASSWORD_CHANGED',
            resource_type=AuditLog.RESOURCE_USER,
            resource_id=current_user.id,
            resource_name=current_user.username,
            description='رمز عبور تغییر کرد',
            request=request
        )
        db.session.commit()
        
        flash('رمز عبور با موفقیت تغییر کرد', 'success')
        return redirect(url_for('security.security_settings'))
    
    return render_template('security/change_password.html')


@security_bp.route('/settings')
@login_required
def security_settings():
    """Security settings page"""
    return render_template('security/settings.html')


@security_bp.route('/sessions')
@login_required
def active_sessions():
    """View active sessions (placeholder for future implementation)"""
    # In production, you would track sessions in database/Redis
    return render_template('security/sessions.html')
