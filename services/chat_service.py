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
from models.audit_log import AuditLog
from models.import_batch import ImportBatch
from models.warehouse_settings import WarehouseSettings
from models.user_hotel import UserHotel
from models.transaction import WASTE_REASONS, DEPARTMENTS
from services.pareto_service import ParetoService
from services.abc_service import ABCService
from services.warehouse_service import WarehouseService
from services.waste_analysis_service import WasteAnalysisService
from services.inventory_count_service import InventoryCountService
from services.ai_service import AIService
from services.hotel_scope_service import get_allowed_hotel_ids, get_user_hotels
from utils.decimal_utils import to_decimal
from decimal import Decimal
import jdatetime
import os
import json
import logging
import requests
from dotenv import load_dotenv
from utils.timezone import get_iran_now, get_iran_today

logger = logging.getLogger(__name__)

load_dotenv()


class ChatService:
    
    def __init__(self):
        self.pareto_service = ParetoService()
        self.abc_service = ABCService()
        self.api_key = os.getenv('GROQ_API_KEY')
        self.max_history_messages = 10  # Number of messages to keep in context
    
    def process_message(self, message: str, user_id: int = None, user=None) -> dict:
        """Process user message with conversation memory
        P0-9: Uses scoped context based on user's allowed hotels
        FULL SYSTEM: Connected to all databases, logs, users, transactions"""
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
                
                # Audit log: record chat interaction (without content for privacy)
                self._log_chat_audit(user, 'chat_message', f'msg_len={len(message)}, resp_len={len(response)}')
                
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
            logger.error(f"Error in process_message: {str(e)}")
            return {
                'success': False,
                'response': 'خطایی در پردازش پیام رخ داد. لطفاً دوباره تلاش کنید.',
                'suggestions': ['کمک', 'خلاصه وضعیت']
            }
    
    def clear_history(self, user_id: int, user=None) -> dict:
        """Clear chat history for a user"""
        try:
            ChatHistory.clear_user_history(user_id)
            self._log_chat_audit(user, 'clear_history', f'user_id={user_id}')
            return {'success': True, 'message': 'تاریخچه گفتگو پاک شد.'}
        except Exception as e:
            logger.error(f"Error clearing history: {str(e)}")
            return {'success': False, 'message': 'خطا در پاک کردن تاریخچه'}
    
    @staticmethod
    def _log_chat_audit(user, action: str, details: str = None):
        """Log chat actions to AuditLog for full system traceability"""
        try:
            if user:
                AuditLog.log(
                    user=user,
                    action=action,
                    resource_type='chat',
                    description=details
                )
                db.session.commit()
        except Exception as e:
            logger.warning(f"Failed to log chat audit: {e}")
    
    def get_history(self, user_id: int, limit: int = 50) -> list:
        """Get chat history for a user"""
        messages = ChatHistory.get_user_history(user_id, limit)
        return [m.to_dict() for m in messages]
    
    def _call_groq(self, message: str, db_context: str, history: list = None) -> str:
        """Call GROQ API with database context and conversation history"""
        if not self.api_key:
            logger.error("GROQ_API_KEY not found in environment")
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
            
            logger.info(f"GROQ Status: {response.status_code}")
            
            if response.status_code == 200:
                return response.json()['choices'][0]['message']['content']
            else:
                logger.error(f"GROQ Error: {response.text}")
                return None
                
        except Exception as e:
            logger.error(f"GROQ Exception: {str(e)}")
            return None
    
    def _get_full_database_context(self, user=None) -> str:
        """Get comprehensive database context for GROQ
        FULL SYSTEM CONNECTION: databases, logs, users, transactions, imports, settings
        P0-9: Scoped to user's allowed hotels"""
        try:
            from models.hotel import Hotel
            from models.user import User, ROLE_LABELS
            
            persian_date = jdatetime.date.today().strftime('%Y/%m/%d')
            iran_now = get_iran_now()
            iran_today = get_iran_today()
            
            # P0-9: Get allowed hotel IDs for scoping
            allowed_hotel_ids = get_allowed_hotel_ids(user) if user else None
            
            # ═══ USER CONTEXT ═══
            user_context = self._get_user_context(user)
            
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
                    hotels_info.append(f"  - {hotel.hotel_name}: {h_items} کالا, {h_trans} تراکنش")
            
            hotels_summary = '\n'.join(hotels_info) if hotels_info else "  (داده‌ای موجود نیست)"
            
            # Transaction stats (30 days, scoped)
            start_date = iran_now - timedelta(days=30)
            
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
            
            today_filter = [func.date(Transaction.transaction_date) == iran_today]
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
            
            # Top items (scoped to user)
            top_purchases = self._get_top_items('خرید', 5, user=user)
            top_waste = self._get_top_items('ضایعات', 5, user=user)
            
            # ═══ ITEM INVENTORY DETAILS ═══
            top_items_with_stock = self._get_items_with_stock(items_query, limit=20)
            
            # ═══ WAREHOUSE CONTEXT ═══
            warehouse_ctx = self._get_warehouse_context(user, allowed_hotel_ids)
            
            # ═══ NEW: DEAD STOCK ANALYSIS ═══
            dead_stock_ctx = self._get_dead_stock_context(allowed_hotel_ids)
            
            # ═══ NEW: WASTE TREND (multi-month) ═══
            waste_trend_ctx = self._get_waste_trend_context(allowed_hotel_ids)
            
            # ═══ NEW: WAREHOUSE SETTINGS ═══
            settings_ctx = self._get_warehouse_settings_context(allowed_hotel_ids)
            
            # ═══ NEW: IMPORT BATCH CONTEXT ═══
            import_ctx = self._get_import_context(allowed_hotel_ids)
            
            # ═══ NEW: RECENT AUDIT LOG ACTIVITY ═══
            audit_ctx = self._get_audit_context(user)
            
            # ═══ NEW: RECENT STOCK MOVEMENTS ═══
            movements_ctx = self._get_recent_movements_context(allowed_hotel_ids)
            
            # ═══ NEW: SYSTEM USERS SUMMARY ═══
            users_ctx = self._get_users_context(user)
            
            context = f"""
تاریخ: {persian_date}
زمان: {iran_now.strftime('%H:%M')}

═══════════════════════════════════════════
👤 اطلاعات کاربر جاری
═══════════════════════════════════════════
{user_context}

═══════════════════════════════════════════
📋 آمار کلی سیستم
═══════════════════════════════════════════
- تعداد کل اقلام: {total_items} قلم
- اقلام غذایی: {food_items} قلم
- اقلام غیرغذایی: {nonfood_items} قلم
- تراکنش‌های امروز: {today_trans}

🏨 توزیع بر اساس هتل:
{hotels_summary}

═══════════════════════════════════════════
💰 مالی (30 روز اخیر)
═══════════════════════════════════════════
- مجموع خرید: {float(purchases_dec):,.0f} ریال
- مجموع مصرف: {float(consumption_dec):,.0f} ریال
- مجموع ضایعات: {float(waste_dec):,.0f} ریال
- نسبت ضایعات به خرید: {float(waste_ratio):.2f}%

═══════════════════════════════════════════
📊 طبقه‌بندی ABC غذایی
═══════════════════════════════════════════
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
📦 موجودی کالاهای اصلی (Top Items Inventory)
═══════════════════════════════════════════
{top_items_with_stock}

═══════════════════════════════════════════
🏭 وضعیت انبار (Warehouse Status)
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

ضایعات بر اساس واحد مقصد:
{self._format_waste_departments(warehouse_ctx['waste_analysis']['current_month'].get('by_department', []))}

پرضایعات‌ترین کالاها:
{self._format_top_wasted(warehouse_ctx['waste_analysis']['current_month']['top_wasted'])}

═══════════════════════════════════════════
📈 روند ضایعات (Waste Trend - 6 ماه)
═══════════════════════════════════════════
{waste_trend_ctx}

═══════════════════════════════════════════
💀 کالاهای راکد (Dead Stock)
═══════════════════════════════════════════
{dead_stock_ctx}

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

═══════════════════════════════════════════
🔄 آخرین حرکات انبار (Recent Movements)
═══════════════════════════════════════════
{movements_ctx}

═══════════════════════════════════════════
⚙️ تنظیمات انبار (Warehouse Settings)
═══════════════════════════════════════════
{settings_ctx}

═══════════════════════════════════════════
📥 آخرین واردات داده (Recent Imports)
═══════════════════════════════════════════
{import_ctx}

═══════════════════════════════════════════
👥 کاربران سیستم
═══════════════════════════════════════════
{users_ctx}

═══════════════════════════════════════════
📝 فعالیت‌های اخیر سیستم (Audit Log)
═══════════════════════════════════════════
{audit_ctx}
"""
            return context
            
        except Exception as e:
            logger.error(f"Error getting context: {str(e)}")
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
    
    def _get_top_items(self, transaction_type: str, limit: int, user=None) -> str:
        """Get top items by transaction type (scoped to user's hotels)"""
        try:
            df = self.pareto_service.calculate_pareto(transaction_type, 'Food', 30, user=user)
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
            logger.warning(f"Error getting items with stock: {e}")
            return "داده‌ای موجود نیست"
    
    def _get_avg_daily_consumption(self, item_id: int, days: int = 30) -> float:
        """Calculate average daily consumption for an item (uses Iran timezone)"""
        start_date = get_iran_today() - timedelta(days=days)
        
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
            
            # ═══ WASTE ANALYSIS (aggregated across scoped hotels) ═══
            today = get_iran_today()
            month_start = today.replace(day=1)

            tx_base = [
                Transaction.transaction_date.between(month_start, today),
                Transaction.is_deleted == False,
            ]
            if hotel_ids is not None:
                tx_base.append(Transaction.hotel_id.in_(hotel_ids))

            total_purchase = db.session.query(func.sum(Transaction.total_amount)).filter(
                Transaction.transaction_type == 'خرید',
                Transaction.is_opening_balance == False,
                *tx_base
            ).scalar() or Decimal(0)

            total_waste = db.session.query(func.sum(Transaction.total_amount)).filter(
                Transaction.transaction_type == 'ضایعات',
                *tx_base
            ).scalar() or Decimal(0)

            waste_rate = (float(total_waste) / float(total_purchase) * 100) if total_purchase else 0
            status = 'good' if waste_rate < 3 else ('warning' if waste_rate < 5 else 'critical')
            current_waste = {
                'total_purchase': float(total_purchase),
                'total_waste': float(total_waste),
                'waste_rate': round(waste_rate, 2),
                'status': status,
            }

            # Breakdown by reason
            reason_rows = db.session.query(
                Transaction.waste_reason,
                func.sum(Transaction.total_amount).label('amount')
            ).filter(
                Transaction.transaction_type == 'ضایعات',
                *tx_base
            ).group_by(Transaction.waste_reason).all()

            waste_by_reason = []
            total_waste_float = float(total_waste or 0)
            for reason, amount in reason_rows:
                amount_f = float(amount or 0)
                waste_by_reason.append({
                    'reason': reason or 'other',
                    'amount': amount_f,
                    'percentage': round((amount_f / total_waste_float * 100), 1) if total_waste_float else 0,
                })
            waste_by_reason.sort(key=lambda x: x['amount'], reverse=True)

            # Breakdown by destination department
            dept_rows = db.session.query(
                Transaction.destination_department,
                func.sum(Transaction.total_amount).label('amount')
            ).filter(
                Transaction.transaction_type == 'ضایعات',
                Transaction.destination_department != None,
                *tx_base
            ).group_by(Transaction.destination_department).all()

            waste_by_department = []
            for dept, amount in dept_rows:
                amount_f = float(amount or 0)
                waste_by_department.append({
                    'department': DEPARTMENTS.get(dept, dept or 'نامشخص'),
                    'amount': amount_f,
                    'percentage': round((amount_f / total_waste_float * 100), 1) if total_waste_float else 0,
                })
            waste_by_department.sort(key=lambda x: x['amount'], reverse=True)

            # Top wasted items
            top_rows = db.session.query(
                Item.item_name_fa,
                func.sum(Transaction.total_amount).label('amount')
            ).join(Transaction, Transaction.item_id == Item.id).filter(
                Transaction.transaction_type == 'ضایعات',
                *tx_base
            ).group_by(Item.id).order_by(func.sum(Transaction.total_amount).desc()).limit(5).all()

            top_wasted = [{'item_name': name, 'waste_amount': float(amount or 0)} for name, amount in top_rows]
            
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
                    "by_department": waste_by_department,
                    "top_wasted": [
                        {"name": item['item_name'], "amount": float(item['waste_amount'])}
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
            if hotel_ids is not None:
                pending_txs = pending_txs.filter(Transaction.hotel_id.in_(hotel_ids))
            pending_txs = pending_txs.all()
            
            # Items needing count across all scoped hotels
            from models.hotel import Hotel
            count_service = InventoryCountService()
            items_needing_count = []
            if hotel_ids is not None:
                hotel_ids_for_counts = list(hotel_ids)
            else:
                hotel_ids_for_counts = [h.id for h in Hotel.query.filter_by(is_active=True).all()]

            for hid in hotel_ids_for_counts[:10]:
                try:
                    items_needing_count.extend(count_service.get_items_needing_count(hotel_id=hid, days_threshold=30))
                except Exception:
                    continue
            
            unresolved = InventoryCount.query.filter(
                InventoryCount.status.in_(['pending', 'investigating'])
            )
            if hotel_ids is not None:
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
                        {"name": item_entry['item'].item_name_fa}
                        for item_entry in items_needing_count[:5]
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
            if hotel_ids is not None:
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
                    item_entry['item'].item_name_fa for item_entry in items_needing_count[:5]
                ]
            }
            
            if waste_by_reason:
                top_reason = waste_by_reason[0]
                reason_text = WASTE_REASONS.get(top_reason['reason'], top_reason['reason'])
                context["smart_suggestions"]["waste_reduction"].append(
                    f"بررسی دلیل اصلی ضایعات: {reason_text}"
                )
            
        except Exception as e:
            logger.error(f"Error building warehouse context: {str(e)}")
        
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

    def _format_waste_departments(self, departments: list) -> str:
        if not departments:
            return "اطلاعاتی موجود نیست"
        return "\n".join([
            f"• {d['department']}: {d['percentage']}% ({d['amount']:,.0f} ریال)"
            for d in departments
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
        elif any(k in msg for k in ['راکد', 'dead', 'منجمد']):
            return ['سرمایه منجمد', 'کالاهای بدون مصرف', 'پیشنهاد خرید']
        elif any(k in msg for k in ['کاربر', 'user', 'دسترسی']):
            return ['لیست کاربران', 'فعالیت‌های اخیر', 'خلاصه وضعیت']
        elif any(k in msg for k in ['واردات', 'import', 'اکسل']):
            return ['آخرین واردات', 'وضعیت داده‌ها', 'خلاصه وضعیت']
        elif any(k in msg for k in ['تنظیمات', 'setting', 'تایید']):
            return ['تنظیمات انبار', 'اقدامات معلق', 'خلاصه وضعیت']
        else:
            return ['خلاصه وضعیت', 'تحلیل پارتو', 'برترین خریدها', 'ضایعات']
    
    # ═══════════════════════════════════════════════════════════════
    # NEW: Full System Context Methods
    # ═══════════════════════════════════════════════════════════════
    
    def _get_user_context(self, user) -> str:
        """Get current user's context for AI personalization"""
        try:
            if not user:
                return "کاربر ناشناس"
            
            from models.user import ROLE_LABELS
            
            role_label = ROLE_LABELS.get(user.role, user.role)
            hotels = get_user_hotels(user)
            allowed_ids = get_allowed_hotel_ids(user)
            if allowed_ids is not None:
                hotel_names = 'همه هتل‌ها'
            elif not hotels:
                hotel_names = 'هیچ هتل'
            else:
                hotel_names = ', '.join([h.hotel_name for h in hotels])
            
            # Count user's recent transactions
            recent_tx_count = Transaction.query.filter(
                Transaction.user_id == user.id,
                Transaction.transaction_date >= get_iran_today() - timedelta(days=7),
                Transaction.is_deleted == False
            ).count()
            
            lines = [
                f"نام: {user.full_name or user.username}",
                f"نقش: {role_label}",
                f"بخش: {user.department or 'مشخص نشده'}",
                f"هتل‌های مجاز: {hotel_names}",
                f"سطح دسترسی: {'مدیر سیستم (دسترسی کامل)' if user.is_admin() else 'مدیر انبار' if user.is_manager() else 'کارمند'}",
                f"تراکنش‌های 7 روز اخیر کاربر: {recent_tx_count}",
            ]
            return '\n'.join(lines)
        except Exception as e:
            logger.warning(f"Error getting user context: {e}")
            return "اطلاعات کاربر در دسترس نیست"
    
    def _get_dead_stock_context(self, hotel_ids) -> str:
        """Get dead stock analysis (scoped to allowed hotels when provided)"""
        try:
            today = get_iran_today()
            cutoff_date = today - timedelta(days=60)

            query = Item.query.filter(
                Item.is_active == True,
                Item.current_stock > 0
            )
            if hotel_ids is not None:
                query = query.filter(Item.hotel_id.in_(hotel_ids))

            items = query.all()

            dead_items = []
            total_frozen_capital = 0

            for item in items:
                last_consumption = db.session.query(
                    func.max(Transaction.transaction_date)
                ).filter(
                    Transaction.item_id == item.id,
                    Transaction.transaction_type == 'مصرف',
                    Transaction.is_deleted == False
                ).scalar()

                is_dead = False
                days_inactive = None

                if last_consumption is None:
                    is_dead = True
                    days_inactive = (today - item.created_at.date()).days if item.created_at else 999
                elif last_consumption < cutoff_date:
                    is_dead = True
                    days_inactive = (today - last_consumption).days

                if is_dead:
                    current_stock = float(item.current_stock or 0)
                    unit_price = float(item.unit_price or 0)
                    frozen_value = current_stock * unit_price
                    total_frozen_capital += frozen_value

                    dead_items.append({
                        'item_id': item.id,
                        'item_name': item.item_name_fa,
                        'unit': item.unit,
                        'current_stock': current_stock,
                        'frozen_value': frozen_value,
                        'days_inactive': days_inactive,
                        'status': 'never_used' if last_consumption is None else 'inactive'
                    })

            dead_items.sort(key=lambda x: x['frozen_value'], reverse=True)

            if not dead_items:
                return "هیچ کالای راکدی یافت نشد ✅"
            
            lines = [
                f"تعداد کالاهای راکد (بدون مصرف 60+ روز): {len(dead_items)} قلم",
                f"سرمایه منجمد: {total_frozen_capital:,.0f} ریال",
                "",
                "کالاهای راکد اصلی:"
            ]
            
            for item in dead_items[:7]:
                status = "هرگز مصرف نشده" if item['status'] == 'never_used' else f"{item['days_inactive']} روز بدون مصرف"
                lines.append(
                    f"  - {item['item_name']}: {item['current_stock']:.1f} {item['unit']} "
                    f"(ارزش: {item['frozen_value']:,.0f} ریال) [{status}]"
                )
            
            return '\n'.join(lines)
        except Exception as e:
            logger.warning(f"Error getting dead stock context: {e}")
            return "اطلاعات کالاهای راکد در دسترس نیست"
    
    def _get_waste_trend_context(self, hotel_ids: list) -> str:
        """Get multi-month waste trend from WasteAnalysisService"""
        try:
            from datetime import timedelta
            
            trend = []
            today = get_iran_today()
            
            for i in range(6 - 1, -1, -1):
                target_date = today - timedelta(days=i * 30)
                month_start = date(target_date.year, target_date.month, 1)
                if target_date.month == 12:
                    month_end = date(target_date.year + 1, 1, 1) - timedelta(days=1)
                else:
                    month_end = date(target_date.year, target_date.month + 1, 1) - timedelta(days=1)
                
                base = [
                    Transaction.transaction_date.between(month_start, month_end),
                    Transaction.is_deleted == False,
                ]
                if hotel_ids is not None:
                    base.append(Transaction.hotel_id.in_(hotel_ids))
                
                waste = db.session.query(func.sum(Transaction.total_amount)).filter(
                    Transaction.transaction_type == 'ضایعات',
                    *base
                ).scalar() or 0
                
                purchase = db.session.query(func.sum(Transaction.total_amount)).filter(
                    Transaction.transaction_type == 'خرید',
                    Transaction.is_opening_balance == False,
                    *base
                ).scalar() or 0
                
                rate = (float(waste) / float(purchase) * 100) if purchase else 0
                trend.append({
                    'month': month_start.strftime('%Y-%m'),
                    'waste_amount': float(waste),
                    'purchase_amount': float(purchase),
                    'waste_rate': round(rate, 2),
                })
            
            if not trend:
                return "داده‌ای موجود نیست"
            
            lines = []
            for month_data in trend:
                rate = month_data['waste_rate']
                status_icon = "✅" if rate < 3 else ("⚠️" if rate < 5 else "🔴")
                lines.append(
                    f"  - {month_data['month']}: نرخ ضایعات {rate}% {status_icon} "
                    f"(ضایعات: {month_data['waste_amount']:,.0f} ریال, خرید: {month_data['purchase_amount']:,.0f} ریال)"
                )
            
            # Add trend direction
            if len(trend) >= 2:
                first_rate = trend[0]['waste_rate']
                last_rate = trend[-1]['waste_rate']
                if last_rate > first_rate * 1.1:
                    lines.append("\n⚠️ روند ضایعات: افزایشی - نیاز به توجه فوری")
                elif last_rate < first_rate * 0.9:
                    lines.append("\n✅ روند ضایعات: کاهشی - عملکرد خوب")
                else:
                    lines.append("\nروند ضایعات: ثابت")
            
            return '\n'.join(lines)
        except Exception as e:
            logger.warning(f"Error getting waste trend context: {e}")
            return "اطلاعات روند ضایعات در دسترس نیست"
    
    def _get_warehouse_settings_context(self, hotel_ids: list) -> str:
        """Get warehouse settings for AI context"""
        try:
            from models.hotel import Hotel
            
            hotels = []
            if hotel_ids is not None:
                if len(hotel_ids) == 0:
                    return "تنظیماتی موجود نیست"
                hotels = Hotel.query.filter(Hotel.id.in_(hotel_ids)).all()
            else:
                hotels = Hotel.query.filter_by(is_active=True).all()
            
            if not hotels:
                return "تنظیماتی موجود نیست"
            
            lines = []
            for hotel in hotels[:3]:  # Limit to 3 hotels
                settings = WarehouseSettings.query.filter_by(hotel_id=hotel.id).first()
                if settings:
                    lines.append(f"  {hotel.hotel_name}:")
                    lines.append(f"    - آستانه تایید ضایعات: {float(settings.waste_approval_threshold or 0):,.0f} ریال")
                    lines.append(f"    - آستانه تایید اصلاحی: {float(settings.adjustment_approval_threshold or 0):.1f} واحد")
                    lines.append(f"    - آستانه هشدار ضایعات: {float(settings.waste_alert_percentage or 0):.1f}%")
                    lines.append(f"    - فرکانس شمارش: هر {settings.count_frequency_days or 30} روز")
                    lines.append(f"    - آخرین شمارش کامل: {settings.last_full_count_date or 'انجام نشده'}")
                    needs = "بله ⚠️" if settings.needs_count() else "خیر ✅"
                    lines.append(f"    - نیاز به شمارش: {needs}")
                else:
                    lines.append(f"  {hotel.hotel_name}: تنظیمات پیش‌فرض (بدون سفارشی‌سازی)")
            
            return '\n'.join(lines)
        except Exception as e:
            logger.warning(f"Error getting warehouse settings context: {e}")
            return "اطلاعات تنظیمات در دسترس نیست"
    
    def _get_import_context(self, hotel_ids: list) -> str:
        """Get recent data import batches for AI context"""
        try:
            query = ImportBatch.query.filter_by(is_active=True)
            if hotel_ids is not None:
                if len(hotel_ids) == 0:
                    return "هیچ واردات داده‌ای ثبت نشده است"
                query = query.filter(ImportBatch.hotel_id.in_(hotel_ids))
            
            recent_imports = query.order_by(ImportBatch.created_at.desc()).limit(5).all()
            
            if not recent_imports:
                return "هیچ واردات داده‌ای ثبت نشده است"
            
            lines = []
            for batch in recent_imports:
                date_str = batch.created_at.strftime('%Y/%m/%d %H:%M') if batch.created_at else 'نامشخص'
                uploader = batch.uploaded_by.full_name if batch.uploaded_by else 'نامشخص'
                lines.append(
                    f"  - {batch.filename} ({date_str}): "
                    f"{batch.items_created} کالای جدید, {batch.items_updated} بروزرسانی, "
                    f"{batch.transactions_created} تراکنش, {batch.errors_count} خطا "
                    f"[وضعیت: {batch.status}] [توسط: {uploader}]"
                )
            
            return '\n'.join(lines)
        except Exception as e:
            logger.warning(f"Error getting import context: {e}")
            return "اطلاعات واردات در دسترس نیست"
    
    def _get_audit_context(self, user) -> str:
        """Get recent audit log entries for AI context (admin sees all; others only own logs)"""
        try:
            if not user:
                return "اطلاعات فعالیت‌ها در دسترس نیست"

            query = AuditLog.query
            if not user.is_admin():
                query = query.filter(AuditLog.user_id == user.id)

            recent_logs = query.order_by(AuditLog.created_at.desc()).limit(10).all()
            
            if not recent_logs:
                return "فعالیتی ثبت نشده است"
            
            lines = []
            for log in recent_logs:
                date_str = log.created_at.strftime('%m/%d %H:%M') if log.created_at else ''
                action_label = AuditLog.ACTION_LABELS.get(log.action, log.action)
                resource_label = AuditLog.RESOURCE_LABELS.get(log.resource_type, log.resource_type)
                lines.append(
                    f"  - [{date_str}] {log.username} ({log.user_role}): "
                    f"{action_label} {resource_label}"
                    f"{' - ' + log.resource_name if log.resource_name else ''}"
                )
            
            return '\n'.join(lines)
        except Exception as e:
            logger.warning(f"Error getting audit context: {e}")
            return "اطلاعات فعالیت‌ها در دسترس نیست"
    
    def _get_recent_movements_context(self, hotel_ids: list) -> str:
        """Get recent stock movements for AI context"""
        try:
            query = Transaction.query.filter(Transaction.is_deleted == False)
            if hotel_ids is not None:
                query = query.filter(Transaction.hotel_id.in_(hotel_ids))
            
            recent = query.order_by(Transaction.created_at.desc()).limit(10).all()
            
            if not recent:
                return "حرکتی ثبت نشده است"
            
            lines = []
            for tx in recent:
                date_str = tx.transaction_date.strftime('%m/%d') if tx.transaction_date else ''
                item_name = tx.item.item_name_fa if tx.item else 'نامشخص'
                user_name = tx.user.full_name if tx.user else 'نامشخص'
                amount_str = f"{float(tx.total_amount or 0):,.0f}" if tx.total_amount else '0'
                
                direction_icon = "📥" if tx.direction == 1 else "📤"
                lines.append(
                    f"  - [{date_str}] {direction_icon} {tx.transaction_type}: "
                    f"{item_name} - {tx.quantity:.1f} {tx.unit or ''} "
                    f"({amount_str} ریال) [توسط: {user_name}]"
                )
            
            return '\n'.join(lines)
        except Exception as e:
            logger.warning(f"Error getting movements context: {e}")
            return "اطلاعات حرکات در دسترس نیست"
    
    def _get_users_context(self, user) -> str:
        """Get system users summary for AI context (admin only)"""
        try:
            from models.user import User, ROLE_LABELS
            
            # Only show user details to admin
            if not user or not user.is_admin():
                return "فقط مدیر سیستم دسترسی به اطلاعات کاربران دارد"
            
            users = User.query.filter_by(is_active=True).all()
            
            if not users:
                return "کاربری ثبت نشده است"
            
            # Summary
            total = len(users)
            admins = sum(1 for u in users if u.role == 'admin')
            managers = sum(1 for u in users if u.role == 'manager')
            staff = sum(1 for u in users if u.role == 'staff')
            
            lines = [
                f"تعداد کل کاربران فعال: {total}",
                f"  - مدیر سیستم: {admins}",
                f"  - مدیر انبار: {managers}",
                f"  - کارمند: {staff}",
                "",
                "لیست کاربران:"
            ]
            
            for u in users[:10]:
                role_label = ROLE_LABELS.get(u.role, u.role)
                last_login = u.last_login.strftime('%Y/%m/%d %H:%M') if u.last_login else 'هرگز'
                locked = " [🔒 قفل]" if u.is_locked() else ""
                twofa = " [2FA]" if u.is_2fa_enabled else ""
                lines.append(
                    f"  - {u.full_name or u.username} ({role_label}){locked}{twofa} - آخرین ورود: {last_login}"
                )
            
            return '\n'.join(lines)
        except Exception as e:
            logger.warning(f"Error getting users context: {e}")
            return "اطلاعات کاربران در دسترس نیست"
