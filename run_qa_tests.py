"""
QA Test Suite - Cost Control System
Based on Test.md - Comprehensive Testing
"""
from playwright.sync_api import sync_playwright
import time

BASE_URL = "http://localhost:8084"

class QAReport:
    def __init__(self):
        self.results = []
    
    def log(self, status, test_id, message):
        icon = "✅" if status == "PASS" else "❌" if status == "FAIL" else "⚠️"
        result = f"{icon} {test_id}: {message}"
        self.results.append((status, test_id, message))
        print(result)
    
    def summary(self):
        passed = sum(1 for s, _, _ in self.results if s == "PASS")
        failed = sum(1 for s, _, _ in self.results if s == "FAIL")
        errors = sum(1 for s, _, _ in self.results if s == "ERROR")
        total = len(self.results)
        
        print("\n" + "="*70)
        print("📊 FINAL QA REPORT - Cost Control System")
        print("="*70)
        print(f"Total Tests: {total}")
        print(f"✅ Passed: {passed}")
        print(f"❌ Failed: {failed}")
        print(f"⚠️ Errors: {errors}")
        print(f"Success Rate: {(passed/total*100):.1f}%" if total > 0 else "N/A")
        print("="*70)

report = QAReport()

def test_security():
    """🛡️ بخش ۴: امنیت و دسترسی"""
    print("\n🛡️ SECURITY & ACCESS CONTROL TESTS")
    print("-"*70)
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False, slow_mo=300)
        
        # TC-401: دسترسی بدون لاگین
        try:
            page = browser.new_page()
            page.goto(f"{BASE_URL}/transactions/create")
            page.wait_for_load_state('networkidle', timeout=5000)
            
            if "/auth/login" in page.url:
                report.log("PASS", "TC-401", "Redirect to login works")
            else:
                report.log("FAIL", "TC-401", "No authentication required!")
            page.close()
        except Exception as e:
            report.log("ERROR", "TC-401", str(e)[:50])
        
        # TC-405: IDOR Attack
        try:
            page = browser.new_page()
            page.goto(f"{BASE_URL}/auth/login")
            page.fill('input[name="username"]', 'admin')
            page.fill('input[name="password"]', 'admin123')
            page.click('button[type="submit"]')
            page.wait_for_load_state('networkidle', timeout=5000)
            
            # تلاش برای دسترسی به hotel_id غیرمجاز
            page.goto(f"{BASE_URL}/warehouse/items?hotel_id=9999")
            time.sleep(1)
            
            content = page.content()
            if "دسترسی" in content or "Access" in content:
                report.log("PASS", "TC-405", "IDOR protection works")
            else:
                report.log("FAIL", "TC-405", "Unauthorized access possible")
            page.close()
        except Exception as e:
            report.log("ERROR", "TC-405", str(e)[:50])
        
        browser.close()

def test_dashboard():
    """📊 بخش ۶: گزارشات و داشبورد"""
    print("\n📊 DASHBOARD & REPORTING TESTS")
    print("-"*70)
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False, slow_mo=300)
        page = browser.new_page()
        
        # Login
        try:
            page.goto(f"{BASE_URL}/auth/login")
            page.fill('input[name="username"]', 'admin')
            page.fill('input[name="password"]', 'admin123')
            page.click('button[type="submit"]')
            page.wait_for_load_state('networkidle', timeout=5000)
            
            # TC-601: بررسی داشبورد
            page.goto(f"{BASE_URL}/")
            page.wait_for_selector('.card', timeout=15000)
            
            cards = page.locator('.card').count()
            if cards >= 3:
                report.log("PASS", "TC-601", f"Dashboard loaded ({cards} widgets)")
            else:
                report.log("FAIL", "TC-601", "Dashboard incomplete")
            
            # TC-603: Timezone
            content = page.content()
            if "امروز" in content:
                report.log("PASS", "TC-603", "Iran timezone working")
            else:
                report.log("FAIL", "TC-603", "Timezone issue")
                
        except Exception as e:
            report.log("ERROR", "TC-601/603", str(e)[:50])
        
        browser.close()

def test_transactions():
    """💳 بخش ۲: موتور تراکنش‌ها"""
    print("\n💳 TRANSACTION ENGINE TESTS")
    print("-"*70)
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False, slow_mo=300)
        page = browser.new_page()
        
        try:
            # Login
            page.goto(f"{BASE_URL}/auth/login")
            page.fill('input[name="username"]', 'admin')
            page.fill('input[name="password"]', 'admin123')
            page.click('button[type="submit"]')
            page.wait_for_load_state('networkidle', timeout=5000)
            
            # TC-201: خرید عادی
            page.goto(f"{BASE_URL}/transactions/create")
            page.wait_for_selector('select[name="item_id"]', timeout=5000)
            
            # انتخاب آیتم
            options = page.locator('select[name="item_id"] option').count()
            if options > 1:
                page.select_option('select[name="item_id"]', index=1)
                page.fill('input[name="quantity"]', '5')
                page.select_option('select[name="transaction_type"]', 'خرید')
                
                page.click('button[type="submit"]')
                time.sleep(2)
                
                if "موفق" in page.content():
                    report.log("PASS", "TC-201", "Purchase transaction created")
                else:
                    report.log("FAIL", "TC-201", "Transaction failed")
            else:
                report.log("ERROR", "TC-201", "No items available")
            
            # TC-206: Decimal precision
            page.goto(f"{BASE_URL}/transactions/create")
            page.wait_for_selector('select[name="item_id"]', timeout=5000)
            page.select_option('select[name="item_id"]', index=1)
            page.fill('input[name="quantity"]', '0.1')
            page.select_option('select[name="transaction_type"]', 'خرید')
            page.click('button[type="submit"]')
            time.sleep(2)
            
            if "موفق" in page.content():
                report.log("PASS", "TC-206", "Decimal quantity handled")
            else:
                report.log("FAIL", "TC-206", "Decimal issue")
                
        except Exception as e:
            report.log("ERROR", "TC-201/206", str(e)[:50])
        
        browser.close()

def test_inventory():
    """📦 بخش ۱: مدیریت کالا"""
    print("\n📦 INVENTORY MANAGEMENT TESTS")
    print("-"*70)
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False, slow_mo=300)
        page = browser.new_page()
        
        try:
            # Login
            page.goto(f"{BASE_URL}/auth/login")
            page.fill('input[name="username"]', 'admin')
            page.fill('input[name="password"]', 'admin123')
            page.click('button[type="submit"]')
            page.wait_for_load_state('networkidle', timeout=5000)
            
            # TC-101: ساخت کالا
            page.goto(f"{BASE_URL}/admin/items/create")
            page.wait_for_selector('input[name="item_code"]', timeout=15000)
            
            unique_code = f"TEST{int(time.time())}"
            page.fill('input[name="item_code"]', unique_code)
            page.fill('input[name="item_name_fa"]', 'کالای تست QA')
            page.select_option('select[name="category"]', 'Food')
            page.select_option('select[name="unit"]', 'کیلوگرم')
            page.fill('input[name="unit_price"]', '1000')
            
            page.click('button[type="submit"]')
            time.sleep(2)
            
            if "موفق" in page.content():
                report.log("PASS", "TC-101", "Item created successfully")
            else:
                report.log("FAIL", "TC-101", "Item creation failed")
            
            # TC-105: لیست موجودی
            page.goto(f"{BASE_URL}/warehouse/items?hotel_id=1")
            page.wait_for_selector('table', timeout=15000)
            
            rows = page.locator('tbody tr').count()
            if rows > 0:
                report.log("PASS", "TC-105", f"Inventory list shows {rows} items")
            else:
                report.log("FAIL", "TC-105", "No items in inventory")
                
        except Exception as e:
            report.log("ERROR", "TC-101/105", str(e)[:50])
        
        browser.close()

def test_brute_force():
    """🔐 TC-702: قفل شدن حساب"""
    print("\n🔐 BRUTE FORCE PROTECTION TEST")
    print("-"*70)
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False, slow_mo=200)
        page = browser.new_page()
        
        try:
            # 5 بار پسورد اشتباه
            for i in range(5):
                page.goto(f"{BASE_URL}/auth/login")
                page.fill('input[name="username"]', 'testuser')
                page.fill('input[name="password"]', f'wrong{i}')
                page.click('button[type="submit"]')
                time.sleep(0.5)
            
            # تلاش ششم
            page.goto(f"{BASE_URL}/auth/login")
            page.fill('input[name="username"]', 'testuser')
            page.fill('input[name="password"]', 'wrong5')
            page.click('button[type="submit"]')
            time.sleep(1)
            
            content = page.content()
            if "قفل" in content or "lock" in content.lower():
                report.log("PASS", "TC-702", "Account locked after 5 attempts")
            else:
                report.log("FAIL", "TC-702", "No lockout mechanism")
                
        except Exception as e:
            report.log("ERROR", "TC-702", str(e)[:50])
        
        browser.close()

if __name__ == "__main__":
    print("="*70)
    print("🕵️‍♂️ QA & PENETRATION TEST - Cost Control System")
    print("="*70)
    print(f"Target: {BASE_URL}")
    print(f"Test Plan: Test.md")
    print("="*70)
    
    test_security()
    test_dashboard()
    test_transactions()
    test_inventory()
    test_brute_force()
    
    report.summary()
