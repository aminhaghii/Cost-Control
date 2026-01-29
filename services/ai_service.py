"""
AI Service - Smart Analytics for Inventory Management
Provides intelligent features like trend-based reorder prediction and dead stock analysis
"""
from datetime import datetime, timedelta
from sqlalchemy import func, and_
from models import db, Transaction, Item
from utils.timezone import get_iran_today
import logging

logger = logging.getLogger(__name__)


class AIService:
    """
    AI-powered analytics service for smart inventory management
    """
    
    @staticmethod
    def calculate_reorder_suggestion(item_id, days=90):
        """
        Smart Reorder Prediction using Trend Analysis
        
        Algorithm:
        1. Fetch consumption data for last 90 days, grouped by month
        2. Calculate trend factor (slope): (Month3 - Month1) / Month1
        3. Predict next month usage: Average * (1 + Trend_Factor)
        4. Suggest order: Prediction - Current_Stock (minimum 0)
        
        Args:
            item_id: ID of the item to analyze
            days: Number of days to analyze (default 90 for 3 months)
        
        Returns:
            dict with keys:
                - item_id
                - item_name
                - current_stock
                - avg_monthly_consumption
                - trend_factor (slope)
                - predicted_next_month
                - suggested_order
                - trend_direction ('up', 'down', 'stable')
        """
        item = Item.query.get(item_id)
        if not item:
            return None
        
        today = get_iran_today()
        start_date = today - timedelta(days=days)
        
        # Fetch consumption transactions for last 90 days
        consumptions = db.session.query(
            func.date_trunc('month', Transaction.transaction_date).label('month'),
            func.sum(Transaction.quantity).label('total_qty')
        ).filter(
            Transaction.item_id == item_id,
            Transaction.transaction_type == 'مصرف',
            Transaction.transaction_date >= start_date,
            Transaction.is_deleted == False
        ).group_by(
            func.date_trunc('month', Transaction.transaction_date)
        ).order_by(
            func.date_trunc('month', Transaction.transaction_date)
        ).all()
        
        if not consumptions or len(consumptions) == 0:
            # No consumption data - suggest based on min_stock
            return {
                'item_id': item.id,
                'item_name': item.item_name_fa,
                'current_stock': item.current_stock,
                'avg_monthly_consumption': 0,
                'trend_factor': 0,
                'predicted_next_month': 0,
                'suggested_order': max(0, item.min_stock - item.current_stock),
                'trend_direction': 'no_data',
                'confidence': 'low'
            }
        
        # Extract monthly totals
        monthly_totals = [float(c.total_qty) for c in consumptions]
        avg_monthly = sum(monthly_totals) / len(monthly_totals)
        
        # Calculate trend factor (slope)
        if len(monthly_totals) >= 2:
            first_month = monthly_totals[0]
            last_month = monthly_totals[-1]
            
            if first_month > 0:
                trend_factor = (last_month - first_month) / first_month
            else:
                trend_factor = 0
        else:
            trend_factor = 0
        
        # Predict next month usage
        predicted_next_month = avg_monthly * (1 + trend_factor)
        
        # Suggested order quantity
        suggested_order = max(0, predicted_next_month - item.current_stock)
        
        # Determine trend direction
        if trend_factor > 0.1:
            trend_direction = 'up'
        elif trend_factor < -0.1:
            trend_direction = 'down'
        else:
            trend_direction = 'stable'
        
        # Confidence level based on data points
        if len(monthly_totals) >= 3:
            confidence = 'high'
        elif len(monthly_totals) >= 2:
            confidence = 'medium'
        else:
            confidence = 'low'
        
        return {
            'item_id': item.id,
            'item_name': item.item_name_fa,
            'item_code': item.item_code,
            'unit': item.unit,
            'current_stock': float(item.current_stock),
            'min_stock': float(item.min_stock),
            'avg_monthly_consumption': round(avg_monthly, 2),
            'trend_factor': round(trend_factor, 3),
            'predicted_next_month': round(predicted_next_month, 2),
            'suggested_order': round(suggested_order, 2),
            'trend_direction': trend_direction,
            'confidence': confidence,
            'data_points': len(monthly_totals)
        }
    
    @staticmethod
    def get_procurement_plan(min_confidence='low'):
        """
        Generate procurement plan for all active items
        
        Args:
            min_confidence: Minimum confidence level ('low', 'medium', 'high')
        
        Returns:
            List of reorder suggestions sorted by priority
        """
        # SINGLE HOTEL MODE: No hotel filtering needed
        query = Item.query.filter(Item.is_active == True)
        
        items = query.all()
        
        suggestions = []
        for item in items:
            suggestion = AIService.calculate_reorder_suggestion(item.id)
            if suggestion and suggestion['suggested_order'] > 0:
                # Filter by confidence
                confidence_levels = {'low': 0, 'medium': 1, 'high': 2}
                if confidence_levels.get(suggestion['confidence'], 0) >= confidence_levels.get(min_confidence, 0):
                    suggestions.append(suggestion)
        
        # Sort by suggested order quantity (descending)
        suggestions.sort(key=lambda x: x['suggested_order'], reverse=True)
        
        return suggestions
    
    @staticmethod
    def analyze_dead_stock(inactive_days=60):
        """
        Dead Stock Hunter - Find items with no recent consumption (frozen capital)
        
        Args:
            inactive_days: Number of days without consumption to consider dead (default 60)
        
        Returns:
            dict with keys:
                - dead_items: List of dead stock items
                - total_frozen_capital: Total value of dead stock
                - total_items: Count of dead items
        """
        today = get_iran_today()
        cutoff_date = today - timedelta(days=inactive_days)
        
        # SINGLE HOTEL MODE: Query all items with stock (no hotel filtering)
        query = Item.query.filter(
            Item.is_active == True,
            Item.current_stock > 0
        )
        
        items = query.all()
        
        dead_items = []
        total_frozen_capital = 0
        
        for item in items:
            # Find last consumption date
            last_consumption = db.session.query(
                func.max(Transaction.transaction_date)
            ).filter(
                Transaction.item_id == item.id,
                Transaction.transaction_type == 'مصرف',
                Transaction.is_deleted == False
            ).scalar()
            
            # Check if item is dead stock
            is_dead = False
            days_inactive = None
            
            if last_consumption is None:
                # Never consumed
                is_dead = True
                # Calculate days since item was created
                days_inactive = (today - item.created_at.date()).days if item.created_at else 999
            elif last_consumption < cutoff_date:
                # Not consumed recently
                is_dead = True
                days_inactive = (today - last_consumption).days
            
            if is_dead:
                frozen_value = float(item.current_stock * item.unit_price)
                total_frozen_capital += frozen_value
                
                dead_items.append({
                    'item_id': item.id,
                    'item_code': item.item_code,
                    'item_name': item.item_name_fa,
                    'category': item.category,
                    'unit': item.unit,
                    'current_stock': float(item.current_stock),
                    'unit_price': float(item.unit_price),
                    'frozen_value': frozen_value,
                    'last_consumption_date': last_consumption,
                    'days_inactive': days_inactive,
                    'status': 'never_used' if last_consumption is None else 'inactive'
                })
        
        # Sort by frozen value (descending)
        dead_items.sort(key=lambda x: x['frozen_value'], reverse=True)
        
        return {
            'dead_items': dead_items,
            'total_frozen_capital': total_frozen_capital,
            'total_items': len(dead_items),
            'inactive_threshold_days': inactive_days
        }
