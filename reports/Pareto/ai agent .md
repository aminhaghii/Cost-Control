🔗 مرحله 1: چک و Integration پلتفرم
چک‌لیست Integration:
به Agent بده:

text
Check and fix all integrations in the Flask app:

1. Verify app.py imports all blueprints correctly
2. Ensure all routes use @login_required where needed
3. Check database relationships (Foreign Keys)
4. Verify templates extend base.html correctly
5. Test all URL routes are registered
6. Check flash messages display properly

Create a test script: test_integration.py that:
- Tests database connection
- Tests all routes are accessible
- Checks model relationships
- Validates Persian/RTL rendering

Output any errors found and fixes needed.
🤖 مرحله 2: اتصال به Llama 4 Maverick
ساختار تحلیل روند با LLM:
python
# llama_analyzer.py
from openai import OpenAI
import json

class WorkflowAnalyzer:
    def __init__(self):
        # Llama 4 Maverick از طریق OpenAI-compatible API
        self.client = OpenAI(
            base_url="https://api.together.xyz/v1",  # یا هر endpoint دیگر
            api_key="YOUR_API_KEY"
        )
        self.model = "meta-llama/llama-4-maverick-17b-128e-instruct"
    
    def analyze_transaction_flow(self, transactions_data):
        """
        تحلیل روند تراکنش‌ها
        """
        prompt = f"""
You are a hotel inventory expert. Analyze this transaction data:

{json.dumps(transactions_data, ensure_ascii=False, indent=2)}

Provide analysis in Persian:
1. الگوهای خرید (Purchase patterns)
2. روند ضایعات (Waste trends)
3. پیشنهادات بهینه‌سازی (Optimization suggestions)
4. هشدارهای موجودی (Stock alerts)

Output in JSON format with Persian text.
"""
        
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": "You are an expert hotel inventory analyst. Always respond in Persian."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.7,
            max_tokens=2000
        )
        
        return response.choices[0].message.content
    
    def analyze_pareto_results(self, pareto_df):
        """
        تحلیل نتایج پارتو
        """
        # تبدیل DataFrame به دیکشنری
        data_dict = pareto_df.to_dict('records')
        
        prompt = f"""
تحلیل دقیق نتایج پارتو زیر را ارائه بده:

{json.dumps(data_dict, ensure_ascii=False, indent=2)}

تحلیل شامل:
1. شناسایی کالاهای کلاس A و اهمیت آن‌ها
2. توصیه‌های مدیریت موجودی برای هر کلاس
3. استراتژی خرید برای 30 روز آینده
4. ریسک‌های احتمالی

خروجی به صورت JSON با ساختار:
{
  "class_a_analysis": "...",
  "recommendations": [...],
  "purchasing_strategy": "...",
  "risks": [...]
}
"""
        
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": "You are a Pareto analysis expert for hotel inventory."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.5,
            max_tokens=1500
        )
        
        return json.loads(response.choices[0].message.content)
    
    def generate_reorder_suggestions(self, items_data, consumption_history):
        """
        پیشنهاد سفارش خرید بر اساس مصرف
        """
        prompt = f"""
بر اساس داده‌های زیر، پیشنهاد سفارش خرید بده:

کالاها:
{json.dumps(items_data, ensure_ascii=False, indent=2)}

تاریخچه مصرف 30 روز اخیر:
{json.dumps(consumption_history, ensure_ascii=False, indent=2)}

برای هر کالا مشخص کن:
1. آیا نیاز به سفارش دارد؟
2. مقدار پیشنهادی سفارش
3. زمان پیشنهادی سفارش
4. اولویت (بحرانی/عادی/پایین)

JSON output format:
[
  {{
    "item_code": "...",
    "item_name": "...",
    "needs_reorder": true/false,
    "suggested_quantity": number,
    "order_date": "YYYY-MM-DD",
    "priority": "critical/normal/low",
    "reason": "..."
  }}
]
"""
        
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": "You are an inventory planning expert."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.3,  # کمتر برای دقت بیشتر
            max_tokens=2000
        )
        
        return json.loads(response.choices[0].message.content)
🔄 مرحله 3: Integration با Routes
اضافه کردن AI Analysis به Reports:
به Agent بده:

text
Create file: hotel_inventory_flask/routes/ai_analysis.py

Requirements:
- Create Blueprint: ai_bp = Blueprint('ai_analysis', __name__)
- Import WorkflowAnalyzer from llama_analyzer
- Import ParetoService, Transaction, Item models
- Create login_required routes

Routes:

1. @ai_bp.route('/analyze-pareto')
   @login_required
   Logic:
   - Get pareto data using ParetoService
   - Call WorkflowAnalyzer.analyze_pareto_results()
   - Render 'ai_analysis/pareto_insights.html' with AI analysis

2. @ai_bp.route('/reorder-suggestions')
   @login_required
   Logic:
   - Get all items from database
   - Get consumption history (last 30 days, type='مصرف')
   - Call WorkflowAnalyzer.generate_reorder_suggestions()
   - Render 'ai_analysis/reorder.html' with suggestions

3. @ai_bp.route('/waste-analysis')
   @login_required
   Logic:
   - Get waste transactions (last 30 days)
   - Group by waste_reason and item
   - Call WorkflowAnalyzer.analyze_transaction_flow()
   - Render 'ai_analysis/waste.html' with insights

Register this blueprint in app.py with url_prefix='/ai'
📊 مرحله 4: Templates برای AI Analysis
Template 1: نمایش تحلیل پارتو
به Agent بده:

text
Create file: hotel_inventory_flask/templates/ai_analysis/pareto_insights.html

Requirements:
- Extend base.html
- Title: "🤖 تحلیل هوشمند پارتو"
- Display AI analysis results in Bootstrap cards:
  
  Card 1: تحلیل کلاس A
  - Show {{ analysis.class_a_analysis }}
  - Use alert-info style
  
  Card 2: توصیه‌های مدیریت
  - Loop through {{ analysis.recommendations }}
  - Display as ordered list
  - Use alert-success style
  
  Card 3: استراتژی خرید
  - Show {{ analysis.purchasing_strategy }}
  - Use alert-warning style
  
  Card 4: ریسک‌ها و هشدارها
  - Loop through {{ analysis.risks }}
  - Display as list with badge-danger
  - Use alert-danger style

- Add "بازگشت به گزارش پارتو" button
- Add "📥 ذخیره تحلیل PDF" button (placeholder for Phase 2)

Use Persian fonts and RTL layout.
Template 2: پیشنهادات سفارش
به Agent بده:

text
Create file: hotel_inventory_flask/templates/ai_analysis/reorder.html

Requirements:
- Extend base.html
- Title: "🛒 پیشنهادات سفارش خرید (AI)"
- Create Bootstrap table with columns:
  * کد کالا
  * نام کالا
  * مقدار پیشنهادی
  * تاریخ پیشنهادی
  * اولویت (badge: danger for critical, warning for normal, secondary for low)
  * دلیل
  * اقدام (button: "✅ ثبت سفارش")

- Filter buttons at top:
  * همه
  * بحرانی
  * عادی

- Show empty state if no suggestions

- Add JavaScript to filter by priority

Use color coding:
- Critical: bg-danger-subtle
- Normal: bg-warning-subtle
- Low: bg-light
🧪 مرحله 5: تست Integration با Llama
اسکریپت تست:
به Agent بده:

text
Create file: hotel_inventory_flask/test_llama_integration.py

Requirements:
- Import app, db
- Import all models
- Import WorkflowAnalyzer
- Create test functions:

1. test_database_connection():
   - Test db.create_all() works
   - Test sample query
   - Print success/failure

2. test_pareto_service():
   - Create sample transactions
   - Run ParetoService.calculate_pareto()
   - Verify DataFrame output
   - Print results

3. test_llama_analyzer():
   - Create WorkflowAnalyzer instance
   - Test with mock data
   - Print AI response
   - Verify JSON parsing works

4. test_full_workflow():
   - Simulate: Login → Add Transaction → View Pareto → AI Analysis
   - Check each step
   - Print complete flow results

if __name__ == '__main__':
    Run all tests and print summary report

Handle errors gracefully and print diagnostics.
📈 مرحله 6: Dashboard با AI Insights
آپدیت Dashboard:
به Agent بده:

text
Update file: hotel_inventory_flask/templates/dashboard/index.html

Add new section after KPI cards:

Section: "🤖 پیشنهادات هوشمند امروز"
- Create Bootstrap card with list-group
- Show top 3 AI insights (fetch from AI route on page load)
- Each insight as list-group-item with:
  * Icon (📊/⚠️/✅)
  * Short text
  * "مشاهده جزئیات" link

Add AJAX call in JavaScript:
- Fetch from /ai/daily-insights endpoint
- Update insights section dynamically
- Show loading spinner while fetching

Example insights:
- "کلاس A: گوشت گوساله نیاز به سفارش فوری دارد"
- "هشدار: روند ضایعات سبزیجات 20% افزایش یافته"
- "پیشنهاد: خرید برنج را به روز شنبه موکول کنید"
🔐 مرحله 7: Environment Variables
به Agent بده:

text
Create file: hotel_inventory_flask/.env.example

Content:
SECRET_KEY=your-secret-key-here
TOGETHER_API_KEY=your-together-ai-key
DATABASE_URL=sqlite:///database/inventory.db

Also update config.py to load these from environment using:
import os
from dotenv import load_dotenv

load_dotenv()
📋 چک‌لیست نهایی Integration
bash
# 1. نصب کتابخانه‌های اضافی
pip install openai python-dotenv

# 2. تنظیم API Key
export TOGETHER_API_KEY="your_key_here"

# 3. اجرای تست‌ها
python test_llama_integration.py

# 4. اجرای برنامه
python app.py

# 5. تست مسیرها:
# - http://localhost:5000/ai/analyze-pareto
# - http://localhost:5000/ai/reorder-suggestions
# - http://localhost:5000/ai/waste-analysis
🎯 Prompt برای Llama 4 (بهینه‌سازی شده)
Template اصلی:
python
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

def create_analysis_prompt(data_type, data, additional_context=""):
    """
    ساخت prompt بهینه برای Llama 4
    """
    
    base_prompts = {
        "pareto": """
تحلیل دقیق داده‌های پارتو زیر را ارائه بده و برای مدیر هتل توصیه‌های عملی بده:

داده‌ها:
{data}

تحلیل مورد نیاز:
1. شناسایی اقلام کلاس A و چرایی اهمیت آن‌ها
2. استراتژی مدیریت برای هر کلاس (A/B/C)
3. پیشنهاد خرید و انبارداری برای 30 روز آینده
4. ریسک‌های احتمالی و راه‌حل‌ها

{additional_context}

خروجی به فرمت JSON:
{{
  "executive_summary": "خلاصه مدیریتی یک پاراگراف",
  "class_a_items": [
    {{
      "item": "نام کالا",
      "importance": "چرا مهم است",
      "action": "اقدام پیشنهادی"
    }}
  ],
  "recommendations": ["توصیه 1", "توصیه 2", ...],
  "risks": [
    {{
      "risk": "شرح ریسک",
      "mitigation": "راه‌حل"
    }}
  ]
}}
""",
        
        "reorder": """
بر اساس داده‌های مصرف و موجودی، پیشنهاد سفارش خرید بده:

اقلام موجود:
{data}

مصرف 30 روز گذشته:
{additional_context}

برای هر کالا تعیین کن:
1. نیاز به سفارش: بله/خیر
2. مقدار پیشنهادی (عدد)
3. فوریت: بحرانی/عادی/پایین
4. دلیل

JSON format:
[
  {{
    "item_code": "F001",
    "item_name": "برنج ایرانی",
    "current_stock": 50,
    "avg_daily_consumption": 10,
    "days_until_stockout": 5,
    "needs_reorder": true,
    "suggested_quantity": 200,
    "priority": "critical",
    "reason": "موجودی برای کمتر از یک هفته کافی است"
  }}
]
"""
    }
    
    return base_prompts[data_type].format(
        data=json.dumps(data, ensure_ascii=False, indent=2),
        additional_context=additional_context
    )
🚀 اجرای نهایی
دستور کامل به Agent:
text
Create a complete integration test script that:

1. Initializes database with sample data
2. Creates 50 sample transactions (mixed Food/NonFood, خرید/مصرف/ضایعات)
3. Runs Pareto analysis
4. Calls Llama 4 for AI analysis
5. Displays results in terminal with Persian formatting
6. Saves results to JSON file: analysis_results.json

Script should handle:
- API connection errors (retry logic)
- Database errors (rollback)
- JSON parsing errors (fallback to plain text)
- Persian text encoding (UTF-8)

Output format:
✅ Database initialized
✅ 50 transactions created
✅ Pareto analysis completed
✅ AI analysis received
━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🤖 AI INSIGHTS:
[display formatted Persian text]
━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📁 Results saved to analysis_results.json