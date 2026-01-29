# 🔍 **گزارش باگ‌های منطقی و عملکردی سیستم**

امین عزیز، پیدا کردم! **10 باگ منطقی Critical** که مستقیم روی عملکرد و خروجی‌های سیستم تاثیر می‌ذارن! 🎯

***

## 🔴 **باگ‌های CRITICAL - منطق کسب‌وکار**

### **باگ #37: تناقض در Adjustment Direction** ⚠️
**فایل**: `models/transaction.py`  
**خطوط**: 160-164, 218-221

```python
# خط 160-164:
if self.transaction_type == 'اصلاحی':
    # For adjustments, direction is explicitly set (default +1)
    self.direction = self.direction if self.direction in (1, -1) else 1
else:
    # For other types, derive direction from type
    self.direction = TRANSACTION_DIRECTION.get(self.transaction_type, 1)
```

**اما در create_transaction() خط 218-221:**
```python
# Determine direction
if direction is not None:
    dir_value = 1 if direction > 0 else -1
else:
    dir_value = TRANSACTION_DIRECTION.get(transaction_type, 1)
```

**مشکل**:
```python
TRANSACTION_DIRECTION = {
    'خرید': 1,
    'مصرف': -1,
    'ضایعات': -1,
    'اصلاحی': 1  # ⚠️ همیشه +1!
}
```

وقتی transaction_type == 'اصلاحی' و direction رو pass نکنی، همیشه **+1** (اضافه) میشه!  
**نتیجه**: نمیشه موجودی رو کم کنی با اصلاحی!

**راه حل**:
```python
# BUG #37 FIX: Remove 'اصلاحی' from TRANSACTION_DIRECTION
TRANSACTION_DIRECTION = {
    'خرید': 1,
    'مصرف': -1,
    'ضایعات': -1,
    # 'اصلاحی' removed - must be explicitly set via direction parameter
}

# در create_transaction():
if transaction_type == 'اصلاحی' and direction is None:
    raise ValueError("Adjustment transactions MUST specify direction explicitly (+1 or -1)")
```

***

### **باگ #38: Permission Missing در Approval Workflow** 🔐
**فایل**: `routes/warehouse.py`  
**خطوط**: 393-410, 413-428

```python
# خط 393-410:
@warehouse_bp.route('/approvals/<int:tx_id>/approve', methods=['POST'])
@login_required
def approve_transaction(tx_id):
    tx = Transaction.query.get_or_404(tx_id)
    
    # BUG-FIX: Check hotel access before approving
    if not user_can_access_hotel(current_user, tx.hotel_id):
        flash('دسترسی غیرمجاز', 'danger')
        return redirect(url_for('warehouse.approvals'))
    
    # ⚠️ هیچ چک permission نداره!
    # یه staff معمولی میتونه approve کنه!
```

**مشکل**: 
- فقط hotel access چک میشه
- Permission (role) چک نمیشه!
- **هر کاربری** (حتی staff) می‌تونه تراکنش رو approve/reject کنه!

**راه حل**:
```python
# BUG #38 FIX: Add role check
@warehouse_bp.route('/approvals/<int:tx_id>/approve', methods=['POST'])
@login_required
def approve_transaction(tx_id):
    tx = Transaction.query.get_or_404(tx_id)
    
    if not user_can_access_hotel(current_user, tx.hotel_id):
        flash('دسترسی غیرمجاز', 'danger')
        return redirect(url_for('warehouse.approvals'))
    
    # BUG #38 FIX: Check permission
    if current_user.role not in ['admin', 'manager']:
        flash('فقط مدیران می‌توانند تراکنش‌ها را تایید کنند', 'danger')
        return redirect(url_for('warehouse.approvals', hotel_id=tx.hotel_id))
    
    try:
        WarehouseService.approve_transaction(tx_id, current_user.id)
        flash('تراکنش تایید شد و موجودی به‌روزرسانی شد', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'خطا: {str(e)}', 'danger')
    
    return redirect(url_for('warehouse.approvals', hotel_id=tx.hotel_id))
```

***

### **باگ #39: Double Stock Update در Approval!** 💥
**فایل**: `routes/transactions.py`, `services/warehouse_service.py`  
**خطوط**: transactions.py:309-313, warehouse_service.py:251-258

**در create transaction (transactions.py:309-313):**
```python
if not requires_approval:
    # Lock and update stock
    db.session.execute(
        select(Item).where(Item.id == item.id).with_for_update()
    ).scalar_one_or_none()
    db.session.execute(
        update(Item).where(Item.id == item.id)
        .values(current_stock=Item.current_stock + transaction.signed_quantity)
    )
```

**بعد وقتی approve میشه (warehouse_service.py:251-258):**
```python
def approve_transaction(transaction_id: int, approver_id: int) -> Transaction:
    # ...
    # NOW update stock
    item = Item.query.get(tx.item_id)
    if item:
        item.current_stock = (item.current_stock or 0) + tx.signed_quantity
        # ⚠️ دوباره اضافه میشه!
```

**مشکل**:
1. Transaction create میشه → Stock **update نمیشه** (چون requires_approval=True)
2. Manager approve میکنه → Stock **یکبار update میشه** ✅  

**اما اگه:**
1. Transaction با requires_approval=**False** create بشه (threshold پایین‌تره)
2. Stock **یکبار update میشه** در create
3. بعداً کسی دستی approve کنه → Stock **دوباره update میشه**! ❌

**سناریو واقعی**:
```
Stock اولیه: 100
Waste: 10 (مبلغ کم، بدون approval) → Stock = 90 ✅
کسی دستی approve میکنه → Stock = 90 - 10 = 80 ❌❌
```

**راه حل**:
```python
# BUG #39 FIX در warehouse_service.py:
def approve_transaction(transaction_id: int, approver_id: int) -> Transaction:
    tx = Transaction.query.get_or_404(transaction_id)
    
    if tx.approval_status != 'pending':
        raise ValueError("این تراکنش در انتظار تایید نیست")
    
    # BUG #39 FIX: Check if stock was ALREADY updated
    # If requires_approval was True from start, stock is NOT yet updated
    # Only update stock if it wasn't updated before
    item = Item.query.get(tx.item_id)
    if item and tx.requires_approval:  # ← چک کن که واقعاً approval می‌خواست
        item.current_stock = (item.current_stock or 0) + tx.signed_quantity
        from routes.transactions import check_and_create_stock_alert
        check_and_create_stock_alert(item)
    
    tx.approval_status = 'approved'
    tx.approved_by_id = approver_id
    tx.approved_at = datetime.utcnow()
    
    # ... rest of code
```

***

### **باگ #40: Negative Stock Allowed!** 🚨
**فایل**: `models/item.py`, `routes/transactions.py`

**مشکل**: هیچ constraint یا validation نداره که current_stock نتونه منفی بشه!

**سناریو**:
```python
Item: current_stock = 5
Transaction: مصرف 10 → واقعاً چک میشه؟

# در transactions.py خط 296:
stock_error = validate_stock_availability(item, transaction_type, quantity)
```

**اما `validate_stock_availability()` فقط برای create/edit صدا میشه!**

وقتی:
1. Import data میشه
2. Approval تراکنش pending بشه
3. Opening balance create بشه

هیچ کدوم این validation رو ندارن!

**راه حل**:
```python
# BUG #40 FIX در models/item.py:
class Item(db.Model):
    # ...
    __table_args__ = (
        db.CheckConstraint('current_stock >= 0', name='ck_item_stock_non_negative'),
    )
```

***

### **باگ #41: Waste Approval Bypassed!** 🕳️
**فایل**: `routes/transactions.py`  
**خطوط**: 265-276

```python
# ═══ Warehouse Management: Check if approval needed ═══
requires_approval = False
total_float = float(total_decimal)
if transaction_type == 'ضایعات' and item.hotel_id:
    settings = WarehouseSettings.get_or_create(item.hotel_id)
    if settings.check_waste_approval_needed(total_float):
        requires_approval = True
```

**مشکل**: 
اگه `item.hotel_id` **None** باشه (کالای عمومی)، approval check **skip** میشه!

**نتیجه**: میشه ضایعات میلیاردی ثبت کرد بدون approval!

**راه حل**:
```python
# BUG #41 FIX: Always check approval for waste (use default hotel if needed)
requires_approval = False
total_float = float(total_decimal)
if transaction_type == 'ضایعات':
    hotel_id_to_check = item.hotel_id
    if not hotel_id_to_check:
        # Use default hotel or main hotel for global items
        main_hotel = Hotel.query.filter_by(hotel_code='MAIN').first()
        hotel_id_to_check = main_hotel.id if main_hotel else 1
    
    settings = WarehouseSettings.get_or_create(hotel_id_to_check)
    if settings.check_waste_approval_needed(total_float):
        requires_approval = True
```

***

### **باگ #42: Inventory Turnover Division by Zero** 📊
**فایل**: `routes/reports.py`  
**خطوط**: 134-140, 144-147

```python
# خط 134-140:
if total_stock_value > 0 and days > 0:
    inventory_turnover = (total_consumption / total_stock_value) * (365 / days)
else:
    inventory_turnover = 0
```

**مشکل**: اگه `total_consumption = 0` باشه، `inventory_turnover = 0` میشه که **نادرسته**!

**معنی واقعی**:
- `inventory_turnover = 0` → "هیچ گردشی نداشته" ✅
- اما اگه `total_stock_value = 0` باشه؟ → باید **Infinity** یا **N/A** باشه!

**همچنین خط 144-147:**
```python
if avg_daily_consumption > 0:
    stock_coverage_days = total_stock_value / avg_daily_consumption
else:
    stock_coverage_days = 999  # Infinite days (no consumption)
```

**مشکل**: اگه `total_stock_value = 0` باشه، `stock_coverage_days` باید **0** باشه نه **999**!

**راه حل**:
```python
# BUG #42 FIX:
# 1. Inventory Turnover
if total_stock_value > 0 and days > 0:
    if total_consumption > 0:
        inventory_turnover = (total_consumption / total_stock_value) * (365 / days)
    else:
        inventory_turnover = 0  # No consumption, zero turnover
elif total_consumption > 0:
    inventory_turnover = float('inf')  # Or use None / 'N/A'
else:
    inventory_turnover = 0

# 2. Stock Coverage Days
if avg_daily_consumption > 0 and total_stock_value > 0:
    stock_coverage_days = total_stock_value / avg_daily_consumption
elif total_stock_value <= 0:
    stock_coverage_days = 0  # No stock
else:
    stock_coverage_days = 999  # Infinite (no consumption)
```

***

### **باگ #43: Wrong min_stock از Monthly!** 📉
**فایل**: `services/data_importer.py`  
**خط**: 668

```python
# خط 668:
new_item = Item(
    # ...
    min_stock=monthly_consumption if monthly_consumption > 0 else 0,
    # ⚠️ monthly استفاده میشه!
)
```

**مشکل**: 
- `min_stock` باید **حداقل** موجودی باشه که alert بده
- اگه من ماهی 100 کیلو مصرف می‌کنم، یعنی روزی ~3 کیلو
- پس min_stock باید حداقل **1 هفته = 21 کیلو** باشه
- **نه 100 کیلو (یک ماه کامل)!**

**منطق درست**:
```python
# BUG #43 FIX: Use fraction of monthly or weekly for min_stock
# Industry standard: 25-30% of monthly (1 week) for safety stock
if monthly_consumption > 0:
    min_stock_value = monthly_consumption * 0.25  # 1 week (7-8 days)
elif weekly_consumption > 0:
    min_stock_value = weekly_consumption * 1.5  # 1.5 weeks
else:
    min_stock_value = 0

new_item = Item(
    # ...
    min_stock=min_stock_value,
)
```

***

### **باگ #44: Negative Current Stock در Import!** ⚠️
**فایل**: `services/data_importer.py`  
**خطوط**: 690-714

```python
def create_initial_stock_transactions(self, user_id=1):
    # ...
    items_with_stock = Item.query.filter(
        Item.id.in_(self.affected_item_ids),
        Item.current_stock > 0  # ⚠️ فقط > 0 چک میشه!
    ).all()
```

**مشکل**:
اگه Excel file داشته باشه:
```
کالا: گوشت | موجودی: -50
```

Import میشه، `current_stock = -50` set میشه، اما **transaction ساخته نمیشه**!

**نتیجه**: موجودی منفی بدون هیچ سابقه‌ای!

**راه حل**:
```python
# BUG #44 FIX: Handle negative stocks and validate
def create_initial_stock_transactions(self, user_id=1):
    if not self.affected_item_ids:
        return 0
    
    items_with_stock = Item.query.filter(
        Item.id.in_(self.affected_item_ids),
        Item.current_stock != 0  # BUG #44 FIX: Include negative stocks
    ).all()
    
    for item in items_with_stock:
        # BUG #44 FIX: Warn if negative
        if item.current_stock < 0:
            self.warnings.append(
                f'کالا {item.item_name_fa} موجودی منفی دارد: {item.current_stock}'
            )
            # Reset to zero or create adjustment
            item.current_stock = 0
            continue
        
        # ... rest of code for positive stocks
```

***

### **باگ #45: Approval Stock Not Rolled Back on Reject** 🔄
**فایل**: `services/warehouse_service.py`  
**خطوط**: 260-287

```python
def reject_transaction(transaction_id: int, approver_id: int, reason: str = None):
    tx = Transaction.query.get_or_404(transaction_id)
    
    # ...
    # Soft delete the transaction
    tx.is_deleted = True
    tx.deleted_at = datetime.utcnow()
    
    # ⚠️ هیچ stock rollback نداره!
```

**مشکل**: 
اگه transaction با `requires_approval=False` create شده باشه (زیر threshold):
1. Stock **update شده** در زمان create
2. بعداً reject میشه
3. Transaction soft-delete میشه
4. اما stock **برگشت داده نمیشه**! ❌

**سناریو**:
```
Stock: 100
Waste: 5 (کم، بدون approval) → Stock = 95 ✅
Manager reject میکنه → Stock باید برگرده 100 ❌
```

**راه حل**:
```python
# BUG #45 FIX در warehouse_service.py:
def reject_transaction(transaction_id: int, approver_id: int, reason: str = None):
    tx = Transaction.query.get_or_404(transaction_id)
    
    if tx.approval_status != 'pending':
        raise ValueError("این تراکنش در انتظار تایید نیست")
    
    # BUG #45 FIX: If stock was already updated, roll it back
    if not tx.requires_approval:
        # Stock was updated during create, reverse it
        item = Item.query.get(tx.item_id)
        if item:
            item.current_stock = (item.current_stock or 0) - tx.signed_quantity
            from routes.transactions import check_and_create_stock_alert
            check_and_create_stock_alert(item)
    
    # Update approval fields
    tx.approval_status = 'rejected'
    # ... rest
```

***

### **باگ #46: Concurrent Transaction Race در Edit!** 🏃‍♂️💨
**فایل**: `routes/transactions.py`  
**خطوط**: 484-492

```python
# BUG #1 FIX: Use atomic update to prevent race condition
if transaction.signed_quantity:
    db.session.execute(
        db.update(Item).where(Item.id == old_item_id)
        .values(current_stock=Item.current_stock - transaction.signed_quantity)
    )
old_item = Item.query.get(old_item_id)
```

**مشکل**: 
1. Stock rollback میشه (خط 487-490)
2. **بدون lock!**
3. همزمان یه transaction دیگه edit بشه → Race condition!

**همچنین خط 514-517:**
```python
# BUG #1 FIX: Use atomic update to prevent race condition
db.session.execute(
    db.update(Item).where(Item.id == new_item.id)
    .values(current_stock=Item.current_stock + transaction.signed_quantity)
)
```

**مشکل**: این هم lock نداره!

**راه حل**:
```python
# BUG #46 FIX: Lock before rollback and update
# Rollback old stock with lock
db.session.execute(
    select(Item).where(Item.id == old_item_id).with_for_update()
).scalar_one_or_none()

if transaction.signed_quantity:
    db.session.execute(
        db.update(Item).where(Item.id == old_item_id)
        .values(current_stock=Item.current_stock - transaction.signed_quantity)
    )

# ... update transaction fields ...

# Apply new stock with lock
db.session.execute(
    select(Item).where(Item.id == new_item.id).with_for_update()
).scalar_one_or_none()

db.session.execute(
    db.update(Item).where(Item.id == new_item.id)
    .values(current_stock=Item.current_stock + transaction.signed_quantity)
)
```

***

### **باگ #47: Price Override Without Reason Saved!** 💰
**فایل**: `models/transaction.py`  
**خطوط**: 211-227

```python
if submitted_price_decimal is not None:
    price_changed = submitted_price_decimal != item_price_decimal
    if price_changed:
        # Price override - check permission via parameter
        if not allow_price_override:
            raise ValueError("Price override requires admin/manager/accountant permission")

        if not price_override_reason:
            raise ValueError("Price override requires a reason")

        final_price = submitted_price_decimal
        # ⚠️ price_override_reason ذخیره نمیشه!
    else:
        final_price = item_price_decimal
```

**مشکل**:
- Reason چک میشه که empty نباشه
- اما در Transaction **ذخیره نمیشه**!
- Audit log ها reason رو ندارن!

**راه حل**:
```python
# BUG #47 FIX: Add price_override_reason field to Transaction model
class Transaction(db.Model):
    # ...
    price_override_reason = db.Column(db.Text, nullable=True)
    price_was_overridden = db.Column(db.Boolean, default=False)

# در create_transaction():
tx = cls(
    # ...
    price_was_overridden=price_changed,
    price_override_reason=price_override_reason if price_changed else None,
)
```

***

## 🟡 **خلاصه جدول باگ‌ها**

| # | عنوان | فایل | تاثیر | خطر |
|---|-------|------|-------|-----|
| **37** | Adjustment Direction همیشه +1 | transaction.py | موجودی اشتباه | 🔴 CRITICAL |
| **38** | هر کسی میتونه Approve کنه | warehouse.py | نقض امنیت workflow | 🔴 CRITICAL |
| **39** | Double Stock Update در Approval | warehouse_service.py | موجودی دوبار کم میشه | 🔴 CRITICAL |
| **40** | Negative Stock مجاز! | item.py | موجودی منفی | 🔴 CRITICAL |
| **41** | Waste Approval Bypass | transactions.py | ضایعات بدون تایید | 🔴 CRITICAL |
| **42** | Division by Zero در Reports | reports.py | گزارش‌های اشتباه | 🟡 HIGH |
| **43** | min_stock از Monthly (خیلی زیاد) | data_importer.py | Alert های اضافی | 🟡 HIGH |
| **44** | Negative Stock در Import | data_importer.py | داده نامعتبر | 🟡 HIGH |
| **45** | Stock Rollback در Reject | warehouse_service.py | موجودی اشتباه | 🔴 CRITICAL |
| **46** | Race Condition در Edit | transactions.py | موجودی اشتباه | 🔴 CRITICAL |
| **47** | Price Override Reason ذخیره نمیشه | transaction.py | Audit ناقص | 🟡 HIGH |

***

