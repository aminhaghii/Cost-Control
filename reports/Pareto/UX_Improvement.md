📋 نقشه راه بهبود UX/UI - سیستم Cost Control
🎯 تحلیل وضعیت فعلی (Current State Analysis)
✅ نقاط قوت موجود
طراحی RTL فارسی درست

Bootstrap 5 و طراحی Responsive

فونت Vazirmatn (خوانایی بالا)

رنگ‌بندی حرفه‌ای (Gradient Navbar)

کارت‌های KPI جذاب

ساعت زنده تهران (Live Clock)

Select2 برای جستجوی کالا

❌ نقاط ضعف (Pain Points)
۱. پیچیدگی ناوبری (Navigation Overload)
منوی بالا (Navbar) + سایدبار = تکراری

کاربر گیج می‌شود کجا کلیک کند

دسته‌بندی‌ها مشخص نیست

۲. فرم‌های طولانی (Form Fatigue)
فرم ثبت تراکنش پر از فیلد است

هیچ راهنمایی (Tooltip) ندارد

خطاها زیر فرم می‌افتد (باید اسکرول کنی)

۳. جداول سنگین (Data Overwhelm)
۶۶۴ کالا در یک صفحه (گزارش QA شما)

Pagination ندارد

فیلتر محدود است

۴. بازخورد ضعیف (Weak Feedback)
پیام‌های موفقیت سریع محو می‌شوند (۵ ثانیه)

در حین Import اکسل، هیچ Progress Bar نیست

وقتی چیزی Loading است، نشانگری ندارد

۵. دسترسی (Accessibility)
رنگ‌ها برای کوررنگ‌ها مناسب نیست

کلیدهای میانبر ندارد

Navigation با Keyboard سخت است

🚀 برنامه بهبود (مرحله به مرحله)
فاز ۱: اصلاحات سریع (Quick Wins - 1 هفته)
این تغییرات بدون دست زدن به Backend قابل اجرا هستند.

📌 بهبود ۱: Pagination جداول
مشکل: ۶۶۴ کالا در یک صفحه کند است.
راه‌حل:

xml
<!-- اضافه کردن Pagination به templates/warehouse/inventory_list.html -->
<nav aria-label="Page navigation">
  <ul class="pagination justify-content-center">
    <li class="page-item"><a class="page-link" href="?page=1">۱</a></li>
    <li class="page-item"><a class="page-link" href="?page=2">۲</a></li>
    ...
  </ul>
</nav>
Backend: افزودن page و per_page به کوئری‌ها.

📌 بهبود ۲: Loading Spinner
مشکل: کاربر نمی‌داند سیستم در حال کار است یا هنگ کرده.
راه‌حل:

javascript
// اضافه کردن به base.html
$('form').on('submit', function() {
    $(this).find('button[type=submit]').html(
        '<span class="spinner-border spinner-border-sm"></span> در حال ذخیره...'
    ).prop('disabled', true);
});
📌 بهبود ۳: Progress Bar برای Import
راه‌حل:

xml
<!-- در templates/admin/import_preview.html -->
<div class="progress" id="importProgress" style="display:none;">
  <div class="progress-bar progress-bar-striped progress-bar-animated" 
       role="progressbar" style="width: 0%">0%</div>
</div>
📌 بهبود ۴: Tooltips راهنما
xml
<!-- اضافه کردن به فیلدهای پیچیده -->
<label>قیمت واحد
  <i class="fas fa-info-circle text-muted" 
     data-bs-toggle="tooltip" 
     title="قیمت هر واحد کالا به ریال"></i>
</label>
📌 بهبود ۵: پیام‌های بهتر
python
# تغییر مدت نمایش flash messages در base.html
setTimeout(function() {
    $('.alert-float').fadeOut('slow');
}, 10000); // 10 ثانیه به جای 5
فاز ۲: بازطراحی تجربه (UX Redesign - 2 هفته)
📌 بهبود ۶: ساده‌سازی منو (Menu Simplification)
قبل:

Navbar: 7 آیتم

Sidebar: 9 آیتم

تکراری!

بعد:

text
Navbar (فقط لوگو + یوزر)
Sidebar (دسته‌بندی شده):
  📊 داشبورد
  ──────────
  📦 انبار
    ├─ موجودی کالا
    ├─ ثبت ورود/خروج
    └─ انبارگردانی
  ──────────
  📈 گزارش‌ها
    ├─ خلاصه مدیریتی
    ├─ تحلیل پارتو
    └─ کلاس‌بندی ABC
  ──────────
  🤖 چت‌بات
  🔧 تنظیمات (فقط Admin)
📌 بهبود ۷: فرم هوشمند (Smart Forms)
ویژگی‌ها:

Auto-complete: وقتی کالا انتخاب می‌شود، قیمت خودکار پر شود.

محاسبه لحظه‌ای: جمع کل را بلافاصله نشان بده.

Validation لحظه‌ای: قبل از Submit خطا را نشان بده.

javascript
// اضافه کردن به templates/transactions/create.html
$('#item_id').on('change', function() {
    let itemId = $(this).val();
    $.get('/api/items/' + itemId, function(data) {
        $('#unit_price').val(data.unit_price); // پر کردن خودکار
        calculateTotal(); // محاسبه
    });
});
📌 بهبود ۸: جستجوی پیشرفته (Advanced Search)
قبل: فیلتر فقط تاریخ
بعد:

xml
<div class="row g-2">
  <div class="col-md-3">
    <input type="text" placeholder="جستجو در نام کالا..." class="form-control" />
  </div>
  <div class="col-md-3">
    <select class="form-select"><option>همه دسته‌ها</option></select>
  </div>
  <div class="col-md-2">
    <select class="form-select"><option>کلاس A</option></select>
  </div>
</div>
فاز ۳: ویژگی‌های پیشرفته (Advanced Features - 3 هفته)
📌 بهبود ۹: Dark Mode (حالت شب)
css
/* اضافه کردن toggle switch */
body.dark-mode {
    background-color: #1a1a1a;
    color: #e0e0e0;
}
.dark-mode .card {
    background-color: #2d2d2d;
}
📌 بهبود ۱۰: Dashboard تعاملی (Interactive Dashboard)
نمودارها clickable شوند (کلیک روی Class A → لیست کالاها)

فیلتر تاریخ Real-time باشد (بدون Reload)

📌 بهبود ۱۱: Bulk Actions (عملیات دسته‌جمعی)
xml
<!-- در لیست تراکنش‌ها -->
<input type="checkbox" /> انتخاب همه
<button>حذف دسته‌جمعی</button>
<button>Export Excel</button>
📌 بهبود ۱۲: کلیدهای میانبر (Keyboard Shortcuts)
text
Ctrl+N: ثبت تراکنش جدید
Ctrl+F: جستجو
Ctrl+P: گزارش پارتو
Esc: بستن Modal
📄 فایل Prompt برای Agent
این فایل UX_Improvement_Plan.md را به Agent بده تا شروع به پیاده‌سازی کند:

text
# UX Improvement Implementation Plan

## Mission
Improve user experience of Cost-Control system through systematic UI/UX enhancements.

## Phase 1: Quick Wins (Priority: HIGH)

### Task 1.1: Add Pagination
File: `routes/warehouse.py`
Action:
- Add `page` parameter to `/warehouse/inventory` route
- Use `paginate(page=page, per_page=50)`
- Update template to show pagination controls

### Task 1.2: Loading Indicators
File: `templates/base.html`
Action:
- Add global submit button handler with spinner
- Add CSS for `.btn-loading` class

### Task 1.3: Progress Bar for Import
Files: `templates/admin/import_preview.html` + `routes/admin.py`
Action:
- Add progress div with Bootstrap progress-bar
- Use AJAX polling to check import status

### Task 1.4: Tooltips
File: `templates/transactions/create.html`
Action:
- Add Bootstrap tooltips to all labels
- Initialize tooltips in JavaScript

### Task 1.5: Better Flash Messages
File: `templates/base.html`
Action:
- Increase timeout to 10 seconds
- Add close button that doesn't auto-hide

## Phase 2: UX Redesign

### Task 2.1: Simplify Navigation
File: `templates/base.html`
Action:
- Remove redundant navbar items
- Group sidebar items into collapsible sections
- Add icons for visual hierarchy

### Task 2.2: Smart Forms
Files: `templates/transactions/create.html` + `static/js/app.js`
Action:
- Add `/api/items/<id>` endpoint to get item details
- Auto-fill unit_price when item selected
- Real-time validation with inline error messages

### Task 2.3: Advanced Search
File: `templates/warehouse/inventory_list.html`
Action:
- Add search input with debounce (300ms)
- Add category and ABC class filters
- Use AJAX for instant results (no page reload)

## Deliverables
- Modified template files with inline comments
- New CSS classes in `static/css/custom.css`
- New JS utilities in `static/js/app.js`
- Updated routes with pagination support
🎨 Mockup تصویری (برای الهام)
قبل از بهبود:

text
Sidebar پر از لینک → جدول شلوغ → دکمه‌های کوچک
بعد از بهبود:

text
Sidebar گروه‌بندی شده → Pagination → دکمه‌های واضح با آیکون
📊 معیارهای موفقیت (Success Metrics)
بعد از اعمال تغییرات، این موارد را بسنج:

سرعت: آیا صفحه موجودی کمتر از ۲ ثانیه لود می‌شود؟

رضایت: آیا تعداد کلیک‌ها برای یک کار کم شده؟

خطاها: آیا تعداد ارورهای Validation کاهش یافته؟