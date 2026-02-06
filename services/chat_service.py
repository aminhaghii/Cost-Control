"""
Intelligent Analytics Chatbot Service with GROQ LLM
Responds to any question using database context + GROQ AI
Includes per-user conversation memory and context window management
P0-9: Scoped summaries - chatbot only sees allowed hotels
"""

from datetime import datetime, timedelta, date
from sqlalchemy import func, desc
from models import db
from models.item import Item
from models.transaction import Transaction
from models.chat_history import ChatHistory
from models.alert import Alert
from models.inventory_count import InventoryCount
from models.transaction import WASTE_REASONS, DEPARTMENTS
from services.pareto_service import ParetoService
from services.abc_service import ABCService
from services.warehouse_service import WarehouseService
from services.waste_analysis_service import WasteAnalysisService
from services.inventory_count_service import InventoryCountService
from services.hotel_scope_service import get_allowed_hotel_ids, get_user_hotels
from utils.decimal_utils import to_decimal
from decimal import Decimal
import jdatetime
import os
import requests
from dotenv import load_dotenv
from utils.timezone import get_iran_now, get_iran_today

load_dotenv()


class ChatService:
    
    def __init__(self):
        self.pareto_service = ParetoService()
        self.abc_service = ABCService()
        self.api_key = os.getenv('GROQ_API_KEY')
        self.max_history_messages = 10  # Number of messages to keep in context
    
    def process_message(self, message: str, user_id: int = None, user=None) -> dict:
        """Process user message with conversation memory
        P0-9: Uses scoped context based on user's allowed hotels"""
        try:
            # Get database context (scoped to user's hotels)
            db_context = self._get_full_database_context(user=user)
            
            # Get conversation history for context window
            history_messages = []
            if user_id:
                history_messages = ChatHistory.get_context_messages(user_id, self.max_history_messages)
            
            # Call GROQ with full context and history
            response = self._call_groq(message, db_context, history_messages)
            
            if response:
                # Save conversation to history
                if user_id:
                    ChatHistory.add_message(user_id, 'user', message)
                    ChatHistory.add_message(user_id, 'assistant', response)
                
                return {
                    'success': True,
                    'response': response,
                    'suggestions': self._get_smart_suggestions(message)
                }
            else:
                return {
                    'success': False,
                    'response': 'متاسفانه در حال حاضر امکان پاسخگویی وجود ندارد. لطفا دوباره تلاش کنید.',
                    'suggestions': ['خلاصه وضعیت', 'کمک']
                }
                
        except Exception as e:
            # Bug #16: Don't expose internal errors to users
            print(f"Error in process_message: {str(e)}")
            return {
                'success': False,
                'response': 'خطایی در پردازش پیام رخ داد. لطفاً دوباره تلاش کنید.',
                'suggestions': ['کمک', 'خلاصه وضعیت']
            }
    
    def clear_history(self, user_id: int) -> dict:
        """Clear chat history for a user"""
        try:
            ChatHistory.clear_user_history(user_id)
            return {'success': True, 'message': 'تاریخچه گفتگو پاک شد.'}
        except Exception as e:
            return {'success': False, 'message': f'خطا: {str(e)}'}
    
    def get_history(self, user_id: int, limit: int = 50) -> list:
        """Get chat history for a user"""
        messages = ChatHistory.get_user_history(user_id, limit)
        return [m.to_dict() for m in messages]
    
    def _call_groq(self, message: str, db_context: str, history: list = None) -> str:
        """Call GROQ API with database context and conversation history"""
        if not self.api_key:
            print("ERROR: GROQ_API_KEY not found in environment")
            return None
        
        headers = {
            'Authorization': f'Bearer {self.api_key}',
            'Content-Type': 'application/json'
        }
        
        system_prompt = f"""تو دستیار هوشمند مدیریت انبار و موجودی هتل هستی.

اطلاعات واقعی و به‌روز از دیتابیس:
{db_context}

قابلیت‌های تو:
۱. پاسخ به سوالات درباره موجودی کالاها (موجودی فعلی، موجودی بحرانی، موجودی اضافی)
۲. تحلیل ضایعات و ارائه پیشنهاد برای کاهش آن (دلایل ضایعات، روندها)
۳. پیشنهاد لیست خرید بر اساس موجودی (کالاهای بحرانی، تخمین زمان اتمام)
۴. هشدار درباره کالاهای کم یا زیاد (موجودی کم، موجودی اضافی)
۵. مقایسه عملکرد هتل‌ها (فقط برای ادمین)
۶. راهنمایی برای انبارگردانی (کالاهای نیازمند شمارش)
۷. تحلیل روند مصرف و ضایعات (افزایش، کاهش، ثابت)
۸. تحلیل پارتو و ABC (کلاس A, B, C)

قوانین پاسخگویی:
- همیشه از داده‌های واقعی سیستم استفاده کن
- اعداد را با جداکننده هزارگان نمایش بده (مثلاً ۱۲۳,۴۵۶ ریال)
- پیشنهادات عملی و قابل اجرا بده
- اگر چیزی نگران‌کننده است، هشدار بده
- از ایموجی برای خوانایی بهتر استفاده کن (📦, 📊, ⚠️, ✅)
- به فارسی و صمیمی پاسخ بده
- از تاریخچه مکالمه برای درک بهتر استفاده کن
- پاسخ را در دو بخش بده:
  1) «پاسخ نهایی»
  2) «خلاصه استدلال» در حد متوسط (۲ تا ۴ bullet) بدون نمایش مراحل محاسبه یا chain-of-thought

نکات مهم:
- کلاس A: اقلام حیاتی (80% ارزش) - نیاز به کنترل روزانه
- کلاس B: اقلام مهم (15% ارزش) - کنترل هفتگی
- کلاس C: اقلام معمولی (5% ارزش) - کنترل ماهانه
- تحلیل پارتو: قانون 80/20
- موجودی بحرانی: زمانی که موجودی فعلی کمتر از حداقل است
- نرخ ضایعات بالا: بیش از 5% نیازمند توجه فوری است"""

        # Build messages array with history
        messages = [{"role": "system", "content": system_prompt}]
        
        # Add conversation history for context
        if history:
            messages.extend(history)
        
        # Add current message
        messages.append({"role": "user", "content": message})

        data = {
            "model": "openai/gpt-oss-120b",
            "messages": messages,
            "max_tokens": 1000,
            "temperature": 0.7
        }
        
        try:
            response = requests.post(
                'https://api.groq.com/openai/v1/chat/completions',
                headers=headers,
                json=data,
                timeout=30
            )
            
            print(f"GROQ Status: {response.status_code}")
            
            if response.status_code == 200:
                return response.json()['choices'][0]['message']['content']
            else:
                print(f"GROQ Error: {response.text}")
                return None
                
        except Exception as e:
            print(f"GROQ Exception: {str(e)}")
            return None
    
    def _get_full_database_context(self, user=None) -> str:
        """Get comprehensive database context for GROQ
        P0-9: Scoped to user's allowed hotels"""
        try:
            from models.hotel import Hotel
            
            persian_date = jdatetime.date.today().strftime('%Y/%m/%d')
            
            # P0-9: Get allowed hotel IDs for scoping
            allowed_hotel_ids = get_allowed_hotel_ids(user) if user else None
            
            # Build scoped queries
            items_query = Item.query
            trans_query = Transaction.query.filter(Transaction.is_deleted != True)
            
            if allowed_hotel_ids is not None:  # None means admin (all hotels)
                items_query = items_query.filter(Item.hotel_id.in_(allowed_hotel_ids))
                trans_query = trans_query.filter(Transaction.hotel_id.in_(allowed_hotel_ids))
            
            # Basic stats (scoped)
            total_items = items_query.count()
            food_items = items_query.filter_by(category='Food').count()
            nonfood_items = items_query.filter_by(category='NonFood').count()
            
            # Hotel stats (scoped)
            hotels_info = []
            hotels_to_show = get_user_hotels(user) if user else Hotel.query.all()
            for hotel in hotels_to_show:
                h_items = Item.query.filter_by(hotel_id=hotel.id).count()
                h_trans = Transaction.query.filter_by(hotel_id=hotel.id).filter(
                    Transaction.is_deleted != True
                ).count()
                if h_items > 0 or h_trans > 0:
                    hotels_info.append(f"  - {hotel.hotel_name}: {h_items} item, {h_trans} transaction")
            
            hotels_summary = '\n'.join(hotels_info) if hotels_info else "  (No data available)"
            
            # Transaction stats (30 days, scoped)
            start_date = get_iran_now() - timedelta(days=30)
            
            base_tx_filter = [
                Transaction.transaction_date >= start_date,
                Transaction.is_deleted != True,
                Transaction.is_opening_balance != True  # P0-4: Exclude opening balances
            ]
            if allowed_hotel_ids is not None:
                base_tx_filter.append(Transaction.hotel_id.in_(allowed_hotel_ids))
            
            purchases_raw = db.session.query(func.sum(Transaction.total_amount)).filter(
                Transaction.transaction_type == 'خرید',
                *base_tx_filter
            ).scalar() or 0
            
            consumption_raw = db.session.query(func.sum(Transaction.total_amount)).filter(
                Transaction.transaction_type == 'مصرف',
                *base_tx_filter
            ).scalar() or 0
            
            waste_raw = db.session.query(func.sum(Transaction.total_amount)).filter(
                Transaction.transaction_type == 'ضایعات',
                *base_tx_filter
            ).scalar() or 0

            purchases_dec = to_decimal(purchases_raw)
            consumption_dec = to_decimal(consumption_raw)
            waste_dec = to_decimal(waste_raw)
            waste_ratio = (waste_dec / purchases_dec * Decimal('100')) if purchases_dec > 0 else Decimal('0')
            
            today_filter = [func.date(Transaction.transaction_date) == get_iran_today()]
            if allowed_hotel_ids is not None:
                today_filter.append(Transaction.hotel_id.in_(allowed_hotel_ids))
            today_trans = Transaction.query.filter(*today_filter).count()
            
            # ABC classification with full details (scoped)
            food_stats = self.pareto_service.get_summary_stats('خرید', 'Food', 30)
            nonfood_stats = self.pareto_service.get_summary_stats('خرید', 'NonFood', 30)
            
            # Get ABC classified items (scoped)
            food_abc = self.abc_service.get_abc_classification('خرید', 'Food', 30, user=user)
            nonfood_abc = self.abc_service.get_abc_classification('خرید', 'NonFood', 30, user=user)
            
            # Format class items (show top 10 for Class A, 5 for B/C)
            class_a_items = self._format_class_items(food_abc.get('A', [])[:10])
            class_b_items = self._format_class_items(food_abc.get('B', [])[:5])
            class_c_items = self._format_class_items(food_abc.get('C', [])[:5])
            
            # Top items
            top_purchases = self._get_top_items('خرید', 5)
            top_waste = self._get_top_items('ضایعات', 5)
            
            # ═══ ADD ITEM INVENTORY DETAILS ═══
            # Get top 20 items with their current stock for AI context
            top_items_with_stock = self._get_items_with_stock(items_query, limit=20)
            
            # ═══ ADD WAREHOUSE CONTEXT ═══
            warehouse_ctx = self._get_warehouse_context(user, allowed_hotel_ids)
            
            context = f"""
تاریخ: {persian_date}

آمار کلی:
- تعداد کل اقلام: {total_items} قلم
- اقلام غذایی: {food_items} قلم
- اقلام غیرغذایی: {nonfood_items} قلم
- تراکنش‌های امروز: {today_trans}

🏨 توزیع بر اساس هتل:
{hotels_summary}

مالی (30 روز اخیر):
- مجموع خرید: {float(purchases_dec):,.0f} ریال
- مجموع مصرف: {float(consumption_dec):,.0f} ریال
- مجموع ضایعات: {float(waste_dec):,.0f} ریال
- نسبت ضایعات به خرید: {float(waste_ratio):.2f}%

طبقه‌بندی ABC غذایی:
کلاس A (حیاتی - 80% ارزش): {food_stats['class_a_count']} قلم - {food_stats['class_a_amount']:,.0f} ریال
{class_a_items}

کلاس B (مهم - 15% ارزش): {food_stats['class_b_count']} قلم - {food_stats.get('class_b_amount', 0):,.0f} ریال
{class_b_items}

کلاس C (معمولی - 5% ارزش): {food_stats['class_c_count']} قلم - {food_stats.get('class_c_amount', 0):,.0f} ریال
{class_c_items}

طبقه‌بندی ABC غیرغذایی:
- کلاس A: {nonfood_stats['class_a_count']} قلم ({nonfood_stats['class_a_amount']:,.0f} ریال)
- کلاس B: {nonfood_stats['class_b_count']} قلم ({nonfood_stats.get('class_b_amount', 0):,.0f} ریال)
- کلاس C: {nonfood_stats['class_c_count']} قلم ({nonfood_stats.get('class_c_amount', 0):,.0f} ریال)

پرخریدترین اقلام:
{top_purchases}

پرضایعات‌ترین اقلام:
{top_waste}

═══════════════════════════════════════════
� موجودی کالاهای اصلی (Top Items Inventory)
═══════════════════════════════════════════
{top_items_with_stock}

═══════════════════════════════════════════
�� وضعیت انبار (Warehouse Status)
═══════════════════════════════════════════
موجودی بحرانی: {warehouse_ctx['stock_status']['critical_count']} قلم
موجودی اضافی: {warehouse_ctx['stock_status']['overstocked_count']} قلم
موجودی سالم: {warehouse_ctx['stock_status']['healthy_count']} قلم

کالاهای نیازمند سفارش فوری:
{self._format_critical_items(warehouse_ctx['stock_status']['critical_items'])}

═══════════════════════════════════════════
📊 تحلیل ضایعات (Waste Analysis)
═══════════════════════════════════════════
نرخ ضایعات ماه جاری: {warehouse_ctx['waste_analysis']['current_month']['rate']}%
هدف: {warehouse_ctx['waste_analysis']['current_month']['target']}%
وضعیت: {warehouse_ctx['waste_analysis']['current_month']['status']}
مجموع ضایعات: {warehouse_ctx['waste_analysis']['current_month']['total_amount']:,.0f} ریال

دلایل اصلی ضایعات:
{self._format_waste_reasons(warehouse_ctx['waste_analysis']['current_month']['by_reason'])}

پرضایعات‌ترین کالاها:
{self._format_top_wasted(warehouse_ctx['waste_analysis']['current_month']['top_wasted'])}

═══════════════════════════════════════════
⏳ اقدامات معلق (Pending Actions)
═══════════════════════════════════════════
تراکنش‌های در انتظار تایید: {warehouse_ctx['pending_actions']['approvals']['count']} مورد
کالاهای نیازمند شمارش: {warehouse_ctx['pending_actions']['inventory_counts']['overdue_count']} قلم
مغایرت‌های حل‌نشده: {warehouse_ctx['pending_actions']['unresolved_variances']['count']} مورد

═══════════════════════════════════════════
🔔 هشدارهای فعال (Active Alerts)
═══════════════════════════════════════════
{self._format_alerts(warehouse_ctx['active_alerts'])}

═══════════════════════════════════════════
💡 پیشنهادات هوشمند (Smart Suggestions)
═══════════════════════════════════════════
لیست سفارش پیشنهادی:
{self._format_reorder_list(warehouse_ctx['smart_suggestions']['reorder_list'])}

پیشنهاد کاهش ضایعات:
{self._format_suggestions(warehouse_ctx['smart_suggestions']['waste_reduction'])}

اولویت شمارش:
{self._format_suggestions(warehouse_ctx['smart_suggestions']['count_priorities'])}
"""
            return context
            
        except Exception as e:
            print(f"Error getting context: {str(e)}")
            return "اطلاعات دیتابیس در دسترس نیست"
    
    def _format_class_items(self, items: list) -> str:
        """Format ABC class items for context"""
        if not items:
            return "  (بدون کالا)"
        lines = []
        for item in items:
            name = item.get('item_name', 'نامشخص')
            amount = item.get('total_amount', 0)
            pct = item.get('percentage', 0)
            lines.append(f"  - {name}: {amount:,.0f} ریال ({pct:.1f}%)")
        return '\n'.join(lines)
    
    def _get_top_items(self, transaction_type: str, limit: int) -> str:
        """Get top items by transaction type"""
        try:
            df = self.pareto_service.calculate_pareto(transaction_type, 'Food', 30)
            if df.empty:
                return "داده‌ای موجود نیست"
            
            top = df.head(limit)
            lines = [f"- {r['item_name']}: {r['amount']:,.0f} ریال" for _, r in top.iterrows()]
            return '\n'.join(lines)
        except Exception:
            return "داده‌ای موجود نیست"
    
    def _get_items_with_stock(self, items_query, limit: int = 20) -> str:
        """Get top items with their current stock for AI context"""
        try:
            items = items_query.filter(Item.is_active == True).order_by(
                Item.current_stock.desc()
            ).limit(limit).all()
            
            if not items:
                return "داده‌ای موجود نیست"
            
            lines = []
            for item in items:
                stock = float(item.current_stock or 0)
                min_stock = float(item.min_stock or 0)
                max_stock = float(item.max_stock or 0)
                unit = item.unit or ''
                
                status = "عادی"
                if min_stock > 0 and stock <= min_stock:
                    status = "⚠️ کم"
                elif max_stock > 0 and stock >= max_stock:
                    status = "📈 زیاد"
                
                lines.append(f"  - {item.item_name_fa}: {stock:.1f} {unit} (حداقل: {min_stock:.1f}, حداکثر: {max_stock:.1f}) [{status}]")
            
            return '\n'.join(lines)
        except Exception as e:
            print(f"Error getting items with stock: {e}")
            return "داده‌ای موجود نیست"
    
    def _get_avg_daily_consumption(self, item_id: int, days: int = 30) -> float:
        """Calculate average daily consumption for an item"""
        start_date = date.today() - timedelta(days=days)
        
        total_consumption = db.session.query(func.sum(Transaction.quantity)).filter(
            Transaction.item_id == item_id,
            Transaction.transaction_type == 'مصرف',
            Transaction.transaction_date >= start_date,
            Transaction.is_deleted == False
        ).scalar() or 0
        
        return float(total_consumption) / days if days > 0 else 0
    
    def _get_warehouse_context(self, user, hotel_ids: list) -> dict:
        """Build comprehensive warehouse context for AI"""
        context = {
            "stock_status": {},
            "waste_analysis": {},
            "pending_actions": {},
            "active_alerts": [],
            "kpis": {},
            "smart_suggestions": {}
        }
        
        try:
            # Apply hotel scoping
            if hotel_ids is None:
                # Admin - all hotels
                hotel_filter = Item.is_active == True
            else:
                hotel_filter = (Item.hotel_id.in_(hotel_ids)) & (Item.is_active == True)
            
            # ═══ STOCK STATUS ═══
            items = Item.query.filter(hotel_filter).all()
            
            critical_items = []
            overstocked_items = []
            
            for item in items:
                if item.current_stock and item.min_stock and item.current_stock <= item.min_stock:
                    # Calculate days to stockout
                    avg_daily = self._get_avg_daily_consumption(item.id, 30)
                    days_left = int(item.current_stock / avg_daily) if avg_daily > 0 else 999
                    
                    # BUG FIX: Handle None values to prevent TypeError
                    current_stock_val = float(item.current_stock or 0)
                    min_stock_val = float(item.min_stock or 0)
                    max_stock_val = float(item.max_stock or 0) if item.max_stock else None
                    suggested = (max_stock_val - current_stock_val) if max_stock_val else (min_stock_val * 2)
                    critical_items.append({
                        "name": item.item_name_fa,
                        "current": current_stock_val,
                        "min": min_stock_val,
                        "unit": item.unit,
                        "days_to_stockout": days_left,
                        "suggested_order": suggested
                    })
                
                if item.max_stock and item.current_stock and item.current_stock >= item.max_stock:
                    overstocked_items.append({
                        "name": item.item_name_fa,
                        "current": float(item.current_stock),
                        "max": float(item.max_stock),
                        "unit": item.unit
                    })
            
            critical_items.sort(key=lambda x: x['days_to_stockout'])
            
            context["stock_status"] = {
                "total_items": len(items),
                "critical_items": critical_items[:10],
                "critical_count": len(critical_items),
                "overstocked_items": overstocked_items[:5],
                "overstocked_count": len(overstocked_items),
                "healthy_count": len(items) - len(critical_items) - len(overstocked_items)
            }
            
            # ═══ WASTE ANALYSIS ═══
            today = date.today()
            month_start = today.replace(day=1)
            
            waste_service = WasteAnalysisService()
            # For waste analysis, use first hotel or skip if None (admin without hotel selection)
            first_hotel_id = hotel_ids[0] if hotel_ids and len(hotel_ids) > 0 else None
            
            if first_hotel_id:
                current_waste = waste_service.get_waste_summary(
                    hotel_id=first_hotel_id,
                    start_date=month_start,
                    end_date=today
                )
                
                waste_by_reason = waste_service.get_waste_by_reason(
                    hotel_id=first_hotel_id,
                    start_date=month_start,
                    end_date=today
                )
                
                top_wasted = waste_service.get_top_wasted_items(
                    hotel_id=first_hotel_id,
                    start_date=month_start,
                    end_date=today,
                    limit=5
                )
            else:
                # Admin without hotel filter - aggregate across all hotels
                from models.hotel import Hotel
                all_hotels = Hotel.query.all()
                if all_hotels:
                    first_hotel_id = all_hotels[0].id
                    current_waste = waste_service.get_waste_summary(
                        hotel_id=first_hotel_id,
                        start_date=month_start,
                        end_date=today
                    )
                    waste_by_reason = waste_service.get_waste_by_reason(
                        hotel_id=first_hotel_id,
                        start_date=month_start,
                        end_date=today
                    )
                    top_wasted = waste_service.get_top_wasted_items(
                        hotel_id=first_hotel_id,
                        start_date=month_start,
                        end_date=today,
                        limit=5
                    )
                else:
                    current_waste = {'waste_rate': 0, 'total_waste': 0, 'status': 'unknown'}
                    waste_by_reason = []
                    top_wasted = []
            
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
                            "percentage": round(float(r['amount']) / float(current_waste.get('total_waste', 1)) * 100) if current_waste.get('total_waste') else 0
                        }
                        for r in waste_by_reason
                    ],
                    "top_wasted": [
                        {"name": item['name'], "amount": float(item['amount'])}
                        for item in top_wasted
                    ]
                }
            }
            
            # ═══ PENDING ACTIONS ═══
            pending_txs = Transaction.query.filter(
                Transaction.requires_approval == True,
                Transaction.approval_status == 'pending',
                Transaction.is_deleted == False
            )
            if hotel_ids:
                pending_txs = pending_txs.filter(Transaction.hotel_id.in_(hotel_ids))
            pending_txs = pending_txs.all()
            
            count_service = InventoryCountService()
            items_needing_count = count_service.get_items_needing_count(
                hotel_id=first_hotel_id,
                days_threshold=30
            )
            
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
                            "reason": WASTE_REASONS.get(tx.waste_reason, tx.waste_reason) if tx.waste_reason else "نامشخص"
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
            alerts = Alert.query.filter(Alert.status == 'active')
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
            
            if waste_by_reason:
                top_reason = waste_by_reason[0]
                reason_text = WASTE_REASONS.get(top_reason['reason'], top_reason['reason'])
                context["smart_suggestions"]["waste_reduction"].append(
                    f"بررسی دلیل اصلی ضایعات: {reason_text}"
                )
            
        except Exception as e:
            print(f"Error building warehouse context: {str(e)}")
        
        return context
    
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
            f"• {item['item']}: {item['suggested_qty']:.0f} {item['unit']} ({item['urgency']})"
            for item in items
        ])
    
    def _format_suggestions(self, suggestions: list) -> str:
        if not suggestions:
            return "پیشنهادی وجود ندارد"
        return "\n".join([f"• {s}" for s in suggestions])
    
    def _get_smart_suggestions(self, message: str) -> list:
        """Get smart suggestions based on message"""
        msg = message.lower()
        
        if any(k in msg for k in ['موجودی', 'انبار', 'stock']):
            return ['موجودی بحرانی', 'پیشنهاد خرید', 'وضعیت انبار']
        elif any(k in msg for k in ['خرید', 'هزینه']):
            return ['بیشترین ضایعات', 'طبقه‌بندی ABC', 'توصیه‌ها']
        elif any(k in msg for k in ['ضایعات', 'هدررفت']):
            return ['توصیه کاهش ضایعات', 'مقایسه ماهانه', 'کلاس A']
        elif any(k in msg for k in ['کلاس', 'abc']):
            return ['کلاس A', 'کلاس B', 'کلاس C']
        elif any(k in msg for k in ['پارتو', 'تحلیل']):
            return ['نمودار پارتو', 'برترین خریدها', 'توصیه‌ها']
        else:
            return ['خلاصه وضعیت', 'تحلیل پارتو', 'برترین خریدها', 'ضایعات']
