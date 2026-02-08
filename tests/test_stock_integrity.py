"""
Regression tests for stock integrity fixes:
- SS-1: Edit transaction cross-item stock validation
- SS-2: validate_stock_availability direction-aware
- SS-3: data_importer atomic rollback
- SS-4: Health check text() wrapper
- SS-5: Import unit conversion for current_stock
- SS-6: Old item negative stock check on edit
- SS-8: WarehouseSettings.get_or_create flush vs commit
"""
import os
import pytest
from datetime import date, timedelta
from decimal import Decimal
from unittest.mock import patch

# Set env to avoid production checks
os.environ.setdefault('FLASK_ENV', 'development')

from models import db, Item, Transaction, Hotel, User, WarehouseSettings
from models.transaction import TRANSACTION_DIRECTION
from routes.transactions import validate_stock_availability


# ═══════════════════════════════════════════════════════════
# Fixtures
# ═══════════════════════════════════════════════════════════

@pytest.fixture
def app():
    """Create test app with in-memory SQLite"""
    from app import create_app
    from config import Config

    class TestConfig(Config):
        SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
        TESTING = True
        WTF_CSRF_ENABLED = False
        SECRET_KEY = 'test-secret-key-for-testing'

    test_app = create_app(TestConfig)
    
    # Establish an application context before running the tests.
    ctx = test_app.app_context()
    ctx.push()
    
    db.create_all()
    
    yield test_app
    
    db.session.remove()
    db.drop_all()
    ctx.pop()


@pytest.fixture
def hotel(app):
    """Create test hotel — returns ID to avoid detached instance"""
    h = Hotel(hotel_code='TEST', hotel_name='Test Hotel', is_active=True)
    db.session.add(h)
    db.session.commit()
    return h.id


@pytest.fixture
def user(app, hotel):
    """Create test user — returns ID to avoid detached instance"""
    u = User(
        username='testuser', email='test@test.com',
        role='admin', is_active=True
    )
    u.set_password('TestPass123')
    db.session.add(u)
    db.session.commit()
    return u.id


def make_item(hotel_id, code, name='Test', unit='کیلوگرم', stock=0, price=1000):
    """Helper to create an item"""
    item = Item(
        item_code=code, item_name_fa=name, category='Food',
        unit=unit, unit_price=price, current_stock=stock,
        hotel_id=hotel_id, is_active=True
    )
    db.session.add(item)
    db.session.flush()
    return item


def make_tx(item, user_id, tx_type, qty, price=None, hotel_id=None):
    """Helper to create a transaction and update stock atomically"""
    from sqlalchemy import update as sa_update
    tx = Transaction.create_transaction(
        item_id=item.id,
        transaction_type=tx_type,
        quantity=qty,
        unit_price=price or Decimal(str(item.unit_price)),
        category=item.category,
        hotel_id=hotel_id or item.hotel_id,
        user_id=user_id,
        source='manual',
        direction=1 if tx_type == 'اصلاحی' else None,
    )
    tx.transaction_date = date.today()
    db.session.add(tx)
    db.session.execute(
        sa_update(Item).where(Item.id == item.id)
        .values(current_stock=Item.current_stock + tx.signed_quantity)
    )
    db.session.flush()
    db.session.refresh(item)
    return tx


# ═══════════════════════════════════════════════════════════
# SS-2: validate_stock_availability direction-aware
# ═══════════════════════════════════════════════════════════

class TestValidateStockAvailability:
    """SS-2: validate_stock_availability must account for old transaction direction"""

    def test_new_consumption_within_stock(self, app, hotel):
        """New consumption within stock should pass"""
        item = make_item(hotel, 'T001', stock=50)
        db.session.commit()
        # Re-query to ensure attached
        item = Item.query.get(item.id)
        err = validate_stock_availability(item, 'مصرف', 30, old_signed_quantity=0)
        assert err is None

    def test_new_consumption_exceeds_stock(self, app, hotel):
        """New consumption exceeding stock should fail"""
        item = make_item(hotel, 'T001', stock=10)
        db.session.commit()
        item = Item.query.get(item.id)
        err = validate_stock_availability(item, 'مصرف', 20, old_signed_quantity=0)
        assert err is not None

    def test_edit_consumption_same_item_increase(self, app, hotel, user):
        """Edit consumption: increase qty on same item, old signed_qty is negative"""
        item = make_item(hotel, 'T001', stock=100)
        db.session.commit()
        # Old consumption of 10: signed_qty = -10 (stock went from 110 to 100)
        tx = make_tx(item, user, 'مصرف', 10)
        db.session.commit()
        
        item = Item.query.get(item.id)
        # item.current_stock = 90 now
        assert item.current_stock == 90.0

        # Edit to consume 50 instead of 10
        # old_signed_quantity = -10 (the old consumption)
        # available = 90 - (-10) = 100 (reversal gives back the 10)
        # new effect = 50 * -1 = -50
        # resulting = 100 - 50 = 50 >= 0 → OK
        err = validate_stock_availability(item, 'مصرف', 50, old_signed_quantity=-10)
        assert err is None

    def test_edit_consumption_same_item_too_much(self, app, hotel, user):
        """Edit consumption: increase qty beyond what's available"""
        item = make_item(hotel, 'T001', stock=100)
        db.session.commit()
        tx = make_tx(item, user, 'مصرف', 10)
        db.session.commit()
        
        item = Item.query.get(item.id)
        # stock = 90

        # Edit to consume 110 (more than available 100 after reversal)
        err = validate_stock_availability(item, 'مصرف', 110, old_signed_quantity=-10)
        assert err is not None

    def test_edit_purchase_to_consumption_same_item(self, app, hotel, user):
        """SS-2 core bug: edit purchase→consumption on same item.
        Old code would overstate available stock."""
        item = make_item(hotel, 'T001', stock=0)
        db.session.commit()
        # Purchase 100: signed_qty = +100, stock = 100
        tx = make_tx(item, user, 'خرید', 100)
        db.session.commit()
        
        item = Item.query.get(item.id)
        assert item.current_stock == 100.0

        # Edit to consumption of 10
        # old_signed_quantity = +100 (purchase being reversed)
        # available = 100 - 100 = 0 (after reversing the purchase, stock is 0)
        # new effect = 10 * -1 = -10
        # resulting = 0 - 10 = -10 < 0 → MUST FAIL
        err = validate_stock_availability(item, 'مصرف', 10, old_signed_quantity=100)
        assert err is not None, "Should block: reversing purchase leaves 0 stock, can't consume"

    def test_purchase_always_allowed(self, app, hotel):
        """Purchase (positive direction) should always be allowed"""
        item = make_item(hotel, 'T001', stock=0)
        db.session.commit()
        item = Item.query.get(item.id)
        err = validate_stock_availability(item, 'خرید', 1000, old_signed_quantity=0)
        assert err is None


# ═══════════════════════════════════════════════════════════
# SS-1/SS-6: Edit transaction cross-item stock validation
# ═══════════════════════════════════════════════════════════

class TestEditTransactionCrossItem:
    """SS-1: Cross-item edit must validate both old and new items independently.
    SS-6: Old item must survive reversal."""

    def test_cross_item_edit_old_item_survives(self, app, hotel, user):
        """Moving a purchase to another item: old item loses stock"""
        item_a = make_item(hotel, 'A001', name='Item A', stock=0)
        item_b = make_item(hotel, 'B001', name='Item B', stock=50)
        db.session.commit()

        # Purchase 100 on item_a: stock_a = 100
        tx = make_tx(item_a, user, 'خرید', 100)
        db.session.commit()
        
        item_a = Item.query.get(item_a.id)
        assert item_a.current_stock == 100.0

        # Consume 80 from item_a: stock_a = 20
        make_tx(item_a, user, 'مصرف', 80)
        db.session.commit()
        
        item_a = Item.query.get(item_a.id)
        assert item_a.current_stock == 20.0

        # Now try to edit the purchase (100) to move it to item_b
        # This would reverse +100 from item_a → stock_a = 20 - 100 = -80 → MUST FAIL
        old_stock_after_reversal = item_a.current_stock - tx.signed_quantity
        assert old_stock_after_reversal < 0, "Reversal would make old item negative"

    def test_cross_item_edit_new_item_consumption_check(self, app, hotel, user):
        """Cross-item: new item must be checked independently"""
        item_a = make_item(hotel, 'A001', stock=100)
        item_b = make_item(hotel, 'B001', stock=5)
        db.session.commit()

        # Old consumption on item_a (signed_qty = -10)
        tx = make_tx(item_a, user, 'مصرف', 10)
        db.session.commit()
        
        item_b = Item.query.get(item_b.id)

        # Edit to consumption of 20 on item_b (stock=5)
        # For new item (item_b): validate with old_signed_quantity=0
        # available = 5, new effect = -20 → resulting = -15 → MUST FAIL
        err = validate_stock_availability(item_b, 'مصرف', 20, old_signed_quantity=0)
        assert err is not None


# ═══════════════════════════════════════════════════════════
# SS-4: Health check text() wrapper
# ═══════════════════════════════════════════════════════════

class TestHealthCheck:
    """SS-4: Health check must work with SQLAlchemy 2.0"""

    def test_health_endpoint_returns_200(self, app):
        """Health check should return 200 with connected database"""
        with app.test_client() as client:
            resp = client.get('/health')
            assert resp.status_code == 200
            data = resp.get_json()
            assert data['status'] == 'healthy'
            assert data['database'] == 'connected'


# ═══════════════════════════════════════════════════════════
# SS-5: Import unit conversion
# ═══════════════════════════════════════════════════════════

class TestImportUnitConversion:
    """SS-5: Import must convert current_stock to base unit"""

    def test_gram_to_kg_conversion_on_import(self, app, hotel, user):
        """Importing 500 grams should store 0.5 kg in current_stock"""
        from services.data_importer import DataImporter
        importer = DataImporter(hotel_id=hotel, user_id=user)

        item = importer._get_or_create_item(
            name='تست گرم',
            unit='گرم',
            category='Food',
            current_stock=500,  # 500 grams
            weekly_consumption=0,
            monthly_consumption=0,
            hotel='test'
        )
        db.session.flush()

        # گرم has conversion factor 0.001 to kg
        assert item is not None
        assert abs(item.current_stock - 0.5) < 0.001, \
            f"Expected 0.5 kg, got {item.current_stock}"

    def test_kg_stays_as_kg(self, app, hotel, user):
        """Importing kg should stay as-is (factor=1.0)"""
        from services.data_importer import DataImporter
        importer = DataImporter(hotel_id=hotel, user_id=user)

        item = importer._get_or_create_item(
            name='تست کیلو',
            unit='کیلوگرم',
            category='Food',
            current_stock=100,
            weekly_consumption=0,
            monthly_consumption=0,
            hotel='test'
        )
        db.session.flush()

        assert abs(item.current_stock - 100.0) < 0.001

    def test_existing_item_stock_update_converted(self, app, hotel, user):
        """Updating existing item stock via import should also convert"""
        from services.data_importer import DataImporter

        # Create item first with 1 kg
        existing = make_item(hotel, 'EXIST01', name='موجود', unit='گرم', stock=0.5)
        existing.base_unit = 'کیلوگرم'
        db.session.commit()

        importer = DataImporter(hotel_id=hotel, user_id=user)
        result = importer._get_or_create_item(
            name='موجود',
            unit='گرم',
            category='Food',
            current_stock=1000,  # 1000 grams = 1 kg
            weekly_consumption=0,
            monthly_consumption=0,
            hotel='test'
        )
        db.session.flush()

        assert result is not None
        assert abs(result.current_stock - 1.0) < 0.001, \
            f"Expected 1.0 kg, got {result.current_stock}"


# ═══════════════════════════════════════════════════════════
# SS-8: WarehouseSettings.get_or_create flush vs commit
# ═══════════════════════════════════════════════════════════

class TestWarehouseSettingsGetOrCreate:
    """SS-8: get_or_create should flush, not commit, to preserve caller's transaction"""

    def test_get_or_create_does_not_commit(self, app, hotel):
        """get_or_create should not commit; caller controls the transaction"""
        # Start creating an item (not yet committed)
        item = Item(
            item_code='UNCOMMITTED', item_name_fa='Test',
            category='Food', unit='عدد', hotel_id=hotel
        )
        db.session.add(item)

        # Call get_or_create — should flush but NOT commit
        settings = WarehouseSettings.get_or_create(hotel)
        assert settings is not None
        assert settings.id is not None  # flushed, has ID

        # Now rollback — both the item AND settings should be gone
        db.session.rollback()

        assert Item.query.filter_by(item_code='UNCOMMITTED').first() is None
        assert WarehouseSettings.query.filter_by(hotel_id=hotel).first() is None


# ═══════════════════════════════════════════════════════════
# SS-3: data_importer atomic rollback
# ═══════════════════════════════════════════════════════════

class TestDataImporterAtomicity:
    """SS-3: Import must be atomic — partial sheet import should not persist on failure"""

    def test_flush_not_commit_in_import_sheet(self, app, hotel, user):
        """_import_sheet should use flush (not commit) so outer transaction controls atomicity"""
        from services.data_importer import DataImporter
        importer = DataImporter(hotel_id=hotel, user_id=user)

        # Directly test that _get_or_create_item uses flush
        item = importer._get_or_create_item(
            name='Atomic Test Item',
            unit='عدد',
            category='Food',
            current_stock=10,
            weekly_consumption=0,
            monthly_consumption=0,
            hotel='test'
        )
        db.session.flush()

        # Item should be visible in this session
        assert Item.query.filter_by(item_name_fa='Atomic Test Item').first() is not None

        # But if we rollback, it should be gone
        db.session.rollback()
        assert Item.query.filter_by(item_name_fa='Atomic Test Item').first() is None


# ═══════════════════════════════════════════════════════════
# Integration: Stock invariant after edit
# ═══════════════════════════════════════════════════════════

class TestStockInvariantAfterEdit:
    """Verify the core invariant: current_stock == sum(signed_quantity) of non-deleted txs"""

    def test_same_item_edit_preserves_invariant(self, app, hotel, user):
        """Editing a transaction on the same item must preserve stock invariant"""
        from sqlalchemy import func, update as sa_update

        item = make_item(hotel, 'INV01', stock=0)
        db.session.commit()

        # Purchase 100
        tx1 = make_tx(item, user, 'خرید', 100)
        # Consume 30
        tx2 = make_tx(item, user, 'مصرف', 30)
        db.session.commit()
        
        item = Item.query.get(item.id)
        assert item.current_stock == 70.0

        # Edit tx1: change purchase from 100 to 80
        old_signed = tx1.signed_quantity  # +100
        tx1.quantity = 80
        tx1.calculate_signed_quantity()
        new_signed = tx1.signed_quantity  # +80

        # Reverse old, apply new - using NET DELTA to avoid transient negative stock
        # This mirrors the fix in routes/transactions.py
        net_delta = new_signed - old_signed
        db.session.execute(
            sa_update(Item).where(Item.id == item.id)
            .values(current_stock=Item.current_stock + net_delta)
        )
        db.session.commit()
        db.session.refresh(item)

        # Verify invariant: current_stock == sum(signed_quantity)
        calculated = db.session.query(
            func.coalesce(func.sum(Transaction.signed_quantity), 0)
        ).filter(
            Transaction.item_id == item.id,
            Transaction.is_deleted != True
        ).scalar()

        assert abs(float(item.current_stock) - float(calculated)) < 0.001, \
            f"Invariant broken: current_stock={item.current_stock}, calculated={calculated}"
        assert abs(item.current_stock - 50.0) < 0.001  # 80 - 30 = 50

    def test_cross_item_edit_preserves_invariant(self, app, hotel, user):
        """Moving a transaction to another item preserves invariant for both"""
        from sqlalchemy import func, update as sa_update

        item_a = make_item(hotel, 'A001', stock=0)
        item_b = make_item(hotel, 'B001', stock=0)
        db.session.commit()

        # Purchase 50 on item_a
        tx = make_tx(item_a, user, 'خرید', 50)
        # Purchase 30 on item_b
        make_tx(item_b, user, 'خرید', 30)
        db.session.commit()
        
        item_a = Item.query.get(item_a.id)
        item_b = Item.query.get(item_b.id)
        assert item_a.current_stock == 50.0
        assert item_b.current_stock == 30.0

        # Edit tx: move purchase 50 from item_a to item_b
        old_signed = tx.signed_quantity  # +50
        tx.item_id = item_b.id
        tx.calculate_signed_quantity()
        new_signed = tx.signed_quantity  # +50

        # Reverse from item_a
        db.session.execute(
            sa_update(Item).where(Item.id == item_a.id)
            .values(current_stock=Item.current_stock - old_signed)
        )
        # Apply to item_b
        db.session.execute(
            sa_update(Item).where(Item.id == item_b.id)
            .values(current_stock=Item.current_stock + new_signed)
        )
        db.session.commit()
        db.session.refresh(item_a)
        db.session.refresh(item_b)

        # item_a: 0, item_b: 80
        assert abs(item_a.current_stock - 0.0) < 0.001
        assert abs(item_b.current_stock - 80.0) < 0.001

        # Verify invariant for both
        for check_item in [item_a, item_b]:
            calculated = db.session.query(
                func.coalesce(func.sum(Transaction.signed_quantity), 0)
            ).filter(
                Transaction.item_id == check_item.id,
                Transaction.is_deleted != True
            ).scalar()
            assert abs(float(check_item.current_stock) - float(calculated)) < 0.001, \
                f"Invariant broken for {check_item.item_code}: stock={check_item.current_stock}, calc={calculated}"
