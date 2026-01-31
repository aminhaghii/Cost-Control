from flask import Blueprint, render_template
from flask_login import login_required, current_user
from models import db, Transaction, Item, Alert
from sqlalchemy import func
from datetime import date, timedelta
from services import ParetoService
from services.hotel_scope_service import get_allowed_hotel_ids
from utils.timezone import get_iran_today

dashboard_bp = Blueprint('dashboard', __name__, url_prefix='/')

@dashboard_bp.route('/')
@login_required
def index():
    today = get_iran_today()
    
    # BUG-FIX: Get allowed hotel IDs for scoping
    allowed_hotel_ids = get_allowed_hotel_ids(current_user)
    
    # Base query filter for non-deleted transactions
    def apply_scope(query):
        query = query.filter(Transaction.is_deleted != True)
        if allowed_hotel_ids is not None:  # None means admin (all hotels)
            query = query.filter(Transaction.hotel_id.in_(allowed_hotel_ids))
        return query
    
    today_transactions = apply_scope(
        Transaction.query.filter(func.date(Transaction.transaction_date) == today)
    ).count()
    
    today_purchase = apply_scope(
        db.session.query(func.coalesce(func.sum(Transaction.total_amount), 0)).filter(
            Transaction.transaction_type == 'خرید',
            func.date(Transaction.transaction_date) == today
        )
    ).scalar()
    
    today_waste = apply_scope(
        db.session.query(func.coalesce(func.sum(Transaction.total_amount), 0)).filter(
            Transaction.transaction_type == 'ضایعات',
            func.date(Transaction.transaction_date) == today
        )
    ).scalar()
    
    today_consumption = apply_scope(
        db.session.query(func.coalesce(func.sum(Transaction.total_amount), 0)).filter(
            Transaction.transaction_type == 'مصرف',
            func.date(Transaction.transaction_date) == today
        )
    ).scalar()
    
    # SINGLE HOTEL MODE: Count all active items (no hotel filtering)
    total_items = Item.query.filter_by(is_active=True).count()
    
    # SINGLE HOTEL MODE: Get all unresolved alerts (no hotel filtering)
    alerts = Alert.query.filter_by(is_resolved=False).order_by(Alert.created_at.desc()).limit(5).all()
    
    pareto_service = ParetoService()
    chart_data_food = pareto_service.get_chart_data(mode='خرید', category='Food', days=30, limit=10)
    chart_data_nonfood = pareto_service.get_chart_data(mode='خرید', category='NonFood', days=30, limit=10)
    
    last_7_days = []
    for i in range(6, -1, -1):
        day = today - timedelta(days=i)
        daily_query = db.session.query(
            func.coalesce(func.sum(Transaction.total_amount), 0)
        ).filter(
            Transaction.transaction_type == 'خرید',
            Transaction.is_deleted != True,
            func.date(Transaction.transaction_date) == day
        )
        if allowed_hotel_ids is not None:
            daily_query = daily_query.filter(Transaction.hotel_id.in_(allowed_hotel_ids))
        daily_total = daily_query.scalar()
        last_7_days.append({
            'date': day.strftime('%m/%d'),
            'amount': float(daily_total)
        })
    
    # BUG-FIX: Apply hotel scope and is_deleted filter to recent transactions
    recent_query = Transaction.query.filter(Transaction.is_deleted != True)
    if allowed_hotel_ids is not None:
        recent_query = recent_query.filter(Transaction.hotel_id.in_(allowed_hotel_ids))
    recent_transactions = recent_query.order_by(Transaction.created_at.desc()).limit(10).all()
    
    return render_template('dashboard/index.html',
                         today=today.isoformat(),  # UX #3: For KPI card links
                         today_transactions=today_transactions,
                         today_purchase=today_purchase,
                         today_waste=today_waste,
                         today_consumption=today_consumption,
                         total_items=total_items,
                         alerts=alerts,
                         chart_data_food=chart_data_food,
                         chart_data_nonfood=chart_data_nonfood,
                         last_7_days=last_7_days,
                         recent_transactions=recent_transactions)
