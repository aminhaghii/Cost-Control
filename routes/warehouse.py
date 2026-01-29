"""
Warehouse Management Routes
"""
from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_required, current_user
from datetime import date, datetime, timedelta
from decimal import Decimal

from models import db, Item, Transaction, Alert, InventoryCount, WarehouseSettings, Hotel
from models.transaction import WASTE_REASONS, DEPARTMENTS
from models.inventory_count import VARIANCE_REASONS
from services.warehouse_service import WarehouseService
from services.inventory_count_service import InventoryCountService
from services.waste_analysis_service import WasteAnalysisService
from services.hotel_scope_service import get_allowed_hotel_ids, user_can_access_hotel, SINGLE_HOTEL_MODE
from utils.decimal_utils import parse_decimal_input
import logging

logger = logging.getLogger(__name__)

warehouse_bp = Blueprint('warehouse', __name__, url_prefix='/warehouse')


def get_user_hotel_id():
    """Get primary hotel ID for current user"""
    # SINGLE HOTEL MODE: Always use the first active hotel
    if SINGLE_HOTEL_MODE:
        main_hotel = Hotel.query.filter_by(hotel_code='MAIN').first()
        if main_hotel:
            return main_hotel.id
        first_hotel = Hotel.query.filter_by(is_active=True).first()
        if first_hotel:
            return first_hotel.id
        fallback_hotel = Hotel.query.first()
        return fallback_hotel.id if fallback_hotel else 1
    
    hotel_ids = get_allowed_hotel_ids(current_user)
    
    # Admin has access to all hotels (returns None)
    if hotel_ids is None:
        main_hotel = Hotel.query.filter_by(hotel_code='MAIN').first()
        if main_hotel:
            return main_hotel.id
        first_hotel = Hotel.query.filter_by(is_active=True).first()
        return first_hotel.id if first_hotel else None
    
    return hotel_ids[0] if hotel_ids else None


@warehouse_bp.route('/')
@login_required
def dashboard():
    """Warehouse dashboard"""
    hotel_id = request.args.get('hotel_id', type=int) or get_user_hotel_id()
    
    if not hotel_id or not user_can_access_hotel(current_user, hotel_id):
        flash('دسترسی به انبار این هتل ندارید', 'danger')
        return redirect(url_for('dashboard.index'))
    
    try:
        data = WarehouseService.get_warehouse_dashboard(hotel_id, current_user)
        
        return render_template('warehouse/dashboard.html',
                             data=data,
                             hotel_id=hotel_id,
                             WASTE_REASONS=WASTE_REASONS,
                             DEPARTMENTS=DEPARTMENTS)
    except PermissionError as e:
        flash(str(e), 'danger')
        return redirect(url_for('dashboard.index'))


@warehouse_bp.route('/api/summary')
@login_required
def api_summary():
    """JSON summary for AJAX updates"""
    hotel_id = request.args.get('hotel_id', type=int) or get_user_hotel_id()
    
    if not hotel_id or not user_can_access_hotel(current_user, hotel_id):
        return jsonify({'error': 'Access denied'}), 403
    
    try:
        data = WarehouseService.get_warehouse_dashboard(hotel_id, current_user)
        return jsonify({
            'summary': data['summary'],
            'waste_rate': data['waste_rate']
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@warehouse_bp.route('/items')
@login_required
def items_list():
    """List all items with stock status"""
    hotel_id = request.args.get('hotel_id', type=int) or get_user_hotel_id()
    category = request.args.get('category')
    status_filter = request.args.get('status')
    search_query = request.args.get('search', '').strip()
    page = request.args.get('page', 1, type=int)
    per_page = 50
    
    if not hotel_id or not user_can_access_hotel(current_user, hotel_id):
        flash('دسترسی غیرمجاز', 'danger')
        return redirect(url_for('dashboard.index'))
    
    items = WarehouseService.get_stock_status(hotel_id, category)
    
    # Apply status filter
    if status_filter:
        items = [i for i in items if i['status'] == status_filter]
    
    # Apply search filter
    if search_query:
        search_lower = search_query.lower()
        items = [i for i in items if 
                 search_lower in i['item'].item_name_fa.lower() or 
                 (i['item'].item_name_en and search_lower in i['item'].item_name_en.lower()) or
                 search_lower in i['item'].item_code.lower()]
    
    # Pagination
    total_items = len(items)
    total_pages = (total_items + per_page - 1) // per_page
    start_idx = (page - 1) * per_page
    end_idx = start_idx + per_page
    items_page = items[start_idx:end_idx]
    
    return render_template('warehouse/items.html',
                         items=items_page,
                         total_items=total_items,
                         page=page,
                         total_pages=total_pages,
                         per_page=per_page,
                         hotel_id=hotel_id,
                         category=category,
                         status_filter=status_filter)


@warehouse_bp.route('/items/<int:item_id>')
@login_required
def item_detail(item_id):
    """Item detail with movement history"""
    item = Item.query.get_or_404(item_id)
    
    if not user_can_access_hotel(current_user, item.hotel_id):
        flash('دسترسی غیرمجاز', 'danger')
        return redirect(url_for('warehouse.items_list'))
    
    # Get movement history
    days = request.args.get('days', 30, type=int)
    start_date = date.today() - timedelta(days=days)
    
    movements = WarehouseService.get_movements(
        item.hotel_id,
        item_id=item_id,
        start_date=start_date
    )
    
    # Get recent counts
    recent_counts = InventoryCount.query.filter_by(item_id=item_id).order_by(
        InventoryCount.count_date.desc()
    ).limit(10).all()
    
    # Calculate stats
    days_on_hand = WarehouseService.calculate_days_on_hand(item)
    
    return render_template('warehouse/item_detail.html',
                         item=item,
                         movements=movements,
                         recent_counts=recent_counts,
                         days_on_hand=days_on_hand,
                         days=days)


@warehouse_bp.route('/movements')
@login_required
def movements():
    """All movements with filters"""
    hotel_id = request.args.get('hotel_id', type=int) or get_user_hotel_id()
    item_id = request.args.get('item_id', type=int)
    movement_type = request.args.get('type')
    days = request.args.get('days', 30, type=int)
    
    if not hotel_id or not user_can_access_hotel(current_user, hotel_id):
        flash('دسترسی غیرمجاز', 'danger')
        return redirect(url_for('dashboard.index'))
    
    start_date = date.today() - timedelta(days=days)
    
    movements_list = WarehouseService.get_movements(
        hotel_id,
        item_id=item_id,
        start_date=start_date,
        movement_type=movement_type,
        limit=200
    )
    
    items = Item.query.filter_by(hotel_id=hotel_id, is_active=True).order_by(Item.item_name_fa).all()
    
    return render_template('warehouse/movements.html',
                         movements=movements_list,
                         items=items,
                         hotel_id=hotel_id,
                         selected_item_id=item_id,
                         selected_type=movement_type,
                         days=days)


@warehouse_bp.route('/count')
@login_required
def count_list():
    """Inventory count overview"""
    hotel_id = request.args.get('hotel_id', type=int) or get_user_hotel_id()
    
    if not hotel_id or not user_can_access_hotel(current_user, hotel_id):
        flash('دسترسی غیرمجاز', 'danger')
        return redirect(url_for('dashboard.index'))
    
    pending_counts = InventoryCountService.get_pending_counts(hotel_id)
    recent_counts = InventoryCountService.get_recent_counts(hotel_id)
    items_needing_count = InventoryCountService.get_items_needing_count(hotel_id)
    variance_summary = InventoryCountService.get_variance_summary(hotel_id)
    
    return render_template('warehouse/count_list.html',
                         pending_counts=pending_counts,
                         recent_counts=recent_counts,
                         items_needing_count=items_needing_count,
                         variance_summary=variance_summary,
                         hotel_id=hotel_id,
                         VARIANCE_REASONS=VARIANCE_REASONS)


@warehouse_bp.route('/count/new', methods=['GET', 'POST'])
@login_required
def count_new():
    """Create new inventory count"""
    hotel_id = request.args.get('hotel_id', type=int) or get_user_hotel_id()
    
    if not hotel_id or not user_can_access_hotel(current_user, hotel_id):
        flash('دسترسی غیرمجاز', 'danger')
        return redirect(url_for('dashboard.index'))
    
    if request.method == 'POST':
        try:
            item_id = request.form.get('item_id', type=int)
            physical_qty_raw = request.form.get('physical_quantity')
            count_date_str = request.form.get('count_date')
            
            if not item_id:
                flash('انتخاب کالا الزامی است', 'danger')
                return redirect(url_for('warehouse.count_new', hotel_id=hotel_id))
            
            try:
                physical_qty = float(parse_decimal_input(physical_qty_raw, allow_negative=False, error_label='موجودی فیزیکی'))
            except ValueError as e:
                flash(str(e), 'danger')
                return redirect(url_for('warehouse.count_new', hotel_id=hotel_id))
            
            count_date = datetime.strptime(count_date_str, '%Y-%m-%d').date() if count_date_str else date.today()
            
            count = InventoryCountService.create_count(
                hotel_id=hotel_id,
                item_id=item_id,
                physical_quantity=physical_qty,
                user_id=current_user.id,
                count_date=count_date
            )
            
            if count.has_variance:
                flash(f'شمارش ثبت شد. مغایرت: {float(count.variance):.2f} واحد ({float(count.variance_percentage):.1f}%)', 'warning')
            else:
                flash('شمارش ثبت شد. بدون مغایرت.', 'success')
            
            return redirect(url_for('warehouse.count_detail', count_id=count.id))
            
        except Exception as e:
            db.session.rollback()
            flash(f'خطا در ثبت شمارش: {str(e)}', 'danger')
    
    items = Item.query.filter_by(hotel_id=hotel_id, is_active=True).order_by(Item.item_name_fa).all()
    items_needing_count = InventoryCountService.get_items_needing_count(hotel_id)
    
    return render_template('warehouse/count_new.html',
                         items=items,
                         items_needing_count=items_needing_count,
                         hotel_id=hotel_id,
                         today=date.today().isoformat())


@warehouse_bp.route('/count/<int:count_id>')
@login_required
def count_detail(count_id):
    """Count detail view"""
    count = InventoryCount.query.get_or_404(count_id)
    
    if not user_can_access_hotel(current_user, count.hotel_id):
        flash('دسترسی غیرمجاز', 'danger')
        return redirect(url_for('warehouse.count_list'))
    
    return render_template('warehouse/count_detail.html',
                         count=count,
                         VARIANCE_REASONS=VARIANCE_REASONS)


@warehouse_bp.route('/count/<int:count_id>/resolve', methods=['POST'])
@login_required
def count_resolve(count_id):
    """Resolve variance"""
    count = InventoryCount.query.get_or_404(count_id)
    
    if not user_can_access_hotel(current_user, count.hotel_id):
        flash('دسترسی غیرمجاز', 'danger')
        return redirect(url_for('warehouse.count_list'))
    
    try:
        action = request.form.get('action')
        reason = request.form.get('reason')
        notes = request.form.get('notes', '')
        
        if not reason:
            flash('انتخاب دلیل الزامی است', 'danger')
            return redirect(url_for('warehouse.count_detail', count_id=count_id))
        
        if action == 'accept':
            # Accept variance without adjustment
            InventoryCountService.resolve_count(count_id, reason, notes, current_user.id)
            flash('مغایرت پذیرفته شد', 'success')
        elif action == 'adjust':
            # Create adjustment transaction
            tx = InventoryCountService.resolve_with_adjustment(
                count_id, reason, notes, current_user.id
            )
            if tx.approval_status == 'pending':
                flash('اصلاحی ثبت شد و در انتظار تایید است', 'warning')
            else:
                flash('اصلاحی ثبت و موجودی به‌روز شد', 'success')
        else:
            flash('عملیات نامعتبر', 'danger')
            
    except Exception as e:
        db.session.rollback()
        flash(f'خطا: {str(e)}', 'danger')
    
    return redirect(url_for('warehouse.count_list', hotel_id=count.hotel_id))


@warehouse_bp.route('/waste')
@login_required
def waste_analysis():
    """Waste analysis dashboard"""
    hotel_id = request.args.get('hotel_id', type=int) or get_user_hotel_id()
    days = request.args.get('days', 30, type=int)
    
    if not hotel_id or not user_can_access_hotel(current_user, hotel_id):
        flash('دسترسی غیرمجاز', 'danger')
        return redirect(url_for('dashboard.index'))
    
    start_date = date.today() - timedelta(days=days)
    end_date = date.today()
    
    summary = WasteAnalysisService.get_waste_summary(hotel_id, start_date, end_date)
    by_reason = WasteAnalysisService.get_waste_by_reason(hotel_id, start_date, end_date)
    top_wasted = WasteAnalysisService.get_top_wasted_items(hotel_id, start_date, end_date)
    trend = WasteAnalysisService.get_waste_trend(hotel_id, months=6)
    
    return render_template('warehouse/waste.html',
                         summary=summary,
                         by_reason=by_reason,
                         top_wasted=top_wasted,
                         trend=trend,
                         hotel_id=hotel_id,
                         days=days,
                         WASTE_REASONS=WASTE_REASONS)


@warehouse_bp.route('/approvals')
@login_required
def approvals():
    """Pending approvals list"""
    hotel_id = request.args.get('hotel_id', type=int) or get_user_hotel_id()
    
    if not hotel_id or not user_can_access_hotel(current_user, hotel_id):
        flash('دسترسی غیرمجاز', 'danger')
        return redirect(url_for('dashboard.index'))
    
    pending = WarehouseService.get_pending_approvals(hotel_id)
    
    return render_template('warehouse/approvals.html',
                         pending=pending,
                         hotel_id=hotel_id,
                         WASTE_REASONS=WASTE_REASONS)
@login_required
def approve_transaction(tx_id):
    """Approve a pending transaction and update stock"""
    tx = Transaction.query.get_or_404(tx_id)
    
    # BUG-FIX: Check hotel access before approving
    if not user_can_access_hotel(current_user, tx.hotel_id):
        flash('دسترسی غیرمجاز', 'danger')
        return redirect(url_for('warehouse.approvals'))
    
    # BUG #38 FIX: Check permission - only admin/manager can approve
    if current_user.role not in ['admin', 'manager']:
        flash('فقط مدیران می‌توانند تراکنش‌ها را تایید کنند', 'danger')
        return redirect(url_for('warehouse.approvals', hotel_id=tx.hotel_id))
    
    try:
        WarehouseService.approve_transaction(tx_id, current_user.id)
        flash('تراکنش تایید شد و موجودی به‌روزرسانی شد', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'خطا: {str(e)}', 'danger')
    
    return redirect(url_for('warehouse.approvals', hotel_id=tx.hotel_id))


@warehouse_bp.route('/approvals/<int:tx_id>/reject', methods=['POST'])
@login_required
def reject_transaction(tx_id):
    """Reject a pending transaction"""
    tx = Transaction.query.get_or_404(tx_id)
    
    # BUG-FIX: Check hotel access before rejecting
    if not user_can_access_hotel(current_user, tx.hotel_id):
        flash('دسترسی غیرمجاز', 'danger')
        return redirect(url_for('warehouse.approvals'))
    
    # BUG #38 FIX: Check permission - only admin/manager can reject
    if current_user.role not in ['admin', 'manager']:
        flash('فقط مدیران می‌توانند تراکنش‌ها را رد کنند', 'danger')
        return redirect(url_for('warehouse.approvals', hotel_id=tx.hotel_id))
    
    try:
        reason = request.form.get('reason', '')
        WarehouseService.reject_transaction(tx_id, current_user.id, reason)
        flash('تراکنش رد شد', 'warning')
    except Exception as e:
        db.session.rollback()
        flash(f'خطا: {str(e)}', 'danger')
    
    return redirect(url_for('warehouse.approvals', hotel_id=tx.hotel_id))


@warehouse_bp.route('/settings', methods=['GET', 'POST'])
@login_required
def settings():
    """Warehouse settings"""
    hotel_id = request.args.get('hotel_id', type=int) or get_user_hotel_id()
    
    if not hotel_id or not user_can_access_hotel(current_user, hotel_id):
        flash('دسترسی غیرمجاز', 'danger')
        return redirect(url_for('dashboard.index'))
    
    if current_user.role not in ['admin', 'manager']:
        flash('فقط مدیران می‌توانند تنظیمات را تغییر دهند', 'danger')
        return redirect(url_for('warehouse.dashboard', hotel_id=hotel_id))
    
    settings = WarehouseSettings.get_or_create(hotel_id)
    
    if request.method == 'POST':
        try:
            settings.waste_approval_threshold = Decimal(request.form.get('waste_approval_threshold', '500000'))
            settings.adjustment_approval_threshold = Decimal(request.form.get('adjustment_approval_threshold', '10'))
            settings.waste_alert_percentage = Decimal(request.form.get('waste_alert_percentage', '5.0'))
            settings.variance_alert_percentage = Decimal(request.form.get('variance_alert_percentage', '1.0'))
            settings.count_frequency_days = int(request.form.get('count_frequency_days', '30'))
            settings.notify_on_low_stock = 'notify_on_low_stock' in request.form
            settings.notify_on_high_waste = 'notify_on_high_waste' in request.form
            settings.notify_on_variance = 'notify_on_variance' in request.form
            
            db.session.commit()
            flash('تنظیمات ذخیره شد', 'success')
            
        except Exception as e:
            db.session.rollback()
            flash(f'خطا در ذخیره تنظیمات: {str(e)}', 'danger')
    
    return render_template('warehouse/settings.html',
                         settings=settings,
                         hotel_id=hotel_id)


@warehouse_bp.route('/alerts')
@login_required
def alerts_list():
    """Active alerts list"""
    hotel_id = request.args.get('hotel_id', type=int) or get_user_hotel_id()
    
    if not hotel_id or not user_can_access_hotel(current_user, hotel_id):
        flash('دسترسی غیرمجاز', 'danger')
        return redirect(url_for('dashboard.index'))
    
    alerts = Alert.query.filter_by(hotel_id=hotel_id).filter(
        Alert.status.in_(['active', 'acknowledged'])
    ).order_by(Alert.created_at.desc()).all()
    
    return render_template('warehouse/alerts.html',
                         alerts=alerts,
                         hotel_id=hotel_id)


@warehouse_bp.route('/alerts/<int:alert_id>/acknowledge', methods=['POST'])
@login_required
def acknowledge_alert(alert_id):
    """Acknowledge an alert"""
    alert = Alert.query.get_or_404(alert_id)
    
    if not user_can_access_hotel(current_user, alert.hotel_id):
        return jsonify({'error': 'Access denied'}), 403
    
    alert.acknowledge(current_user.id)
    db.session.commit()
    
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return jsonify({'success': True})
    
    flash('هشدار مشاهده شد', 'info')
    return redirect(url_for('warehouse.alerts_list', hotel_id=alert.hotel_id))


@warehouse_bp.route('/alerts/<int:alert_id>/resolve', methods=['POST'])
@login_required
def resolve_alert(alert_id):
    """Resolve an alert"""
    alert = Alert.query.get_or_404(alert_id)
    
    if not user_can_access_hotel(current_user, alert.hotel_id):
        return jsonify({'error': 'Access denied'}), 403
    
    alert.resolve()
    db.session.commit()
    
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return jsonify({'success': True})
    
    flash('هشدار حل شد', 'success')
    return redirect(url_for('warehouse.alerts_list', hotel_id=alert.hotel_id))
