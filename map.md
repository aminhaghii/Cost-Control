🗺️ COMPLETE REFACTORING MAP FOR STRATEGY ANALYTICS
📋 EXECUTIVE SUMMARY
Current State:

12 KPIs implemented in services/strategy_analytics_service.py

3 KPIs have fundamental design flaws (XYZ, Demand Proxy, Forecast)

4 KPIs need moderate improvements (ABC, Price Trend, Category Mix, Purchase Frequency)

5 KPIs are excellent and need only minor enhancements

Target State:

10 reliable KPIs (remove Demand Proxy, replace with Consumption Analysis)

All KPIs return actionable alerts with thresholds

XYZ and Forecast recalculated using correct methodology

Complete validation layer to prevent data quality issues

Integration hooks for supplier and event data

Estimated Effort: 3-5 days for a senior developer

🔴 CRITICAL FIXES (Do First)
FIX #1: XYZ Analysis - Switch from Purchase to Consumption
Problem:

python
# Current (WRONG): Line 47-79 in strategy_analytics_service.py
df['month'] = df['transaction_date'].dt.to_period('M').astype(str)
monthly = df.groupby(['item_id', 'item_code', 'item_name_fa', 'month']).agg(
    amount=('total_amount', 'sum')
).reset_index()
This calculates CV from purchase transactions, which reflects buyer behavior (batch ordering) not actual demand volatility.

Solution:

python
def analyse_xyz(days=90, category=None):
    """
    XYZ Analysis based on CONSUMPTION volatility, not purchase.
    X = Stable consumption (CV < 0.5)
    Y = Moderate volatility (0.5 ≤ CV < 1.0)
    Z = High volatility (CV ≥ 1.0)
    """
    # Query CONSUMPTION transactions instead of purchase
    start_date = date.today() - timedelta(days=days)
    q = db.session.query(Transaction).join(Item).filter(
        Transaction.transaction_type == 'مصرف',  # ← KEY CHANGE
        Transaction.is_deleted != True,
        Transaction.is_opening_balance != True,
        Transaction.transaction_date >= start_date,
    )
    if category and category != 'all':
        q = q.filter(Item.category == category)
    
    rows = q.with_entities(
        Item.id.label('item_id'),
        Item.item_code,
        Item.item_name_fa,
        Item.category,
        Transaction.quantity.label('consumption_qty'),
        Transaction.transaction_date,
    ).all()
    
    if not rows:
        return {
            'data': pd.DataFrame(),
            'summary': {'message': 'داده مصرف کافی وجود ندارد'},
            'chart': {},
            'warning': 'XYZ needs consumption data. Currently no consumption transactions found.'
        }
    
    df = pd.DataFrame([dict(r._mapping) for r in rows])
    df['consumption_qty'] = df['consumption_qty'].astype(float)
    df['transaction_date'] = pd.to_datetime(df['transaction_date'])
    
    # Group by item + DAY (not month, for more granular view)
    df['day'] = df['transaction_date'].dt.date
    daily = df.groupby(['item_id', 'item_code', 'item_name_fa', 'day']).agg(
        daily_consumption=('consumption_qty', 'sum')
    ).reset_index()
    
    # Calculate CV per item
    stats = daily.groupby(['item_id', 'item_code', 'item_name_fa']).agg(
        mean_consumption=('daily_consumption', 'mean'),
        std_consumption=('daily_consumption', 'std'),
        days_active=('day', 'nunique'),
    ).reset_index()
    
    # Filter: only items with sufficient data points
    MIN_DAYS = 14  # Need at least 2 weeks of data
    stats = stats[stats['days_active'] >= MIN_DAYS].copy()
    
    if stats.empty:
        return {
            'data': pd.DataFrame(),
            'summary': {'message': f'هیچ کالایی با حداقل {MIN_DAYS} روز مصرف یافت نشد'},
            'chart': {},
            'warning': f'XYZ requires minimum {MIN_DAYS} days of consumption data per item.'
        }
    
    stats['std_consumption'] = stats['std_consumption'].fillna(0)
    stats['cv'] = np.where(
        stats['mean_consumption'] > 0,
        stats['std_consumption'] / stats['mean_consumption'],
        0
    )
    
    def _xyz_class(cv):
        if cv < 0.5:
            return 'X'
        elif cv < 1.0:
            return 'Y'
        return 'Z'
    
    stats['xyz_class'] = stats['cv'].apply(_xyz_class)
    stats = stats.sort_values('cv')
    stats['cv'] = stats['cv'].round(3)
    stats['mean_consumption'] = stats['mean_consumption'].round(2)
    
    # Add recommendations per class
    def _xyz_recommendation(xyz_class):
        playbook = {
            'X': 'مصرف پایدار → قرارداد بلندمدت، سفارش منظم (مثلاً هفتگی)',
            'Y': 'مصرف متوسط → موجودی ایمنی متوسط، بررسی ماهانه',
            'Z': 'مصرف بی‌ثبات → موجودی ایمنی بالا، سفارش مبتنی بر نیاز فوری',
        }
        return playbook.get(xyz_class, '-')
    
    stats['recommendation'] = stats['xyz_class'].apply(_xyz_recommendation)
    
    summary = {
        'x_count': int((stats['xyz_class'] == 'X').sum()),
        'y_count': int((stats['xyz_class'] == 'Y').sum()),
        'z_count': int((stats['xyz_class'] == 'Z').sum()),
        'total_items': len(stats),
        'data_quality': 'consumption-based',  # Flag for clarity
        'min_days_threshold': MIN_DAYS,
    }
    
    chart = {
        'labels': stats['item_name_fa'].tolist()[:20],
        'cv_values': stats['cv'].tolist()[:20],
        'classes': stats['xyz_class'].tolist()[:20],
    }
    
    return {
        'data': stats,
        'summary': summary,
        'chart': chart,
        'methodology': 'CV calculated from DAILY consumption (not purchase batches)',
    }
What happens:

✅ CV now reflects actual demand volatility

✅ Filter items with insufficient data (< 14 days)

✅ Daily granularity (not monthly) for better detection

✅ Recommendations embedded in output

Required:

Ensure Transaction.transaction_type == 'مصرف' data exists

If not, create consumption transactions from kitchen/outlet usage

FIX #2: ABC-XYZ Matrix - Add Validation Layer
Problem:

python
# Current: Line 84-120 in strategy_analytics_service.py
merged = abc_df.merge(
    xyz_df[['item_code', 'xyz_class', 'cv']],
    on='item_code', how='left'
)
merged['xyz_class'] = merged['xyz_class'].fillna('Z')
No validation that items appear only once in the matrix.

Solution:

python
def analyse_abc_xyz(days=90, category='Food'):
    abc_result = analyse_abc(days, category)
    xyz_result = analyse_xyz(days, category)
    abc_df = abc_result['data']
    xyz_df = xyz_result['data']
    
    if abc_df.empty or xyz_df.empty:
        return {
            'data': pd.DataFrame(),
            'summary': {'message': 'ABC or XYZ data is empty'},
            'chart': {},
            'matrix': {},
            'errors': [],
        }
    
    merged = abc_df.merge(
        xyz_df[['item_code', 'xyz_class', 'cv']],
        on='item_code',
        how='left'
    )
    
    # VALIDATION 1: Check for duplicates
    duplicates = merged[merged.duplicated(subset=['item_code'], keep=False)]
    errors = []
    if not duplicates.empty:
        dup_codes = duplicates['item_code'].unique().tolist()
        errors.append({
            'type': 'duplicate_items',
            'message': f'{len(dup_codes)} items appear multiple times in matrix',
            'items': dup_codes,
            'action': 'Check ABC and XYZ source data for duplicates'
        })
        # Deduplicate by keeping first occurrence
        merged = merged.drop_duplicates(subset=['item_code'], keep='first')
    
    # VALIDATION 2: Check for items missing XYZ class
    missing_xyz = merged[merged['xyz_class'].isna()]
    if not missing_xyz.empty:
        errors.append({
            'type': 'missing_xyz',
            'message': f'{len(missing_xyz)} items from ABC not found in XYZ (insufficient consumption data)',
            'items': missing_xyz['item_code'].tolist(),
            'action': 'These items assigned to Z class (high volatility) by default as conservative approach'
        })
    
    merged['xyz_class'] = merged['xyz_class'].fillna('Z')
    merged['cv'] = merged['cv'].fillna(999)  # High value to flag missing data
    merged['matrix_class'] = merged['abc_class'] + merged['xyz_class']
    
    # VALIDATION 3: Check that each item is in exactly one cell
    cell_counts = merged.groupby('item_code')['matrix_class'].nunique()
    if (cell_counts > 1).any():
        multi_cell_items = cell_counts[cell_counts > 1].index.tolist()
        errors.append({
            'type': 'multi_cell_assignment',
            'message': f'{len(multi_cell_items)} items in multiple cells',
            'items': multi_cell_items,
            'action': 'CRITICAL: This should not happen after deduplication. Check merge logic.'
        })
    
    # Build matrix counts
    matrix = {}
    for a in ['A', 'B', 'C']:
        for x in ['X', 'Y', 'Z']:
            key = f'{a}{x}'
            subset = merged[merged['matrix_class'] == key]
            matrix[key] = {
                'count': len(subset),
                'amount': float(subset['amount'].sum()) if not subset.empty else 0,
                'items': subset['item_name_fa'].tolist()[:5],  # Top 5 for reference
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
    
    return {
        'data': merged,
        'summary': summary,
        'chart': chart,
        'matrix': matrix,
        'errors': errors,  # For debugging and data quality monitoring
    }

def _get_matrix_recommendation(matrix_class):
    """Strategic playbook per ABC-XYZ cell."""
    playbook = {
        'AX': '🔵 قرارداد بلندمدت + سفارش منظم + کنترل قیمت دقیق + موجودی متوسط',
        'AY': '🟢 ذخیره ایمنی متوسط + مذاکره قیمت فصلی + بررسی ماهانه',
        'AZ': '🔴 چند تأمین‌کننده + سقف قیمت + موجودی ایمنی بالا + مذاکره ویژه',
        'BX': '🔵 سفارش دوره‌ای (دو‌هفتگی) + قرارداد کوتاه‌مدت',
        'BY': '🟢 موجودی buffer + بررسی فصلی',
        'BZ': '🟡 سفارش مبتنی بر نیاز + تأمین‌کننده پشتیبان',
        'CX': '⚪ ساده‌سازی + خرید دسته‌جمعی با سایر اقلام',
        'CY': '⚪ کنترل سبک + بررسی سالانه',
        'CZ': '⚠️ بررسی حذف از منو یا جایگزین با قلم استاندارد',
    }
    return playbook.get(matrix_class, '-')
What happens:

✅ Detects and fixes duplicate items

✅ Flags items missing XYZ data

✅ Returns validation errors for monitoring

✅ Embeds strategic recommendations per cell

FIX #3: Demand Proxy - Replace with Actual Consumption Analysis
Problem:
analyse_demand_proxy uses purchase quantity as demand proxy, which is fundamentally wrong.

Solution:

python
def analyse_consumption_trend(days=90, category=None, top_n=10):
    """
    ACTUAL consumption trend analysis (replaces demand proxy).
    Uses 'مصرف' transactions to track real usage patterns.
    """
    start_date = date.today() - timedelta(days=days)
    q = db.session.query(Transaction).join(Item).filter(
        Transaction.transaction_type == 'مصرف',  # KEY: consumption, not purchase
        Transaction.is_deleted != True,
        Transaction.is_opening_balance != True,
        Transaction.transaction_date >= start_date,
    )
    if category and category != 'all':
        q = q.filter(Item.category == category)
    
    rows = q.with_entities(
        Item.id.label('item_id'),
        Item.item_code,
        Item.item_name_fa,
        Item.category,
        Transaction.quantity,
        Transaction.transaction_date,
    ).all()
    
    if not rows:
        return {
            'data': pd.DataFrame(),
            'summary': {
                'message': 'داده مصرف وجود ندارد',
                'warning': 'Consumption transactions required. Please ensure مصرف type is being recorded.'
            },
            'chart': {},
            'items_chart': [],
        }
    
    df = pd.DataFrame([dict(r._mapping) for r in rows])
    df['quantity'] = df['quantity'].astype(float)
    df['transaction_date'] = pd.to_datetime(df['transaction_date'])
    
    # Top N items by total consumption
    top_items = df.groupby('item_id')['quantity'].sum().nlargest(top_n).index.tolist()
    df_top = df[df['item_id'].isin(top_items)].copy()
    
    df_top['week'] = df_top['transaction_date'].dt.strftime('%Y-W%W')
    weekly = df_top.groupby(['item_code', 'item_name_fa', 'week']).agg(
        total_consumption=('quantity', 'sum'),
    ).reset_index().sort_values(['item_code', 'week'])
    
    items_chart = []
    consumption_changes = []
    
    for item_code, grp in weekly.groupby('item_code'):
        items_chart.append({
            'name': grp.iloc[0]['item_name_fa'],
            'weeks': grp['week'].tolist(),
            'consumption': [round(q, 2) for q in grp['total_consumption'].tolist()],
        })
        
        if len(grp) >= 3:  # Need at least 3 weeks for trend
            # Use linear regression for trend (not first-last)
            x = np.arange(len(grp))
            y = grp['total_consumption'].values
            coeffs = np.polyfit(x, y, 1)
            slope = coeffs[0]
            avg = y.mean()
            trend_pct = (slope / avg * 100) if avg > 0 else 0
            
            consumption_changes.append({
                'item_code': item_code,
                'item_name': grp.iloc[0]['item_name_fa'],
                'avg_weekly': round(avg, 2),
                'trend_pct': round(trend_pct, 1),
                'direction': 'صعودی' if slope > 0 else 'نزولی',
                'weeks_count': len(grp),
            })
    
    consumption_df = pd.DataFrame(consumption_changes).sort_values(
        'trend_pct', ascending=False
    ) if consumption_changes else pd.DataFrame()
    
    # Thresholds for alerts
    TREND_THRESHOLD_RISING = 15  # >15% weekly increase
    TREND_THRESHOLD_FALLING = -15  # <-15% weekly decrease
    
    rising = consumption_df[consumption_df['trend_pct'] > TREND_THRESHOLD_RISING] if not consumption_df.empty else pd.DataFrame()
    falling = consumption_df[consumption_df['trend_pct'] < TREND_THRESHOLD_FALLING] if not consumption_df.empty else pd.DataFrame()
    
    summary = {
        'rising_consumption': len(rising),
        'falling_consumption': len(falling),
        'stable_consumption': len(consumption_df) - len(rising) - len(falling) if not consumption_df.empty else 0,
        'methodology': 'Linear regression on weekly consumption (not purchase)',
        'alert_level': 'green',
        'actions': [],
    }
    
    # Generate alerts
    if not rising.empty:
        summary['alert_level'] = 'yellow'
        summary['actions'].append({
            'type': 'rising_consumption',
            'items': rising['item_name'].tolist(),
            'action': 'افزایش سفارش این اقلام - بررسی موجودی و reorder point',
        })
    
    if not falling.empty:
        summary['alert_level'] = 'yellow'
        summary['actions'].append({
            'type': 'falling_consumption',
            'items': falling['item_name'].tolist(),
            'action': 'کاهش سفارش - بررسی تغییر منو یا مشکل کیفیت',
        })
    
    return {
        'data': consumption_df,
        'summary': summary,
        'chart': {},
        'items_chart': items_chart,
        'rising_items': rising.to_dict('records') if not rising.empty else [],
        'falling_items': falling.to_dict('records') if not falling.empty else [],
    }
What happens:

✅ Uses actual consumption (not purchase)

✅ Linear regression for trend (not first-last)

✅ Alert thresholds for rising/falling consumption

✅ Actionable recommendations

In main service file, REPLACE:

python
# OLD (line 322-362):
def analyse_demand_proxy(days=90, category=None, top_n=10):
    ...

# NEW:
# Rename and replace with consumption-based analysis
FIX #4: Forecast - Add Occupancy Adjustment
Problem:
Simple moving average ignores hotel occupancy and events.

Solution:

python
def analyse_forecast(days=90, category=None, forecast_periods=4, occupancy_forecast=None, events=None):
    """
    Cost forecast with optional occupancy adjustment.
    
    Parameters:
    - occupancy_forecast: list of occupancy % for next periods, e.g. [75, 80, 85, 90]
    - events: list of dicts with 'week' and 'multiplier', e.g. [{'week': 1, 'multiplier': 1.5}]
    """
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
    
    # Baseline: Linear trend
    x = np.arange(len(weekly))
    y = weekly['total_amount'].values.astype(float)
    coeffs = np.polyfit(x, y, 1)
    slope, intercept = coeffs
    
    # Average historical weekly spend
    avg_weekly = float(weekly['total_amount'].mean())
    
    # Forecast
    forecast_weeks = []
    for i in range(1, forecast_periods + 1):
        # Baseline trend
        trend_value = slope * (len(weekly) + i) + intercept
        
        # Blend with moving average (60% trend, 40% avg)
        baseline_forecast = 0.6 * trend_value + 0.4 * avg_weekly
        
        # Occupancy adjustment (if provided)
        if occupancy_forecast and len(occupancy_forecast) >= i:
            # Assume historical avg occupancy was 70%
            HISTORICAL_AVG_OCC = 70  # Can be calculated if occupancy data available
            occ_multiplier = occupancy_forecast[i-1] / HISTORICAL_AVG_OCC
            baseline_forecast *= occ_multiplier
        
        # Event spikes (if provided)
        event_multiplier = 1.0
        if events:
            for event in events:
                if event.get('week') == i:
                    event_multiplier = event.get('multiplier', 1.0)
                    break
        baseline_forecast *= event_multiplier
        
        forecast_weeks.append({
            'week': f'پیش‌بینی {i}',
            'total_amount': round(max(0, baseline_forecast)),
            'is_forecast': True,
            'occupancy_adjusted': occupancy_forecast is not None,
            'event_adjusted': event_multiplier > 1.0,
        })
    
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
        'events_included': events is not None and len(events) > 0,
        'methodology': 'Linear trend + occupancy + events' if occupancy_forecast else 'Linear trend only',
        'warning': [] if occupancy_forecast else ['پیش‌بینی بدون در نظر گرفتن اشغال هتل - ممکن است ناقص باشد'],
    }
    
    chart = {
        'labels': combined['week'].tolist(),
        'amounts': combined['total_amount'].tolist(),
        'is_forecast': combined['is_forecast'].tolist(),
    }
    
    return {
        'data': combined,
        'summary': summary,
        'chart': chart,
    }
What happens:

✅ Occupancy adjustment optional (defaults to baseline if not provided)

✅ Event spikes can be injected

✅ Warns if occupancy not included

✅ More realistic for hotel operations

Usage example:

python
# Basic (current behavior)
forecast = analyse_forecast(days=90, category='Food')

# With occupancy (better)
forecast = analyse_forecast(
    days=90,
    category='Food',
    occupancy_forecast=[75, 80, 85, 90],  # Next 4 weeks
)

# With events (best)
forecast = analyse_forecast(
    days=90,
    category='Food',
    occupancy_forecast=[75, 80, 200, 90],  # Week 3 spike
    events=[
        {'week': 3, 'multiplier': 2.5, 'description': 'کنفرانس ۳۰۰ نفره'}
    ]
)
🟡 MODERATE IMPROVEMENTS (Do Second)
IMPROVE #5: ABC Analysis - Add Criticality Dimension
Add new function:

python
def analyse_abc_with_criticality(days=90, category='Food'):
    """
    ABC with criticality overlay.
    Identifies items that are low-value but high-criticality (e.g., salt, yeast).
    """
    abc_result = analyse_abc(days, category)
    abc_df = abc_result['data']
    
    if abc_df.empty:
        return abc_result
    
    # Get criticality from Item table (needs new field: Item.criticality)
    # For now, use a static mapping (should be configurable in DB)
    CRITICAL_ITEMS = {
        # Add item_codes that are operationally critical
        # Example: 'F1020': 'نمک', 'F1021': 'خمیرمایه', etc.
    }
    
    abc_df['is_critical'] = abc_df['item_code'].isin(CRITICAL_ITEMS.keys())
    abc_df['alert'] = abc_df.apply(
        lambda row: '⚠️ کم‌ارزش اما حیاتی' if row['abc_class'] == 'C' and row['is_critical'] else '',
        axis=1
    )
    
    critical_c_items = abc_df[(abc_df['abc_class'] == 'C') & (abc_df['is_critical'])]
    
    abc_result['data'] = abc_df
    abc_result['summary']['critical_c_count'] = len(critical_c_items)
    abc_result['critical_c_items'] = critical_c_items[['item_name_fa', 'amount', 'percentage']].to_dict('records')
    
    if not critical_c_items.empty:
        abc_result['summary']['actions'] = [{
            'type': 'critical_c_items',
            'items': critical_c_items['item_name_fa'].tolist(),
            'action': 'این اقلام ارزش ریالی کم دارند اما حیاتی هستند - موجودی ایمنی حفظ شود',
        }]
    
    return abc_result
What happens:

✅ Flags low-value but critical items

✅ Prevents wrong decisions (e.g., removing salt because it's class C)

IMPROVE #6: Price Trend - Use Regression Instead of First-Last
Replace in analyse_price_trend:

python
# OLD (line 143-148):
first_price = grp.iloc[0]['avg_price']
last_price = grp.iloc[-1]['avg_price']
change_pct = ((last_price - first_price) / first_price * 100) if first_price > 0 else 0

# NEW:
if len(grp) >= 3:
    x = np.arange(len(grp))
    y = grp['avg_price'].values
    coeffs = np.polyfit(x, y, 1)
    slope = coeffs[0]
    avg_price = y.mean()
    # Weekly trend as percentage
    trend_pct_per_week = (slope / avg_price * 100) if avg_price > 0 else 0
    # Total change over period
    change_pct = trend_pct_per_week * len(grp)
else:
    # Fallback to first-last if insufficient data
    first_price = grp.iloc[0]['avg_price']
    last_price = grp.iloc[-1]['avg_price']
    change_pct = ((last_price - first_price) / first_price * 100) if first_price > 0 else 0
IMPROVE #7: Price Volatility - Filter Low-Frequency Items
Add filter in analyse_price_volatility:

python
# After line 189 in strategy_analytics_service.py
stats = df.groupby(['item_id', 'item_code', 'item_name_fa']).agg(
    mean_price=('unit_price', 'mean'),
    std_price=('unit_price', 'std'),
    min_price=('unit_price', 'min'),
    max_price=('unit_price', 'max'),
    purchase_count=('unit_price', 'count'),
).reset_index()

# ADD THIS:
MIN_PURCHASES = 5  # Need at least 5 transactions for reliable CV
stats = stats[stats['purchase_count'] >= MIN_PURCHASES].copy()

if stats.empty:
    return {
        'data': pd.DataFrame(),
        'summary': {
            'message': f'هیچ کالایی با حداقل {MIN_PURCHASES} تراکنش خرید یافت نشد',
            'warning': 'Price volatility requires minimum purchase frequency'
        },
        'chart': {},
    }
IMPROVE #8: Category Mix - Add Subcategories
Solution:
This requires database migration to add subcategories. For now, add a note:

python
def analyse_category_mix(days=90):
    # ... existing code ...
    
    summary['recommendation'] = (
        'برای تحلیل دقیق‌تر، زیرگروه‌های Food را تعریف کنید: '
        'Protein, Dairy, Produce, Dry Goods, Beverage'
    )
    
    return result
IMPROVE #9: Purchase Frequency - Link to Reorder Logic
Add to output:

python
def analyse_purchase_frequency(days=90, category=None):
    # ... existing calculation ...
    
    # Add suggested reorder interval
    freq['suggested_reorder_interval'] = freq.apply(
        lambda row: _calculate_reorder_interval(
            row['avg_interval_days'],
            row['freq_class']
        ),
        axis=1
    )
    
    return result

def _calculate_reorder_interval(avg_interval, freq_class):
    """Suggest reorder interval based on purchase pattern."""
    if freq_class == 'بسیار مکرر':
        return f'{int(avg_interval)} روز (سفارش خودکار)'
    elif freq_class == 'مکرر':
        return f'{int(avg_interval * 1.2)} روز (بررسی هفتگی)'
    elif freq_class == 'متوسط':
        return f'{int(avg_interval * 1.5)} روز (بررسی دو‌هفتگی)'
    else:
        return 'مبتنی بر نیاز (بررسی ماهانه)'
🟢 MINOR ENHANCEMENTS (Do Third)
ENHANCE #10: Add Alert Levels to All KPIs
Create a utility function:

python
def _add_alert_level(summary, thresholds):
    """
    Add alert_level and actions to summary based on thresholds.
    
    Parameters:
    - summary: dict with KPI values
    - thresholds: dict with 'red' and 'yellow' conditions
    
    Returns: summary with alert_level and actions added
    """
    summary['alert_level'] = 'green'
    summary['actions'] = []
    
    for level, conditions in thresholds.items():
        for condition in conditions:
            metric = condition['metric']
            operator = condition['operator']
            threshold = condition['threshold']
            action = condition['action']
            
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
                summary['alert_level'] = level
                summary['actions'].append({
                    'metric': metric,
                    'value': value,
                    'threshold': threshold,
                    'action': action,
                })
    
    return summary
Apply to Budget Burndown:

python
def analyse_budget_burndown(days=30, category=None, budget=None):
    # ... existing calculation ...
    
    # Add alert thresholds
    thresholds = {
        'red': [
            {
                'metric': 'pct_used',
                'operator': '>=',
                'threshold': 90,
                'action': '🔴 بحران: توقف خرید غیرضروری - فقط اقلام حیاتی با تأیید دو مرحله‌ای'
            },
            {
                'metric': 'estimated_days_left',
                'operator': '<=',
                'threshold': 3,
                'action': '🔴 بحران: بودجه تا ۳ روز دیگر تمام می‌شود - محدودیت فوری'
            },
        ],
        'yellow': [
            {
                'metric': 'pct_used',
                'operator': '>=',
                'threshold': 80,
                'action': '🟡 هشدار: کنترل هفتگی هزینه و سقف روزانه فعال شود'
            },
            {
                'metric': 'estimated_days_left',
                'operator': '<=',
                'threshold': 7,
                'action': '🟡 هشدار: کمتر از یک هفته بودجه باقی‌مانده - محدودیت خرید'
            },
        ],
    }
    
    summary = _add_alert_level(summary, thresholds)
    
    return result
Apply same pattern to:

Anomaly Detection (anomaly_rate > 15% = red)

Price Volatility (high_risk_count > X = yellow)

Spend Trend (if trend_direction = up + slope > threshold = yellow)

🔧 INFRASTRUCTURE IMPROVEMENTS
INFRA #1: Add Data Quality Checks
Create new file: services/strategy_validation.py

python
"""
Data quality validation for strategy analytics.
Run before generating any KPI to ensure data integrity.
"""
import logging
from datetime import date, timedelta
from models import db, Transaction, Item

logger = logging.getLogger(__name__)

class StrategyDataValidator:
    """Validates data quality before analytics run."""
    
    @staticmethod
    def validate_transactions(days=90):
        """Check for data quality issues in transactions."""
        start_date = date.today() - timedelta(days=days)
        issues = []
        
        # Check 1: Any transactions with zero or negative amounts
        zero_amount = db.session.query(Transaction).filter(
            Transaction.transaction_date >= start_date,
            Transaction.is_deleted != True,
            Transaction.total_amount <= 0,
        ).count()
        
        if zero_amount > 0:
            issues.append({
                'type': 'zero_or_negative_amount',
                'count': zero_amount,
                'severity': 'high',
                'message': f'{zero_amount} تراکنش با مبلغ صفر یا منفی',
                'action': 'این تراکنش‌ها باید بررسی و اصلاح شوند'
            })
        
        # Check 2: Transactions with unit_price = 0 but total_amount > 0
        price_mismatch = db.session.query(Transaction).filter(
            Transaction.transaction_date >= start_date,
            Transaction.is_deleted != True,
            Transaction.unit_price == 0,
            Transaction.total_amount > 0,
        ).count()
        
        if price_mismatch > 0:
            issues.append({
                'type': 'price_mismatch',
                'count': price_mismatch,
                'severity': 'medium',
                'message': f'{price_mismatch} تراکنش با قیمت واحد صفر اما مبلغ کل غیرصفر',
                'action': 'احتمال خطای ثبت - بررسی شود'
            })
        
        # Check 3: Check for consumption data availability
        consumption_count = db.session.query(Transaction).filter(
            Transaction.transaction_type == 'مصرف',
            Transaction.transaction_date >= start_date,
            Transaction.is_deleted != True,
        ).count()
        
        if consumption_count == 0:
            issues.append({
                'type': 'no_consumption_data',
                'count': 0,
                'severity': 'critical',
                'message': 'هیچ تراکنش مصرفی در این دوره وجود ندارد',
                'action': 'XYZ و Consumption Trend بدون داده مصرف کار نمی‌کنند - شروع ثبت مصرف کنید'
            })
        
        # Check 4: Items without category
        items_no_category = db.session.query(Item).filter(
            Item.is_active == True,
            Item.category.is_(None) | (Item.category == ''),
        ).count()
        
        if items_no_category > 0:
            issues.append({
                'type': 'items_without_category',
                'count': items_no_category,
                'severity': 'medium',
                'message': f'{items_no_category} کالای فعال بدون گروه',
                'action': 'Category Mix کامل نخواهد بود - گروه‌ها را تکمیل کنید'
            })
        
        return {
            'is_valid': len([i for i in issues if i['severity'] == 'critical']) == 0,
            'issues': issues,
            'total_issues': len(issues),
            'critical_issues': len([i for i in issues if i['severity'] == 'critical']),
        }
    
    @staticmethod
    def validate_unit_consistency():
        """Check for unit consistency issues."""
        # Add checks for unit conversions, etc.
        pass
Usage in strategy overview:

python
def get_strategy_overview(days=90, category='Food'):
    """Quick summary for the strategy hub page."""
    
    # Validate data first
    validator = StrategyDataValidator()
    validation = validator.validate_transactions(days)
    
    if not validation['is_valid']:
        return {
            'has_data': False,
            'validation': validation,
            'error': 'Data quality issues detected. Please fix before running analytics.',
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
        return {'has_data': False, 'error': str(e)}
INFRA #2: Standardize Currency Units
Create utility in utils/currency.py:

python
"""Currency formatting and standardization."""

def format_amount(amount, unit='ریال', scale='auto'):
    """
    Format amount with consistent unit.
    
    Parameters:
    - amount: numeric value in base currency (ریال)
    - unit: 'ریال' or 'تومان'
    - scale: 'auto', 'میلیون', 'میلیارد', or None
    
    Returns: formatted string with unit
    """
    if amount is None:
        return '-'
    
    amount = float(amount)
    
    # Convert to تومان if requested
    if unit == 'تومان':
        amount = amount / 10
    
    # Auto-scale
    if scale == 'auto':
        if amount >= 1_000_000_000:
            scale = 'میلیارد'
        elif amount >= 1_000_000:
            scale = 'میلیون'
    
    # Apply scale
    if scale == 'میلیارد':
        value = amount / 1_000_000_000
        return f'{value:,.1f} میلیارد {unit}'
    elif scale == 'میلیون':
        value = amount / 1_000_000
        return f'{value:,.1f} میلیون {unit}'
    else:
        return f'{amount:,.0f} {unit}'

def standardize_summary_amounts(summary, keys=None):
    """
    Standardize all amount fields in summary dict.
    
    Parameters:
    - summary: dict with numeric values
    - keys: list of keys to format (None = auto-detect)
    
    Returns: summary with formatted values added (original values preserved)
    """
    if keys is None:
        # Auto-detect amount keys
        keys = [k for k in summary.keys() if any(x in k.lower() for x in [
            'amount', 'spend', 'budget', 'cost', 'total', 'value'
        ])]
    
    for key in keys:
        if key in summary and summary[key] is not None:
            original_key = f'{key}_raw'
            formatted_key = f'{key}_formatted'
            summary[original_key] = summary[key]
            summary[formatted_key] = format_amount(summary[key])
    
    return summary
Apply in all KPIs:

python
# At the end of each analyse_* function:
from utils.currency import standardize_summary_amounts

summary = standardize_summary_amounts(summary)
📝 COMPLETE IMPLEMENTATION CHECKLIST
Phase 1: Critical Fixes (Day 1-2)
 Replace analyse_xyz with consumption-based version

 Add validation to analyse_abc_xyz

 Replace analyse_demand_proxy with analyse_consumption_trend

 Update analyse_forecast with occupancy parameters

 Test all 4 fixes with verification script

Phase 2: Moderate Improvements (Day 2-3)
 Add criticality to ABC analysis

 Fix Price Trend to use regression

 Add minimum purchase filter to Price Volatility

 Add subcategory note to Category Mix

 Add reorder interval to Purchase Frequency

Phase 3: Enhancements (Day 3-4)
 Create _add_alert_level utility

 Add alert thresholds to Budget Burndown

 Add alert thresholds to Anomaly Detection

 Add alert thresholds to Price Volatility

 Add alert thresholds to Spend Trend

Phase 4: Infrastructure (Day 4-5)
 Create strategy_validation.py

 Create utils/currency.py

 Apply validation to get_strategy_overview

 Apply currency formatting to all KPIs

 Update verification script to test new features

Phase 5: Documentation & Testing (Day 5)
 Update README with new KPI definitions

 Document alert thresholds and actions

 Update verification script expected values

 Run full test suite

 Create migration guide for users

🎯 PROMPT FOR AI AGENT IN IDE
text
You are tasked with refactoring the Strategy Analytics Service for a hotel cost control system.

**CRITICAL RULES:**
1. Preserve all existing function signatures for backward compatibility
2. Add new parameters as optional (with defaults)
3. All changes must pass existing verification script
4. Return structured outputs with 'data', 'summary', 'chart' keys
5. Add 'errors', 'warnings', 'actions' keys where applicable
6. Use Persian (فارسی) for all user-facing text
7. Round all currency values appropriately
8. Handle empty DataFrames gracefully

**FILES TO MODIFY:**
- `services/strategy_analytics_service.py` (main refactoring)
- `services/strategy_validation.py` (create new)
- `utils/currency.py` (create new)
- `scripts/verify_strategy_analyses.py` (update tests)

**IMPLEMENTATION ORDER:**
1. Start with FIX #1 (XYZ Analysis) - highest impact
2. Then FIX #2 (ABC-XYZ validation)
3. Then FIX #3 (replace Demand Proxy with Consumption Trend)
4. Then FIX #4 (Forecast with occupancy)
5. Then apply moderate improvements
6. Then add infrastructure utilities
7. Finally update tests

**FOR EACH CHANGE:**
- Add docstring explaining methodology
- Add inline comments for complex logic
- Include example usage in docstring
- Return clear error messages when data is insufficient
- Log warnings for data quality issues

**VALIDATION:**
After each change, run:
```bash
python scripts/verify_strategy_analyses.py
All tests must pass. If a test fails, fix the implementation, not the test (unless the test expectation was wrong).

FINAL DELIVERABLES:

Refactored strategy_analytics_service.py with all fixes

New strategy_validation.py module

New utils/currency.py module

Updated verification script with new test cases

Migration notes documenting breaking changes (if any)

START WITH: FIX #1 - XYZ Analysis consumption-based refactoring.

text

***

