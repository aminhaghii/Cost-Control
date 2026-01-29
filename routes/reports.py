from flask import Blueprint, render_template, request
from flask_login import login_required
from services import ParetoService, ABCService
from models import db, Transaction, Item
from sqlalchemy import func
from datetime import date, timedelta
# BUG-FIX #15: Import timezone utility
from utils.timezone import get_iran_today

reports_bp = Blueprint('reports', __name__, url_prefix='/reports')


@reports_bp.route('/executive-summary')
@login_required
def executive_summary():
    """
    خلاصه اجرایی مدیریتی - صفحه ویژه مدیر هتل
    نمایش سریع وضعیت مالی و اقلام حیاتی با پیشنهادات عملی
    """
    days = request.args.get('days', 30, type=int)
    if days <= 0 or days > 365:
        days = 30
    
    pareto_service = ParetoService()
    abc_service = ABCService()
    
    # دریافت داده‌های پارتو برای غذایی و غیرغذایی
    food_stats = pareto_service.get_summary_stats('خرید', 'Food', days)
    nonfood_stats = pareto_service.get_summary_stats('خرید', 'NonFood', days)
    waste_stats = pareto_service.get_summary_stats('ضایعات', 'Food', days)
    
    # دریافت ۵ قلم برتر هر دسته
    food_df = pareto_service.calculate_pareto('خرید', 'Food', days)
    nonfood_df = pareto_service.calculate_pareto('خرید', 'NonFood', days)
    waste_df = pareto_service.calculate_pareto('ضایعات', 'Food', days)
    
    top_food = food_df.head(5).to_dict('records') if not food_df.empty else []
    top_nonfood = nonfood_df.head(5).to_dict('records') if not nonfood_df.empty else []
    top_waste = waste_df.head(5).to_dict('records') if not waste_df.empty else []
    
    # محاسبه کل هزینه‌ها
    total_purchase = food_stats.get('total_amount', 0) + nonfood_stats.get('total_amount', 0)
    total_waste = waste_stats.get('total_amount', 0)
    waste_ratio = (total_waste / total_purchase * 100) if total_purchase > 0 else 0
    
    # محاسبه صرفه‌جویی بالقوه (۱۰% کاهش در اقلام کلاس A)
    potential_savings_food = food_stats.get('class_a_amount', 0) * 0.10
    potential_savings_nonfood = nonfood_stats.get('class_a_amount', 0) * 0.10
    potential_savings = potential_savings_food + potential_savings_nonfood
    
    # BUG-FIX #15: Use Iran timezone instead of UTC
    today = get_iran_today()
    current_start = today - timedelta(days=days)
    previous_start = current_start - timedelta(days=days)
    
    current_total = db.session.query(
        func.coalesce(func.sum(Transaction.total_amount), 0)
    ).filter(
        Transaction.transaction_type == 'خرید',
        Transaction.transaction_date >= current_start
    ).scalar()
    
    previous_total = db.session.query(
        func.coalesce(func.sum(Transaction.total_amount), 0)
    ).filter(
        Transaction.transaction_type == 'خرید',
        Transaction.transaction_date >= previous_start,
        Transaction.transaction_date < current_start
    ).scalar()
    
    change_percentage = ((current_total - previous_total) / previous_total * 100) if previous_total > 0 else 0
    
    # پیشنهادات عملی بر اساس تحلیل
    action_items = []
    
    # پیشنهاد برای اقلام پرهزینه
    if top_food:
        action_items.append({
            'type': 'warning',
            'icon': '',
            'title': f'کنترل ویژه {top_food[0]["item_name"]}',
            'description': f'این قلم {top_food[0]["percentage"]:.1f}% کل هزینه غذایی را تشکیل می‌دهد. مذاکره با تأمین‌کننده برای تخفیف حجمی پیشنهاد می‌شود.',
            'amount': top_food[0]['amount']
        })
    
    # پیشنهاد برای ضایعات
    if waste_ratio > 5:
        action_items.append({
            'type': 'danger',
            'icon': '',
            'title': 'نسبت ضایعات بالا',
            'description': f'ضایعات {waste_ratio:.1f}% از کل خرید است. هدف‌گذاری برای کاهش به زیر ۵% ضروری است.',
            'amount': total_waste
        })
    
    # پیشنهاد صرفه‌جویی
    if potential_savings > 0:
        action_items.append({
            'type': 'success',
            'icon': '',
            'title': 'فرصت صرفه‌جویی',
            'description': f'با ۱۰% کاهش در اقلام کلاس A، ماهانه {potential_savings:,.0f} ریال صرفه‌جویی ممکن است.',
            'amount': potential_savings
        })
    
    # روند هزینه‌ها
    if change_percentage > 10:
        action_items.append({
            'type': 'warning',
            'icon': '',
            'title': 'افزایش هزینه‌ها',
            'description': f'هزینه‌ها نسبت به دوره قبل {change_percentage:.1f}% افزایش یافته. بررسی علل توصیه می‌شود.',
            'amount': current_total - previous_total
        })
    elif change_percentage < -5:
        action_items.append({
            'type': 'success',
            'icon': '',
            'title': 'کاهش هزینه‌ها',
            'description': f'هزینه‌ها نسبت به دوره قبل {abs(change_percentage):.1f}% کاهش یافته. عملکرد خوب!',
            'amount': abs(current_total - previous_total)
        })
    
    # ═══ NEW ANALYTICAL KPIs FOR MANAGERS ═══
    
    # 1. Average Daily Spend
    avg_daily_spend = total_purchase / days if days > 0 else 0
    
    # 2. Transaction Count & Average
    trans_count = db.session.query(func.count(Transaction.id)).filter(
        Transaction.transaction_type == 'خرید',
        Transaction.transaction_date >= current_start
    ).scalar() or 0
    avg_transaction = total_purchase / trans_count if trans_count > 0 else 0
    
    # 3. Consumption Stats
    total_consumption = db.session.query(
        func.coalesce(func.sum(Transaction.total_amount), 0)
    ).filter(
        Transaction.transaction_type == 'مصرف',
        Transaction.transaction_date >= current_start
    ).scalar() or 0
    
    # 4. Inventory Turnover Ratio (Consumption / Avg Inventory)
    total_stock_value = db.session.query(
        func.coalesce(func.sum(Item.current_stock * Item.unit_price), 0)
    ).filter(Item.is_active == True).scalar() or 0
    
    # Convert to float for calculations
    total_consumption = float(total_consumption)
    total_stock_value = float(total_stock_value)
    
    inventory_turnover = (total_consumption / total_stock_value * (365/days)) if total_stock_value > 0 else 0
    
    # 5. Stock Coverage Days (How many days current stock will last)
    avg_daily_consumption = total_consumption / days if days > 0 else 0
    stock_coverage_days = total_stock_value / avg_daily_consumption if avg_daily_consumption > 0 else 0
    
    # 6. Efficiency Score (lower waste = higher efficiency)
    efficiency_score = 100 - waste_ratio if waste_ratio <= 100 else 0
    
    # 7. Critical Items Count
    critical_items_count = Item.query.filter(
        Item.is_active == True,
        Item.current_stock < Item.min_stock
    ).count()
    
    # 8. Items by ABC Class
    total_items = Item.query.filter(Item.is_active == True).count()
    
    # Bundle all KPIs
    kpis = {
        'avg_daily_spend': avg_daily_spend,
        'trans_count': trans_count,
        'avg_transaction': avg_transaction,
        'total_consumption': total_consumption,
        'inventory_turnover': inventory_turnover,
        'stock_coverage_days': stock_coverage_days,
        'efficiency_score': efficiency_score,
        'critical_items_count': critical_items_count,
        'total_stock_value': total_stock_value,
        'total_items': total_items
    }
    
    return render_template('reports/executive_summary.html',
                         days=days,
                         food_stats=food_stats,
                         nonfood_stats=nonfood_stats,
                         waste_stats=waste_stats,
                         top_food=top_food,
                         top_nonfood=top_nonfood,
                         top_waste=top_waste,
                         total_purchase=total_purchase,
                         total_waste=total_waste,
                         waste_ratio=waste_ratio,
                         potential_savings=potential_savings,
                         change_percentage=change_percentage,
                         action_items=action_items,
                         kpis=kpis)

@reports_bp.route('/pareto')
@login_required
def pareto():
    mode = request.args.get('mode', 'خرید')
    category = request.args.get('category', 'Food')
    days = request.args.get('days', 30, type=int)
    page = request.args.get('page', 1, type=int)
    per_page = 50
    
    # Bug #11: Validate days parameter
    if days <= 0 or days > 365:
        days = 30
    
    pareto_service = ParetoService()
    
    df = pareto_service.calculate_pareto(mode, category, days)
    chart_data = pareto_service.get_chart_data(mode, category, days, limit=15)
    stats = pareto_service.get_summary_stats(mode, category, days)
    
    pareto_data = df.to_dict('records') if not df.empty else []
    
    # Pagination
    total_items = len(pareto_data)
    total_pages = (total_items + per_page - 1) // per_page
    start_idx = (page - 1) * per_page
    end_idx = start_idx + per_page
    pareto_page = pareto_data[start_idx:end_idx]
    
    return render_template('reports/pareto.html',
                         pareto_data=pareto_page,
                         chart_data=chart_data,
                         stats=stats,
                         total_items=total_items,
                         page=page,
                         total_pages=total_pages,
                         mode=mode,
                         category=category,
                         days=days)

@reports_bp.route('/abc')
@login_required
def abc():
    mode = request.args.get('mode', 'خرید')
    category = request.args.get('category', 'Food')
    days = request.args.get('days', 30, type=int)
    page = request.args.get('page', 1, type=int)
    per_page = 50
    
    # Bug #11: Validate days parameter
    if days <= 0 or days > 365:
        days = 30
    
    abc_service = ABCService()
    pareto_service = ParetoService()
    
    classified = abc_service.get_abc_classification(mode, category, days)
    stats = pareto_service.get_summary_stats(mode, category, days)
    
    # Pagination for each class
    for abc_class in ['A', 'B', 'C']:
        items = classified.get(abc_class, [])
        total = len(items)
        total_pages = (total + per_page - 1) // per_page
        start = (page - 1) * per_page
        end = start + per_page
        classified[f'{abc_class}_page'] = items[start:end]
        classified[f'{abc_class}_total'] = total
        classified[f'{abc_class}_pages'] = total_pages
    
    recommendations = {
        'A': abc_service.get_recommendations('A'),
        'B': abc_service.get_recommendations('B'),
        'C': abc_service.get_recommendations('C')
    }
    
    return render_template('reports/abc.html',
                         classified=classified,
                         recommendations=recommendations,
                         stats=stats,
                         page=page,
                         per_page=per_page,
                         mode=mode,
                         category=category,
                         days=days)
