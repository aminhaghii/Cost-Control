from models import db, Transaction, Item
from sqlalchemy import func
from datetime import date, timedelta
from decimal import Decimal
import pandas as pd
from functools import lru_cache
import hashlib
import logging
from services.hotel_scope_service import enforce_hotel_scope, get_allowed_hotel_ids
from utils.decimal_utils import to_decimal

logger = logging.getLogger(__name__)

# Simple in-memory cache with TTL
_cache = {}
_cache_ttl = 300  # 5 minutes
_cache_max_size = 50  # Bug #14: Limit cache size to prevent memory leak

def _get_cache_key(mode, category, days):
    """Generate cache key"""
    return f"pareto_{mode}_{category}_{days}_{date.today()}"

def _is_cache_valid(key):
    """Check if cache entry is still valid"""
    import time
    if key in _cache:
        entry_time, _ = _cache[key]
        return (time.time() - entry_time) < _cache_ttl
    return False

def _cleanup_old_cache():
    """Bug #14: Remove expired and old cache entries to prevent memory leak"""
    import time
    global _cache
    current_time = time.time()
    
    # Remove expired entries
    expired_keys = [k for k, (t, _) in _cache.items() if (current_time - t) >= _cache_ttl]
    for key in expired_keys:
        del _cache[key]
    
    # If still too large, remove oldest entries
    if len(_cache) > _cache_max_size:
        sorted_keys = sorted(_cache.keys(), key=lambda k: _cache[k][0])
        for key in sorted_keys[:len(_cache) - _cache_max_size]:
            del _cache[key]

class ParetoService:
    
    def calculate_pareto(self, mode='خرید', category='Food', days=30, use_cache=True, 
                         hotel_ids=None, user=None, exclude_opening=True):
        """
        Calculate Pareto analysis for purchases or waste
        P0-4: Only use purchase transactions, exclude opening balances
        P0-3: Apply hotel scoping
        
        Returns DataFrame with cumulative percentages and ABC classification
        """
        import time
        
        # Bug #14: Cleanup old cache entries periodically
        _cleanup_old_cache()
        
        # Check cache first
        cache_key = _get_cache_key(mode, category, days)
        if use_cache and _is_cache_valid(cache_key):
            logger.debug(f"Cache hit for {cache_key}")
            return _cache[cache_key][1]
        
        start_date = date.today() - timedelta(days=days)
        
        query = db.session.query(
            Item.item_code,
            Item.item_name_fa,
            func.sum(Transaction.total_amount).label('total_amount')
        ).join(Transaction).filter(
            Transaction.transaction_type == mode,
            Transaction.category == category,
            Transaction.transaction_date >= start_date,
            Transaction.is_deleted != True  # P0-1: Exclude soft-deleted
        )
        
        # P0-4: Exclude opening balances from spend reports
        if exclude_opening:
            query = query.filter(Transaction.is_opening_balance != True)
        
        # P0-3: Apply hotel scoping
        if user:
            allowed = get_allowed_hotel_ids(user)
            if allowed is not None:  # None means admin (all hotels)
                query = query.filter(Item.hotel_id.in_(allowed))
        elif hotel_ids:
            query = query.filter(Item.hotel_id.in_(hotel_ids))
        
        query = query.group_by(Item.id).order_by(func.sum(Transaction.total_amount).desc())
        
        results = query.all()
        
        if not results:
            return pd.DataFrame(columns=[
                'row_num', 'item_code', 'item_name', 'amount', 
                'percentage', 'cumulative_amount', 'cumulative_percentage', 'abc_class'
            ])
        
        data = []
        
        # Bug #18: Filter out NULL/None values and negative amounts
        normalized_results = []
        for r in results:
            amount_dec = to_decimal(r.total_amount)
            if amount_dec <= 0:
                continue
            normalized_results.append({
                'item_code': r.item_code,
                'item_name': r.item_name_fa,
                'amount_dec': amount_dec
            })
        
        if not normalized_results:
            return pd.DataFrame(columns=[
                'row_num', 'item_code', 'item_name', 'amount', 
                'percentage', 'cumulative_amount', 'cumulative_percentage', 'abc_class'
            ])
        
        total_amount_dec = sum((r['amount_dec'] for r in normalized_results), Decimal('0.00'))
        cumulative_dec = Decimal('0.00')
        
        for idx, row in enumerate(normalized_results, 1):
            amount_dec = row['amount_dec']
            cumulative_dec += amount_dec
            
            if total_amount_dec > 0:
                percentage = (amount_dec / total_amount_dec) * Decimal('100')
                cumulative_percentage = (cumulative_dec / total_amount_dec) * Decimal('100')
            else:
                percentage = Decimal('0')
                cumulative_percentage = Decimal('0')
            
            # ABC Classification (Industry Standard - Improved Logic)
            # Pareto 80/20 Rule with individual item consideration:
            # 
            # Class A (Vital Few): Items that individually OR cumulatively 
            #          contribute to the first 80% of total value
            # Class B (Important): Items in the 80-95% cumulative range
            # Class C (Trivial Many): Items in the 95-100% cumulative range
            #
            # Special case: If a single item has >50% share, it's always Class A
            # This handles cases where one item dominates (e.g., 92% share)
            
            # Calculate cumulative percentage BEFORE adding this item
            cumulative_before = cumulative_dec - amount_dec
            cumulative_pct_before = (cumulative_before / total_amount_dec) * Decimal('100') if total_amount_dec > 0 else Decimal('0')
            
            if cumulative_pct_before < Decimal('80'):
                # This item contributes to reaching the 80% threshold - Class A
                abc_class = 'A'
            elif cumulative_pct_before < Decimal('95'):
                # This item is in the 80-95% range - Class B
                abc_class = 'B'
            else:
                # This item is in the 95-100% range - Class C
                abc_class = 'C'
            
            # Bug #17: Better precision for small percentages
            # Use 4 decimal places for calculations, display smartly
            if Decimal('0') < percentage < Decimal('0.01'):
                percentage_display = 0.01  # Show as "< 0.01%" indicator
            else:
                percentage_display = float(percentage.quantize(Decimal('0.01')))
            
            data.append({
                'row_num': idx,
                'item_code': row['item_code'],
                'item_name': row['item_name'],
                'amount': float(amount_dec),
                'percentage': percentage_display,
                'percentage_exact': float(percentage.quantize(Decimal('0.0001'))),
                'cumulative_amount': float(cumulative_dec),
                'cumulative_percentage': float(cumulative_percentage.quantize(Decimal('0.01'))),
                'abc_class': abc_class
            })
        
        df = pd.DataFrame(data)
        
        # Store in cache
        if use_cache:
            _cache[cache_key] = (time.time(), df)
            logger.debug(f"Cached {cache_key}")
        
        return df
    
    def clear_cache(self):
        """Clear all cached data"""
        global _cache
        _cache = {}
        logger.info("Pareto cache cleared")
    
    def get_chart_data(self, mode='خرید', category='Food', days=30, limit=10):
        """
        Get data formatted for Chart.js
        """
        df = self.calculate_pareto(mode, category, days)
        
        if df.empty:
            return {
                'labels': [],
                'amounts': [],
                'cumulative': []
            }
        
        df_limited = df.head(limit)
        
        return {
            'labels': df_limited['item_name'].tolist(),
            'amounts': df_limited['amount'].tolist(),
            'cumulative': df_limited['cumulative_percentage'].tolist()
        }
    
    def get_summary_stats(self, mode='خرید', category='Food', days=30):
        """
        Get summary statistics for dashboard
        """
        df = self.calculate_pareto(mode, category, days)
        
        if df.empty:
            return {
                'total_items': 0,
                'total_amount': 0,
                'class_a_count': 0,
                'class_b_count': 0,
                'class_c_count': 0,
                'class_a_amount': 0,
                'class_b_amount': 0,
                'class_c_amount': 0,
                'pareto_ratio': 0,
                'pareto_valid': False,
                'gini_coefficient': 0
            }
        
        total_items = len(df)
        total_amount = df['amount'].sum()
        class_a_count = len(df[df['abc_class'] == 'A'])
        class_a_amount = df[df['abc_class'] == 'A']['amount'].sum()
        
        # Pareto 80/20 validation
        # Check if ~20% of items contribute ~80% of value
        class_a_percentage_items = (class_a_count / total_items * 100) if total_items > 0 else 0
        class_a_percentage_value = (class_a_amount / total_amount * 100) if total_amount > 0 else 0
        
        # Pareto is valid if Class A items (≤30% of items) contribute ≥70% of value
        pareto_valid = class_a_percentage_items <= 35 and class_a_percentage_value >= 70
        pareto_ratio = class_a_percentage_value / class_a_percentage_items if class_a_percentage_items > 0 else 0
        
        # Calculate Gini coefficient for inequality measurement
        gini = self._calculate_gini(df['amount'].tolist())
        
        return {
            'total_items': total_items,
            'total_amount': total_amount,
            'class_a_count': class_a_count,
            'class_b_count': len(df[df['abc_class'] == 'B']),
            'class_c_count': len(df[df['abc_class'] == 'C']),
            'class_a_amount': class_a_amount,
            'class_b_amount': df[df['abc_class'] == 'B']['amount'].sum(),
            'class_c_amount': df[df['abc_class'] == 'C']['amount'].sum(),
            'class_a_pct_items': round(class_a_percentage_items, 1),
            'class_a_pct_value': round(class_a_percentage_value, 1),
            'pareto_ratio': round(pareto_ratio, 2),
            'pareto_valid': pareto_valid,
            'gini_coefficient': round(gini, 3)
        }
    
    def _calculate_gini(self, values):
        """
        Calculate Gini coefficient for measuring inequality
        0 = perfect equality, 1 = perfect inequality
        For Pareto distributions, expect 0.6-0.8
        BUG #17 FIX: Added zero division protection
        """
        if not values or len(values) < 2:
            return 0
        
        sorted_values = sorted(values)
        n = len(sorted_values)
        total = sum(sorted_values)
        
        # BUG #17 FIX: Check for zero or near-zero total
        if total == 0 or total <= 0.001:
            return 0  # Perfect equality for zero values
        
        # Alternative Gini calculation using cumulative sum
        cumsum = 0
        for i, val in enumerate(sorted_values, 1):
            cumsum += (2 * i - n - 1) * val
        
        gini = cumsum / (n * total)
        return max(0, min(1, gini))  # Clamp between 0 and 1
