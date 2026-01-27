#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Llama 4 Maverick Workflow Analyzer
AI-powered analysis for hotel inventory management
"""

import os
import json
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

try:
    from openai import OpenAI
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False


class WorkflowAnalyzer:
    """
    AI Analyzer using Llama 4 Maverick via OpenAI-compatible API
    """
    
    SYSTEM_PROMPT = """
You are an expert hotel inventory management consultant with 15 years of experience.
You specialize in:
- Pareto (80/20) analysis
- ABC classification
- Demand forecasting
- Waste reduction strategies
- Persian hotel industry practices

Always respond in fluent Persian (Farsi).
Provide actionable, data-driven recommendations.
Use JSON format when requested for structured output.
Be concise but thorough.
"""
    
    def __init__(self):
        self.api_key = os.environ.get('GROQ_API_KEY', '')
        self.base_url = "https://api.groq.com/openai/v1"
        self.model = "llama-3.3-70b-versatile"
        self.client = None
        self._init_client()
    
    def _init_client(self):
        """Initialize OpenAI client with Together AI endpoint"""
        if not OPENAI_AVAILABLE:
            print("⚠️ OpenAI library not available. Install with: pip install openai")
            return
        
        if not self.api_key:
            print("⚠️ GROQ_API_KEY not found in environment variables")
            return
        
        try:
            self.client = OpenAI(
                base_url=self.base_url,
                api_key=self.api_key
            )
        except Exception as e:
            print(f"⚠️ Failed to initialize OpenAI client: {str(e)}")
    
    def is_available(self):
        """Check if the analyzer is properly configured"""
        return self.client is not None and self.api_key
    
    def _call_api(self, prompt, temperature=0.7, max_tokens=2000):
        """Make API call to Llama 4"""
        if not self.is_available():
            return self._get_fallback_response(prompt)
        
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": self.SYSTEM_PROMPT},
                    {"role": "user", "content": prompt}
                ],
                temperature=temperature,
                max_tokens=max_tokens
            )
            content = response.choices[0].message.content
            # Clean markdown code blocks if present
            content = self._clean_json_response(content)
            return content
        except Exception as e:
            print(f"⚠️ API call failed: {str(e)}")
            return self._get_fallback_response(prompt)
    
    def _clean_json_response(self, content):
        """Remove markdown code blocks from JSON response"""
        if not content:
            return content
        
        # Remove ```json and ``` markers
        content = content.strip()
        if content.startswith('```json'):
            content = content[7:]
        elif content.startswith('```'):
            content = content[3:]
        
        if content.endswith('```'):
            content = content[:-3]
        
        return content.strip()
    
    def _get_fallback_response(self, prompt):
        """Return fallback response when API is unavailable"""
        return json.dumps({
            "status": "fallback",
            "message": "سرویس هوش مصنوعی در دسترس نیست. لطفاً بعداً تلاش کنید.",
            "executive_summary": "تحلیل آفلاین: بر اساس داده‌های موجود، کالاهای کلاس A نیاز به توجه ویژه دارند.",
            "recommendations": [
                "کنترل روزانه موجودی کالاهای کلاس A",
                "بررسی هفتگی قیمت تأمین‌کنندگان",
                "کاهش ضایعات با مدیریت بهتر انبار"
            ],
            "risks": [
                {"risk": "عدم دسترسی به API", "mitigation": "استفاده از تحلیل آفلاین"}
            ]
        }, ensure_ascii=False)
    
    def analyze_transaction_flow(self, transactions_data):
        """
        تحلیل روند تراکنش‌ها
        """
        prompt = f"""
تحلیل دقیق داده‌های تراکنش زیر را ارائه بده:

{json.dumps(transactions_data, ensure_ascii=False, indent=2)}

تحلیل شامل:
1. الگوهای خرید (Purchase patterns)
2. روند ضایعات (Waste trends)
3. پیشنهادات بهینه‌سازی (Optimization suggestions)
4. هشدارهای موجودی (Stock alerts)

خروجی به فرمت JSON:
{{
  "purchase_patterns": "...",
  "waste_trends": "...",
  "optimization_suggestions": ["..."],
  "stock_alerts": ["..."]
}}
"""
        
        result = self._call_api(prompt, temperature=0.7, max_tokens=2000)
        
        try:
            return json.loads(result)
        except json.JSONDecodeError:
            return {
                "raw_response": result,
                "purchase_patterns": "تحلیل در حال پردازش",
                "waste_trends": "نیاز به بررسی بیشتر",
                "optimization_suggestions": ["بهینه‌سازی موجودی"],
                "stock_alerts": ["بررسی موجودی انبار"]
            }
    
    def analyze_pareto_results(self, pareto_data):
        """
        تحلیل نتایج پارتو با خروجی خوانا
        Expert-level Pareto 80/20 analysis with validation
        """
        if hasattr(pareto_data, 'to_dict'):
            data_dict = pareto_data.to_dict('records')
        else:
            data_dict = pareto_data
        
        # Filter out invalid data (NULL, negative, zero)
        valid_data = [d for d in data_dict if d.get('amount', 0) and d.get('amount', 0) > 0]
        
        if not valid_data:
            return {
                "executive_summary": "داده‌ای معتبر برای تحلیل یافت نشد.",
                "class_a_analysis": "لطفاً ابتدا تراکنش‌های معتبر ثبت کنید.",
                "class_a_items": [],
                "recommendations": [],
                "risks": [],
                "pareto_validation": {"valid": False, "reason": "داده‌ای وجود ندارد"}
            }
        
        # Extract class A items (cumulative <= 80%)
        class_a_items = []
        for item in valid_data:
            if item.get('cumulative_percentage', 0) <= 80:
                class_a_items.append({
                    'item': item.get('item_name', 'نامشخص'),
                    'importance': f"{item.get('percentage', 0):.1f}% از کل ارزش - {item.get('amount', 0):,.0f} ریال",
                    'action': 'کنترل روزانه و ذخیره ایمنی'
                })
        
        # Calculate summary
        total_items = len(valid_data)
        class_a_count = len(class_a_items)
        total_amount = sum(item.get('amount', 0) for item in valid_data)
        class_a_amount = sum(item.get('amount', 0) for item in valid_data if item.get('cumulative_percentage', 0) <= 80)
        
        # Pareto 80/20 Validation
        class_a_pct_items = (class_a_count / total_items * 100) if total_items > 0 else 0
        class_a_pct_value = (class_a_amount / total_amount * 100) if total_amount > 0 else 0
        
        # True Pareto: ~20% items = ~80% value
        # Acceptable range: 15-35% items = 65-85% value
        pareto_valid = (15 <= class_a_pct_items <= 35) and (65 <= class_a_pct_value <= 85)
        pareto_ratio = class_a_pct_value / class_a_pct_items if class_a_pct_items > 0 else 0
        
        prompt = f"""
بر اساس تحلیل پارتو داده‌های موجودی هتل:
- تعداد کل اقلام: {total_items}
- اقلام کلاس A (حیاتی): {class_a_count} قلم
- ارزش کل: {total_amount:,.0f} ریال
- ارزش کلاس A: {class_a_amount:,.0f} ریال

یک خلاصه مدیریتی 2-3 جمله‌ای بنویس که:
1. وضعیت کلی را توضیح دهد
2. نکته مهم برای مدیر را بگوید
3. پیشنهاد عملی بدهد

فقط متن فارسی بده، بدون JSON یا فرمت خاص.
"""
        
        executive_summary = self._call_api(prompt, temperature=0.5, max_tokens=300)
        if not executive_summary or executive_summary.startswith('{'):
            # Bug #10: Prevent division by zero
            if total_items > 0 and total_amount > 0:
                executive_summary = f"از {total_items} قلم کالا، {class_a_count} قلم ({class_a_count/total_items*100:.0f}%) در کلاس A قرار دارند و {class_a_amount/total_amount*100:.0f}% ارزش کل را تشکیل می‌دهند. تمرکز بر این اقلام حیاتی، کلید مدیریت هزینه است."
            else:
                executive_summary = "داده‌ای برای تحلیل یافت نشد. لطفاً ابتدا تراکنش‌هایی ثبت کنید."
        
        # Bug #10: Safe division for class_a_analysis
        if total_items > 0 and total_amount > 0:
            class_a_analysis = f"{class_a_count} قلم از {total_items} قلم موجودی ({class_a_count/total_items*100:.0f}%) در کلاس A هستند. این اقلام {class_a_amount/total_amount*100:.0f}% از کل هزینه خرید را تشکیل می‌دهند و نیاز به کنترل روزانه و ذخیره ایمنی بالا دارند."
        else:
            class_a_analysis = "داده‌ای برای تحلیل یافت نشد."
        
        # Pareto validation message for CEO
        if pareto_valid:
            pareto_status = "✅ توزیع داده‌ها با قانون پارتو (80/20) سازگار است"
            pareto_confidence = "بالا"
        elif class_a_pct_value >= 60:
            pareto_status = "⚠️ توزیع نزدیک به پارتو است اما دقیقاً 80/20 نیست"
            pareto_confidence = "متوسط"
        else:
            pareto_status = "❌ توزیع با قانون پارتو مطابقت ندارد - بررسی داده‌ها توصیه می‌شود"
            pareto_confidence = "پایین"
        
        return {
            "executive_summary": executive_summary,
            "class_a_analysis": class_a_analysis,
            "class_a_items": class_a_items[:10],
            "recommendations": [
                "کنترل روزانه موجودی کالاهای کلاس A",
                "تأمین‌کننده بکاپ برای اقلام حیاتی داشته باشید",
                "بررسی هفتگی قیمت تأمین‌کنندگان",
                "ذخیره ایمنی 2 هفته‌ای برای کلاس A",
                "سفارش انبوه برای کالاهای کلاس C"
            ],
            "purchasing_strategy": f"تمرکز اصلی روی {class_a_count} قلم کلاس A باشد. برای این اقلام خرید دقیق و منظم انجام شود. کالاهای کلاس C را می‌توان انبوه و با فاصله زمانی بیشتر سفارش داد.",
            "risks": [
                {"risk": "کمبود موجودی کالاهای کلاس A", "mitigation": "نگهداری ذخیره ایمنی 2 هفته‌ای"},
                {"risk": "افزایش قیمت تأمین‌کنندگان", "mitigation": "قرارداد بلندمدت با قیمت ثابت"},
                {"risk": "ضایعات بالا در کالاهای فاسدشدنی", "mitigation": "خرید متناسب با مصرف واقعی"}
            ],
            # Expert Pareto validation for CEO trust
            "pareto_validation": {
                "valid": pareto_valid,
                "status": pareto_status,
                "confidence": pareto_confidence,
                "class_a_items_pct": round(class_a_pct_items, 1),
                "class_a_value_pct": round(class_a_pct_value, 1),
                "pareto_ratio": round(pareto_ratio, 2),
                "interpretation": f"{class_a_pct_items:.1f}% از کالاها، {class_a_pct_value:.1f}% از ارزش را تشکیل می‌دهند (نسبت: {pareto_ratio:.1f}x)"
            }
        }
    
    def generate_reorder_suggestions(self, items_data, consumption_history, purchase_history=None, stock_data=None):
        """
        پیشنهاد سفارش خرید بر اساس مصرف، خرید و موجودی - محاسبه هوشمند
        """
        import jdatetime
        
        suggestions = []
        
        # Create lookups
        consumption_lookup = {c['code']: c for c in consumption_history}
        purchase_lookup = {p['code']: p for p in (purchase_history or [])}
        stock_lookup = {s['code']: s for s in (stock_data or [])}
        
        for item in items_data:
            code = item.get('code', '')
            name = item.get('name', 'نامشخص')
            unit = item.get('unit', 'واحد')
            
            # Get consumption data
            consumption = consumption_lookup.get(code, {})
            total_consumed = consumption.get('total_consumed', 0)
            consumption_count = consumption.get('transaction_count', 0)
            
            # Get purchase data
            purchase = purchase_lookup.get(code, {})
            total_purchased = purchase.get('total_purchased', 0)
            purchase_count = purchase.get('transaction_count', 0)
            
            # Get current stock
            stock = stock_lookup.get(code, {})
            current_stock = stock.get('current_stock', 0)
            
            # Calculate daily averages
            daily_consumption = total_consumed / 30 if total_consumed > 0 else 0
            daily_purchase = total_purchased / 30 if total_purchased > 0 else 0
            
            # Smart priority calculation
            needs_reorder = False
            priority = 'low'
            reason = ''
            suggested_qty = 10  # Default minimum
            
            # Priority 1: High consumption items
            if daily_consumption > 10:
                priority = 'critical'
                needs_reorder = True
                suggested_qty = int(daily_consumption * 14)  # 2 weeks supply
                reason = f'مصرف بالا: روزانه {daily_consumption:.1f} {unit}'
            
            # Priority 2: Medium consumption items
            elif daily_consumption > 3:
                priority = 'normal'
                needs_reorder = True
                suggested_qty = int(daily_consumption * 14)
                reason = f'مصرف متوسط: روزانه {daily_consumption:.1f} {unit}'
            
            # Priority 3: Low stock with consumption history
            elif daily_consumption > 0 and current_stock < daily_consumption * 7:
                priority = 'critical'
                needs_reorder = True
                suggested_qty = int(daily_consumption * 14)
                reason = f'موجودی کم: {current_stock:.0f} {unit} (کمتر از 1 هفته)'
            
            # Priority 4: Frequent purchases (high purchase activity)
            elif purchase_count >= 3:
                priority = 'normal'
                needs_reorder = True
                avg_purchase = total_purchased / purchase_count if purchase_count > 0 else 10
                suggested_qty = int(avg_purchase)
                reason = f'خرید مکرر: {purchase_count} سفارش در ۳۰ روز'
            
            # Priority 5: Any consumption history
            elif consumption_count >= 2:
                priority = 'low'
                needs_reorder = True
                suggested_qty = int(daily_consumption * 14) if daily_consumption > 0 else 10
                reason = f'مصرف کم: {consumption_count} تراکنش در ۳۰ روز'
            
            # Priority 6: Low stock even without consumption
            elif current_stock > 0 and current_stock < 10:
                priority = 'low'
                needs_reorder = True
                suggested_qty = 20
                reason = f'موجودی پایین: {current_stock:.0f} {unit}'
            
            # No reorder needed
            else:
                needs_reorder = False
                reason = 'موجودی کافی یا بدون فعالیت'
            
            # Order date suggestion
            order_date = jdatetime.date.today().strftime('%Y/%m/%d')
            
            suggestions.append({
                "item_code": code,
                "item_name": name,
                "needs_reorder": needs_reorder,
                "suggested_quantity": max(suggested_qty, 1),
                "order_date": order_date,
                "priority": priority,
                "reason": reason,
                "current_stock": current_stock,
                "daily_consumption": daily_consumption
            })
        
        # Sort by priority and needs_reorder
        priority_order = {'critical': 0, 'normal': 1, 'low': 2}
        suggestions.sort(key=lambda x: (
            0 if x['needs_reorder'] else 1,
            priority_order.get(x['priority'], 3), 
            -x.get('suggested_quantity', 0)
        ))
        
        return suggestions
    
    def analyze_waste(self, waste_data):
        """
        تحلیل ضایعات
        """
        prompt = f"""
تحلیل داده‌های ضایعات زیر را ارائه بده:

{json.dumps(waste_data[:20], ensure_ascii=False, indent=2)}

تحلیل شامل:
1. الگوی ضایعات بر اساس نوع کالا
2. علل احتمالی ضایعات
3. راهکارهای کاهش ضایعات
4. اولویت‌بندی اقدامات

خروجی به فرمت JSON:
{{
  "waste_summary": "خلاصه وضعیت ضایعات",
  "patterns": [
    {{
      "item": "نام کالا",
      "waste_percentage": "درصد ضایعات",
      "cause": "علت احتمالی"
    }}
  ],
  "reduction_strategies": ["استراتژی 1", "استراتژی 2"],
  "priority_actions": [
    {{
      "action": "اقدام",
      "priority": "high/medium/low",
      "expected_impact": "تأثیر مورد انتظار"
    }}
  ]
}}
"""
        
        result = self._call_api(prompt, temperature=0.5, max_tokens=1500)
        
        try:
            return json.loads(result)
        except json.JSONDecodeError:
            return {
                "waste_summary": "تحلیل ضایعات نیاز به بررسی بیشتر دارد.",
                "patterns": [],
                "reduction_strategies": [
                    "بهبود شرایط نگهداری",
                    "کنترل دقیق تاریخ انقضا",
                    "آموزش پرسنل"
                ],
                "priority_actions": [
                    {"action": "بررسی سردخانه", "priority": "high", "expected_impact": "کاهش ۲۰٪ ضایعات"}
                ]
            }
    
    def get_daily_insights(self, kpi_data):
        """
        تولید بینش‌های روزانه برای داشبورد
        """
        prompt = f"""
بر اساس KPI های زیر، ۳ بینش مهم برای مدیر هتل تولید کن:

{json.dumps(kpi_data, ensure_ascii=False, indent=2)}

خروجی دقیقاً به این فرمت JSON:
[
  {{
    "icon": "📊",
    "text": "متن کوتاه بینش",
    "type": "info/warning/success",
    "link": "/reports/pareto"
  }},
  {{
    "icon": "⚠️",
    "text": "هشدار مهم",
    "type": "warning",
    "link": "/reports/abc"
  }},
  {{
    "icon": "✅",
    "text": "پیشنهاد مثبت",
    "type": "success",
    "link": "/transactions/"
  }}
]
"""
        
        result = self._call_api(prompt, temperature=0.7, max_tokens=500)
        
        try:
            parsed = json.loads(result)
            if isinstance(parsed, list):
                return parsed[:3]
            return [parsed]
        except json.JSONDecodeError:
            return [
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
