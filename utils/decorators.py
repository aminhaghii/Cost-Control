"""
Access Control Decorators
Provides role-based access control for routes
"""
from functools import wraps
from flask import flash, redirect, url_for, abort, request
from flask_login import current_user, login_required


def admin_required(f):
    """
    Decorator to require admin role for a route
    Must be used after @login_required
    """
    @wraps(f)
    @login_required
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            flash('لطفاً ابتدا وارد شوید', 'warning')
            return redirect(url_for('auth.login', next=request.url))
        
        if not current_user.is_admin():
            flash('شما دسترسی به این بخش را ندارید. فقط مدیر سیستم مجاز است.', 'danger')
            return redirect(url_for('dashboard.index'))
        
        return f(*args, **kwargs)
    return decorated_function


def manager_required(f):
    """
    Decorator to require manager or admin role for a route
    Must be used after @login_required
    """
    @wraps(f)
    @login_required
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            flash('لطفاً ابتدا وارد شوید', 'warning')
            return redirect(url_for('auth.login', next=request.url))
        
        if not current_user.is_manager():
            flash('شما دسترسی به این بخش را ندارید. فقط مدیران مجاز هستند.', 'danger')
            return redirect(url_for('dashboard.index'))
        
        return f(*args, **kwargs)
    return decorated_function


def role_required(role):
    """
    Decorator factory to require a specific role level
    Usage: @role_required('manager')
    """
    def decorator(f):
        @wraps(f)
        @login_required
        def decorated_function(*args, **kwargs):
            if not current_user.is_authenticated:
                flash('لطفاً ابتدا وارد شوید', 'warning')
                return redirect(url_for('auth.login', next=request.url))
            
            if not current_user.has_role(role):
                flash(f'شما دسترسی کافی برای این عملیات را ندارید.', 'danger')
                return redirect(url_for('dashboard.index'))
            
            return f(*args, **kwargs)
        return decorated_function
    return decorator


def log_action(action, resource_type):
    """
    Decorator to automatically log actions
    Usage: @log_action('view', 'report')
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            from models import AuditLog, db
            
            result = f(*args, **kwargs)
            
            # Log the action after successful execution
            try:
                AuditLog.log(
                    user=current_user,
                    action=action,
                    resource_type=resource_type,
                    request=request
                )
                db.session.commit()
            except Exception as e:
                # Don't fail the request if logging fails
                pass
            
            return result
        return decorated_function
    return decorator
