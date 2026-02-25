"""
Strategy Analytics Routes
Provides a hub page with hamburger menu and individual analysis pages.
"""
from flask import Blueprint, render_template, request
from flask_login import login_required
import logging

logger = logging.getLogger(__name__)

strategy_bp = Blueprint('strategy', __name__, url_prefix='/strategy')


def _get_params():
    """Extract common query parameters."""
    days = request.args.get('days', 90, type=int)
    category = request.args.get('category', 'Food')
    return days, category


@strategy_bp.route('/')
@login_required
def hub():
    from services.strategy_analytics_service import get_strategy_overview
    days, category = _get_params()
    overview = get_strategy_overview(days, category)
    return render_template('strategy/hub.html', overview=overview, days=days, category=category)


@strategy_bp.route('/abc')
@login_required
def abc():
    from services.strategy_analytics_service import analyse_abc
    days, category = _get_params()
    result = analyse_abc(days, category)
    return render_template('strategy/abc.html', result=result, days=days, category=category)


@strategy_bp.route('/xyz')
@login_required
def xyz():
    from services.strategy_analytics_service import analyse_xyz
    days, category = _get_params()
    result = analyse_xyz(days, category)
    return render_template('strategy/xyz.html', result=result, days=days, category=category)


@strategy_bp.route('/abc-xyz')
@login_required
def abc_xyz():
    from services.strategy_analytics_service import analyse_abc_xyz
    days, category = _get_params()
    result = analyse_abc_xyz(days, category)
    return render_template('strategy/abc_xyz.html', result=result, days=days, category=category)


@strategy_bp.route('/price-trend')
@login_required
def price_trend():
    from services.strategy_analytics_service import analyse_price_trend
    days, category = _get_params()
    result = analyse_price_trend(days, category)
    return render_template('strategy/price_trend.html', result=result, days=days, category=category)


@strategy_bp.route('/price-volatility')
@login_required
def price_volatility():
    from services.strategy_analytics_service import analyse_price_volatility
    days, category = _get_params()
    result = analyse_price_volatility(days, category)
    return render_template('strategy/price_volatility.html', result=result, days=days, category=category)


@strategy_bp.route('/spend-trend')
@login_required
def spend_trend():
    from services.strategy_analytics_service import analyse_spend_trend
    days, category = _get_params()
    period = request.args.get('period', 'weekly')
    result = analyse_spend_trend(days, category, period)
    return render_template('strategy/spend_trend.html', result=result, days=days, category=category, period=period)


@strategy_bp.route('/category-mix')
@login_required
def category_mix():
    from services.strategy_analytics_service import analyse_category_mix
    days = request.args.get('days', 90, type=int)
    result = analyse_category_mix(days)
    return render_template('strategy/category_mix.html', result=result, days=days)


@strategy_bp.route('/purchase-frequency')
@login_required
def purchase_frequency():
    from services.strategy_analytics_service import analyse_purchase_frequency
    days, category = _get_params()
    result = analyse_purchase_frequency(days, category)
    return render_template('strategy/purchase_frequency.html', result=result, days=days, category=category)


@strategy_bp.route('/demand-proxy')
@login_required
def demand_proxy():
    from services.strategy_analytics_service import analyse_demand_proxy
    days, category = _get_params()
    result = analyse_demand_proxy(days, category)
    return render_template('strategy/demand_proxy.html', result=result, days=days, category=category)


@strategy_bp.route('/anomalies')
@login_required
def anomalies():
    from services.strategy_analytics_service import analyse_anomalies
    days, category = _get_params()
    result = analyse_anomalies(days, category)
    return render_template('strategy/anomalies.html', result=result, days=days, category=category)


@strategy_bp.route('/forecast')
@login_required
def forecast():
    from services.strategy_analytics_service import analyse_forecast
    days, category = _get_params()
    result = analyse_forecast(days, category)
    return render_template('strategy/forecast.html', result=result, days=days, category=category)


@strategy_bp.route('/history')
@login_required
def history():
    from services.strategy_analytics_service import get_kpi_history
    granularity = request.args.get('granularity', 'monthly')
    category = request.args.get('category', 'Food')
    if granularity not in ('monthly', 'quarterly', 'semi_annual', 'annual'):
        granularity = 'monthly'
    data = get_kpi_history(granularity, category)
    return render_template('strategy/history.html', data=data, granularity=granularity, category=category)


@strategy_bp.route('/budget-burndown')
@login_required
def budget_burndown():
    from services.strategy_analytics_service import analyse_budget_burndown
    days = request.args.get('days', 30, type=int)
    category = request.args.get('category', None)
    budget = request.args.get('budget', 0, type=float)
    result = analyse_budget_burndown(days, category, budget if budget > 0 else None)
    return render_template('strategy/budget_burndown.html', result=result, days=days, category=category, budget=budget)
