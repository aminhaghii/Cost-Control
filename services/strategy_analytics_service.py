"""
Strategy Analytics Service
All 12 strategic analyses based on purchase transaction data.
Each method returns a dict with 'data', 'summary', and 'chart' keys.
"""
import logging
import numpy as np
import pandas as pd
from datetime import date, timedelta
from decimal import Decimal, ROUND_HALF_UP
from sqlalchemy import func, extract
from models import db, Transaction, Item
from services.pareto_service import ParetoService

logger = logging.getLogger(__name__)


def _base_purchase_query(days=90, category=None):
    """Return base query for purchase transactions within date range."""
    start_date = date.today() - timedelta(days=days)
    q = db.session.query(Transaction).join(Item).filter(
        Transaction.transaction_type == 'خرید',
        Transaction.is_deleted != True,
        Transaction.is_opening_balance != True,
        Transaction.transaction_date >= start_date,
    )
    if category and category != 'all':
        q = q.filter(Transaction.category == category)
    return q, start_date


def _base_purchase_df(days=90, category=None):
    """Load purchase transactions into a DataFrame."""
    q, start_date = _base_purchase_query(days, category)
    rows = q.with_entities(
        Item.id.label('item_id'),
        Item.item_code,
        Item.item_name_fa,
        Item.category,
        Item.unit,
        Transaction.quantity,
        Transaction.unit_price,
        Transaction.total_amount,
        Transaction.transaction_date,
    ).all()
    if not rows:
        return pd.DataFrame()
    df = pd.DataFrame([dict(r._mapping) for r in rows])
    df['total_amount'] = df['total_amount'].astype(float)
    df['unit_price'] = df['unit_price'].astype(float)
    df['quantity'] = df['quantity'].astype(float)
    df['transaction_date'] = pd.to_datetime(df['transaction_date'])
    return df


# ──────────────────────────────────────────────
# 1. ABC Analysis (delegates to ParetoService)
# ──────────────────────────────────────────────
def analyse_abc(days=90, category='Food'):
    ps = ParetoService()
    df = ps.calculate_pareto(mode='خرید', category=category, days=days, use_cache=False)
    summary = ps.get_summary_stats(mode='خرید', category=category, days=days)
    chart = ps.get_chart_data(mode='خرید', category=category, days=days, limit=15)
    return {'data': df, 'summary': summary, 'chart': chart}


# ──────────────────────────────────────────────
# 2. XYZ Analysis (purchase volatility)
# ──────────────────────────────────────────────
def analyse_xyz(days=90, category=None):
    df = _base_purchase_df(days, category)
    if df.empty:
        return {'data': pd.DataFrame(), 'summary': {}, 'chart': {}}

    # Group by item + month
    df['month'] = df['transaction_date'].dt.to_period('M').astype(str)
    monthly = df.groupby(['item_id', 'item_code', 'item_name_fa', 'month']).agg(
        amount=('total_amount', 'sum')
    ).reset_index()

    stats = monthly.groupby(['item_id', 'item_code', 'item_name_fa']).agg(
        mean_amount=('amount', 'mean'),
        std_amount=('amount', 'std'),
        months_active=('month', 'nunique'),
    ).reset_index()
    stats['std_amount'] = stats['std_amount'].fillna(0)
    stats['cv'] = np.where(stats['mean_amount'] > 0,
                           stats['std_amount'] / stats['mean_amount'], 0)

    def _xyz_class(cv):
        if cv < 0.5:
            return 'X'
        elif cv < 1.0:
            return 'Y'
        return 'Z'

    stats['xyz_class'] = stats['cv'].apply(_xyz_class)
    stats = stats.sort_values('cv')
    stats['cv'] = stats['cv'].round(3)
    stats['mean_amount'] = stats['mean_amount'].round(0)

    summary = {
        'x_count': int((stats['xyz_class'] == 'X').sum()),
        'y_count': int((stats['xyz_class'] == 'Y').sum()),
        'z_count': int((stats['xyz_class'] == 'Z').sum()),
        'total_items': len(stats),
    }
    chart = {
        'labels': stats['item_name_fa'].tolist()[:20],
        'cv_values': stats['cv'].tolist()[:20],
        'classes': stats['xyz_class'].tolist()[:20],
    }
    return {'data': stats, 'summary': summary, 'chart': chart}


# ──────────────────────────────────────────────
# 3. ABC-XYZ Matrix
# ──────────────────────────────────────────────
def analyse_abc_xyz(days=90, category='Food'):
    abc_result = analyse_abc(days, category)
    xyz_result = analyse_xyz(days, category)
    abc_df = abc_result['data']
    xyz_df = xyz_result['data']
    if abc_df.empty or xyz_df.empty:
        return {'data': pd.DataFrame(), 'summary': {}, 'chart': {}, 'matrix': {}}

    merged = abc_df.merge(
        xyz_df[['item_code', 'xyz_class', 'cv']],
        on='item_code', how='left'
    )
    merged['xyz_class'] = merged['xyz_class'].fillna('Z')
    merged['cv'] = merged['cv'].fillna(0)
    merged['matrix_class'] = merged['abc_class'] + merged['xyz_class']

    # Build matrix counts
    matrix = {}
    for a in ['A', 'B', 'C']:
        for x in ['X', 'Y', 'Z']:
            key = f'{a}{x}'
            subset = merged[merged['matrix_class'] == key]
            matrix[key] = {
                'count': len(subset),
                'amount': float(subset['amount'].sum()) if not subset.empty else 0,
            }

    summary = {
        'total_items': len(merged),
        'top_class': merged['matrix_class'].value_counts().idxmax() if not merged.empty else '-',
        'ax_count': matrix.get('AX', {}).get('count', 0),
        'cz_count': matrix.get('CZ', {}).get('count', 0),
    }
    chart = {
        'classes': list(matrix.keys()),
        'counts': [v['count'] for v in matrix.values()],
        'amounts': [round(v['amount']) for v in matrix.values()],
    }
    return {'data': merged, 'summary': summary, 'chart': chart, 'matrix': matrix}


# ──────────────────────────────────────────────
# 4. Price Trend / Inflation
# ──────────────────────────────────────────────
def analyse_price_trend(days=90, category=None, top_n=10):
    df = _base_purchase_df(days, category)
    if df.empty:
        return {'data': pd.DataFrame(), 'summary': {}, 'chart': {}, 'items': []}

    # Top N items by total spend
    top_items = df.groupby('item_id')['total_amount'].sum().nlargest(top_n).index.tolist()
    df_top = df[df['item_id'].isin(top_items)].copy()

    df_top['week'] = df_top['transaction_date'].dt.isocalendar().week.astype(int)
    df_top['year_week'] = df_top['transaction_date'].dt.strftime('%Y-W%W')

    weekly_price = df_top.groupby(['item_code', 'item_name_fa', 'year_week']).agg(
        avg_price=('unit_price', 'mean'),
        total_qty=('quantity', 'sum'),
    ).reset_index().sort_values(['item_code', 'year_week'])

    # Price change per item (first vs last period)
    price_changes = []
    for item_code, grp in weekly_price.groupby('item_code'):
        if len(grp) < 2:
            continue
        first_price = grp.iloc[0]['avg_price']
        last_price = grp.iloc[-1]['avg_price']
        change_pct = ((last_price - first_price) / first_price * 100) if first_price > 0 else 0
        price_changes.append({
            'item_code': item_code,
            'item_name': grp.iloc[0]['item_name_fa'],
            'first_price': round(first_price),
            'last_price': round(last_price),
            'change_pct': round(change_pct, 1),
        })

    price_changes_df = pd.DataFrame(price_changes).sort_values('change_pct', ascending=False) if price_changes else pd.DataFrame()

    # Build chart data: one series per item
    items_chart = []
    for item_code, grp in weekly_price.groupby('item_code'):
        items_chart.append({
            'name': grp.iloc[0]['item_name_fa'],
            'weeks': grp['year_week'].tolist(),
            'prices': [round(p) for p in grp['avg_price'].tolist()],
        })

    avg_inflation = float(price_changes_df['change_pct'].mean()) if not price_changes_df.empty else 0
    summary = {
        'avg_inflation': round(avg_inflation, 1),
        'max_increase_item': price_changes_df.iloc[0]['item_name'] if not price_changes_df.empty else '-',
        'max_increase_pct': float(price_changes_df.iloc[0]['change_pct']) if not price_changes_df.empty else 0,
        'items_with_increase': int((price_changes_df['change_pct'] > 0).sum()) if not price_changes_df.empty else 0,
        'items_with_decrease': int((price_changes_df['change_pct'] < 0).sum()) if not price_changes_df.empty else 0,
    }
    return {'data': price_changes_df, 'summary': summary, 'chart': {}, 'items_chart': items_chart}


# ──────────────────────────────────────────────
# 5. Price Volatility per Item
# ──────────────────────────────────────────────
def analyse_price_volatility(days=90, category=None):
    df = _base_purchase_df(days, category)
    if df.empty:
        return {'data': pd.DataFrame(), 'summary': {}, 'chart': {}}

    stats = df.groupby(['item_id', 'item_code', 'item_name_fa']).agg(
        mean_price=('unit_price', 'mean'),
        std_price=('unit_price', 'std'),
        min_price=('unit_price', 'min'),
        max_price=('unit_price', 'max'),
        purchase_count=('unit_price', 'count'),
    ).reset_index()
    stats['std_price'] = stats['std_price'].fillna(0)
    stats['price_cv'] = np.where(stats['mean_price'] > 0,
                                  stats['std_price'] / stats['mean_price'], 0)
    stats['price_range'] = stats['max_price'] - stats['min_price']
    stats = stats.sort_values('price_cv', ascending=False)
    stats = stats.round({'mean_price': 0, 'std_price': 0, 'price_cv': 3, 'min_price': 0, 'max_price': 0, 'price_range': 0})

    summary = {
        'most_volatile': stats.iloc[0]['item_name_fa'] if not stats.empty else '-',
        'most_volatile_cv': float(stats.iloc[0]['price_cv']) if not stats.empty else 0,
        'most_stable': stats.iloc[-1]['item_name_fa'] if not stats.empty else '-',
        'avg_cv': round(float(stats['price_cv'].mean()), 3) if not stats.empty else 0,
        'high_risk_count': int((stats['price_cv'] > 0.3).sum()),
    }
    chart = {
        'labels': stats['item_name_fa'].tolist()[:20],
        'cv_values': stats['price_cv'].tolist()[:20],
        'ranges': stats['price_range'].tolist()[:20],
    }
    return {'data': stats, 'summary': summary, 'chart': chart}


# ──────────────────────────────────────────────
# 6. Spend Trend (weekly / monthly)
# ──────────────────────────────────────────────
def analyse_spend_trend(days=90, category=None, period='weekly'):
    df = _base_purchase_df(days, category)
    if df.empty:
        return {'data': pd.DataFrame(), 'summary': {}, 'chart': {}}

    if period == 'monthly':
        df['period'] = df['transaction_date'].dt.to_period('M').astype(str)
    else:
        df['period'] = df['transaction_date'].dt.strftime('%Y-W%W')

    trend = df.groupby('period').agg(
        total_amount=('total_amount', 'sum'),
        tx_count=('total_amount', 'count'),
        avg_basket=('total_amount', 'mean'),
    ).reset_index().sort_values('period')
    trend = trend.round({'total_amount': 0, 'avg_basket': 0})

    # Category breakdown
    cat_trend = df.groupby(['period', 'category']).agg(
        amount=('total_amount', 'sum')
    ).reset_index().sort_values('period')

    avg_spend = float(trend['total_amount'].mean()) if not trend.empty else 0
    max_spend_period = trend.loc[trend['total_amount'].idxmax(), 'period'] if not trend.empty else '-'
    summary = {
        'avg_spend': round(avg_spend),
        'max_spend_period': max_spend_period,
        'max_spend': round(float(trend['total_amount'].max())) if not trend.empty else 0,
        'total_spend': round(float(trend['total_amount'].sum())) if not trend.empty else 0,
        'periods_count': len(trend),
        'trend_direction': 'up' if len(trend) >= 2 and trend.iloc[-1]['total_amount'] > trend.iloc[0]['total_amount'] else 'down',
    }
    chart = {
        'labels': trend['period'].tolist(),
        'amounts': trend['total_amount'].tolist(),
        'counts': trend['tx_count'].tolist(),
    }
    return {'data': trend, 'summary': summary, 'chart': chart, 'category_trend': cat_trend}


# ──────────────────────────────────────────────
# 7. Category Mix Analysis
# ──────────────────────────────────────────────
def analyse_category_mix(days=90):
    df = _base_purchase_df(days, category=None)
    if df.empty:
        return {'data': pd.DataFrame(), 'summary': {}, 'chart': {}}

    mix = df.groupby('category').agg(
        total_amount=('total_amount', 'sum'),
        tx_count=('total_amount', 'count'),
        item_count=('item_id', 'nunique'),
        avg_price=('unit_price', 'mean'),
    ).reset_index()
    grand_total = mix['total_amount'].sum()
    mix['share_pct'] = (mix['total_amount'] / grand_total * 100).round(1) if grand_total > 0 else 0
    mix = mix.sort_values('total_amount', ascending=False)
    mix = mix.round({'total_amount': 0, 'avg_price': 0})

    summary = {
        'categories': len(mix),
        'dominant_category': mix.iloc[0]['category'] if not mix.empty else '-',
        'dominant_share': float(mix.iloc[0]['share_pct']) if not mix.empty else 0,
        'grand_total': round(float(grand_total)),
    }
    chart = {
        'labels': mix['category'].tolist(),
        'amounts': mix['total_amount'].tolist(),
        'shares': mix['share_pct'].tolist(),
    }
    return {'data': mix, 'summary': summary, 'chart': chart}


# ──────────────────────────────────────────────
# 8. Purchase Frequency / Reorder Rhythm
# ──────────────────────────────────────────────
def analyse_purchase_frequency(days=90, category=None):
    df = _base_purchase_df(days, category)
    if df.empty:
        return {'data': pd.DataFrame(), 'summary': {}, 'chart': {}}

    freq = df.groupby(['item_id', 'item_code', 'item_name_fa']).agg(
        purchase_count=('transaction_date', 'count'),
        first_purchase=('transaction_date', 'min'),
        last_purchase=('transaction_date', 'max'),
        total_amount=('total_amount', 'sum'),
    ).reset_index()

    freq['days_span'] = (freq['last_purchase'] - freq['first_purchase']).dt.days
    freq['avg_interval_days'] = np.where(
        freq['purchase_count'] > 1,
        freq['days_span'] / (freq['purchase_count'] - 1),
        days  # single purchase – assume full period
    )
    freq = freq.sort_values('purchase_count', ascending=False)
    freq = freq.round({'avg_interval_days': 1, 'total_amount': 0})

    def _freq_class(count, total_days=days):
        monthly_rate = count / (total_days / 30)
        if monthly_rate >= 4:
            return 'بسیار مکرر'
        elif monthly_rate >= 2:
            return 'مکرر'
        elif monthly_rate >= 1:
            return 'متوسط'
        return 'کم‌تکرار'

    freq['freq_class'] = freq['purchase_count'].apply(_freq_class)

    summary = {
        'most_frequent': freq.iloc[0]['item_name_fa'] if not freq.empty else '-',
        'most_frequent_count': int(freq.iloc[0]['purchase_count']) if not freq.empty else 0,
        'avg_interval': round(float(freq['avg_interval_days'].mean()), 1) if not freq.empty else 0,
        'single_purchase_items': int((freq['purchase_count'] == 1).sum()),
        'total_items': len(freq),
    }
    chart = {
        'labels': freq['item_name_fa'].tolist()[:20],
        'counts': freq['purchase_count'].tolist()[:20],
        'intervals': freq['avg_interval_days'].tolist()[:20],
    }
    return {'data': freq, 'summary': summary, 'chart': chart}


# ──────────────────────────────────────────────
# 9. Demand Proxy from Purchases
# ──────────────────────────────────────────────
def analyse_demand_proxy(days=90, category=None, top_n=10):
    df = _base_purchase_df(days, category)
    if df.empty:
        return {'data': pd.DataFrame(), 'summary': {}, 'chart': {}, 'items': []}

    top_items = df.groupby('item_id')['quantity'].sum().nlargest(top_n).index.tolist()
    df_top = df[df['item_id'].isin(top_items)].copy()

    df_top['week'] = df_top['transaction_date'].dt.strftime('%Y-W%W')
    weekly = df_top.groupby(['item_code', 'item_name_fa', 'week']).agg(
        total_qty=('quantity', 'sum'),
        total_amount=('total_amount', 'sum'),
    ).reset_index().sort_values(['item_code', 'week'])

    items_chart = []
    demand_changes = []
    for item_code, grp in weekly.groupby('item_code'):
        items_chart.append({
            'name': grp.iloc[0]['item_name_fa'],
            'weeks': grp['week'].tolist(),
            'quantities': [round(q, 2) for q in grp['total_qty'].tolist()],
        })
        if len(grp) >= 2:
            first_qty = grp.iloc[0]['total_qty']
            last_qty = grp.iloc[-1]['total_qty']
            change = ((last_qty - first_qty) / first_qty * 100) if first_qty > 0 else 0
            demand_changes.append({
                'item_code': item_code,
                'item_name': grp.iloc[0]['item_name_fa'],
                'first_qty': round(first_qty, 2),
                'last_qty': round(last_qty, 2),
                'change_pct': round(change, 1),
            })

    demand_df = pd.DataFrame(demand_changes).sort_values('change_pct', ascending=False) if demand_changes else pd.DataFrame()

    summary = {
        'rising_demand': int((demand_df['change_pct'] > 10).sum()) if not demand_df.empty else 0,
        'falling_demand': int((demand_df['change_pct'] < -10).sum()) if not demand_df.empty else 0,
        'stable_demand': int(((demand_df['change_pct'] >= -10) & (demand_df['change_pct'] <= 10)).sum()) if not demand_df.empty else 0,
    }
    return {'data': demand_df, 'summary': summary, 'chart': {}, 'items_chart': items_chart}


# ──────────────────────────────────────────────
# 10. Anomaly Detection
# ──────────────────────────────────────────────
def analyse_anomalies(days=90, category=None, z_threshold=2.0):
    df = _base_purchase_df(days, category)
    if df.empty:
        return {'data': pd.DataFrame(), 'summary': {}, 'chart': {}}

    # Per-item stats
    item_stats = df.groupby(['item_id', 'item_code', 'item_name_fa']).agg(
        mean_amount=('total_amount', 'mean'),
        std_amount=('total_amount', 'std'),
        mean_qty=('quantity', 'mean'),
        std_qty=('quantity', 'std'),
        mean_price=('unit_price', 'mean'),
        std_price=('unit_price', 'std'),
    ).reset_index()
    item_stats = item_stats.fillna(0)

    # Merge stats back
    df_merged = df.merge(item_stats, on=['item_id', 'item_code', 'item_name_fa'], suffixes=('', '_stat'))

    anomalies = []
    for _, row in df_merged.iterrows():
        reasons = []
        if row['std_amount'] > 0:
            z_amount = abs(row['total_amount'] - row['mean_amount']) / row['std_amount']
            if z_amount >= z_threshold:
                reasons.append(f'مبلغ غیرعادی (Z={z_amount:.1f})')
        if row['std_qty'] > 0:
            z_qty = abs(row['quantity'] - row['mean_qty']) / row['std_qty']
            if z_qty >= z_threshold:
                reasons.append(f'مقدار غیرعادی (Z={z_qty:.1f})')
        if row['std_price'] > 0:
            z_price = abs(row['unit_price'] - row['mean_price']) / row['std_price']
            if z_price >= z_threshold:
                reasons.append(f'قیمت غیرعادی (Z={z_price:.1f})')

        if reasons:
            anomalies.append({
                'item_code': row['item_code'],
                'item_name': row['item_name_fa'],
                'date': row['transaction_date'].strftime('%Y-%m-%d'),
                'quantity': round(row['quantity'], 2),
                'unit_price': round(row['unit_price']),
                'total_amount': round(row['total_amount']),
                'reasons': ' | '.join(reasons),
            })

    anomaly_df = pd.DataFrame(anomalies) if anomalies else pd.DataFrame()
    summary = {
        'total_anomalies': len(anomalies),
        'total_transactions': len(df),
        'anomaly_rate': round(len(anomalies) / len(df) * 100, 1) if len(df) > 0 else 0,
        'unique_items_with_anomaly': len(set(a['item_code'] for a in anomalies)),
    }
    chart = {
        'labels': ['عادی', 'غیرعادی'],
        'counts': [len(df) - len(anomalies), len(anomalies)],
    }
    return {'data': anomaly_df, 'summary': summary, 'chart': chart}


# ──────────────────────────────────────────────
# 11. Cost Forecast (simple moving average)
# ──────────────────────────────────────────────
def analyse_forecast(days=90, category=None, forecast_periods=4):
    df = _base_purchase_df(days, category)
    if df.empty:
        return {'data': pd.DataFrame(), 'summary': {}, 'chart': {}}

    df['week'] = df['transaction_date'].dt.strftime('%Y-W%W')
    weekly = df.groupby('week').agg(
        total_amount=('total_amount', 'sum')
    ).reset_index().sort_values('week')

    if len(weekly) < 3:
        return {'data': weekly, 'summary': {'message': 'داده کافی برای پیش‌بینی وجود ندارد'}, 'chart': {}}

    # Simple Moving Average (window=3)
    window = min(3, len(weekly))
    weekly['sma'] = weekly['total_amount'].rolling(window=window).mean()

    # Linear trend
    x = np.arange(len(weekly))
    y = weekly['total_amount'].values.astype(float)
    coeffs = np.polyfit(x, y, 1)
    slope, intercept = coeffs

    # Forecast
    forecast_weeks = []
    last_sma = float(weekly['sma'].iloc[-1]) if pd.notna(weekly['sma'].iloc[-1]) else float(weekly['total_amount'].iloc[-1])
    for i in range(1, forecast_periods + 1):
        trend_value = slope * (len(weekly) + i) + intercept
        # Blend SMA and trend
        forecast_value = (last_sma + trend_value) / 2
        forecast_weeks.append({
            'week': f'پیش‌بینی {i}',
            'total_amount': round(max(0, forecast_value)),
            'is_forecast': True,
        })

    forecast_df = pd.DataFrame(forecast_weeks)
    historical_for_chart = weekly[['week', 'total_amount']].copy()
    historical_for_chart['is_forecast'] = False

    combined = pd.concat([historical_for_chart, forecast_df], ignore_index=True)

    total_forecast = sum(f['total_amount'] for f in forecast_weeks)
    avg_historical = float(weekly['total_amount'].mean())
    summary = {
        'avg_weekly_spend': round(avg_historical),
        'forecast_total': round(total_forecast),
        'trend': 'صعودی' if slope > 0 else 'نزولی',
        'slope_per_week': round(float(slope)),
        'forecast_periods': forecast_periods,
    }
    chart = {
        'labels': combined['week'].tolist(),
        'amounts': combined['total_amount'].tolist(),
        'is_forecast': combined['is_forecast'].tolist(),
    }
    return {'data': combined, 'summary': summary, 'chart': chart}


# ──────────────────────────────────────────────
# 12. Budget Burn-down
# ──────────────────────────────────────────────
def analyse_budget_burndown(days=30, category=None, budget=None):
    df = _base_purchase_df(days, category)
    if df.empty:
        return {'data': pd.DataFrame(), 'summary': {}, 'chart': {}}

    # If no budget provided, estimate from average monthly spend
    if budget is None or budget <= 0:
        total_spend_period = float(df['total_amount'].sum())
        budget = total_spend_period * 1.1  # 10% headroom

    df_sorted = df.sort_values('transaction_date')
    df_sorted['cumulative_spend'] = df_sorted['total_amount'].cumsum()
    df_sorted['remaining_budget'] = budget - df_sorted['cumulative_spend']
    df_sorted['budget_pct_used'] = (df_sorted['cumulative_spend'] / budget * 100)

    daily = df_sorted.groupby(df_sorted['transaction_date'].dt.strftime('%Y-%m-%d')).agg(
        daily_spend=('total_amount', 'sum'),
        cumulative=('cumulative_spend', 'max'),
    ).reset_index()
    daily['remaining'] = budget - daily['cumulative']
    daily['pct_used'] = (daily['cumulative'] / budget * 100).round(1)

    total_spent = float(df['total_amount'].sum())
    days_elapsed = (date.today() - df_sorted['transaction_date'].dt.date.min()).days or 1
    daily_rate = total_spent / days_elapsed
    days_remaining = max(0, (budget - total_spent) / daily_rate) if daily_rate > 0 else 999

    summary = {
        'budget': round(budget),
        'total_spent': round(total_spent),
        'remaining': round(budget - total_spent),
        'pct_used': round(total_spent / budget * 100, 1) if budget > 0 else 0,
        'daily_burn_rate': round(daily_rate),
        'estimated_days_left': round(days_remaining),
        'on_track': total_spent <= budget,
    }
    chart = {
        'labels': daily['transaction_date'].tolist(),
        'cumulative': daily['cumulative'].tolist(),
        'remaining': daily['remaining'].tolist(),
        'budget_line': [round(budget)] * len(daily),
    }
    return {'data': daily, 'summary': summary, 'chart': chart}


# ──────────────────────────────────────────────
# Hub summary for dashboard cards
# ──────────────────────────────────────────────
def get_strategy_overview(days=90, category='Food'):
    """Quick summary for the strategy hub page."""
    try:
        abc = analyse_abc(days, category)
        xyz = analyse_xyz(days, category)
        spend = analyse_spend_trend(days, category)
        anomaly = analyse_anomalies(days, category)
        return {
            'abc_summary': abc.get('summary', {}),
            'xyz_summary': xyz.get('summary', {}),
            'spend_summary': spend.get('summary', {}),
            'anomaly_summary': anomaly.get('summary', {}),
            'has_data': True,
        }
    except Exception as e:
        logger.error(f'Strategy overview error: {e}')
        return {'has_data': False, 'error': str(e)}
