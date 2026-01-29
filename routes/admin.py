"""
Admin Panel Routes
Complete management panel for admin and manager roles
"""
from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_required, current_user
from models import db, User, Item, Transaction, Alert, AuditLog, ROLES, ROLE_LABELS
from utils.decorators import admin_required, manager_required
from datetime import datetime, timedelta
from sqlalchemy import func, desc
from utils.timezone import get_iran_now
import logging

logger = logging.getLogger(__name__)

admin_bp = Blueprint('admin', __name__, url_prefix='/admin')


# ============== Dashboard ==============
@admin_bp.route('/')
@admin_required
def dashboard():
    """Admin dashboard with system overview"""
    # Statistics
    total_users = User.query.count()
    active_users = User.query.filter_by(is_active=True).count()
    total_items = Item.query.count()
    total_transactions = Transaction.query.count()
    
    # Recent activity (last 24 hours)
    yesterday = datetime.utcnow() - timedelta(hours=24)
    recent_logs = AuditLog.query.filter(AuditLog.created_at >= yesterday).count()
    
    # Users by role
    users_by_role = db.session.query(
        User.role, func.count(User.id)
    ).group_by(User.role).all()
    
    # Recent audit logs
    recent_activity = AuditLog.query.order_by(desc(AuditLog.created_at)).limit(10).all()
    
    # Log this view
    AuditLog.log(
        user=current_user,
        action=AuditLog.ACTION_VIEW,
        resource_type=AuditLog.RESOURCE_SYSTEM,
        description='مشاهده داشبورد مدیریت',
        request=request
    )
    db.session.commit()
    
    return render_template('admin/dashboard.html',
                         total_users=total_users,
                         active_users=active_users,
                         total_items=total_items,
                         total_transactions=total_transactions,
                         recent_logs=recent_logs,
                         users_by_role=dict(users_by_role),
                         recent_activity=recent_activity,
                         role_labels=ROLE_LABELS)


# ============== User Management ==============
@admin_bp.route('/users')
@admin_required
def users_list():
    """List all users with filters"""
    page = request.args.get('page', 1, type=int)
    role_filter = request.args.get('role', '')
    status_filter = request.args.get('status', '')
    search = request.args.get('search', '')
    
    query = User.query
    
    if role_filter:
        query = query.filter(User.role == role_filter)
    
    if status_filter == 'active':
        query = query.filter(User.is_active == True)
    elif status_filter == 'inactive':
        query = query.filter(User.is_active == False)
    
    if search:
        query = query.filter(
            (User.username.ilike(f'%{search}%')) |
            (User.full_name.ilike(f'%{search}%')) |
            (User.email.ilike(f'%{search}%'))
        )
    
    users = query.order_by(User.created_at.desc()).paginate(page=page, per_page=20)
    
    return render_template('admin/users/list.html',
                         users=users,
                         roles=ROLES,
                         role_labels=ROLE_LABELS,
                         role_filter=role_filter,
                         status_filter=status_filter,
                         search=search)


@admin_bp.route('/users/create', methods=['GET', 'POST'])
@admin_required
def users_create():
    """Create a new user"""
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '')
        full_name = request.form.get('full_name', '').strip()
        role = request.form.get('role', 'staff')
        department = request.form.get('department', '').strip()
        phone = request.form.get('phone', '').strip()
        is_active = request.form.get('is_active') == 'on'
        
        # Validation
        errors = []
        if not username:
            errors.append('نام کاربری الزامی است')
        elif User.query.filter_by(username=username).first():
            errors.append('این نام کاربری قبلاً استفاده شده است')
        
        if not email:
            errors.append('ایمیل الزامی است')
        elif User.query.filter_by(email=email).first():
            errors.append('این ایمیل قبلاً استفاده شده است')
        
        if not password or len(password) < 8:
            errors.append('رمز عبور باید حداقل 8 کاراکتر باشد')
        
        if role not in ROLES:
            errors.append('نقش انتخابی نامعتبر است')
        
        if errors:
            for error in errors:
                flash(error, 'danger')
            return render_template('admin/users/create.html',
                                 roles=ROLES,
                                 role_labels=ROLE_LABELS)
        
        # Create user
        user = User(
            username=username,
            email=email,
            full_name=full_name,
            role=role,
            department=department,
            phone=phone,
            is_active=is_active,
            created_by_id=current_user.id
        )
        user.set_password(password)
        
        db.session.add(user)
        
        # Log the action
        AuditLog.log(
            user=current_user,
            action=AuditLog.ACTION_CREATE,
            resource_type=AuditLog.RESOURCE_USER,
            resource_id=user.id,
            resource_name=user.username,
            new_values={
                'username': username,
                'email': email,
                'role': role,
                'department': department,
                'is_active': is_active
            },
            description=f'ایجاد کاربر جدید: {username}',
            request=request
        )
        
        db.session.commit()
        
        flash(f'کاربر {username} با موفقیت ایجاد شد', 'success')
        logger.info(f'User {username} created by {current_user.username}')
        
        return redirect(url_for('admin.users_list'))
    
    return render_template('admin/users/create.html',
                         roles=ROLES,
                         role_labels=ROLE_LABELS)


@admin_bp.route('/users/<int:user_id>/edit', methods=['GET', 'POST'])
@admin_required
def users_edit(user_id):
    """Edit an existing user"""
    user = User.query.get_or_404(user_id)
    
    if request.method == 'POST':
        old_values = {
            'username': user.username,
            'email': user.email,
            'role': user.role,
            'department': user.department,
            'is_active': user.is_active
        }
        
        username = request.form.get('username', '').strip()
        email = request.form.get('email', '').strip()
        full_name = request.form.get('full_name', '').strip()
        role = request.form.get('role', 'staff')
        department = request.form.get('department', '').strip()
        phone = request.form.get('phone', '').strip()
        is_active = request.form.get('is_active') == 'on'
        new_password = request.form.get('new_password', '')
        
        # Validation
        errors = []
        if not username:
            errors.append('نام کاربری الزامی است')
        elif username != user.username and User.query.filter_by(username=username).first():
            errors.append('این نام کاربری قبلاً استفاده شده است')
        
        if not email:
            errors.append('ایمیل الزامی است')
        elif email != user.email and User.query.filter_by(email=email).first():
            errors.append('این ایمیل قبلاً استفاده شده است')
        
        if new_password and len(new_password) < 8:
            errors.append('رمز عبور جدید باید حداقل 8 کاراکتر باشد')
        
        if role not in ROLES:
            errors.append('نقش انتخابی نامعتبر است')
        
        # Prevent self-demotion from admin
        if user.id == current_user.id and role != 'admin':
            errors.append('شما نمی‌توانید نقش خود را از مدیر سیستم تغییر دهید')
        
        if errors:
            for error in errors:
                flash(error, 'danger')
            return render_template('admin/users/edit.html',
                                 user=user,
                                 roles=ROLES,
                                 role_labels=ROLE_LABELS)
        
        # Track role change separately
        role_changed = user.role != role
        
        # Update user
        user.username = username
        user.email = email
        user.full_name = full_name
        user.role = role
        user.department = department
        user.phone = phone
        user.is_active = is_active
        
        if new_password:
            user.set_password(new_password)
        
        new_values = {
            'username': username,
            'email': email,
            'role': role,
            'department': department,
            'is_active': is_active
        }
        
        # Log the action
        action = AuditLog.ACTION_ROLE_CHANGE if role_changed else AuditLog.ACTION_UPDATE
        AuditLog.log(
            user=current_user,
            action=action,
            resource_type=AuditLog.RESOURCE_USER,
            resource_id=user.id,
            resource_name=user.username,
            old_values=old_values,
            new_values=new_values,
            description=f'ویرایش کاربر: {user.username}' + (' (تغییر نقش)' if role_changed else ''),
            request=request
        )
        
        if new_password:
            AuditLog.log(
                user=current_user,
                action=AuditLog.ACTION_PASSWORD_CHANGE,
                resource_type=AuditLog.RESOURCE_USER,
                resource_id=user.id,
                resource_name=user.username,
                description=f'تغییر رمز عبور کاربر: {user.username}',
                request=request
            )
        
        db.session.commit()
        
        flash(f'کاربر {username} با موفقیت ویرایش شد', 'success')
        logger.info(f'User {username} edited by {current_user.username}')
        
        return redirect(url_for('admin.users_list'))
    
    return render_template('admin/users/edit.html',
                         user=user,
                         roles=ROLES,
                         role_labels=ROLE_LABELS)


@admin_bp.route('/users/<int:user_id>/toggle-status', methods=['POST'])
@admin_required
def users_toggle_status(user_id):
    """Toggle user active status"""
    user = User.query.get_or_404(user_id)
    
    if user.id == current_user.id:
        flash('شما نمی‌توانید وضعیت خود را غیرفعال کنید', 'danger')
        return redirect(url_for('admin.users_list'))
    
    old_status = user.is_active
    user.is_active = not user.is_active
    
    AuditLog.log(
        user=current_user,
        action=AuditLog.ACTION_UPDATE,
        resource_type=AuditLog.RESOURCE_USER,
        resource_id=user.id,
        resource_name=user.username,
        old_values={'is_active': old_status},
        new_values={'is_active': user.is_active},
        description=f'{"فعال‌سازی" if user.is_active else "غیرفعال‌سازی"} کاربر: {user.username}',
        request=request
    )
    
    db.session.commit()
    
    status_text = 'فعال' if user.is_active else 'غیرفعال'
    flash(f'کاربر {user.username} {status_text} شد', 'success')
    
    return redirect(url_for('admin.users_list'))


@admin_bp.route('/users/<int:user_id>/delete', methods=['POST'])
@admin_required
def users_delete(user_id):
    """Delete a user"""
    user = User.query.get_or_404(user_id)
    
    if user.id == current_user.id:
        flash('شما نمی‌توانید خودتان را حذف کنید', 'danger')
        return redirect(url_for('admin.users_list'))
    
    # Prevention: Check if user has related records (transactions, logs, etc.)
    if user.transactions.count() > 0 or user.audit_logs.count() > 0:
        flash('این کاربر دارای سابقه فعالیت (تراکنش یا لاگ) است و قابل حذف نیست. لطفاً حساب را غیرفعال کنید.', 'warning')
        return redirect(url_for('admin.users_list'))
    
    username = user.username
    
    AuditLog.log(
        user=current_user,
        action=AuditLog.ACTION_DELETE,
        resource_type=AuditLog.RESOURCE_USER,
        resource_id=user.id,
        resource_name=username,
        old_values={
            'username': user.username,
            'email': user.email,
            'role': user.role
        },
        description=f'حذف کاربر: {username}',
        request=request
    )
    
    db.session.delete(user)
    db.session.commit()
    
    flash(f'کاربر {username} با موفقیت حذف شد', 'success')
    logger.info(f'User {username} deleted by {current_user.username}')
    
    return redirect(url_for('admin.users_list'))


# ============== Items Management ==============
@admin_bp.route('/items')
@manager_required
def items_list():
    """List all items with filters"""
    from services.hotel_scope_service import get_allowed_hotel_ids
    
    page = request.args.get('page', 1, type=int)
    category_filter = request.args.get('category', '')
    status_filter = request.args.get('status', '')
    search = request.args.get('search', '')
    
    query = Item.query
    
    # BUG-FIX: Apply hotel scope for non-admin users
    if current_user.role != 'admin':
        allowed_hotel_ids = get_allowed_hotel_ids(current_user)
        if allowed_hotel_ids:
            query = query.filter(Item.hotel_id.in_(allowed_hotel_ids))
    
    if category_filter:
        query = query.filter(Item.category == category_filter)
    
    if status_filter == 'active':
        query = query.filter(Item.is_active == True)
    elif status_filter == 'inactive':
        query = query.filter(Item.is_active == False)
    elif status_filter == 'low_stock':
        query = query.filter(Item.current_stock < Item.min_stock)
    
    if search:
        query = query.filter(
            (Item.item_code.ilike(f'%{search}%')) |
            (Item.item_name_fa.ilike(f'%{search}%'))
        )
    
    items = query.order_by(Item.item_name_fa).paginate(page=page, per_page=20)
    
    return render_template('admin/items/list.html',
                         items=items,
                         category_filter=category_filter,
                         status_filter=status_filter,
                         search=search)


@admin_bp.route('/items/create', methods=['GET', 'POST'])
@manager_required
def items_create():
    """Create a new item"""
    if request.method == 'POST':
        item_code = request.form.get('item_code', '').strip()
        item_name_fa = request.form.get('item_name_fa', '').strip()
        category = request.form.get('category', 'Food')
        unit = request.form.get('unit', '').strip()
        unit_price = request.form.get('unit_price', 0, type=float)
        min_stock = request.form.get('min_stock', 0, type=float)
        max_stock = request.form.get('max_stock', 0, type=float)
        current_stock = request.form.get('current_stock', 0, type=float)
        is_active = request.form.get('is_active') == 'on'
        
        # Validation
        errors = []
        if not item_code:
            errors.append('کد کالا الزامی است')
        elif Item.query.filter_by(item_code=item_code).first():
            errors.append('این کد کالا قبلاً استفاده شده است')
        
        if not item_name_fa:
            errors.append('نام کالا الزامی است')
        
        if not unit:
            errors.append('واحد کالا الزامی است')
        
        if errors:
            for error in errors:
                flash(error, 'danger')
            return render_template('admin/items/create.html')
        
        # Create item with unit_price
        item = Item(
            item_code=item_code,
            item_name_fa=item_name_fa,
            category=category,
            unit=unit,
            unit_price=unit_price,
            min_stock=min_stock,
            max_stock=max_stock,
            # P0-1: current_stock starts at 0, updated via transaction
            current_stock=0, 
            is_active=is_active
        )
        
        db.session.add(item)
        db.session.flush() # Get item ID
        
        # P0-1/P0-3: Create opening balance transaction if current_stock > 0
        if current_stock > 0:
            transaction = Transaction.create_transaction(
                item_id=item.id,
                transaction_type='خرید', # Or 'اصلاحی' with opening balance flag
                quantity=current_stock,
                unit_price=item.unit_price or 0,
                category=category,
                hotel_id=item.hotel_id,
                user_id=current_user.id,
                description='موجودی اولیه (ایجاد کالا دستی)',
                source='manual',
                is_opening_balance=True
            )
            transaction.transaction_date = datetime.utcnow().date()
            db.session.add(transaction)
            item.current_stock = current_stock # Explicitly set for initial state
        
        # Log the action
        AuditLog.log(
            user=current_user,
            action=AuditLog.ACTION_CREATE,
            resource_type=AuditLog.RESOURCE_ITEM,
            resource_id=item.id,
            resource_name=item.item_name_fa,
            new_values={
                'item_code': item_code,
                'item_name_fa': item_name_fa,
                'category': category,
                'unit': unit,
                'min_stock': min_stock,
                'initial_stock': current_stock
            },
            description=f'ایجاد کالای جدید: {item_name_fa}',
            request=request
        )
        
        db.session.commit()
        
        flash(f'کالای {item_name_fa} با موفقیت ایجاد شد', 'success')
        logger.info(f'Item {item_code} created by {current_user.username}')
        
        return redirect(url_for('admin.items_list'))
    
    return render_template('admin/items/create.html')


@admin_bp.route('/items/<int:item_id>/edit', methods=['GET', 'POST'])
@manager_required
def items_edit(item_id):
    """Edit an existing item"""
    item = Item.query.get_or_404(item_id)
    
    if request.method == 'POST':
        old_values = {
            'item_code': item.item_code,
            'item_name_fa': item.item_name_fa,
            'category': item.category,
            'unit': item.unit,
            'min_stock': item.min_stock,
            'max_stock': item.max_stock,
            'current_stock': item.current_stock,
            'is_active': item.is_active
        }
        
        item_code = request.form.get('item_code', '').strip()
        item_name_fa = request.form.get('item_name_fa', '').strip()
        category = request.form.get('category', 'Food')
        unit = request.form.get('unit', '').strip()
        unit_price = request.form.get('unit_price', 0, type=float)
        min_stock = request.form.get('min_stock', 0, type=float)
        max_stock = request.form.get('max_stock', 0, type=float)
        current_stock = request.form.get('current_stock', 0, type=float)
        is_active = request.form.get('is_active') == 'on'
        
        # Validation
        errors = []
        if not item_code:
            errors.append('کد کالا الزامی است')
        elif item_code != item.item_code and Item.query.filter_by(item_code=item_code).first():
            errors.append('این کد کالا قبلاً استفاده شده است')
        
        if not item_name_fa:
            errors.append('نام کالا الزامی است')
        
        if not unit:
            errors.append('واحد کالا الزامی است')
        
        if errors:
            for error in errors:
                flash(error, 'danger')
            return render_template('admin/items/edit.html', item=item)
        
        # Update item
        item.item_code = item_code
        item.item_name_fa = item_name_fa
        item.category = category
        item.unit = unit
        item.unit_price = unit_price
        item.min_stock = min_stock
        item.max_stock = max_stock
        # item.current_stock = current_stock # BUG-FIX: Forbidden to edit stock directly!
        item.is_active = is_active
        
        new_values = {
            'item_code': item_code,
            'item_name_fa': item_name_fa,
            'category': category,
            'unit': unit,
            'unit_price': unit_price,
            'min_stock': min_stock,
            'max_stock': max_stock,
            # 'current_stock': current_stock,
            'is_active': is_active
        }
        
        # P0-3: If stock manual edit was attempted, inform user it was ignored or create adjustment
        if abs(current_stock - old_values['current_stock']) > 0.001:
            flash('تغییر مستقیم موجودی مجاز نیست. لطفاً از بخش تراکنش‌ها برای اصلاح موجودی استفاده کنید.', 'warning')
        
        # Log the action
        AuditLog.log(
            user=current_user,
            action=AuditLog.ACTION_UPDATE,
            resource_type=AuditLog.RESOURCE_ITEM,
            resource_id=item.id,
            resource_name=item.item_name_fa,
            old_values=old_values,
            new_values=new_values,
            description=f'ویرایش کالا: {item.item_name_fa}',
            request=request
        )
        
        db.session.commit()
        
        flash(f'کالای {item_name_fa} با موفقیت ویرایش شد', 'success')
        logger.info(f'Item {item_code} edited by {current_user.username}')
        
        return redirect(url_for('admin.items_list'))
    
    return render_template('admin/items/edit.html', item=item)


@admin_bp.route('/items/<int:item_id>/delete', methods=['POST'])
@manager_required
def items_delete(item_id):
    """Delete an item"""
    item = Item.query.get_or_404(item_id)
    
    # Check if item has transactions
    if item.transactions.count() > 0:
        flash('این کالا دارای تراکنش است و نمی‌توان آن را حذف کرد. می‌توانید آن را غیرفعال کنید.', 'danger')
        return redirect(url_for('admin.items_list'))
    
    item_name = item.item_name_fa
    
    AuditLog.log(
        user=current_user,
        action=AuditLog.ACTION_DELETE,
        resource_type=AuditLog.RESOURCE_ITEM,
        resource_id=item.id,
        resource_name=item_name,
        old_values={
            'item_code': item.item_code,
            'item_name_fa': item.item_name_fa,
            'category': item.category
        },
        description=f'حذف کالا: {item_name}',
        request=request
    )
    
    db.session.delete(item)
    db.session.commit()
    
    flash(f'کالای {item_name} با موفقیت حذف شد', 'success')
    logger.info(f'Item {item_name} deleted by {current_user.username}')
    
    return redirect(url_for('admin.items_list'))


# ============== Audit Logs ==============
@admin_bp.route('/logs')
@admin_required
def logs_list():
    """View audit logs with filters"""
    page = request.args.get('page', 1, type=int)
    user_filter = request.args.get('user_id', '', type=str)
    action_filter = request.args.get('action', '')
    resource_filter = request.args.get('resource_type', '')
    date_from = request.args.get('date_from', '')
    date_to = request.args.get('date_to', '')
    
    query = AuditLog.query
    
    if user_filter:
        query = query.filter(AuditLog.user_id == int(user_filter))
    
    if action_filter:
        query = query.filter(AuditLog.action == action_filter)
    
    if resource_filter:
        query = query.filter(AuditLog.resource_type == resource_filter)
    
    if date_from:
        try:
            from_date = datetime.strptime(date_from, '%Y-%m-%d')
            query = query.filter(AuditLog.created_at >= from_date)
        except:
            pass
    
    if date_to:
        try:
            to_date = datetime.strptime(date_to, '%Y-%m-%d') + timedelta(days=1)
            query = query.filter(AuditLog.created_at < to_date)
        except:
            pass
    
    logs = query.order_by(desc(AuditLog.created_at)).paginate(page=page, per_page=50)
    
    # Get all users for filter dropdown
    users = User.query.order_by(User.username).all()
    
    return render_template('admin/logs/list.html',
                         logs=logs,
                         users=users,
                         user_filter=user_filter,
                         action_filter=action_filter,
                         resource_filter=resource_filter,
                         date_from=date_from,
                         date_to=date_to,
                         action_labels=AuditLog.ACTION_LABELS,
                         resource_labels=AuditLog.RESOURCE_LABELS)


@admin_bp.route('/logs/<int:log_id>')
@admin_required
def logs_detail(log_id):
    """View detailed audit log"""
    log = AuditLog.query.get_or_404(log_id)
    return render_template('admin/logs/detail.html', log=log)


@admin_bp.route('/logs/export')
@admin_required
def logs_export():
    """Export audit logs to Excel"""
    from io import BytesIO
    from openpyxl import Workbook
    from flask import send_file
    
    # Get filter parameters
    user_filter = request.args.get('user_id', '', type=str)
    action_filter = request.args.get('action', '')
    resource_filter = request.args.get('resource_type', '')
    date_from = request.args.get('date_from', '')
    date_to = request.args.get('date_to', '')
    
    query = AuditLog.query
    
    if user_filter:
        query = query.filter(AuditLog.user_id == int(user_filter))
    if action_filter:
        query = query.filter(AuditLog.action == action_filter)
    if resource_filter:
        query = query.filter(AuditLog.resource_type == resource_filter)
    if date_from:
        try:
            from_date = datetime.strptime(date_from, '%Y-%m-%d')
            query = query.filter(AuditLog.created_at >= from_date)
        except:
            pass
    if date_to:
        try:
            to_date = datetime.strptime(date_to, '%Y-%m-%d') + timedelta(days=1)
            query = query.filter(AuditLog.created_at < to_date)
        except:
            pass
    
    logs = query.order_by(desc(AuditLog.created_at)).limit(10000).all()
    
    # Create Excel
    wb = Workbook()
    ws = wb.active
    ws.title = 'Audit Logs'
    ws.sheet_view.rightToLeft = True
    
    # Headers
    headers = ['تاریخ', 'کاربر', 'نقش', 'عملیات', 'نوع منبع', 'شناسه منبع', 'نام منبع', 'توضیحات', 'IP']
    ws.append(headers)
    
    # Data
    for log in logs:
        ws.append([
            log.created_at.strftime('%Y-%m-%d %H:%M:%S'),
            log.username,
            ROLE_LABELS.get(log.user_role, log.user_role),
            log.action_label,
            log.resource_label,
            log.resource_id or '',
            log.resource_name or '',
            log.description or '',
            log.ip_address or ''
        ])
    
    # Log the export action
    AuditLog.log(
        user=current_user,
        action=AuditLog.ACTION_EXPORT,
        resource_type=AuditLog.RESOURCE_SYSTEM,
        description=f'خروجی گزارش لاگ فعالیت‌ها ({len(logs)} رکورد)',
        request=request
    )
    db.session.commit()
    
    # Save to BytesIO
    output = BytesIO()
    wb.save(output)
    output.seek(0)
    
    filename = f'audit_logs_{get_iran_now().strftime("%Y%m%d_%H%M%S")}.xlsx'
    
    return send_file(
        output,
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        as_attachment=True,
        download_name=filename
    )


# ============== Data Import ==============
@admin_bp.route('/import', methods=['GET', 'POST'])
@admin_required
def data_import():
    """Import data from Excel files"""
    import os
    from werkzeug.utils import secure_filename
    
    UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'uploads')
    ALLOWED_EXTENSIONS = {'xlsx', 'xls'}
    
    # Create upload folder if not exists
    os.makedirs(UPLOAD_FOLDER, exist_ok=True)
    
    if request.method == 'POST':
        if 'file' not in request.files:
            flash('فایلی انتخاب نشده است', 'danger')
            return redirect(request.url)
        
        file = request.files['file']
        
        if file.filename == '':
            flash('فایلی انتخاب نشده است', 'danger')
            return redirect(request.url)
        
        # BUG #5 FIX: Check file size before saving (max 16MB)
        MAX_UPLOAD_SIZE = 16 * 1024 * 1024  # 16 MB
        file.seek(0, os.SEEK_END)
        file_size = file.tell()
        file.seek(0)  # Reset to beginning
        
        if file_size > MAX_UPLOAD_SIZE:
            flash(f'حجم فایل نباید بیشتر از {MAX_UPLOAD_SIZE/1024/1024:.0f} مگابایت باشد', 'danger')
            return redirect(request.url)
        
        if file and '.' in file.filename and file.filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS:
            filename = secure_filename(file.filename)
            filepath = os.path.join(UPLOAD_FOLDER, filename)
            file.save(filepath)
            
            # Import the data
            # P3-FIX: Pass user context to DataImporter for proper auditing
            from services.data_importer import DataImporter
            
            importer = DataImporter(user_id=current_user.id, hotel_id=None)
            result = importer.import_excel(filepath)
            
            if result['success']:
                # Log the import
                AuditLog.log(
                    user=current_user,
                    action=AuditLog.ACTION_CREATE,
                    resource_type=AuditLog.RESOURCE_ITEM,
                    description=f'وارد کردن داده از فایل: {filename} ({result["total_items"]} کالا)',
                    request=request
                )
                db.session.commit()
                
                flash(f'داده‌ها با موفقیت وارد شدند: {result["total_items"]} کالا از {len(result["sheets"])} شیت', 'success')
                
                # BUG-FIX #5: Delete uploaded file after successful import
                try:
                    os.remove(filepath)
                    logger.info(f'Deleted uploaded file after import: {filename}')
                except OSError as e:
                    logger.warning(f'Failed to delete file {filename}: {e}')
                
                # Show detailed results
                return render_template('admin/import/result.html', result=result, filename=filename)
            else:
                flash(f'خطا در وارد کردن داده: {result.get("error", "خطای نامشخص")}', 'danger')
                
                # BUG-FIX #5: Delete file even on import failure
                try:
                    os.remove(filepath)
                    logger.info(f'Deleted failed import file: {filename}')
                except OSError:
                    pass
        else:
            flash('فقط فایل‌های Excel (.xlsx, .xls) مجاز هستند', 'danger')
        
        return redirect(request.url)
    
    # Get existing files in upload folder
    existing_files = []
    if os.path.exists(UPLOAD_FOLDER):
        for f in os.listdir(UPLOAD_FOLDER):
            if f.endswith(('.xlsx', '.xls')):
                filepath = os.path.join(UPLOAD_FOLDER, f)
                existing_files.append({
                    'name': f,
                    'size': os.path.getsize(filepath),
                    'modified': datetime.fromtimestamp(os.path.getmtime(filepath))
                })
    
    return render_template('admin/import/index.html', existing_files=existing_files)


@admin_bp.route('/import/file/<filename>')
@admin_required
def import_existing_file(filename):
    """Import from an existing uploaded file"""
    import os
    from werkzeug.utils import secure_filename
    
    UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'uploads')
    filename = secure_filename(filename)
    filepath = os.path.join(UPLOAD_FOLDER, filename)
    
    if not os.path.exists(filepath):
        flash('فایل یافت نشد', 'danger')
        return redirect(url_for('admin.data_import'))
    
    # P3-FIX: Pass user context to DataImporter for proper auditing
    from services.data_importer import DataImporter
    
    importer = DataImporter(user_id=current_user.id, hotel_id=None)
    result = importer.import_excel(filepath)
    
    if result['success']:
        AuditLog.log(
            user=current_user,
            action=AuditLog.ACTION_CREATE,
            resource_type=AuditLog.RESOURCE_ITEM,
            description=f'وارد کردن داده از فایل: {filename} ({result["total_items"]} کالا)',
            request=request
        )
        db.session.commit()
        
        flash(f'داده‌ها با موفقیت وارد شدند: {result["total_items"]} کالا', 'success')
        return render_template('admin/import/result.html', result=result, filename=filename)
    else:
        flash(f'خطا: {result.get("error", "خطای نامشخص")}', 'danger')
    
    return redirect(url_for('admin.data_import'))


@admin_bp.route('/import/preview/<filename>')
@admin_required
def import_preview(filename):
    """Preview Excel file contents before import"""
    import os
    import pandas as pd
    from werkzeug.utils import secure_filename
    
    UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'uploads')
    filename = secure_filename(filename)
    filepath = os.path.join(UPLOAD_FOLDER, filename)
    
    if not os.path.exists(filepath):
        flash('فایل یافت نشد', 'danger')
        return redirect(url_for('admin.data_import'))
    
    try:
        excel_file = pd.ExcelFile(filepath)
        sheets_info = []
        
        for sheet_name in excel_file.sheet_names:
            df = pd.read_excel(excel_file, sheet_name=sheet_name, nrows=5)
            sheets_info.append({
                'name': sheet_name,
                'rows': len(pd.read_excel(excel_file, sheet_name=sheet_name)),
                'columns': list(df.columns),
                'preview': df.head(5).to_dict('records')
            })
        
        return render_template('admin/import/preview.html', 
                             filename=filename, 
                             sheets=sheets_info)
    except Exception as e:
        flash(f'خطا در خواندن فایل: {str(e)}', 'danger')
        return redirect(url_for('admin.data_import'))


# ============== User Activity Report ==============
@admin_bp.route('/users/<int:user_id>/activity')
@admin_required
def user_activity(user_id):
    """View activity history for a specific user"""
    user = User.query.get_or_404(user_id)
    page = request.args.get('page', 1, type=int)
    
    logs = AuditLog.query.filter_by(user_id=user_id)\
        .order_by(desc(AuditLog.created_at))\
        .paginate(page=page, per_page=50)
    
    # Statistics
    total_actions = AuditLog.query.filter_by(user_id=user_id).count()
    actions_today = AuditLog.query.filter(
        AuditLog.user_id == user_id,
        AuditLog.created_at >= datetime.utcnow().date()
    ).count()
    
    # Actions by type
    actions_by_type = db.session.query(
        AuditLog.action, func.count(AuditLog.id)
    ).filter(AuditLog.user_id == user_id)\
     .group_by(AuditLog.action).all()
    
    return render_template('admin/users/activity.html',
                         user=user,
                         logs=logs,
                         total_actions=total_actions,
                         actions_today=actions_today,
                         actions_by_type=dict(actions_by_type),
                         action_labels=AuditLog.ACTION_LABELS)
