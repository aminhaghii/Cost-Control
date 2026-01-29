from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify, abort
from flask_login import login_required, current_user
from sqlalchemy import update
from models import db, Transaction, Item, Alert, WarehouseSettings
from models.transaction import WASTE_REASONS, DEPARTMENTS
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, ROUND_HALF_UP
from utils.decimal_utils import parse_decimal_input
import html
import logging

# BUG-FIX #11: Import limiter for API rate limiting
try:
    from app import limiter
except ImportError:
    limiter = None

logger = logging.getLogger(__name__)

# Iran timezone (UTC+03:30)
IRAN_TZ = timezone(timedelta(hours=3, minutes=30))

def get_iran_today():
    """Get current date in Iran timezone"""
    return datetime.now(IRAN_TZ).date()

# Validation Constants
MAX_QUANTITY = 999999
MAX_PRICE = 999999999
MIN_QUANTITY = 1
MIN_PRICE = 1

transactions_bp = Blueprint('transactions', __name__, url_prefix='/transactions')


def validate_transaction_data(quantity, unit_price, transaction_date_str):
    """Validate transaction input data and return errors list"""
    errors = []
    
    # Bug #1: Validate negative values
    if quantity is None or quantity <= 0:
        errors.append('مقدار باید بزرگتر از صفر باشد')
    
    if unit_price is None or unit_price <= 0:
        errors.append('قیمت واحد باید بزرگتر از صفر باشد')
    
    # Bug #2: Validate max values
    if quantity and quantity > MAX_QUANTITY:
        errors.append(f'مقدار نمی‌تواند بیشتر از {MAX_QUANTITY:,} باشد')
    
    if unit_price and unit_price > MAX_PRICE:
        errors.append(f'قیمت واحد نمی‌تواند بیشتر از {MAX_PRICE:,} ریال باشد')
    
    # Bug #4: Validate date format only (future date validation handled by frontend)
    if transaction_date_str:
        try:
            datetime.strptime(transaction_date_str, '%Y-%m-%d').date()
        except ValueError:
            errors.append('فرمت تاریخ نامعتبر است')
    
    return errors


def validate_stock_availability(item, transaction_type, quantity, old_quantity=0):
    """Bug #7: Check if stock is sufficient for consumption/waste transactions"""
    if transaction_type in ['مصرف', 'ضایعات']:
        available_stock = item.current_stock + old_quantity  # Add back old quantity if editing
        if quantity > available_stock:
            return f'موجودی کافی نیست! موجودی فعلی: {available_stock:,.2f} {item.unit}'
    return None


def auto_set_category(item):
    """Bug #8: Auto-set category from item to ensure consistency"""
    return item.category


def check_and_create_stock_alert(item):
    """Bug #9: Create alert if stock is below minimum"""
    from models import Alert
    
    if item.min_stock > 0 and item.current_stock < item.min_stock:
        # Check if alert already exists for this item
        existing_alert = Alert.query.filter_by(
            item_id=item.id,
            alert_type='low_stock',
            is_resolved=False
        ).first()
        
        if not existing_alert:
            alert = Alert(
                alert_type='low_stock',
                item_id=item.id,
                message=f'موجودی {item.item_name_fa} کمتر از حد مینیمم است ({item.current_stock:,.2f} از {item.min_stock:,.2f} {item.unit})',
                severity='warning'
            )
            db.session.add(alert)
            logger.info(f'Created low stock alert for item {item.item_code}')
    elif item.min_stock > 0 and item.current_stock >= item.min_stock:
        # Resolve existing alerts if stock is now sufficient
        Alert.query.filter_by(
            item_id=item.id,
            alert_type='low_stock',
            is_resolved=False
        ).update({'is_resolved': True, 'resolved_at': datetime.utcnow()})


def sanitize_text(text):
    """Bug #6: Sanitize text to prevent XSS"""
    if not text:
        return ''
    return html.escape(text.strip())

@transactions_bp.route('/')
@login_required
def list_transactions():
    from services.hotel_scope_service import get_allowed_hotel_ids
    
    page = request.args.get('page', 1, type=int)
    per_page = 20
    
    category_filter = request.args.get('category', '')
    type_filter = request.args.get('type', '')
    date_from = request.args.get('date_from', '')
    date_to = request.args.get('date_to', '')
    
    # BUG-FIX: Filter out deleted transactions
    query = Transaction.query.filter(Transaction.is_deleted != True)
    
    # BUG-FIX: Apply hotel scope for non-admin users
    if current_user.role != 'admin':
        allowed_hotel_ids = get_allowed_hotel_ids(current_user)
        if allowed_hotel_ids:
            query = query.filter(Transaction.hotel_id.in_(allowed_hotel_ids))
    
    if category_filter:
        query = query.filter(Transaction.category == category_filter)
    
    if type_filter:
        query = query.filter(Transaction.transaction_type == type_filter)
    
    from_date = None
    to_date = None
    
    if date_from:
        try:
            from_date = datetime.strptime(date_from, '%Y-%m-%d').date()
            query = query.filter(Transaction.transaction_date >= from_date)
        except ValueError:
            flash('فرمت تاریخ شروع نامعتبر است', 'warning')
    
    if date_to:
        try:
            to_date = datetime.strptime(date_to, '%Y-%m-%d').date()
            query = query.filter(Transaction.transaction_date <= to_date)
        except ValueError:
            flash('فرمت تاریخ پایان نامعتبر است', 'warning')
    
    # Bug #3: Validate date range
    if from_date and to_date and from_date > to_date:
        flash('تاریخ پایان باید بزرگتر از تاریخ شروع باشد', 'warning')
        # Reset date filters only, keep other filters
        date_from = ''
        date_to = ''
        # Rebuild query with all filters except date
        query = Transaction.query.filter(Transaction.is_deleted != True)
        if current_user.role != 'admin':
            if allowed_hotel_ids:
                query = query.filter(Transaction.hotel_id.in_(allowed_hotel_ids))
        if category_filter:
            query = query.filter(Transaction.category == category_filter)
        if type_filter:
            query = query.filter(Transaction.transaction_type == type_filter)
    
    transactions = query.order_by(Transaction.transaction_date.desc(), Transaction.created_at.desc()).paginate(
        page=page, per_page=per_page, error_out=False
    )
    
    return render_template('transactions/list.html',
                         transactions=transactions,
                         category_filter=category_filter,
                         type_filter=type_filter,
                         date_from=date_from,
                         date_to=date_to)

@transactions_bp.route('/create', methods=['GET', 'POST'])
@login_required
def create():
    items = Item.query.filter_by(is_active=True).order_by(Item.item_name_fa).all()
    today = get_iran_today().isoformat()
    
    from services.hotel_scope_service import check_record_access

    if request.method == 'POST':
        try:
            transaction_date_str = request.form.get('transaction_date')
            item_id_raw = request.form.get('item_id')
            if not item_id_raw:
                flash('انتخاب کالا الزامی است', 'danger')
                return render_template('transactions/create.html', items=items, today=today)
            
            # BUG-001 Fix: Safe item_id parsing with proper error handling
            try:
                item_id = int(item_id_raw)
            except (TypeError, ValueError):
                flash('شناسه کالا نامعتبر است', 'danger')
                return render_template('transactions/create.html', items=items, today=today), 400

            transaction_type = request.form.get('transaction_type')
            category = request.form.get('category')
            quantity_raw = request.form.get('quantity')
            
            try:
                quantity_decimal = parse_decimal_input(quantity_raw, allow_negative=False, quantize='0.001', error_label='مقدار')
            except ValueError as exc:
                flash(str(exc), 'danger')
                return render_template('transactions/create.html', items=items, today=today), 400
            
            quantity = float(quantity_decimal)
            if quantity <= 0:
                flash('مقدار باید بزرگتر از صفر باشد', 'danger')
                return render_template('transactions/create.html', items=items, today=today), 400
            
            unit_price_raw = (request.form.get('unit_price') or '').strip()
            try:
                unit_price_decimal = parse_decimal_input(unit_price_raw, allow_negative=False, quantize='0.01', error_label='قیمت واحد')
            except ValueError as exc:
                flash(str(exc), 'danger')
                return render_template('transactions/create.html', items=items, today=today), 400
            
            unit_price = float(unit_price_decimal)
            description = request.form.get('description', '').strip()

            item = Item.query.get_or_404(item_id)
            check_record_access(current_user, item)
            
            if not all([transaction_date_str, item_id, transaction_type, category, quantity is not None, unit_price > 0]):
                flash('لطفاً تمام فیلدهای الزامی را پر کنید', 'danger')
                return render_template('transactions/create.html', items=items, today=today)
            
            # Validate input data (Bug #1, #2, #4)
            validation_errors = validate_transaction_data(quantity, unit_price, transaction_date_str)
            if validation_errors:
                for error in validation_errors:
                    flash(error, 'danger')
                return render_template('transactions/create.html', items=items, today=get_iran_today().isoformat())
            
            # Sanitize description (Bug #6)
            description = sanitize_text(description)
            
            transaction_date = datetime.strptime(transaction_date_str, '%Y-%m-%d').date()
            
            # P0-4: Use Decimal for money precision
            price_decimal = unit_price_decimal
            total_decimal = (quantity_decimal * price_decimal).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
            
            logger.info(f'Creating transaction: item={item_id}, qty={quantity}, price={price_decimal}, total={total_decimal}')
            
            # Bug #8 / P0-2: Auto-set category from item before creation
            category = auto_set_category(item)

            # ═══ Warehouse Management: Validate waste transactions ═══
            waste_reason = request.form.get('waste_reason')
            waste_reason_detail = request.form.get('waste_reason_detail', '').strip()
            destination_department = request.form.get('destination_department')
            reference_number = request.form.get('reference_number', '').strip()
            
            # Waste transactions MUST have waste_reason
            if transaction_type == 'ضایعات' and not waste_reason:
                flash('انتخاب دلیل ضایعات الزامی است', 'danger')
                return render_template('transactions/create.html', items=items, today=today,
                                     WASTE_REASONS=WASTE_REASONS, DEPARTMENTS=DEPARTMENTS)
            
            # ═══ Warehouse Management: Check if approval needed ═══
            requires_approval = False
            total_float = float(total_decimal)
            if transaction_type == 'ضایعات' and item.hotel_id:
                settings = WarehouseSettings.get_or_create(item.hotel_id)
                if settings.check_waste_approval_needed(total_float):
                    requires_approval = True
            
            # BUG-FIX #2: Check permission before calling create_transaction
            allow_override = current_user.role in ['admin', 'manager', 'accountant']
            
            # P0-2/P0-3: Use centralized transaction creation
            transaction = Transaction.create_transaction(
                item_id=item.id,
                transaction_type=transaction_type,
                quantity=quantity,
                unit_price=price_decimal,
                category=category,
                hotel_id=item.hotel_id,
                user_id=current_user.id,
                description=description,
                source='manual',
                allow_price_override=allow_override,
                price_override_reason=request.form.get('price_override_reason')
            )
            transaction.transaction_date = transaction_date
            
            # ═══ Warehouse Management: Set additional fields ═══
            transaction.waste_reason = waste_reason if transaction_type == 'ضایعات' else None
            transaction.waste_reason_detail = waste_reason_detail if transaction_type == 'ضایعات' else None
            transaction.destination_department = destination_department if transaction_type == 'مصرف' else None
            transaction.reference_number = reference_number if transaction_type == 'خرید' else None
            
            if requires_approval:
                transaction.requires_approval = True
                transaction.approval_status = 'pending'
            
            # Bug #7: Validate stock availability for consumption/waste
            stock_error = validate_stock_availability(item, transaction_type, quantity)
            if stock_error:
                flash(stock_error, 'danger')
                return render_template('transactions/create.html', items=items, today=today,
                                     WASTE_REASONS=WASTE_REASONS, DEPARTMENTS=DEPARTMENTS)
            
            # P0-2: Update stock using signed_quantity from transaction
            # Only update stock if approval NOT required
            # P1-FIX: Use atomic database update to prevent race conditions
            if not requires_approval:
                db.session.execute(
                    update(Item).where(Item.id == item.id)
                    .values(current_stock=Item.current_stock + transaction.signed_quantity)
                )
                db.session.flush()  # Ensure update is applied before alert check
                db.session.refresh(item)  # Refresh to get updated stock value
                # Bug #9: Check and create stock alerts (only if stock updated)
                check_and_create_stock_alert(item)
            
            db.session.add(transaction)
            db.session.commit()
            
            # ═══ Warehouse Management: Create approval alert if needed ═══
            if requires_approval:
                Alert.create_if_not_exists(
                    hotel_id=item.hotel_id,
                    alert_type='pending_approval',
                    item_id=item.id,
                    related_transaction_id=transaction.id,
                    message=f'ضایعات {item.item_name_fa} به مبلغ {total_decimal:,.0f} ریال نیاز به تایید دارد',
                    severity='warning',
                    threshold_value=settings.waste_approval_threshold if 'settings' in locals() else None,
                    actual_value=Decimal(str(total_float))
                )
                db.session.commit()
            
            if requires_approval:
                flash('تراکنش ثبت شد و در انتظار تایید مدیر است', 'warning')
            else:
                flash('تراکنش با موفقیت ثبت شد', 'success')
            
            return redirect(url_for('transactions.list_transactions'))
            
        except Exception as e:
            db.session.rollback()
            flash(f'خطا در ثبت تراکنش: {str(e)}', 'danger')
    
    return render_template('transactions/create.html', items=items, today=today,
                         WASTE_REASONS=WASTE_REASONS, DEPARTMENTS=DEPARTMENTS)

@transactions_bp.route('/edit/<int:id>', methods=['GET', 'POST'])
@login_required
def edit(id):
    transaction = Transaction.query.get_or_404(id)
    
    # P1-1: Enforce hotel scoping on detail endpoint
    from services.hotel_scope_service import check_record_access
    check_record_access(current_user, transaction)
    
    items = Item.query.filter_by(is_active=True).order_by(Item.item_name_fa).all()
    
    if request.method == 'POST':
        try:
            old_quantity = transaction.quantity
            old_type = transaction.transaction_type
            old_item_id = transaction.item_id
            
            transaction_date_str = request.form.get('transaction_date')
            item_id = request.form.get('item_id', type=int)
            transaction_type = request.form.get('transaction_type')
            category = request.form.get('category')
            quantity_raw = request.form.get('quantity')
            
            try:
                quantity_decimal = parse_decimal_input(quantity_raw, allow_negative=False, quantize='0.001', error_label='مقدار')
            except ValueError as exc:
                flash(str(exc), 'danger')
                return render_template('transactions/edit.html', transaction=transaction, items=items), 400
            
            quantity = float(quantity_decimal)
            if quantity <= 0:
                flash('مقدار باید بزرگتر از صفر باشد', 'danger')
                return render_template('transactions/edit.html', transaction=transaction, items=items), 400
            
            unit_price_raw = (request.form.get('unit_price') or '').strip()
            try:
                unit_price_decimal = parse_decimal_input(unit_price_raw, allow_negative=False, quantize='0.01', error_label='قیمت واحد')
            except ValueError as exc:
                flash(str(exc), 'danger')
                return render_template('transactions/edit.html', transaction=transaction, items=items), 400
            
            unit_price = float(unit_price_decimal)
            description = request.form.get('description', '').strip()
            
            if not all([transaction_date_str, item_id, transaction_type, category, quantity is not None, unit_price > 0]):
                flash('لطفاً تمام فیلدهای الزامی را پر کنید', 'danger')
                return render_template('transactions/edit.html', transaction=transaction, items=items)
            
            # Validate input data (Bug #1, #2, #4)
            validation_errors = validate_transaction_data(quantity, unit_price, transaction_date_str)
            if validation_errors:
                for error in validation_errors:
                    flash(error, 'danger')
                return render_template('transactions/edit.html', transaction=transaction, items=items)
            
            # Sanitize description (Bug #6)
            description = sanitize_text(description)
            
            new_item = Item.query.get(item_id)
            if not new_item:
                flash('کالای انتخابی یافت نشد', 'danger')
                return render_template('transactions/edit.html', transaction=transaction, items=items)
            
            # Bug #7: Validate stock availability for consumption/waste (consider old quantity)
            stock_error = validate_stock_availability(new_item, transaction_type, quantity, old_quantity if old_item_id == item_id else 0)
            if stock_error:
                flash(stock_error, 'danger')
                return render_template('transactions/edit.html', transaction=transaction, items=items)
            
            # BUG #1 FIX: Use atomic update to prevent race condition
            if transaction.signed_quantity:
                db.session.execute(
                    db.update(Item).where(Item.id == old_item_id)
                    .values(current_stock=Item.current_stock - transaction.signed_quantity)
                )
            old_item = Item.query.get(old_item_id)
            
            # Bug #8: Auto-set category from item
            category = auto_set_category(new_item)
            
            # P0-4: Use Decimal for money
            price_decimal = Decimal(str(unit_price)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
            total_decimal = (quantity_decimal * price_decimal).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
            
            # Update transaction fields
            transaction.transaction_date = datetime.strptime(transaction_date_str, '%Y-%m-%d').date()
            transaction.item_id = item_id
            transaction.transaction_type = transaction_type
            transaction.category = category
            transaction.quantity = quantity
            transaction.unit_price = price_decimal
            transaction.total_amount = total_decimal
            transaction.description = description
            
            # P0-2: Recalculate signed_quantity
            transaction.calculate_signed_quantity()
            
            # BUG #1 FIX: Use atomic update to prevent race condition
            db.session.execute(
                db.update(Item).where(Item.id == new_item.id)
                .values(current_stock=Item.current_stock + transaction.signed_quantity)
            )
            # Refresh to get updated stock
            db.session.refresh(new_item)
            
            # Bug #9: Check and create stock alerts for both items
            if old_item:
                check_and_create_stock_alert(old_item)
            check_and_create_stock_alert(new_item)
            
            db.session.commit()
            
            flash('تراکنش با موفقیت ویرایش شد', 'success')
            return redirect(url_for('transactions.list_transactions'))
            
        except Exception as e:
            db.session.rollback()
            flash(f'خطا در ویرایش تراکنش: {str(e)}', 'danger')
    
    return render_template('transactions/edit.html', transaction=transaction, items=items)

@transactions_bp.route('/delete/<int:id>', methods=['POST'])
@login_required
def delete(id):
    transaction = Transaction.query.get_or_404(id)
    
    # P1-1: Enforce hotel scoping on delete endpoint
    from services.hotel_scope_service import check_record_access
    check_record_access(current_user, transaction)
    
    try:
        item = Item.query.get(transaction.item_id)
        if item:
            # P0-2: Soft delete - mark as deleted
            transaction.is_deleted = True
            transaction.deleted_at = datetime.utcnow()
            
            # BUG #4 FIX: Use atomic update for stock
            db.session.execute(
                db.update(Item).where(Item.id == item.id)
                .values(current_stock=Item.current_stock - transaction.signed_quantity)
            )
            
            # First commit: transaction and stock update
            db.session.commit()
            
            # BUG #4 FIX: After successful commit, check alerts separately
            try:
                db.session.refresh(item)
                check_and_create_stock_alert(item)
                db.session.commit()
            except Exception as alert_error:
                logger.warning(f'Alert creation failed after delete: {alert_error}')
                # Don't fail the whole operation if alert fails
        else:
            db.session.commit()
        
        flash('تراکنش با موفقیت حذف شد', 'success')
    except Exception as e:
        db.session.rollback()
        logger.error(f'Transaction delete failed: {e}')
        flash(f'خطا در حذف تراکنش: {str(e)}', 'danger')
    
    return redirect(url_for('transactions.list_transactions'))


# API endpoint for fetching item details including price
@transactions_bp.route('/api/item/<int:item_id>')
@login_required
# BUG-FIX #11: Add rate limiting
@limiter.limit("60 per minute") if limiter else lambda f: f
def api_get_item(item_id):
    """Get item details including unit price for transaction form"""
    from services.hotel_scope_service import get_allowed_hotel_ids, user_can_access_hotel
    
    item = Item.query.get_or_404(item_id)
    
    # Security: Check hotel access
    if item.hotel_id and not user_can_access_hotel(current_user, item.hotel_id):
        return jsonify({'error': 'دسترسی غیرمجاز'}), 403
    
    return jsonify({
        'id': item.id,
        'item_code': item.item_code,
        'item_name_fa': item.item_name_fa,
        'category': item.category,
        'unit': item.unit,
        'unit_price': float(item.unit_price or 0),
        'current_stock': float(item.current_stock or 0)
    })


# UX #5: API endpoint for Load More transactions
@transactions_bp.route('/api/list')
@login_required
# BUG-FIX #11: Add rate limiting to API endpoint
@limiter.limit("30 per minute") if limiter else lambda f: f
def api_list_transactions():
    """API endpoint for loading more transactions (AJAX)"""
    from services.hotel_scope_service import get_allowed_hotel_ids
    
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 10, type=int)
    
    # Limit per_page to prevent abuse
    per_page = min(per_page, 50)
    
    # BUG-FIX: Apply hotel scope filtering for security
    query = Transaction.query.filter(Transaction.is_deleted != True)
    if current_user.role != 'admin':
        allowed_hotel_ids = get_allowed_hotel_ids(current_user)
        if allowed_hotel_ids:
            query = query.filter(Transaction.hotel_id.in_(allowed_hotel_ids))
    
    transactions = query.order_by(
        Transaction.created_at.desc()
    ).paginate(page=page, per_page=per_page, error_out=False)
    
    result = []
    for trans in transactions.items:
        result.append({
            'id': trans.id,
            'date': trans.transaction_date.strftime('%Y/%m/%d'),
            'item_name': trans.item.item_name_fa if trans.item else '-',
            'type': trans.transaction_type,
            'quantity': f'{trans.quantity:,.2f}',
            'amount': f'{trans.total_amount:,.0f}'
        })
    
    return jsonify({
        'transactions': result,
        'has_more': transactions.has_next,
        'total': transactions.total,
        'page': page
    })
