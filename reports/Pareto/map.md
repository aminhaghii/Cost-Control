🏗️ COMPLETE FLASK SYSTEM ARCHITECTURE
text
┌─────────────────────────────────────────────────────────┐
│  FLASK WEB APPLICATION (Multi-User)                    │
│  • Login/Authentication                                 │
│  • Dashboard (KPIs + Charts)                           │
│  • Forms (ورود تراکنش Food/NonFood)                    │
│  • Reports (Pareto + ABC + Trends)                     │
│  • Excel Export (Charts + Flowcharts + Tables)         │
└─────────────────────────────────────────────────────────┘
📁 COMPLETE FILE STRUCTURE
text
hotel_inventory_flask/
│
├── app.py                          # Flask app entry point
├── config.py                       # Configuration
├── requirements.txt                # Dependencies
├── .env                            # Environment variables
│
├── models/                         # SQLAlchemy Models
│   ├── __init__.py
│   ├── user.py                     # User model (login)
│   ├── item.py                     # Item master
│   ├── transaction.py              # Transaction model
│   └── alert.py                    # Alert model
│
├── routes/                         # Flask Routes (Controllers)
│   ├── __init__.py
│   ├── auth.py                     # Login/Logout/Register
│   ├── dashboard.py                # Main dashboard
│   ├── transactions.py             # Transaction CRUD
│   ├── reports.py                  # Reports & Analytics
│   └── export.py                   # Excel export
│
├── services/                       # Business Logic
│   ├── __init__.py
│   ├── pareto_service.py           # Pareto calculations
│   ├── abc_service.py              # ABC classification
│   ├── alert_service.py            # Alert generation
│   └── excel_service.py            # Excel generation with charts
│
├── templates/                      # Jinja2 HTML Templates (RTL)
│   ├── base.html                   # Base layout (RTL, Bootstrap RTL)
│   ├── auth/
│   │   ├── login.html
│   │   └── register.html
│   ├── dashboard/
│   │   └── index.html              # Main dashboard
│   ├── transactions/
│   │   ├── list.html               # Transaction list
│   │   ├── create.html             # Add transaction form
│   │   └── edit.html               # Edit transaction
│   └── reports/
│       ├── pareto.html             # Pareto report
│       └── abc.html                # ABC report
│
├── static/                         # CSS/JS/Images
│   ├── css/
│   │   ├── style.css               # Custom RTL styles
│   │   └── bootstrap-rtl.min.css   # Bootstrap RTL
│   ├── js/
│   │   ├── chart.js                # Chart.js for web charts
│   │   └── app.js                  # Custom JS
│   └── images/
│       └── logo.png
│
├── database/                       # SQLite database
│   └── inventory.db
│
├── exports/                        # Generated Excel files
│   └── [auto-generated files]
│
└── utils/                          # Utilities
    ├── __init__.py
    ├── decorators.py               # login_required decorator
    ├── persian_helper.py           # Persian date/number
    └── validators.py               # Form validation
🔐 FEATURES: چه قابلیت‌هایی دارد؟
1. Authentication System
python
# routes/auth.py
@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        user = User.query.filter_by(username=username).first()
        if user and user.check_password(password):
            session['user_id'] = user.id
            session['username'] = user.username
            flash('خوش آمدید!', 'success')
            return redirect(url_for('dashboard.index'))
        else:
            flash('نام کاربری یا رمز عبور اشتباه است', 'danger')
    
    return render_template('auth/login.html')
2. Dashboard با نمودارها
python
# routes/dashboard.py
@dashboard_bp.route('/')
@login_required
def index():
    # محاسبه KPIs
    today_transactions = Transaction.query.filter_by(
        transaction_date=date.today()
    ).count()
    
    today_purchase = db.session.query(
        func.sum(Transaction.total_amount)
    ).filter(
        Transaction.transaction_type == 'خرید',
        Transaction.transaction_date == date.today()
    ).scalar() or 0
    
    today_waste = db.session.query(
        func.sum(Transaction.total_amount)
    ).filter(
        Transaction.transaction_type == 'ضایعات',
        Transaction.transaction_date == date.today()
    ).scalar() or 0
    
    # هشدارها
    alerts = Alert.query.filter_by(is_resolved=False).limit(5).all()
    
    # داده نمودار
    chart_data = get_pareto_chart_data(days=30, category='Food')
    
    return render_template('dashboard/index.html',
                         today_transactions=today_transactions,
                         today_purchase=today_purchase,
                         today_waste=today_waste,
                         alerts=alerts,
                         chart_data=chart_data)
3. فرم ورود تراکنش (با Select2 برای جستجو)
xml
<!-- templates/transactions/create.html -->
<form method="POST" class="needs-validation" novalidate>
    <div class="row">
        <div class="col-md-6 mb-3">
            <label>تاریخ</label>
            <input type="date" name="transaction_date" 
                   class="form-control" required>
        </div>
        
        <div class="col-md-6 mb-3">
            <label>کالا</label>
            <select name="item_code" class="form-control select2" required>
                <option value="">انتخاب کالا...</option>
                {% for item in items %}
                <option value="{{ item.item_code }}">
                    {{ item.item_name_fa }} ({{ item.item_code }})
                </option>
                {% endfor %}
            </select>
        </div>
    </div>
    
    <div class="row">
        <div class="col-md-6 mb-3">
            <label>نوع تراکنش</label>
            <select name="transaction_type" class="form-control" required>
                <option value="خرید">خرید</option>
                <option value="مصرف">مصرف</option>
                <option value="ضایعات">ضایعات</option>
                <option value="اصلاحی">اصلاحی</option>
            </select>
        </div>
        
        <div class="col-md-6 mb-3">
            <label>گروه</label>
            <select name="category" class="form-control" required>
                <option value="Food">مواد غذایی</option>
                <option value="NonFood">مواد غیرغذایی</option>
            </select>
        </div>
    </div>
    
    <div class="row">
        <div class="col-md-4 mb-3">
            <label>مقدار</label>
            <input type="number" step="0.01" name="quantity" 
                   class="form-control" required>
        </div>
        
        <div class="col-md-4 mb-3">
            <label>قیمت واحد (ریال)</label>
            <input type="number" name="unit_price" 
                   class="form-control persian-number" required>
        </div>
        
        <div class="col-md-4 mb-3">
            <label>مبلغ کل</label>
            <input type="text" id="total_amount" 
                   class="form-control persian-number" readonly>
        </div>
    </div>
    
    <button type="submit" class="btn btn-primary btn-lg">
        💾 ذخیره تراکنش
    </button>
</form>
📊 EXCEL EXPORT: خروجی زیبا با نمودار و Flowchart
python
# services/excel_service.py
from openpyxl import Workbook
from openpyxl.chart import BarChart, LineChart, Reference
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils.dataframe import dataframe_to_rows
from openpyxl.drawing.image import Image

class ExcelReportGenerator:
    
    def generate_pareto_report(self, mode='purchase', category='Food', days=30):
        """
        ساخت فایل Excel با:
        - جدول پارتو با فرمت زیبا
        - نمودار Pareto (Bar + Line)
        - Flowchart تصمیم‌گیری
        - جدول ABC با رنگ‌بندی
        - Dashboard KPIs
        """
        wb = Workbook()
        
        # Sheet 1: Dashboard Overview
        self._create_dashboard_sheet(wb)
        
        # Sheet 2: Pareto Analysis + Chart
        self._create_pareto_sheet(wb, mode, category, days)
        
        # Sheet 3: ABC Classification
        self._create_abc_sheet(wb, mode, category, days)
        
        # Sheet 4: Flowchart
        self._create_flowchart_sheet(wb)
        
        # Sheet 5: Raw Data
        self._create_data_sheet(wb, days)
        
        # تنظیمات کلی
        for sheet in wb.worksheets:
            sheet.sheet_view.rightToLeft = True
        
        return wb
    
    def _create_dashboard_sheet(self, wb):
        ws = wb.active
        ws.title = "📊 Dashboard"
        
        # عنوان اصلی
        ws.merge_cells('A1:H1')
        ws['A1'] = '🏨 گزارش تحلیل موجودی هتل'
        ws['A1'].font = Font(name='B Nazanin', size=20, bold=True, color='FFFFFF')
        ws['A1'].fill = PatternFill(start_color='1F4788', end_color='1F4788', fill_type='solid')
        ws['A1'].alignment = Alignment(horizontal='center', vertical='center')
        ws.row_dimensions[1].height = 35
        
        # KPI Cards
        kpis = [
            ('B3', 'تراکنش امروز', 25, 'E8F5E9'),
            ('D3', 'خرید امروز', '12,500,000', 'E3F2FD'),
            ('F3', 'ضایعات امروز', '350,000', 'FFEBEE'),
            ('H3', 'هشدارها', 3, 'FFF3E0')
        ]
        
        for cell, title, value, color in kpis:
            # Title
            ws[cell] = title
            ws[cell].font = Font(name='B Nazanin', size=12, bold=True)
            ws[cell].fill = PatternFill(start_color=color, fill_type='solid')
            
            # Value
            value_cell = ws[chr(ord(cell[0]) + 1) + cell[1:]]
            value_cell.value = value
            value_cell.font = Font(size=18, bold=True)
            value_cell.alignment = Alignment(horizontal='center')
    
    def _create_pareto_sheet(self, wb, mode, category, days):
        ws = wb.create_sheet(f"📈 Pareto {category}")
        
        # دریافت داده
        pareto_df = self.pareto_service.calculate_pareto(mode, category, days)
        
        # عنوان
        ws.merge_cells('A1:H1')
        ws['A1'] = f'تحلیل پارتو: {mode} - {category} (آخرین {days} روز)'
        ws['A1'].font = Font(name='B Nazanin', size=16, bold=True, color='FFFFFF')
        ws['A1'].fill = PatternFill(start_color='2E7D32', fill_type='solid')
        ws['A1'].alignment = Alignment(horizontal='center', vertical='center')
        ws.row_dimensions[1].height = 30
        
        # Headers با رنگ
        headers = ['ردیف', 'کد کالا', 'نام کالا', 'مبلغ', 'درصد سهم', 
                   'مبلغ تجمعی', 'درصد تجمعی', 'کلاس ABC']
        
        for col_num, header in enumerate(headers, 1):
            cell = ws.cell(row=3, column=col_num)
            cell.value = header
            cell.font = Font(name='B Nazanin', size=12, bold=True, color='FFFFFF')
            cell.fill = PatternFill(start_color='455A64', fill_type='solid')
            cell.alignment = Alignment(horizontal='center', vertical='center')
        
        # Data rows با Conditional Formatting
        for r_idx, row in enumerate(dataframe_to_rows(pareto_df, index=False, header=False), 4):
            for c_idx, value in enumerate(row, 1):
                cell = ws.cell(row=r_idx, column=c_idx, value=value)
                cell.alignment = Alignment(horizontal='right')
                cell.font = Font(name='Calibri', size=11)
                
                # رنگ‌بندی ABC
                if c_idx == 8:  # ABC class column
                    if value == 'A':
                        cell.fill = PatternFill(start_color='C8E6C9', fill_type='solid')
                        cell.font = Font(bold=True, color='1B5E20')
                    elif value == 'B':
                        cell.fill = PatternFill(start_color='FFF9C4', fill_type='solid')
                        cell.font = Font(bold=True, color='F57F17')
                    elif value == 'C':
                        cell.fill = PatternFill(start_color='FFCCBC', fill_type='solid')
                        cell.font = Font(color='BF360C')
        
        # نمودار Pareto (Bar + Line combo)
        chart = BarChart()
        chart.type = "col"
        chart.style = 10
        chart.title = f"نمودار پارتو - {category}"
        chart.y_axis.title = 'مبلغ (ریال)'
        
        data = Reference(ws, min_col=4, min_row=3, max_row=3 + len(pareto_df))
        cats = Reference(ws, min_col=3, min_row=4, max_row=3 + len(pareto_df))
        chart.add_data(data, titles_from_data=True)
        chart.set_categories(cats)
        
        # خط درصد تجمعی
        line = LineChart()
        line.y_axis.axId = 200
        line.y_axis.title = "درصد تجمعی"
        
        data_line = Reference(ws, min_col=7, min_row=3, max_row=3 + len(pareto_df))
        line.add_data(data_line, titles_from_data=True)
        
        chart.y_axis.crosses = "max"
        chart += line
        
        ws.add_chart(chart, "J5")
        
        # Column widths
        ws.column_dimensions['A'].width = 8
        ws.column_dimensions['B'].width = 12
        ws.column_dimensions['C'].width = 25
        ws.column_dimensions['D'].width = 15
        ws.column_dimensions['E'].width = 12
        ws.column_dimensions['F'].width = 15
        ws.column_dimensions['G'].width = 14
        ws.column_dimensions['H'].width = 12
    
    def _create_flowchart_sheet(self, wb):
        ws = wb.create_sheet("🔄 Flowchart")
        
        ws.merge_cells('A1:J1')
        ws['A1'] = '🔄 فرآیند تصمیم‌گیری بر اساس کلاس ABC'
        ws['A1'].font = Font(name='B Nazanin', size=16, bold=True, color='FFFFFF')
        ws['A1'].fill = PatternFill(start_color='6A1B9A', fill_type='solid')
        ws['A1'].alignment = Alignment(horizontal='center', vertical='center')
        ws.row_dimensions[1].height = 30
        
        # ساخت flowchart با shapes و رنگ
        flowchart_data = [
            (3, 'D', '🎯 شروع: شناسایی کالا', 'FFE082'),
            (5, 'D', '📊 محاسبه پارتو و ABC', 'B2DFDB'),
            (7, 'D', 'کلاس کالا چیست؟', 'FFE0B2'),
            (9, 'B', '✅ کلاس A (80% ارزش)', 'C8E6C9'),
            (9, 'F', '⚠️ کلاس B (15% ارزش)', 'FFF9C4'),
            (9, 'H', '⚪ کلاس C (5% ارزش)', 'FFCCBC'),
            (11, 'B', 'کنترل روزانه موجودی', 'A5D6A7'),
            (11, 'F', 'کنترل هفتگی', 'FFF59D'),
            (11, 'H', 'کنترل ماهانه', 'FFAB91'),
        ]
        
        for row, col, text, color in flowchart_data:
            start_cell = f'{col}{row}'
            end_col = chr(ord(col) + 1)
            end_cell = f'{end_col}{row}'
            
            ws.merge_cells(f'{start_cell}:{end_cell}')
            cell = ws[start_cell]
            cell.value = text
            cell.font = Font(name='B Nazanin', size=11, bold=True)
            cell.fill = PatternFill(start_color=color, fill_type='solid')
            cell.alignment = Alignment(horizontal='center', vertical='center', wrap_text=True)
            
            # Border
            thin_border = Border(
                left=Side(style='medium'),
                right=Side(style='medium'),
                top=Side(style='medium'),
                bottom=Side(style='medium')
            )
            cell.border = thin_border
            ws.row_dimensions[row].height = 35
        
        # اضافه کردن فلش‌ها (با characters)
        arrows = [
            (4, 'D', '⬇'),
            (6, 'D', '⬇'),
            (8, 'D', '⬇'),
            (10, 'B', '⬇'),
            (10, 'F', '⬇'),
            (10, 'H', '⬇'),
        ]
        
        for row, col, arrow in arrows:
            cell = ws[f'{col}{row}']
            cell.value = arrow
            cell.font = Font(size=20, color='1976D2')
            cell.alignment = Alignment(horizontal='center')
🎨 OUTPUT EXCEL: چه شکلی است؟
Sheet 1: Dashboard Overview
text
┌──────────────────────────────────────────────────────────────┐
│  🏨 گزارش تحلیل موجودی هتل                                    │
└──────────────────────────────────────────────────────────────┘

┌─────────────┬─────────────┬─────────────┬─────────────┐
│ تراکنش امروز│  خرید امروز  │ ضایعات امروز │  هشدارها    │
│     25      │ 12,500,000  │   350,000   │      3      │
└─────────────┴─────────────┴─────────────┴─────────────┘

📊 نمودار میله‌ای روند ۳۰ روز گذشته
[Chart embedded in Excel]
Sheet 2: Pareto Analysis + Chart
text
┌──────────────────────────────────────────────────────────────┐
│  تحلیل پارتو: خرید - Food (آخرین 30 روز)                     │
└──────────────────────────────────────────────────────────────┘

┌──┬────┬─────────┬──────────┬──────┬────────┬──────┬────┐
│رد│کد  │نام کالا │  مبلغ    │سهم % │تجمعی   │تجم % │ ABC│
├──┼────┼─────────┼──────────┼──────┼────────┼──────┼────┤
│1 │F003│گوشت گوساله│185,000,000│42%│185,000,000│42%│🟢 A│
│2 │F001│برنج ایرانی│42,500,000 │10%│227,500,000│52%│🟢 A│
│3 │F006│ماهی      │78,400,000 │18%│305,900,000│70%│🟢 A│
│4 │F007│پنیر      │26,000,000 │6% │331,900,000│76%│🟢 A│
│5 │F002│روغن مایع  │16,800,000 │4% │348,700,000│80%│🟢 A│
│6 │F008│ماست      │16,800,000 │4% │365,500,000│84%│🟡 B│
└──┴────┴─────────┴──────────┴──────┴────────┴──────┴────┘

        [نمودار Pareto: Bar + Line]
           ██████          /
           ███            /
           ██            /
           █            /___
          F003 F001 F006 F007
Sheet 3: ABC Classification
text
🏷️ کلاس‌بندی ABC

┌────────────────────────────────────────────────┐
│ 🟢 کلاس A: اقلام حیاتی (80% ارزش)             │
│ تعداد: 5 قلم                                  │
│ توصیه: کنترل روزانه، سفارش دقیق، تامین بکاپ   │
└────────────────────────────────────────────────┘
[لیست کالاهای A با highlight سبز]

┌────────────────────────────────────────────────┐
│ 🟡 کلاس B: اقلام مهم (15% ارزش)              │
│ تعداد: 8 قلم                                  │
│ توصیه: کنترل هفتگی، سفارش معمولی              │
└────────────────────────────────────────────────┘
[لیست کالاهای B با highlight زرد]

┌────────────────────────────────────────────────┐
│ ⚪ کلاس C: اقلام معمولی (5% ارزش)             │
│ تعداد: 25 قلم                                 │
│ توصیه: کنترل ماهانه، سفارش انبوه              │
└────────────────────────────────────────────────┘
Sheet 4: Flowchart
text
         ┌─────────────────────┐
         │  🎯 شروع: شناسایی   │
         │      کالا           │
         └─────────┬───────────┘
                   ↓
         ┌─────────────────────┐
         │  📊 محاسبه پارتو    │
         │     و ABC           │
         └─────────┬───────────┘
                   ↓
         ┌─────────────────────┐
         │   کلاس کالا چیست؟   │
         └────┬─────┬──────┬───┘
              ↓     ↓      ↓
      ┌───────┐ ┌───────┐ ┌───────┐
      │کلاس A│ │کلاس B│ │کلاس C│
      │80%    │ │15%    │ │5%     │
      └───┬───┘ └───┬───┘ └───┬───┘
          ↓         ↓         ↓
      ┌───────┐ ┌───────┐ ┌───────┐
      │کنترل  │ │کنترل  │ │کنترل  │
      │روزانه │ │هفتگی  │ │ماهانه │
      └───────┘ └───────┘ └───────┘
🚀 QUICK START: نصب و اجرا
requirements.txt
text
Flask==3.0.0
Flask-SQLAlchemy==3.1.1
Flask-Login==0.6.3
Flask-WTF==1.2.1
WTForms==3.1.1
openpyxl==3.1.2
pandas==2.1.4
plotly==5.18.0
jdatetime==4.1.1
python-dotenv==1.0.0
Werkzeug==3.0.1
اجرا (فقط 3 دستور)
bash
# 1. نصب
pip install -r requirements.txt

# 2. ایجاد دیتابیس
python init_db.py

# 3. اجرا
python app.py

# باز شدن: http://localhost:5000
📊 نمونه کد کامل Excel Generator
python
# Route برای دانلود
@export_bp.route('/download-pareto-excel')
@login_required
def download_pareto_excel():
    mode = request.args.get('mode', 'خرید')
    category = request.args.get('category', 'Food')
    days = int(request.args.get('days', 30))
    
    # ساخت Excel
    excel_gen = ExcelReportGenerator()
    wb = excel_gen.generate_pareto_report(mode, category, days)
    
    # ذخیره در memory
    from io import BytesIO
    output = BytesIO()
    wb.save(output)
    output.seek(0)
    
    filename = f"Pareto_Report_{category}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
    
    return send_file(
        output,
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        as_attachment=True,
        download_name=filename
    )