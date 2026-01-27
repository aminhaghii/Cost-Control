1️⃣ فاز اول: اصلاحات حیاتی داده و همزمانی (Data Integrity & Race Conditions)
هدف: حل مشکل گم شدن موجودی در همزمانی، باگ رول‌بک ایمپورت اکسل و مشکل تبدیل واحد.

text
Act as a Senior Python Backend Engineer. I need you to fix three CRITICAL data integrity issues in my Flask application (`services/stock_service.py`, `services/data_importer.py`, `models/transaction.py`).

**Task 1: Fix Race Condition in Stock Updates (Atomic Updates)**
In `services/stock_service.py` and `routes/transactions.py`, we currently update stock using Python arithmetic (`item.current_stock += quantity`), which causes lost updates in concurrent scenarios.
- Refactor stock updates to use SQLAlchemy's atomic increment: `Item.query.filter_by(id=item_id).update({'current_stock': Item.current_stock + signed_qty})`.
- Ensure `rebuild_stock` uses database locking (e.g., `with_for_update`) if supported by the DB, or ensuring isolation.

**Task 2: Fix Excel Import Rollback (Nested Transactions)**
In `services/data_importer.py`, the `import_excel` method handles "Replace Mode" by soft-deleting old transactions. If the new import fails mid-way, we are left with deleted old data and no new data.
- Wrap the entire import process in a nested transaction using `db.session.begin_nested()`.
- Ensure that if ANY exception occurs during the import loop, `db.session.rollback()` is called to revert the soft-deletes of the old batch.

**Task 3: Fix Unit Conversion Default Logic**
In `models/transaction.py`, the `calculate_signed_quantity` method currently defaults `conversion_factor_to_base` to `1.0` if it's None. This is dangerous for items like "Gram" vs "Kg".
- Change the logic: If `conversion_factor_to_base` is None, it MUST attempt to fetch it from `Item.get_conversion_factor(self.unit)`.
- If it still cannot find a factor, raise a `ValueError` instead of silently defaulting to 1.0 (unless the unit is exactly the same as base unit).

Implement these changes with high precision.
2️⃣ فاز دوم: اصلاحات امنیتی حیاتی (Critical Security Fixes)
هدف: جلوگیری از حملات Brute-force روی 2FA و تنظیمات امنیتی سشن.

text
Act as a Security Engineer. I need to harden the authentication and session security of the application.

**Task 1: Implement Rate Limiting for 2FA**
In `routes/security.py`, the `/2fa/verify` endpoint currently has NO rate limiting. A bot can brute-force the TOTP code.
- Apply the rate limiter decorator `@limiter.limit("5 per minute")` to the `verify_2fa` route.
- Ensure the rate limiter is properly initialized in `app.py` if not already fully configured.

**Task 2: Fix Session Security Configuration**
In `config.py`, `SESSION_COOKIE_SECURE` depends on `FLASK_ENV == 'production'`. This is risky if the ENV var is missing.
- Change `SESSION_COOKIE_SECURE` to be `True` by default (Secure by Default approach), or at least `True` if `FLASK_ENV != 'development'`.
- Ensure `RATELIMIT_STORAGE_URL` is configurable via env vars (e.g., Redis) and defaults to "memory://" only for dev.
- Update `SECRET_KEY` logic: It should raise a warning or error in production if a fixed key is not provided in ENV (using `secrets.token_hex` creates invalid sessions on restart).

**Task 3: Fix Lockout Duration Mismatch**
- In `config.py`, `LOGIN_LOCKOUT_DURATION` is 300 seconds (5 mins).
- In `models/user.py`, the `record_failed_login` method hardcodes `timedelta(minutes=15)`.
- Refactor `models/user.py` to import and use the value from `current_app.config['LOGIN_LOCKOUT_DURATION']` instead of the hardcoded 15 minutes.
3️⃣ فاز سوم: اصلاحات لاجیک و باگ‌های جزئی (Logic Bugs & Context)
هدف: حل مشکل کانتکست ایمپورت ادمین و منطق موجودی اولیه.

text
Act as a Senior Python Developer. I need to fix logic bugs regarding context and initialization.

**Task 1: Fix Admin Import Context**
In `routes/admin.py`, inside the `data_import` function, `DataImporter` is instantiated without user context: `importer = DataImporter()`.
- Update this to pass the context: `importer = DataImporter(user_id=current_user.id, hotel_id=None)`.
- Ensure `DataImporter` correctly handles `hotel_id=None` by relying on sheet-name mapping logic strictly.

**Task 2: Fix Initial Stock Transaction Logic**
In `services/data_importer.py`, the method `create_initial_stock_transactions` iterates over ALL items with stock > 0.
- This is risky during concurrent imports or re-imports.
- Refactor this method to ONLY process items that were created or updated in the *current* `import_batch`.
- You can track affected item IDs during the import loop and pass them to `create_initial_stock_transactions`.

**Task 3: Fix Weighted Average Cost Division by Zero**
In `services/pareto_service.py` (or wherever WAC is calculated), check for potential `ZeroDivisionError`.
- Ensure that any division by `total_quantity` checks `if total_quantity > 0` before dividing.
4️⃣ فاز چهارم: تست و پایداری (Testing & Stability)
هدف: اطمینان از اینکه تغییرات بالا سیستم را خراب نکرده‌اند.

text
Act as a QA Automation Engineer. Now that we have applied critical fixes, I need you to generate a Python script `tests/test_critical_fixes.py` to verify them.

The script should verify:
1. **Concurrency:** Simulate 2 threads trying to buy the same item. Verify stock is decremented correctly (Atomic check).
2. **Import Rollback:** Simulate an import that fails on the 2nd row. Verify the database state remains unchanged (no partial data).
3. **2FA Rate Limit:** Simulate hitting the 2FA endpoint 10 times in 10 seconds and assert that it returns 429 (Too Many Requests).
4. **Unit Conversion:** Try to create a transaction with `conversion_factor=None` for a unit that differs from base unit, and verify it raises ValueError or calculates correctly (depending on fix).

Please write this test suite using `pytest` and `threading`.