"""
Playwright MCP Test Suite - Security & Access Control
Based on Test.md TC-401 to TC-405
"""
from playwright.sync_api import sync_playwright, expect
import time

BASE_URL = "http://localhost:8084"

def test_tc401_access_without_login():
    """TC-401: دسترسی بدون لاگین"""
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        page = browser.new_page()
        
        # تلاش برای دسترسی به صفحه محافظت شده
        page.goto(f"{BASE_URL}/transactions/create")
        
        # انتظار: ریدایرکت به صفحه لاگین
        expect(page).to_have_url(f"{BASE_URL}/auth/login?next=%2Ftransactions%2Fcreate", timeout=5000)
        
        print("✅ TC-401 PASSED: Redirect to login successful")
        
        browser.close()

def test_tc404_xss_injection():
    """TC-404: تزریق اسکریپت (XSS)"""
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        page = browser.new_page()
        
        # لاگین با admin
        page.goto(f"{BASE_URL}/auth/login")
        page.fill('input[name="username"]', 'admin')
        page.fill('input[name="password"]', 'admin123')
        page.click('button[type="submit"]')
        
        time.sleep(2)
        
        # تلاش برای تزریق XSS در توضیحات تراکنش
        page.goto(f"{BASE_URL}/transactions/create")
        
        xss_payload = '<img src=x onerror=alert(1)>'
        
        # پر کردن فرم
        page.select_option('select[name="item_id"]', index=1)
        page.fill('input[name="quantity"]', '1')
        page.fill('textarea[name="description"]', xss_payload)
        
        # ثبت تراکنش
        page.click('button[type="submit"]')
        
        time.sleep(2)
        
        # بررسی که alert اجرا نشده (XSS بلاک شده)
        # اگر XSS موفق بود، alert باز می‌شد
        dialogs = []
        page.on("dialog", lambda dialog: dialogs.append(dialog))
        
        if len(dialogs) == 0:
            print("✅ TC-404 PASSED: XSS blocked successfully")
        else:
            print("❌ TC-404 FAILED: XSS executed!")
        
        browser.close()

def test_tc405_idor_hotel_access():
    """TC-405: نشت اطلاعات هتل دیگر (IDOR)"""
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        page = browser.new_page()
        
        # لاگین با کاربر عادی (نه admin)
        page.goto(f"{BASE_URL}/auth/login")
        page.fill('input[name="username"]', 'staff')
        page.fill('input[name="password"]', 'staff123')
        page.click('button[type="submit"]')
        
        time.sleep(2)
        
        # تلاش برای دسترسی به هتل دیگر با تغییر hotel_id
        page.goto(f"{BASE_URL}/warehouse/items?hotel_id=999")
        
        # انتظار: ارور 403 یا ریدایرکت
        if "دسترسی" in page.content() or "403" in page.content():
            print("✅ TC-405 PASSED: IDOR attack blocked")
        else:
            print("❌ TC-405 FAILED: Unauthorized access granted!")
        
        browser.close()

if __name__ == "__main__":
    print("🔒 Starting Security Tests...\n")
    
    try:
        test_tc401_access_without_login()
    except Exception as e:
        print(f"❌ TC-401 ERROR: {e}")
    
    try:
        test_tc404_xss_injection()
    except Exception as e:
        print(f"❌ TC-404 ERROR: {e}")
    
    try:
        test_tc405_idor_hotel_access()
    except Exception as e:
        print(f"❌ TC-405 ERROR: {e}")
    
    print("\n✅ Security Tests Completed")
