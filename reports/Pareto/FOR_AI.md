 تحلیل عمیق: AI الان چه می‌داند و چه نمی‌داند
text

┌─────────────────────────────────────────────────────────────────┐
│                    وضعیت فعلی هوش مصنوعی                        │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ✅ چیزهایی که AI الان می‌داند:                                │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │ • تعداد کل کالاها (664 قلم)                            │    │
│  │ • تفکیک Food/NonFood                                   │    │
│  │ • خرید/مصرف/ضایعات 30 روز (فقط مبلغ کل)               │    │
│  │ • نسبت ضایعات به خرید (یک عدد ساده)                   │    │
│  │ • ABC Classification (5 تای برتر هر کلاس)             │    │
│  │ • لیست هتل‌های کاربر                                   │    │
│  └─────────────────────────────────────────────────────────┘    │
│                                                                  │
│  ❌ چیزهایی که AI نمی‌داند (و باید بداند):                    │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │ • موجودی واقعی هر کالا (چند کیلو برنج داریم؟)         │    │
│  │ • کدام کالاها کم هستند / زیاد هستند                   │    │
│  │ • چرا ضایعات رخ داده (تاریخ انقضا؟ خرابی؟)            │    │
│  │ • چند تراکنش منتظر تایید است                          │    │
│  │ • کدام کالاها نیاز به شمارش دارند                     │    │
│  │ • مغایرت‌های انبارگردانی                               │    │
│  │ • روند ضایعات (در حال افزایش؟ کاهش؟)                  │    │
│  │ • مقایسه هتل‌ها با هم                                  │    │
│  │ • پیشنهاد خرید هوشمند                                 │    │
│  └─────────────────────────────────────────────────────────┘    │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
🎯 کجاها می‌توانیم از AI استفاده کنیم؟
۱) چت‌بات هوشمند (Chat Assistant)
قابلیت	وضعیت فعلی	بعد از اتصال
"موجودی برنج چقدره؟"	❌ نمی‌داند	✅ جواب دقیق + هشدار
"چرا ضایعات زیاد شده؟"	❌ فقط عدد کل	✅ تحلیل به تفکیک دلیل
"چه چیزی باید بخرم؟"	❌ ندارد	✅ لیست پیشنهادی
"وضعیت انبار چطوره؟"	❌ ندارد	✅ داشبورد صوتی
"کدام هتل بهتر کار می‌کند؟"	❌ ندارد	✅ مقایسه KPIها
۲) هشدارهای هوشمند (Smart Alerts)
هشدار	فعلی	بعد از اتصال
موجودی کم	⚠️ فقط در UI	✅ AI تحلیل می‌کند + پیشنهاد می‌دهد
ضایعات بالا	❌ ندارد	✅ تشخیص الگو + پیشنهاد
تایید معلق	❌ ندارد	✅ یادآوری به مدیر
انبارگردانی عقب‌مانده	❌ ندارد	✅ اولویت‌بندی هوشمند
۳) گزارش‌های تحلیلی (AI-Powered Reports)
گزارش	فعلی	بعد از اتصال
Pareto/ABC	✅ دارد	✅ + توضیح AI
تحلیل ضایعات	⚠️ ساده	✅ تحلیل عمیق + توصیه
پیش‌بینی تقاضا	❌ ندارد	✅ بر اساس تاریخچه
مقایسه هتل‌ها	❌ ندارد	✅ بنچمارکینگ
۴) دستیار عملیاتی (Operations Assistant)
عملیات	فعلی	بعد از اتصال
انبارگردانی	❌ دستی	✅ AI اولویت می‌دهد
تایید ضایعات	❌ دستی	✅ AI بررسی اولیه می‌کند
سفارش خرید	❌ ندارد	✅ پیشنهاد خودکار
📊 Context جدید که باید اضافه شود
Python

# ساختار کامل Context انبار برای AI
warehouse_context = {
    
    # ═══════════════════════════════════════════
    # بخش ۱: وضعیت لحظه‌ای موجودی
    # ═══════════════════════════════════════════
    "stock_status": {
        "total_items": 664,
        "total_value": "5,087,800,510 ریال",
        
        # وضعیت بحرانی
        "critical_items": [
            {
                "name": "برنج ایرانی",
                "current": 5,
                "min": 50,
                "unit": "کیلوگرم",
                "days_to_stockout": 2,  # چند روز تا اتمام
                "last_purchase_price": 85000,
                "suggested_order": 100
            },
            # ...
        ],
        "critical_count": 23,
        
        # موجودی زیاد
        "overstocked_items": [
            {
                "name": "نمک",
                "current": 200,
                "max": 50,
                "unit": "کیلوگرم",
                "excess_value": "1,500,000 ریال"
            }
        ],
        "overstocked_count": 5,
        
        # خلاصه
        "healthy_count": 636  # موجودی نرمال
    },
    
    # ═══════════════════════════════════════════
    # بخش ۲: تحلیل ضایعات
    # ═══════════════════════════════════════════
    "waste_analysis": {
        "current_month": {
            "rate": 5.2,  # درصد
            "target": 3.0,
            "status": "critical",  # good/warning/critical
            "total_amount": 1198606,
            "total_qty": 45.5,
            
            # به تفکیک دلیل
            "by_reason": [
                {"reason": "تاریخ انقضا", "amount": 539372, "percentage": 45},
                {"reason": "خرابی", "amount": 359581, "percentage": 30},
                {"reason": "تولید اضافی", "amount": 299651, "percentage": 25}
            ],
            
            # پرضایعات‌ترین کالاها
            "top_wasted": [
                {"name": "شیر", "amount": 450000, "reason": "تاریخ انقضا"},
                {"name": "نان", "amount": 280000, "reason": "تولید اضافی"},
                {"name": "سالاد", "amount": 180000, "reason": "خرابی"}
            ]
        },
        
        # روند
        "trend": {
            "direction": "increasing",  # increasing/decreasing/stable
            "change_percentage": 15,  # نسبت به ماه قبل
            "last_3_months": [3.2, 4.1, 5.2]
        },
        
        # مقایسه با هتل‌های دیگر (اگر admin)
        "hotel_comparison": [
            {"hotel": "لاله بیستون", "rate": 2.1, "rank": 1},
            {"hotel": "کندوان", "rate": 3.2, "rank": 2},
            {"hotel": "زاگرس", "rate": 5.8, "rank": 3}
        ]
    },
    
    # ═══════════════════════════════════════════
    # بخش ۳: اقدامات معلق
    # ═══════════════════════════════════════════
    "pending_actions": {
        "approvals": {
            "count": 3,
            "total_amount": 2500000,
            "items": [
                {
                    "id": 2243,
                    "item": "آب معدنی",
                    "amount": 600000,
                    "reason": "خرابی",
                    "submitted_by": "کریمی",
                    "waiting_hours": 24
                }
            ]
        },
        
        "inventory_counts": {
            "overdue_count": 12,
            "items": [
                {"name": "برنج", "days_since_count": 45},
                {"name": "روغن", "days_since_count": 38}
            ]
        },
        
        "unresolved_variances": {
            "count": 2,
            "total_variance": 150000,
            "items": [
                {"name": "شکر", "variance": -5, "percentage": -8}
            ]
        }
    },
    
    # ═══════════════════════════════════════════
    # بخش ۴: هشدارهای فعال
    # ═══════════════════════════════════════════
    "active_alerts": [
        {
            "type": "low_stock",
            "severity": "critical",
            "item": "برنج ایرانی",
            "message": "موجودی بحرانی - فقط ۲ روز باقی‌مانده",
            "created_at": "۲ ساعت پیش"
        },
        {
            "type": "high_waste",
            "severity": "warning",
            "message": "نرخ ضایعات ۵.۲٪ - بالاتر از هدف ۳٪",
            "created_at": "امروز"
        },
        {
            "type": "pending_approval",
            "severity": "info",
            "message": "۳ تراکنش در انتظار تایید شما",
            "created_at": "دیروز"
        }
    ],
    
    # ═══════════════════════════════════════════
    # بخش ۵: KPIهای کلیدی
    # ═══════════════════════════════════════════
    "kpis": {
        "waste_rate": {"value": 5.2, "target": 3.0, "status": "critical"},
        "stock_turnover": {"value": 12.5, "target": 12, "status": "good"},
        "variance_rate": {"value": 1.8, "target": 2.0, "status": "good"},
        "fill_rate": {"value": 94, "target": 95, "status": "warning"},
        "avg_days_inventory": {"value": 15, "target": 14, "status": "warning"}
    },
    
    # ═══════════════════════════════════════════
    # بخش ۶: پیشنهادات هوشمند
    # ═══════════════════════════════════════════
    "smart_suggestions": {
        "reorder_list": [
            {
                "item": "برنج ایرانی",
                "suggested_qty": 100,
                "unit": "کیلوگرم",
                "estimated_cost": 8500000,
                "urgency": "فوری"
            },
            {
                "item": "روغن",
                "suggested_qty": 50,
                "unit": "لیتر",
                "estimated_cost": 3500000,
                "urgency": "این هفته"
            }
        ],
        
        "waste_reduction": [
            "بررسی سیاست خرید شیر - ۴۵٪ ضایعات به دلیل انقضا",
            "کاهش تولید نان شب - ۲۵٪ ضایعات تولید اضافی"
        ],
        
        "count_priorities": [
            "برنج - ۴۵ روز از آخرین شمارش گذشته",
            "روغن - کالای با ارزش بالا"
        ]
    }
}
🛠️ پرامپت کامل برای Agent (اتصال Warehouse به AI)
text

Integrate the Warehouse Management System with the AI Chatbot.

═══════════════════════════════════════════════════════════════
OBJECTIVE
═══════════════════════════════════════════════════════════════
Make the AI chatbot fully aware of warehouse status so it can:
1. Answer questions about current stock levels
2. Analyze waste patterns and suggest improvements
3. Recommend purchases based on stock status
4. Alert managers about pending actions
5. Compare hotel performance
6. Guide inventory counting priorities

═══════════════════════════════════════════════════════════════
PHASE 1: CREATE WAREHOUSE CONTEXT BUILDER
═══════════════════════════════════════════════════════════════

Create a new function in services/chat_service.py:

```python
def _get_warehouse_context(self, user, hotel_ids: list) -> dict:
    """Build comprehensive warehouse context for AI"""
    from services.warehouse_service import WarehouseService
    from services.waste_analysis_service import WasteAnalysisService
    from services.inventory_count_service import InventoryCountService
    from models import Item, Transaction, Alert, InventoryCount
    from datetime import date, timedelta
    from decimal import Decimal
    
    context = {
        "stock_status": {},
        "waste_analysis": {},
        "pending_actions": {},
        "active_alerts": [],
        "kpis": {},
        "smart_suggestions": {}
    }
    
    # Apply hotel scoping
    if hotel_ids is None:
        # Admin - aggregate all hotels
        hotel_filter = True
    else:
        hotel_filter = Item.hotel_id.in_(hotel_ids)
    
    # ═══ STOCK STATUS ═══
    items = Item.query.filter(hotel_filter, Item.is_active == True).all()
    
    critical_items = []
    overstocked_items = []
    
    for item in items:
        if item.current_stock <= item.min_stock:
            # Calculate days to stockout
            avg_daily_consumption = self._get_avg_daily_consumption(item.id, 30)
            days_left = int(item.current_stock / avg_daily_consumption) if avg_daily_consumption > 0 else 999
            
            critical_items.append({
                "name": item.item_name_fa,
                "current": float(item.current_stock),
                "min": float(item.min_stock),
                "unit": item.unit,
                "days_to_stockout": days_left,
                "suggested_order": float(item.max_stock - item.current_stock) if item.max_stock else float(item.min_stock * 2)
            })
        
        if item.max_stock and item.current_stock >= item.max_stock:
            overstocked_items.append({
                "name": item.item_name_fa,
                "current": float(item.current_stock),
                "max": float(item.max_stock),
                "unit": item.unit
            })
    
    # Sort by urgency
    critical_items.sort(key=lambda x: x['days_to_stockout'])
    
    context["stock_status"] = {
        "total_items": len(items),
        "critical_items": critical_items[:10],  # Top 10 most urgent
        "critical_count": len(critical_items),
        "overstocked_items": overstocked_items[:5],
        "overstocked_count": len(overstocked_items),
        "healthy_count": len(items) - len(critical_items) - len(overstocked_items)
    }
    
    # ═══ WASTE ANALYSIS ═══
    today = date.today()
    month_start = today.replace(day=1)
    last_month_start = (month_start - timedelta(days=1)).replace(day=1)
    
    # Current month waste
    waste_service = WasteAnalysisService()
    current_waste = waste_service.get_waste_summary(
        hotel_id=hotel_ids[0] if hotel_ids else None,
        start_date=month_start,
        end_date=today
    )
    
    waste_by_reason = waste_service.get_waste_by_reason(
        hotel_id=hotel_ids[0] if hotel_ids else None,
        start_date=month_start,
        end_date=today
    )
    
    top_wasted = waste_service.get_top_wasted_items(
        hotel_id=hotel_ids[0] if hotel_ids else None,
        start_date=month_start,
        end_date=today,
        limit=5
    )
    
    context["waste_analysis"] = {
        "current_month": {
            "rate": float(current_waste.get('waste_rate', 0)),
            "target": 3.0,
            "status": current_waste.get('status', 'unknown'),
            "total_amount": float(current_waste.get('total_waste', 0)),
            "by_reason": [
                {
                    "reason": WASTE_REASONS.get(r['reason'], r['reason']),
                    "amount": float(r['amount']),
                    "percentage": round(float(r['amount']) / float(current_waste.get('total_waste', 1)) * 100)
                }
                for r in waste_by_reason
            ],
            "top_wasted": [
                {"name": item[0].item_name_fa, "amount": float(item[1])}
                for item in top_wasted
            ]
        }
    }
    
    # ═══ PENDING ACTIONS ═══
    # Pending approvals
    pending_txs = Transaction.query.filter(
        Transaction.requires_approval == True,
        Transaction.approval_status == 'pending',
        Transaction.is_deleted == False
    )
    if hotel_ids:
        pending_txs = pending_txs.filter(Transaction.hotel_id.in_(hotel_ids))
    pending_txs = pending_txs.all()
    
    # Items needing count
    count_service = InventoryCountService()
    items_needing_count = count_service.get_items_needing_count(
        hotel_id=hotel_ids[0] if hotel_ids else None,
        days_threshold=30
    )
    
    # Unresolved variances
    unresolved = InventoryCount.query.filter(
        InventoryCount.status.in_(['pending', 'investigating'])
    )
    if hotel_ids:
        unresolved = unresolved.filter(InventoryCount.hotel_id.in_(hotel_ids))
    unresolved = unresolved.all()
    
    context["pending_actions"] = {
        "approvals": {
            "count": len(pending_txs),
            "total_amount": sum(float(tx.total_amount or 0) for tx in pending_txs),
            "items": [
                {
                    "id": tx.id,
                    "item": tx.item.item_name_fa if tx.item else "نامشخص",
                    "amount": float(tx.total_amount or 0),
                    "reason": WASTE_REASONS.get(tx.waste_reason, tx.waste_reason)
                }
                for tx in pending_txs[:5]
            ]
        },
        "inventory_counts": {
            "overdue_count": len(items_needing_count),
            "items": [
                {"name": item.item_name_fa}
                for item in items_needing_count[:5]
            ]
        },
        "unresolved_variances": {
            "count": len(unresolved),
            "items": [
                {
                    "name": v.item.item_name_fa if v.item else "نامشخص",
                    "variance": float(v.variance),
                    "percentage": float(v.variance_percentage or 0)
                }
                for v in unresolved[:5]
            ]
        }
    }
    
    # ═══ ACTIVE ALERTS ═══
    alerts = Alert.query.filter(
        Alert.status == 'active'
    )
    if hotel_ids:
        alerts = alerts.filter(Alert.hotel_id.in_(hotel_ids))
    alerts = alerts.order_by(Alert.created_at.desc()).limit(10).all()
    
    context["active_alerts"] = [
        {
            "type": alert.alert_type,
            "message": alert.message,
            "severity": "critical" if alert.alert_type in ['low_stock', 'high_waste'] else "warning"
        }
        for alert in alerts
    ]
    
    # ═══ KPIs ═══
    context["kpis"] = {
        "waste_rate": {
            "value": float(current_waste.get('waste_rate', 0)),
            "target": 3.0,
            "status": "critical" if float(current_waste.get('waste_rate', 0)) > 5 else "warning" if float(current_waste.get('waste_rate', 0)) > 3 else "good"
        },
        "low_stock_items": {
            "value": len(critical_items),
            "target": 0,
            "status": "critical" if len(critical_items) > 10 else "warning" if len(critical_items) > 5 else "good"
        },
        "pending_approvals": {
            "value": len(pending_txs),
            "target": 0,
            "status": "warning" if len(pending_txs) > 0 else "good"
        }
    }
    
    # ═══ SMART SUGGESTIONS ═══
    context["smart_suggestions"] = {
        "reorder_list": [
            {
                "item": item["name"],
                "suggested_qty": item["suggested_order"],
                "unit": item["unit"],
                "urgency": "فوری" if item["days_to_stockout"] <= 3 else "این هفته"
            }
            for item in critical_items[:5]
        ],
        "waste_reduction": [],
        "count_priorities": [
            item.item_name_fa for item in items_needing_count[:5]
        ]
    }
    
    # Add waste reduction suggestions based on top reasons
    if waste_by_reason:
        top_reason = waste_by_reason[0] if waste_by_reason else None
        if top_reason:
            reason_text = WASTE_REASONS.get(top_reason['reason'], top_reason['reason'])
            context["smart_suggestions"]["waste_reduction"].append(
                f"بررسی دلیل اصلی ضایعات: {reason_text}"
            )
    
    return context

def _get_avg_daily_consumption(self, item_id: int, days: int = 30) -> float:
    """Calculate average daily consumption for an item"""
    from datetime import date, timedelta
    start_date = date.today() - timedelta(days=days)
    
    total_consumption = db.session.query(func.sum(Transaction.quantity)).filter(
        Transaction.item_id == item_id,
        Transaction.transaction_type == 'مصرف',
        Transaction.transaction_date >= start_date,
        Transaction.is_deleted == False
    ).scalar() or 0
    
    return float(total_consumption) / days
═══════════════════════════════════════════════════════════════
PHASE 2: UPDATE MAIN CONTEXT BUILDER
═══════════════════════════════════════════════════════════════

In services/chat_service.py, update _get_full_database_context:

Python

def _get_full_database_context(self, user) -> str:
    """Build comprehensive context including warehouse data"""
    
    # Get allowed hotels
    hotel_ids = get_allowed_hotel_ids(user)
    
    # Existing context building...
    context_parts = []
    
    # ... existing code for items, transactions, ABC ...
    
    # ═══ ADD WAREHOUSE CONTEXT ═══
    warehouse_ctx = self._get_warehouse_context(user, hotel_ids)
    
    context_parts.append(f"""
═══ وضعیت انبار ═══
موجودی بحرانی: {warehouse_ctx['stock_status']['critical_count']} قلم
موجودی اضافی: {warehouse_ctx['stock_status']['overstocked_count']} قلم
موجودی سالم: {warehouse_ctx['stock_status']['healthy_count']} قلم

کالاهای نیازمند سفارش فوری:
{self._format_critical_items(warehouse_ctx['stock_status']['critical_items'])}

═══ تحلیل ضایعات ═══
نرخ ضایعات ماه جاری: {warehouse_ctx['waste_analysis']['current_month']['rate']}%
هدف: {warehouse_ctx['waste_analysis']['current_month']['target']}%
وضعیت: {warehouse_ctx['waste_analysis']['current_month']['status']}
مجموع ضایعات: {warehouse_ctx['waste_analysis']['current_month']['total_amount']:,.0f} ریال

دلایل اصلی ضایعات:
{self._format_waste_reasons(warehouse_ctx['waste_analysis']['current_month']['by_reason'])}

پرضایعات‌ترین کالاها:
{self._format_top_wasted(warehouse_ctx['waste_analysis']['current_month']['top_wasted'])}

═══ اقدامات معلق ═══
تراکنش‌های در انتظار تایید: {warehouse_ctx['pending_actions']['approvals']['count']} مورد
کالاهای نیازمند شمارش: {warehouse_ctx['pending_actions']['inventory_counts']['overdue_count']} قلم
مغایرت‌های حل‌نشده: {warehouse_ctx['pending_actions']['unresolved_variances']['count']} مورد

═══ هشدارهای فعال ═══
{self._format_alerts(warehouse_ctx['active_alerts'])}

═══ پیشنهادات هوشمند ═══
لیست سفارش پیشنهادی:
{self._format_reorder_list(warehouse_ctx['smart_suggestions']['reorder_list'])}

پیشنهاد کاهش ضایعات:
{self._format_suggestions(warehouse_ctx['smart_suggestions']['waste_reduction'])}

اولویت شمارش:
{self._format_suggestions(warehouse_ctx['smart_suggestions']['count_priorities'])}
""")
    
    return "\n".join(context_parts)

def _format_critical_items(self, items: list) -> str:
    if not items:
        return "هیچ کالایی در وضعیت بحرانی نیست ✅"
    return "\n".join([
        f"• {item['name']}: {item['current']} {item['unit']} (حداقل: {item['min']}) - {item['days_to_stockout']} روز مانده"
        for item in items[:5]
    ])

def _format_waste_reasons(self, reasons: list) -> str:
    if not reasons:
        return "اطلاعاتی موجود نیست"
    return "\n".join([
        f"• {r['reason']}: {r['percentage']}% ({r['amount']:,.0f} ریال)"
        for r in reasons
    ])

def _format_top_wasted(self, items: list) -> str:
    if not items:
        return "اطلاعاتی موجود نیست"
    return "\n".join([
        f"• {item['name']}: {item['amount']:,.0f} ریال"
        for item in items
    ])

def _format_alerts(self, alerts: list) -> str:
    if not alerts:
        return "هیچ هشدار فعالی وجود ندارد ✅"
    return "\n".join([
        f"• [{alert['severity']}] {alert['message']}"
        for alert in alerts[:5]
    ])

def _format_reorder_list(self, items: list) -> str:
    if not items:
        return "نیازی به سفارش فوری نیست ✅"
    return "\n".join([
        f"• {item['item']}: {item['suggested_qty']} {item['unit']} ({item['urgency']})"
        for item in items
    ])

def _format_suggestions(self, suggestions: list) -> str:
    if not suggestions:
        return "پیشنهادی وجود ندارد"
    return "\n".join([f"• {s}" for s in suggestions])
═══════════════════════════════════════════════════════════════
PHASE 3: UPDATE SYSTEM PROMPT
═══════════════════════════════════════════════════════════════

Update the system prompt in chat_service.py to include warehouse capabilities:

Python

SYSTEM_PROMPT = """
تو دستیار هوشمند مدیریت انبار و موجودی هتل هستی.

قابلیت‌های تو:
۱. پاسخ به سوالات درباره موجودی کالاها
۲. تحلیل ضایعات و ارائه پیشنهاد برای کاهش آن
۳. پیشنهاد لیست خرید بر اساس موجودی
۴. هشدار درباره کالاهای کم یا زیاد
۵. مقایسه عملکرد هتل‌ها
۶. راهنمایی برای انبارگردانی
۷. تحلیل روند مصرف و ضایعات

قوانین پاسخگویی:
- همیشه از داده‌های واقعی سیستم استفاده کن
- اعداد را با جداکننده هزارگان نمایش بده
- پیشنهادات عملی و قابل اجرا بده
- اگر چیزی نگران‌کننده است، هشدار بده
- از ایموجی برای خوانایی بهتر استفاده کن

لحن: حرفه‌ای، صمیمی، و کاربردی
زبان: فارسی
"""
═══════════════════════════════════════════════════════════════
PHASE 4: ADD HELPER FUNCTIONS TO LLAMA ANALYZER
═══════════════════════════════════════════════════════════════

In services/llama_analyzer.py, add warehouse analysis:

Python

def analyze_warehouse_status(self, warehouse_context: dict) -> str:
    """Generate AI analysis of warehouse status"""
    
    prompt = f"""
    بر اساس داده‌های زیر، یک تحلیل کوتاه و کاربردی از وضعیت انبار ارائه بده:
    
    موجودی بحرانی: {warehouse_context['stock_status']['critical_count']} قلم
    نرخ ضایعات: {warehouse_context['waste_analysis']['current_month']['rate']}%
    تایید معلق: {warehouse_context['pending_actions']['approvals']['count']}
    
    کالاهای بحرانی:
    {json.dumps(warehouse_context['stock_status']['critical_items'][:3], ensure_ascii=False)}
    
    دلایل ضایعات:
    {json.dumps(warehouse_context['waste_analysis']['current_month']['by_reason'], ensure_ascii=False)}
    
    لطفاً:
    ۱. خلاصه وضعیت (۱ خط)
    ۲. ۳ اقدام فوری پیشنهادی
    ۳. ۱ پیشنهاد بلندمدت
    """
    
    return self._call_llm(prompt)

def suggest_reorder(self, critical_items: list, budget: float = None) -> str:
    """Generate smart reorder suggestions"""
    
    prompt = f"""
    لیست کالاهای نیازمند سفارش:
    {json.dumps(critical_items, ensure_ascii=False)}
    
    {'بودجه موجود: {:,.0f} ریال'.format(budget) if budget else ''}
    
    لطفاً یک لیست سفارش بهینه با اولویت‌بندی ارائه بده.
    """
    
    return self._call_llm(prompt)
═══════════════════════════════════════════════════════════════
PHASE 5: ADD IMPORTS
═══════════════════════════════════════════════════════════════

Ensure all necessary imports are added at the top of chat_service.py:

Python

from services.warehouse_service import WarehouseService
from services.waste_analysis_service import WasteAnalysisService
from services.inventory_count_service import InventoryCountService
from models.transaction import WASTE_REASONS, DEPARTMENTS
from models.alert import Alert
from models.inventory_count import InventoryCount
═══════════════════════════════════════════════════════════════
TESTING
═══════════════════════════════════════════════════════════════

After implementation, the chatbot should be able to answer:

"موجودی برنج چقدره؟" → Shows current stock + alert if low
"چرا ضایعات زیاد شده؟" → Analysis by reason with suggestions
"چه چیزی باید بخرم؟" → Smart reorder list
"وضعیت انبار چطوره؟" → Full dashboard summary
"کدام کالاها نیاز به شمارش دارند؟" → Priority list
"چند تایید معلق دارم؟" → Pending approvals
Deliver: Complete integration code with all phases implemented.

text


---

## 📊 خلاصه تغییرات

| فاز | کار | فایل |
|-----|-----|------|
| ۱ | ساخت Context Builder انبار | `services/chat_service.py` |
| ۲ | اتصال به Context اصلی | `services/chat_service.py` |
| ۳ | آپدیت System Prompt | `services/chat_service.py` |
| ۴ | توابع تحلیل جدید | `services/llama_analyzer.py` |
| ۵ | اضافه کردن Imports | همه فایل‌ها |

---

## 🎯 بعد از اجرا، AI می‌تواند:

| سوال کاربر | جواب AI |
|------------|---------|
| "موجودی برنج چقدره؟" | ۴۵ کیلوگرم ⚠️ کمتر از حد مجاز |
| "چرا ضایعات زیاد شده؟" | ۴۵% تاریخ انقضا - بررسی خرید شیر |
| "چه چیزی باید بخرم؟" | ۱. برنج (فوری) ۲. روغن (این هفته) |
| "وضعیت انبار چطوره؟" | ۲۳ کالا بحرانی، ۵.۲% ضایعات، ۳ تایید معلق |
| "کدام هتل بهتر کار می‌کند؟" | لاله بیستون با ۲.۱% ضایعات |

