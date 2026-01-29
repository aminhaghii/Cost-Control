#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
AI Analysis Routes
Llama 4 Maverick powered analysis endpoints
"""

import json
from flask import Blueprint, render_template, jsonify, request
from flask_login import login_required, current_user
from models import db, Transaction, Item
from services.pareto_service import ParetoService
from services.abc_service import ABCService
from services.llama_analyzer import WorkflowAnalyzer
from utils.timezone import get_iran_now, get_iran_today
from sqlalchemy import func

ai_bp = Blueprint('ai_analysis', __name__, url_prefix='/ai')


@ai_bp.route('/analyze-pareto')
@login_required
def analyze_pareto():
    """AI-powered Pareto analysis insights"""
    mode = request.args.get('mode', 'خرید')
    category = request.args.get('category', 'Food')
    days = int(request.args.get('days', 30))
    
    pareto_service = ParetoService()
    pareto_data = pareto_service.calculate_pareto(
        mode=mode,
        category=category,
        days=days
    )
    
    analyzer = WorkflowAnalyzer()
    
    if pareto_data is not None and not pareto_data.empty:
        pareto_dict = pareto_data.to_dict('records')
        analysis = analyzer.analyze_pareto_results(pareto_dict)
    else:
        analysis = {
            "executive_summary": "داده‌ای برای تحلیل یافت نشد.",
            "class_a_analysis": "لطفاً ابتدا تراکنش‌هایی ثبت کنید.",
            "recommendations": [],
            "risks": []
        }
    
    return render_template('ai_analysis/pareto_insights.html',
                         analysis=analysis,
                         mode=mode,
                         category=category,
                         days=days,
                         ai_available=analyzer.is_available())


@ai_bp.route('/reorder-suggestions')
@login_required
def reorder_suggestions():
    """AI-powered reorder suggestions"""
    category = request.args.get('category', 'Food')
    
    items = Item.query.filter_by(category=category).all()
    items_data = [{
        'code': item.item_code,
        'name': item.item_name_fa,
        'unit': item.unit,
        'category': item.category
    } for item in items]
    
    thirty_days_ago = get_iran_now() - timedelta(days=30)
    
    # Get consumption data
    consumption = db.session.query(
        Item.item_code,
        Item.item_name_fa,
        func.sum(Transaction.quantity).label('total_consumed'),
        func.count(Transaction.id).label('transaction_count')
    ).join(Transaction, Transaction.item_id == Item.id)\
     .filter(Transaction.transaction_type == 'مصرف')\
     .filter(Transaction.transaction_date >= thirty_days_ago)\
     .filter(Item.category == category)\
     .group_by(Item.id).all()
    
    consumption_history = [{
        'code': c.item_code,
        'name': c.item_name_fa,
        'total_consumed': float(c.total_consumed) if c.total_consumed else 0,
        'transaction_count': c.transaction_count
    } for c in consumption]
    
    # Get purchase data
    purchases = db.session.query(
        Item.item_code,
        Item.item_name_fa,
        func.sum(Transaction.quantity).label('total_purchased'),
        func.count(Transaction.id).label('transaction_count')
    ).join(Transaction, Transaction.item_id == Item.id)\
     .filter(Transaction.transaction_type == 'خرید')\
     .filter(Transaction.transaction_date >= thirty_days_ago)\
     .filter(Item.category == category)\
     .group_by(Item.id).all()
    
    purchase_history = [{
        'code': p.item_code,
        'name': p.item_name_fa,
        'total_purchased': float(p.total_purchased) if p.total_purchased else 0,
        'transaction_count': p.transaction_count
    } for p in purchases]
    
    # Get current stock
    stock_data = [{
        'code': item.item_code,
        'name': item.item_name_fa,
        'current_stock': float(item.current_stock) if item.current_stock else 0
    } for item in items]
    
    analyzer = WorkflowAnalyzer()
    suggestions = analyzer.generate_reorder_suggestions(
        items_data, 
        consumption_history, 
        purchase_history,
        stock_data
    )
    
    return render_template('ai_analysis/reorder.html',
                         suggestions=suggestions,
                         category=category,
                         ai_available=True)


@ai_bp.route('/waste-analysis')
@login_required
def waste_analysis():
    """AI-powered waste analysis"""
    category = request.args.get('category', 'Food')
    days = int(request.args.get('days', 30))
    
    start_date = get_iran_now() - timedelta(days=days)
    
    waste_transactions = db.session.query(
        Item.item_code,
        Item.item_name_fa,
        Item.category,
        Transaction.quantity,
        Transaction.total_amount,
        Transaction.transaction_date,
        Transaction.description
    ).join(Transaction, Transaction.item_id == Item.id)\
     .filter(Transaction.transaction_type == 'ضایعات')\
     .filter(Transaction.transaction_date >= start_date)\
     .filter(Item.category == category)\
     .order_by(Transaction.transaction_date.desc()).all()
    
    waste_data = [{
        'code': w.item_code,
        'name': w.item_name_fa,
        'category': w.category,
        'quantity': float(w.quantity),
        'amount': float(w.total_amount) if w.total_amount else 0,
        'date': w.transaction_date.strftime('%Y/%m/%d'),
        'notes': w.description or ''
    } for w in waste_transactions]
    
    total_waste_amount = sum(w['amount'] for w in waste_data)
    total_waste_quantity = sum(w['quantity'] for w in waste_data)
    
    analyzer = WorkflowAnalyzer()
    analysis = analyzer.analyze_waste(waste_data)
    
    return render_template('ai_analysis/waste.html',
                         analysis=analysis,
                         waste_data=waste_data,
                         total_amount=total_waste_amount,
                         total_quantity=total_waste_quantity,
                         category=category,
                         days=days,
                         ai_available=analyzer.is_available())


@ai_bp.route('/daily-insights')
@login_required
def daily_insights():
    """Get daily AI insights for dashboard"""
    today = get_iran_today()
    
    today_transactions = Transaction.query.filter(
        func.date(Transaction.transaction_date) == today
    ).count()
    
    today_purchases = db.session.query(func.sum(Transaction.total_amount))\
        .filter(Transaction.transaction_type == 'خرید')\
        .filter(func.date(Transaction.transaction_date) == today).scalar() or 0
    
    today_waste = db.session.query(func.sum(Transaction.total_amount))\
        .filter(Transaction.transaction_type == 'ضایعات')\
        .filter(func.date(Transaction.transaction_date) == today).scalar() or 0
    
    total_items = Item.query.count()
    
    kpi_data = {
        'today_transactions': today_transactions,
        'today_purchases': float(today_purchases),
        'today_waste': float(today_waste),
        'total_items': total_items,
        'date': today.strftime('%Y/%m/%d')
    }
    
    analyzer = WorkflowAnalyzer()
    insights_raw = analyzer.get_daily_insights(kpi_data) or []
    
    # Normalize insights to avoid undefined links/text
    insights = []
    for ins in insights_raw:
        if not isinstance(ins, dict):
            continue
        icon = ins.get('icon', '📊')
        text = ins.get('text', 'بینش جدید')
        link = ins.get('link') or '/reports/pareto'
        type_ = ins.get('type', 'info')
        insights.append({
            'icon': icon,
            'text': text,
            'link': link,
            'type': type_
        })
    
    if not insights:
        insights = [
            {
                "icon": "📊",
                "text": "کالاهای کلاس A نیاز به بررسی دارند",
                "type": "info",
                "link": "/reports/pareto"
            },
            {
                "icon": "⚠️",
                "text": "روند ضایعات افزایشی است",
                "type": "warning",
                "link": "/reports/abc"
            },
            {
                "icon": "✅",
                "text": "موجودی کالاهای اصلی کافی است",
                "type": "success",
                "link": "/transactions/"
            }
        ]
    
    return jsonify({
        'success': True,
        'insights': insights,
        'ai_available': analyzer.is_available()
    })


@ai_bp.route('/test-connection')
@login_required
def test_connection():
    """Test AI API connection with human-readable output"""
    analyzer = WorkflowAnalyzer()
    parsed_response = None
    
    if analyzer.is_available():
        test_result = analyzer._call_api("سلام، یک تست ساده. فقط بگو: تست موفق", max_tokens=50)
        
        try:
            parsed_response = json.loads(test_result)
        except Exception:
            parsed_response = None
        
        return render_template(
            'ai_analysis/test_connection.html',
            success=True,
            message='اتصال به API برقرار است',
            response=test_result,
            parsed_response=parsed_response,
            model=analyzer.model,
            ai_available=True
        )
    else:
        return render_template(
            'ai_analysis/test_connection.html',
            success=False,
            message='API در دسترس نیست. GROQ_API_KEY را بررسی کنید.',
            response='ارتباط برقرار نشد',
            parsed_response=None,
            model=analyzer.model,
            ai_available=False
        )
