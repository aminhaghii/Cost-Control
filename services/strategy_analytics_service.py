"""
Strategy Analytics Service
Refactored analyses with data quality checks, alert levels,
consumption-based demand metrics, and formatted summaries.
"""
import logging
from datetime import date, timedelta

import numpy as np
import pandas as pd

from models import db, Transaction, Item
from services.pareto_service import ParetoService
from services.strategy_validation import StrategyDataValidator
from utils.currency import standardize_summary_amounts

logger = logging.getLogger(__name__)


def _base_purchase_query(days=90, category=None):
    """Return base query for purchase transactions within date range."""
    start_date = date.today() - timedelta(days=days)
    q = db.session.query(Transaction).join(Item).filter(
        Transaction.transaction_type == 'خرید',
        Transaction.is_deleted != True,
        Transaction.is_opening_balance != True,
        Transaction.unit_price > 0,
        Transaction.source != 'opening_import',
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


def _base_consumption_query(days=90, category=None):
    """Return base query for consumption transactions within date range."""
    start_date = date.today() - timedelta(days=days)
    q = db.session.query(Transaction).join(Item).filter(
        Transaction.transaction_type == 'مصرف',
        Transaction.is_deleted != True,
        Transaction.is_opening_balance != True,
        Transaction.source != 'opening_import',
        Transaction.transaction_date >= start_date,
    )
    if category and category != 'all':
        q = q.filter(Item.category == category)
    return q, start_date


def _base_consumption_df(days=90, category=None):
    """Load consumption transactions into a DataFrame."""
    q, start_date = _base_consumption_query(days, category)
    rows = q.with_entities(
        Item.id.label('item_id'),
        Item.item_code,
        Item.item_name_fa,
        Item.category,
        Item.unit,
        Transaction.quantity,
        Transaction.transaction_date,
    ).all()
    if not rows:
        return pd.DataFrame()
    df = pd.DataFrame([dict(r._mapping) for r in rows])
    df['quantity'] = df['quantity'].astype(float)
    df['transaction_date'] = pd.to_datetime(df['transaction_date'])
    return df


def _add_alert_level(summary, thresholds):
    """Add alert_level and actions to summary based on threshold rules."""
    summary['alert_level'] = 'green'
    summary['actions'] = summary.get('actions', [])

    for level in ['yellow', 'red']:
        for condition in thresholds.get(level, []):
            metric = condition.get('metric')
            operator = condition.get('operator')
            threshold = condition.get('threshold')
            action = condition.get('action')
            value = summary.get(metric)
            if value is None:
                continue

            triggered = False
            if operator == '>':
                triggered = value > threshold
            elif operator == '<':
                triggered = value < threshold
            elif operator == '>=':
                triggered = value >= threshold
            elif operator == '<=':
                triggered = value <= threshold

            if triggered:
                if level == 'red' or (level == 'yellow' and summary['alert_level'] != 'red'):
                    summary['alert_level'] = level
                summary['actions'].append(
                    {
                        'metric': metric,
                        'value': value,
                        'threshold': threshold,
                        'action': action,
                    }
                )

    return summary


def _get_matrix_recommendation(matrix_class):
    """Strategic playbook per ABC-XYZ cell."""
    playbook = {
        'AX': 'قرارداد بلندمدت + سفارش منظم + کنترل قیمت دقیق + موجودی متوسط',
        'AY': 'ذخیره ایمنی متوسط + مذاکره قیمت فصلی + بررسی ماهانه',
        'AZ': 'چند تامین کننده + سقف قیمت + موجودی ایمنی بالا + مذاکره ویژه',
        'BX': 'سفارش دوره‌ای (دو هفته‌ای) + قرارداد کوتاه‌مدت',
        'BY': 'موجودی buffer + بررسی فصلی',
        'BZ': 'سفارش مبتنی بر نیاز + تامین کننده پشتیبان',
        'CX': 'ساده‌سازی + خرید دسته‌جمعی با سایر اقلام',
        'CY': 'کنترل سبک + بررسی سالانه',
        'CZ': 'بررسی حذف از منو یا جایگزین با قلم استاندارد',
    }
    return playbook.get(matrix_class, '-')


def _calculate_reorder_interval(avg_interval, freq_class):
    """Suggest reorder interval based on purchase pattern."""
    safe_interval = max(1, int(round(avg_interval)))
    if freq_class == 'بسیار مکرر':
        return f'{safe_interval} روز (سفارش خودکار)'
    if freq_class == 'مکرر':
        return f'{max(1, int(round(avg_interval * 1.2)))} روز (بررسی هفتگی)'
    if freq_class == 'متوسط':
        return f'{max(1, int(round(avg_interval * 1.5)))} روز (بررسی دو هفتگی)'
    return 'مبتنی بر نیاز (بررسی ماهانه)'


# ──────────────────────────────────────────────
# 1. ABC Analysis (delegates to ParetoService)
# ──────────────────────────────────────────────
def analyse_abc(days=90, category='Food'):
    """ABC classification on purchase value."""
    ps = ParetoService()
    df = ps.calculate_pareto(mode='خرید', category=category, days=days, use_cache=False)
    summary = ps.get_summary_stats(mode='خرید', category=category, days=days)
    chart = ps.get_chart_data(mode='خرید', category=category, days=days, limit=15)
    summary = standardize_summary_amounts(summary, keys=['total_amount'])
    return {'data': df, 'summary': summary, 'chart': chart}


def analyse_abc_with_criticality(days=90, category='Food'):
    """ABC with criticality overlay to flag low-value but operationally critical items."""
    abc_result = analyse_abc(days, category)
    abc_df = abc_result.get('data', pd.DataFrame())

    if abc_df.empty:
        return abc_result

    critical_items = {
        # e.g. 'F1020': 'نمک', 'F1021': 'خمیرمایه'
    }

    abc_df = abc_df.copy()
    abc_df['is_critical'] = abc_df['item_code'].isin(critical_items.keys())
    abc_df['alert'] = abc_df.apply(
        lambda row: 'کم‌ارزش اما حیاتی' if row.get('abc_class') == 'C' and row.get('is_critical') else '',
        axis=1,
    )

    critical_c_items = abc_df[(abc_df['abc_class'] == 'C') & (abc_df['is_critical'])]
    abc_result['data'] = abc_df
    abc_result['summary']['critical_c_count'] = int(len(critical_c_items))
    abc_result['critical_c_items'] = (
        critical_c_items[['item_name', 'amount', 'percentage']].to_dict('records')
        if not critical_c_items.empty
        else []
    )

    if not critical_c_items.empty:
        abc_result['summary']['actions'] = [
            {
                'type': 'critical_c_items',
                'items': critical_c_items['item_name'].tolist(),
                'action': 'این اقلام ارزش ریالی کم دارند اما حیاتی هستند - موجودی ایمنی حفظ شود',
            }
        ]

    return abc_result


# ──────────────────────────────────────────────
# 2. XYZ Analysis (consumption volatility)
# ──────────────────────────────────────────────
def analyse_xyz(days=90, category=None):
    """
    XYZ analysis based on daily CONSUMPTION volatility (not purchase).
    X = cv < 0.5, Y = 0.5 <= cv < 1.0, Z = cv >= 1.0.
    """
    df = _base_consumption_df(days, category)
    min_days = 14
    if df.empty:
        return {
            'data': pd.DataFrame(),
            'summary': {
                'x_count': 0,
                'y_count': 0,
                'z_count': 0,
                'total_items': 0,
                'message': 'داده مصرف کافی وجود ندارد',
                'min_days_threshold': min_days,
            },
            'chart': {},
            'warnings': ['تراکنش مصرفی برای تحلیل XYZ یافت نشد'],
        }

    df['day'] = df['transaction_date'].dt.date
    daily = df.groupby(['item_id', 'item_code', 'item_name_fa', 'day']).agg(
        daily_consumption=('quantity', 'sum')
    ).reset_index()

    start_date = date.today() - timedelta(days=days)
    end_date = date.today()
    all_dates = pd.date_range(start=start_date, end=end_date).date

    items_info = df[['item_id', 'item_code', 'item_name_fa']].drop_duplicates().copy()
    items_info['key'] = 1
    date_df = pd.DataFrame({'day': all_dates, 'key': 1})
    grid = pd.merge(items_info, date_df, on='key').drop('key', axis=1)

    daily_full = pd.merge(grid, daily, on=['item_id', 'item_code', 'item_name_fa', 'day'], how='left')
    daily_full['daily_consumption'] = daily_full['daily_consumption'].fillna(0)

    stats = daily_full.groupby(['item_id', 'item_code', 'item_name_fa']).agg(
        mean_consumption=('daily_consumption', 'mean'),
        std_consumption=('daily_consumption', 'std'),
    ).reset_index()

    active_days = daily_full[daily_full['daily_consumption'] > 0].groupby('item_id')['day'].nunique().reset_index(name='days_active')
    stats = pd.merge(stats, active_days, on='item_id', how='left')
    stats['days_active'] = stats['days_active'].fillna(0)

    stats = stats[stats['days_active'] >= min_days].copy()

    if stats.empty:
        return {
            'data': pd.DataFrame(),
            'summary': {
                'x_count': 0,
                'y_count': 0,
                'z_count': 0,
                'total_items': 0,
                'message': f'هیچ کالایی با حداقل {min_days} روز مصرف یافت نشد',
                'min_days_threshold': min_days,
            },
            'chart': {},
            'warnings': [f'برای XYZ حداقل {min_days} روز داده مصرفی برای هر کالا لازم است'],
        }

    stats['std_consumption'] = stats['std_consumption'].fillna(0)
    stats['cv'] = np.where(
        stats['mean_consumption'] > 0,
        stats['std_consumption'] / stats['mean_consumption'],
        0,
    )

    def _xyz_class(cv):
        if cv < 0.5:
            return 'X'
        if cv < 1.0:
            return 'Y'
        return 'Z'

    def _xyz_recommendation(xyz_class):
        playbook = {
            'X': 'مصرف پایدار - قرارداد بلندمدت و سفارش منظم',
            'Y': 'مصرف متوسط - موجودی ایمنی متوسط و بازبینی ماهانه',
            'Z': 'مصرف بی‌ثبات - موجودی ایمنی بالا و سفارش مبتنی بر نیاز',
        }
        return playbook.get(xyz_class, '-')

    stats['xyz_class'] = stats['cv'].apply(_xyz_class)
    stats['recommendation'] = stats['xyz_class'].apply(_xyz_recommendation)
    stats = stats.sort_values('cv')
    stats['cv'] = stats['cv'].round(3)
    stats['mean_consumption'] = stats['mean_consumption'].round(2)
    stats['std_consumption'] = stats['std_consumption'].round(2)

    # Backward-compatible aliases used by templates
    stats['mean_amount'] = stats['mean_consumption']
    stats['std_amount'] = stats['std_consumption']

    summary = {
        'x_count': int((stats['xyz_class'] == 'X').sum()),
        'y_count': int((stats['xyz_class'] == 'Y').sum()),
        'z_count': int((stats['xyz_class'] == 'Z').sum()),
        'total_items': len(stats),
        'data_quality': 'consumption_based',
        'min_days_threshold': min_days,
        'methodology': 'CV از مصرف روزانه محاسبه شده است',
    }
    chart = {
        'labels': stats['item_name_fa'].tolist()[:20],
        'cv_values': stats['cv'].tolist()[:20],
        'classes': stats['xyz_class'].tolist()[:20],
    }
    return {'data': stats, 'summary': summary, 'chart': chart, 'warnings': []}


# ──────────────────────────────────────────────
# 3. ABC-XYZ Matrix
# ──────────────────────────────────────────────
def analyse_abc_xyz(days=90, category='Food'):
    """Build validated ABC-XYZ matrix and return data quality errors."""
    abc_result = analyse_abc(days, category)
    xyz_result = analyse_xyz(days, category)
    abc_df = abc_result.get('data', pd.DataFrame())
    xyz_df = xyz_result.get('data', pd.DataFrame())

    if abc_df.empty or xyz_df.empty:
        return {
            'data': pd.DataFrame(),
            'summary': {'message': 'ABC یا XYZ داده کافی ندارد', 'validation_errors': 0},
            'chart': {},
            'matrix': {},
            'errors': [],
        }

    merged = abc_df.merge(
        xyz_df[['item_code', 'xyz_class', 'cv']],
        on='item_code',
        how='left',
    )

    errors = []
    duplicates = merged[merged.duplicated(subset=['item_code'], keep=False)]
    if not duplicates.empty:
        dup_codes = duplicates['item_code'].unique().tolist()
        errors.append(
            {
                'type': 'duplicate_items',
                'message': f'{len(dup_codes)} کالا در ماتریس تکراری هستند',
                'items': dup_codes,
                'action': 'داده مبنای ABC و XYZ بررسی شود',
            }
        )
        merged = merged.drop_duplicates(subset=['item_code'], keep='first')

    missing_xyz = merged[merged['xyz_class'].isna()]
    if not missing_xyz.empty:
        errors.append(
            {
                'type': 'missing_xyz',
                'message': f'{len(missing_xyz)} کالا در XYZ کلاس ندارد',
                'items': missing_xyz['item_code'].tolist(),
                'action': 'به صورت محافظه‌کارانه در کلاس Z قرار گرفتند',
            }
        )

    merged['xyz_class'] = merged['xyz_class'].fillna('Z')
    merged['cv'] = merged['cv'].fillna(999)
    merged['matrix_class'] = merged['abc_class'] + merged['xyz_class']

    cell_counts = merged.groupby('item_code')['matrix_class'].nunique()
    if (cell_counts > 1).any():
        multi_cell_items = cell_counts[cell_counts > 1].index.tolist()
        errors.append(
            {
                'type': 'multi_cell_assignment',
                'message': f'{len(multi_cell_items)} کالا در چند خانه قرار گرفته‌اند',
                'items': multi_cell_items,
                'action': 'منطق ادغام ماتریس بررسی شود',
            }
        )

    matrix = {}
    for abc_class in ['A', 'B', 'C']:
        for xyz_class in ['X', 'Y', 'Z']:
            key = f'{abc_class}{xyz_class}'
            subset = merged[merged['matrix_class'] == key]
            matrix[key] = {
                'count': len(subset),
                'amount': float(subset['amount'].sum()) if not subset.empty else 0,
                'items': (subset['item_name'].tolist() if 'item_name' in subset else subset['item_name_fa'].tolist())[:5],
                'recommendation': _get_matrix_recommendation(key),
            }

    summary = {
        'total_items': len(merged),
        'top_class': merged['matrix_class'].value_counts().idxmax() if not merged.empty else '-',
        'ax_count': matrix.get('AX', {}).get('count', 0),
        'az_count': matrix.get('AZ', {}).get('count', 0),
        'cz_count': matrix.get('CZ', {}).get('count', 0),
        'validation_errors': len(errors),
        'data_quality_issues': [e['type'] for e in errors],
    }
    chart = {
        'classes': list(matrix.keys()),
        'counts': [v['count'] for v in matrix.values()],
        'amounts': [round(v['amount']) for v in matrix.values()],
    }
    return {'data': merged, 'summary': summary, 'chart': chart, 'matrix': matrix, 'errors': errors}


# ──────────────────────────────────────────────
# 4. Price Trend / Inflation
# ──────────────────────────────────────────────
def analyse_price_trend(days=90, category=None, top_n=10):
    """Price trend analysis using regression-based change detection."""
    df = _base_purchase_df(days, category)
    if df.empty:
        return {'data': pd.DataFrame(), 'summary': {}, 'chart': {}, 'items_chart': []}

    top_items = df.groupby('item_id')['total_amount'].sum().nlargest(top_n).index.tolist()
    df_top = df[df['item_id'].isin(top_items)].copy()
    df_top['year_week'] = df_top['transaction_date'].dt.strftime('%Y-W%W')
    df_top['week_start'] = df_top['transaction_date'] - pd.to_timedelta(df_top['transaction_date'].dt.weekday, unit='D')
    df_top['week_start'] = df_top['week_start'].dt.normalize()

    weekly_price = df_top.groupby(['item_code', 'item_name_fa', 'year_week']).agg(
        avg_price=('unit_price', 'mean'),
        total_qty=('quantity', 'sum'),
        week_start=('week_start', 'min'),
    ).reset_index().sort_values(['item_code', 'year_week'])

    price_changes = []
    for item_code, grp in weekly_price.groupby('item_code'):
        if len(grp) < 2:
            continue

        first_price = float(grp.iloc[0]['avg_price'])
        last_price = float(grp.iloc[-1]['avg_price'])

        if len(grp) >= 3:
            first_date = grp['week_start'].min()
            x = (grp['week_start'] - first_date).dt.days / 7.0
            y = grp['avg_price'].values.astype(float)
            coeffs = np.polyfit(x, y, 1)
            slope = coeffs[0]
            avg_price = y.mean()
            trend_pct_per_week = (slope / avg_price * 100) if avg_price > 0 else 0
            
            total_weeks_span = (grp['week_start'].max() - first_date).days / 7.0
            change_pct = trend_pct_per_week * max(1, total_weeks_span)
        else:
            trend_pct_per_week = 0
            change_pct = ((last_price - first_price) / first_price * 100) if first_price > 0 else 0

        price_changes.append(
            {
                'item_code': item_code,
                'item_name': grp.iloc[0]['item_name_fa'],
                'first_price': round(first_price),
                'last_price': round(last_price),
                'change_pct': round(change_pct, 1),
                'trend_pct_per_week': round(trend_pct_per_week, 2),
                'weeks_count': len(grp),
            }
        )

    price_changes_df = (
        pd.DataFrame(price_changes).sort_values('change_pct', ascending=False)
        if price_changes
        else pd.DataFrame()
    )

    items_chart = []
    for item_code, grp in weekly_price.groupby('item_code'):
        items_chart.append(
            {
                'name': grp.iloc[0]['item_name_fa'],
                'weeks': grp['year_week'].tolist(),
                'prices': [round(float(p)) for p in grp['avg_price'].tolist()],
            }
        )

    avg_inflation = float(price_changes_df['change_pct'].mean()) if not price_changes_df.empty else 0
    summary = {
        'avg_inflation': round(avg_inflation, 1),
        'max_increase_item': price_changes_df.iloc[0]['item_name'] if not price_changes_df.empty else '-',
        'max_increase_pct': float(price_changes_df.iloc[0]['change_pct']) if not price_changes_df.empty else 0,
        'items_with_increase': int((price_changes_df['change_pct'] > 0).sum()) if not price_changes_df.empty else 0,
        'items_with_decrease': int((price_changes_df['change_pct'] < 0).sum()) if not price_changes_df.empty else 0,
        'methodology': 'رگرسیون خطی هفتگی (به‌جای مقایسه ابتدا و انتها)',
    }
    return {'data': price_changes_df, 'summary': summary, 'chart': {}, 'items_chart': items_chart}


# ──────────────────────────────────────────────
# 5. Price Volatility per Item
# ──────────────────────────────────────────────
def analyse_price_volatility(days=90, category=None):
    """Price volatility analysis with minimum sample-size filter."""
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

    min_purchases = 5
    stats = stats[stats['purchase_count'] >= min_purchases].copy()
    if stats.empty:
        return {
            'data': pd.DataFrame(),
            'summary': {
                'message': f'هیچ کالایی با حداقل {min_purchases} تراکنش خرید یافت نشد',
                'warning': 'تحلیل نوسان قیمت نیازمند حداقل تکرار خرید است',
            },
            'chart': {},
        }

    stats['std_price'] = stats['std_price'].fillna(0)
    stats['price_cv'] = np.where(
        stats['mean_price'] > 0,
        stats['std_price'] / stats['mean_price'],
        0,
    )
    stats['price_range'] = stats['max_price'] - stats['min_price']
    stats = stats.sort_values('price_cv', ascending=False)
    stats = stats.round(
        {
            'mean_price': 0,
            'std_price': 0,
            'price_cv': 3,
            'min_price': 0,
            'max_price': 0,
            'price_range': 0,
        }
    )

    summary = {
        'most_volatile': stats.iloc[0]['item_name_fa'] if not stats.empty else '-',
        'most_volatile_cv': float(stats.iloc[0]['price_cv']) if not stats.empty else 0,
        'most_stable': stats.iloc[-1]['item_name_fa'] if not stats.empty else '-',
        'avg_cv': round(float(stats['price_cv'].mean()), 3) if not stats.empty else 0,
        'high_risk_count': int((stats['price_cv'] > 0.3).sum()) if not stats.empty else 0,
        'min_purchases_threshold': min_purchases,
    }
    thresholds = {
        'red': [
            {
                'metric': 'high_risk_count',
                'operator': '>=',
                'threshold': 8,
                'action': 'ریسک نوسان قیمت بالا است - مذاکره قرارداد و چند تامین‌کننده ضروری است',
            }
        ],
        'yellow': [
            {
                'metric': 'high_risk_count',
                'operator': '>=',
                'threshold': 4,
                'action': 'اقلام پرنوسان زیاد شده‌اند - بازنگری سیاست خرید پیشنهاد می‌شود',
            }
        ],
    }
    summary = _add_alert_level(summary, thresholds)

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
    """Spend trend with slope-based directional alerts."""
    df = _base_purchase_df(days, category)
    if df.empty:
        return {'data': pd.DataFrame(), 'summary': {}, 'chart': {}}

    if period == 'monthly':
        df['period'] = df['transaction_date'].dt.to_period('M').astype(str)
        df['period_start'] = df['transaction_date'].dt.to_period('M').dt.start_time
    else:
        df['period'] = df['transaction_date'].dt.strftime('%Y-W%W')
        df['period_start'] = df['transaction_date'] - pd.to_timedelta(df['transaction_date'].dt.weekday, unit='D')
        df['period_start'] = df['period_start'].dt.normalize()

    trend = df.groupby('period').agg(
        total_amount=('total_amount', 'sum'),
        tx_count=('total_amount', 'count'),
        avg_basket=('total_amount', 'mean'),
        period_start=('period_start', 'min'),
    ).reset_index().sort_values('period_start')
    trend = trend.round({'total_amount': 0, 'avg_basket': 0})

    cat_trend = df.groupby(['period', 'category']).agg(
        amount=('total_amount', 'sum')
    ).reset_index().sort_values('period')

    avg_spend = float(trend['total_amount'].mean()) if not trend.empty else 0
    max_spend_period = trend.loc[trend['total_amount'].idxmax(), 'period'] if not trend.empty else '-'

    if len(trend) >= 2:
        first_date = trend['period_start'].min()
        if period == 'monthly':
            x = (trend['period_start'] - first_date).dt.days / 30.436875
        else:
            x = (trend['period_start'] - first_date).dt.days / 7.0
            
        y = trend['total_amount'].values.astype(float)
        slope = float(np.polyfit(x, y, 1)[0])
    else:
        slope = 0
    slope_pct = (slope / avg_spend * 100) if avg_spend > 0 else 0

    summary = {
        'avg_spend': round(avg_spend),
        'max_spend_period': max_spend_period,
        'max_spend': round(float(trend['total_amount'].max())) if not trend.empty else 0,
        'total_spend': round(float(trend['total_amount'].sum())) if not trend.empty else 0,
        'periods_count': len(trend),
        'trend_direction': 'up' if slope > 0 else 'down',
        'trend_slope': round(slope),
        'trend_slope_pct': round(slope_pct, 2),
    }
    thresholds = {
        'red': [
            {
                'metric': 'trend_slope_pct',
                'operator': '>=',
                'threshold': 15,
                'action': 'شتاب رشد هزینه بسیار بالا است - برنامه کنترل اضطراری هزینه فعال شود',
            }
        ],
        'yellow': [
            {
                'metric': 'trend_slope_pct',
                'operator': '>=',
                'threshold': 8,
                'action': 'هزینه در حال افزایش است - سقف خرید و بازبینی هفتگی پیشنهاد می‌شود',
            }
        ],
    }
    if summary['trend_direction'] == 'up':
        summary = _add_alert_level(summary, thresholds)
    else:
        summary['alert_level'] = 'green'
        summary['actions'] = []

    summary = standardize_summary_amounts(summary, keys=['avg_spend', 'max_spend', 'total_spend'])

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
        'recommendation': 'برای تحلیل دقیق‌تر، زیرگروه‌های Food را تعریف کنید: Protein, Dairy, Produce, Dry Goods, Beverage',
    }
    summary = standardize_summary_amounts(summary, keys=['grand_total'])

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
        days,
    )
    freq = freq.sort_values('purchase_count', ascending=False)
    freq = freq.round({'avg_interval_days': 1, 'total_amount': 0})

    def _freq_class(count, total_days=days):
        monthly_rate = count / (total_days / 30)
        if monthly_rate >= 4:
            return 'بسیار مکرر'
        if monthly_rate >= 2:
            return 'مکرر'
        if monthly_rate >= 1:
            return 'متوسط'
        return 'کم‌تکرار'

    freq['freq_class'] = freq['purchase_count'].apply(_freq_class)
    freq['suggested_reorder_interval'] = freq.apply(
        lambda row: _calculate_reorder_interval(row['avg_interval_days'], row['freq_class']),
        axis=1,
    )

    summary = {
        'most_frequent': freq.iloc[0]['item_name_fa'] if not freq.empty else '-',
        'most_frequent_count': int(freq.iloc[0]['purchase_count']) if not freq.empty else 0,
        'avg_interval': round(float(freq['avg_interval_days'].mean()), 1) if not freq.empty else 0,
        'single_purchase_items': int((freq['purchase_count'] == 1).sum()) if not freq.empty else 0,
        'total_items': len(freq),
    }
    chart = {
        'labels': freq['item_name_fa'].tolist()[:20],
        'counts': freq['purchase_count'].tolist()[:20],
        'intervals': freq['avg_interval_days'].tolist()[:20],
    }
    return {'data': freq, 'summary': summary, 'chart': chart}


# ──────────────────────────────────────────────
# 9. Consumption Trend (compat via analyse_demand_proxy)
# ──────────────────────────────────────────────
def analyse_demand_proxy(days=90, category=None, top_n=10):
    """Consumption trend analysis (keeps legacy function name for compatibility)."""
    df = _base_consumption_df(days, category)
    if df.empty:
        return {
            'data': pd.DataFrame(),
            'summary': {
                'message': 'داده مصرف وجود ندارد',
                'warning': 'تحلیل روند تقاضا نیازمند ثبت تراکنش مصرف است',
                'rising_consumption': 0,
                'falling_consumption': 0,
                'stable_consumption': 0,
                'rising_demand': 0,
                'falling_demand': 0,
                'stable_demand': 0,
            },
            'chart': {},
            'items_chart': [],
            'rising_items': [],
            'falling_items': [],
        }

    top_items = df.groupby('item_id')['quantity'].sum().nlargest(top_n).index.tolist()
    df_top = df[df['item_id'].isin(top_items)].copy()
    df_top['week'] = df_top['transaction_date'].dt.strftime('%Y-W%W')
    df_top['week_start'] = df_top['transaction_date'] - pd.to_timedelta(df_top['transaction_date'].dt.weekday, unit='D')
    df_top['week_start'] = df_top['week_start'].dt.normalize()

    weekly = df_top.groupby(['item_code', 'item_name_fa', 'week']).agg(
        total_consumption=('quantity', 'sum'),
        week_start=('week_start', 'min'),
    ).reset_index().sort_values(['item_code', 'week'])

    items_chart = []
    consumption_changes = []

    for item_code, grp in weekly.groupby('item_code'):
        series_values = [round(float(q), 2) for q in grp['total_consumption'].tolist()]
        items_chart.append(
            {
                'name': grp.iloc[0]['item_name_fa'],
                'weeks': grp['week'].tolist(),
                'consumption': series_values,
                'quantities': series_values,
            }
        )

        if len(grp) >= 3:
            first_date = grp['week_start'].min()
            x = (grp['week_start'] - first_date).dt.days / 7.0
            y = grp['total_consumption'].values.astype(float)
            slope = float(np.polyfit(x, y, 1)[0])
            avg = float(y.mean())
            trend_pct = (slope / avg * 100) if avg > 0 else 0
            first_qty = float(y[0])
            last_qty = float(y[-1])
            consumption_changes.append(
                {
                    'item_code': item_code,
                    'item_name': grp.iloc[0]['item_name_fa'],
                    'avg_weekly': round(avg, 2),
                    'trend_pct': round(trend_pct, 1),
                    'change_pct': round(trend_pct, 1),
                    'direction': 'صعودی' if slope > 0 else 'نزولی',
                    'weeks_count': len(grp),
                    'first_qty': round(first_qty, 2),
                    'last_qty': round(last_qty, 2),
                }
            )

    demand_df = (
        pd.DataFrame(consumption_changes).sort_values('trend_pct', ascending=False)
        if consumption_changes
        else pd.DataFrame()
    )

    trend_threshold_rising = 15
    trend_threshold_falling = -15
    rising = demand_df[demand_df['trend_pct'] > trend_threshold_rising] if not demand_df.empty else pd.DataFrame()
    falling = demand_df[demand_df['trend_pct'] < trend_threshold_falling] if not demand_df.empty else pd.DataFrame()

    stable_count = len(demand_df) - len(rising) - len(falling) if not demand_df.empty else 0
    summary = {
        'rising_consumption': len(rising),
        'falling_consumption': len(falling),
        'stable_consumption': stable_count,
        'rising_demand': len(rising),
        'falling_demand': len(falling),
        'stable_demand': stable_count,
        'methodology': 'رگرسیون خطی روی مصرف هفتگی (نه خرید)',
        'alert_level': 'green',
        'actions': [],
    }

    if not rising.empty:
        summary['alert_level'] = 'yellow'
        summary['actions'].append(
            {
                'type': 'rising_consumption',
                'items': rising['item_name'].tolist(),
                'action': 'افزایش سفارش این اقلام و بازبینی نقطه سفارش',
            }
        )

    if not falling.empty:
        summary['alert_level'] = 'yellow'
        summary['actions'].append(
            {
                'type': 'falling_consumption',
                'items': falling['item_name'].tolist(),
                'action': 'کاهش سفارش و بررسی تغییر منو یا کیفیت',
            }
        )

    return {
        'data': demand_df,
        'summary': summary,
        'chart': {},
        'items_chart': items_chart,
        'rising_items': rising.to_dict('records') if not rising.empty else [],
        'falling_items': falling.to_dict('records') if not falling.empty else [],
    }


# ──────────────────────────────────────────────
# 10. Anomaly Detection
# ──────────────────────────────────────────────
def analyse_anomalies(days=90, category=None, z_threshold=2.0):
    df = _base_purchase_df(days, category)
    if df.empty:
        return {'data': pd.DataFrame(), 'summary': {}, 'chart': {}}

    df = df.sort_values(['item_id', 'transaction_date']).copy()
    window = 5

    for col, stat_name in [('total_amount', 'amount'), ('quantity', 'qty'), ('unit_price', 'price')]:
        df[f'mean_{stat_name}'] = df.groupby('item_id')[col].transform(lambda x: x.rolling(window, min_periods=2).mean().shift())
        df[f'std_{stat_name}'] = df.groupby('item_id')[col].transform(lambda x: x.rolling(window, min_periods=2).std().shift())

        global_mean = df.groupby('item_id')[col].transform('mean')
        global_std = df.groupby('item_id')[col].transform('std')

        df[f'mean_{stat_name}'] = df[f'mean_{stat_name}'].fillna(global_mean)
        df[f'std_{stat_name}'] = df[f'std_{stat_name}'].fillna(global_std).fillna(0)

    anomalies = []
    for _, row in df.iterrows():
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
            anomalies.append(
                {
                    'item_code': row['item_code'],
                    'item_name': row['item_name_fa'],
                    'date': row['transaction_date'].strftime('%Y-%m-%d'),
                    'quantity': round(float(row['quantity']), 2),
                    'unit_price': round(float(row['unit_price'])),
                    'total_amount': round(float(row['total_amount'])),
                    'reasons': ' | '.join(reasons),
                }
            )

    anomaly_df = pd.DataFrame(anomalies) if anomalies else pd.DataFrame()
    anomaly_rate = round(len(anomalies) / len(df) * 100, 1) if len(df) > 0 else 0
    summary = {
        'total_anomalies': len(anomalies),
        'total_transactions': len(df),
        'anomaly_rate': anomaly_rate,
        'unique_items_with_anomaly': len(set(a['item_code'] for a in anomalies)),
    }
    thresholds = {
        'red': [
            {
                'metric': 'anomaly_rate',
                'operator': '>',
                'threshold': 15,
                'action': 'نرخ ناهنجاری بحرانی است - پایش فاکتور و تایید دو مرحله‌ای فعال شود',
            }
        ],
        'yellow': [
            {
                'metric': 'anomaly_rate',
                'operator': '>',
                'threshold': 8,
                'action': 'نرخ ناهنجاری بالا است - نمونه‌برداری و ممیزی خرید پیشنهاد می‌شود',
            }
        ],
    }
    summary = _add_alert_level(summary, thresholds)

    chart = {
        'labels': ['عادی', 'غیرعادی'],
        'counts': [len(df) - len(anomalies), len(anomalies)],
    }
    return {'data': anomaly_df, 'summary': summary, 'chart': chart}


# ──────────────────────────────────────────────
# 11. Cost Forecast (occupancy-aware)
# ──────────────────────────────────────────────
def analyse_forecast(days=90, category=None, forecast_periods=4, occupancy_forecast=None, events=None, historical_avg_occ=100):
    """Cost forecast with optional occupancy and event adjustments."""
    df = _base_purchase_df(days, category)
    if df.empty:
        return {
            'data': pd.DataFrame(),
            'summary': {'message': 'داده خرید کافی برای پیش‌بینی وجود ندارد'},
            'chart': {},
        }

    df['week'] = df['transaction_date'].dt.strftime('%Y-W%W')
    weekly = df.groupby('week').agg(
        total_amount=('total_amount', 'sum')
    ).reset_index().sort_values('week')

    if len(weekly) < 3:
        return {
            'data': weekly,
            'summary': {'message': 'داده کافی برای پیش‌بینی وجود ندارد (حداقل ۳ هفته)'},
            'chart': {},
        }

    x = np.arange(len(weekly))
    y = weekly['total_amount'].values.astype(float)
    slope, intercept = np.polyfit(x, y, 1)
    avg_weekly = float(weekly['total_amount'].mean())

    forecast_weeks = []
    for i in range(1, forecast_periods + 1):
        trend_value = slope * (len(weekly) + i) + intercept
        baseline_forecast = 0.6 * trend_value + 0.4 * avg_weekly

        if occupancy_forecast and len(occupancy_forecast) >= i:
            occ_multiplier = occupancy_forecast[i - 1] / historical_avg_occ
            baseline_forecast *= occ_multiplier

        event_multiplier = 1.0
        if events:
            for event in events:
                if event.get('week') == i:
                    event_multiplier = event.get('multiplier', 1.0)
                    break
        baseline_forecast *= event_multiplier

        forecast_weeks.append(
            {
                'week': f'پیش‌بینی {i}',
                'total_amount': round(max(0, baseline_forecast)),
                'is_forecast': True,
                'occupancy_adjusted': occupancy_forecast is not None,
                'event_adjusted': event_multiplier > 1.0,
            }
        )

    forecast_df = pd.DataFrame(forecast_weeks)
    historical_for_chart = weekly[['week', 'total_amount']].copy()
    historical_for_chart['is_forecast'] = False
    historical_for_chart['occupancy_adjusted'] = False
    historical_for_chart['event_adjusted'] = False
    combined = pd.concat([historical_for_chart, forecast_df], ignore_index=True)

    total_forecast = sum(f['total_amount'] for f in forecast_weeks)
    summary = {
        'avg_weekly_spend': round(avg_weekly),
        'forecast_total': round(total_forecast),
        'trend': 'صعودی' if slope > 0 else 'نزولی',
        'slope_per_week': round(float(slope)),
        'forecast_periods': forecast_periods,
        'occupancy_adjusted': occupancy_forecast is not None,
        'events_included': bool(events),
        'methodology': 'Linear trend + occupancy + events' if occupancy_forecast else 'Linear trend only',
        'warning': [] if occupancy_forecast else ['پیش‌بینی بدون در نظر گرفتن اشغال هتل انجام شده است'],
    }
    summary = standardize_summary_amounts(summary, keys=['avg_weekly_spend', 'forecast_total'])

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

    if budget is None or budget <= 0:
        total_spend_period = float(df['total_amount'].sum())
        budget = total_spend_period * 1.1

    df_sorted = df.sort_values('transaction_date')
    df_sorted['cumulative_spend'] = df_sorted['total_amount'].cumsum()

    daily = df_sorted.groupby(df_sorted['transaction_date'].dt.strftime('%Y-%m-%d')).agg(
        daily_spend=('total_amount', 'sum'),
        cumulative=('cumulative_spend', 'max'),
    ).reset_index()
    daily['remaining'] = budget - daily['cumulative']
    daily['pct_used'] = (daily['cumulative'] / budget * 100).round(1)

    total_spent = float(df['total_amount'].sum())
    days_elapsed = max(1, days)
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
    thresholds = {
        'red': [
            {
                'metric': 'pct_used',
                'operator': '>=',
                'threshold': 90,
                'action': 'بحران بودجه - توقف خرید غیرضروری و تایید دو مرحله‌ای ضروری است',
            },
            {
                'metric': 'estimated_days_left',
                'operator': '<=',
                'threshold': 3,
                'action': 'بحران بودجه - کمتر از ۳ روز تا اتمام بودجه باقی مانده است',
            },
        ],
        'yellow': [
            {
                'metric': 'pct_used',
                'operator': '>=',
                'threshold': 80,
                'action': 'هشدار بودجه - کنترل هفتگی هزینه و سقف روزانه فعال شود',
            },
            {
                'metric': 'estimated_days_left',
                'operator': '<=',
                'threshold': 7,
                'action': 'هشدار بودجه - کمتر از یک هفته بودجه باقی مانده است',
            },
        ],
    }
    summary = _add_alert_level(summary, thresholds)
    summary = standardize_summary_amounts(summary, keys=['budget', 'total_spent', 'remaining', 'daily_burn_rate'])

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
    validation = StrategyDataValidator.validate_transactions(days)
    if not validation.get('is_valid', True):
        return {
            'has_data': False,
            'validation': validation,
            'error': 'مشکلات کیفی داده وجود دارد. ابتدا داده‌ها اصلاح شوند.',
        }

    try:
        abc = analyse_abc(days, category)
        xyz = analyse_xyz(days, category)
        spend = analyse_spend_trend(days, category)
        anomaly = analyse_anomalies(days, category)
        budget = analyse_budget_burndown(days, category)
        return {
            'abc_summary': abc.get('summary', {}),
            'xyz_summary': xyz.get('summary', {}),
            'spend_summary': spend.get('summary', {}),
            'anomaly_summary': anomaly.get('summary', {}),
            'budget_summary': budget.get('summary', {}),
            'validation': validation,
            'has_data': True,
        }
    except Exception as e:
        logger.error(f'Strategy overview error: {e}')
        return {'has_data': False, 'error': str(e), 'validation': validation}
