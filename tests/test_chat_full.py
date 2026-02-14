
"""
Comprehensive tests for ChatService integration and context awareness.
Verifies:
- Full database context generation (User, Items, Transactions, Waste, Settings, etc.)
- Hotel scoping for context (Admin vs Restricted User)
- Audit logging for chat actions
- Dead stock and waste trend analysis integration
"""
import os
# Set env to avoid production checks BEFORE importing app code
os.environ['FLASK_ENV'] = 'development'
os.environ['SECRET_KEY'] = 'test-key-for-chat-tests'

import pytest
from datetime import date, timedelta, datetime
from decimal import Decimal
from unittest.mock import MagicMock, patch
from models import db, User, Hotel, Item, Transaction, AuditLog, WarehouseSettings, ImportBatch, UserHotel
from services.chat_service import ChatService
import services.hotel_scope_service
from utils.timezone import get_iran_today

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
    
    # Patch SINGLE_HOTEL_MODE to False for all tests
    original_mode = services.hotel_scope_service.SINGLE_HOTEL_MODE
    services.hotel_scope_service.SINGLE_HOTEL_MODE = False
    
    yield test_app
    
    services.hotel_scope_service.SINGLE_HOTEL_MODE = original_mode
    db.session.remove()
    db.drop_all()
    ctx.pop()

@pytest.fixture
def chat_service():
    return ChatService()

@pytest.fixture
def setup_data(app):
    # Use existing context from app fixture
    # Create Hotels
    hotel1 = Hotel(hotel_code="HTL01", hotel_name="Hotel A", is_active=True)
    hotel2 = Hotel(hotel_code="HTL02", hotel_name="Hotel B", is_active=True)
    db.session.add_all([hotel1, hotel2])
    db.session.commit()

    # Create Users
    admin_user = User(username="admin_chat", email="admin@test.com", full_name="Admin User", role="admin", is_active=True)
    admin_user.set_password("password")
    
    restricted_user = User(username="manager_chat", email="manager@test.com", full_name="Manager User", role="manager", is_active=True)
    restricted_user.set_password("password")
    
    db.session.add_all([admin_user, restricted_user])
    db.session.commit()

    # Assign Restricted User to Hotel A only
    user_hotel = UserHotel(user_id=restricted_user.id, hotel_id=hotel1.id, role='manager')
    db.session.add(user_hotel)
    db.session.commit()

    # Create Items
    item1 = Item(item_code="ITM01", item_name_fa="Item A1", hotel_id=hotel1.id, category="Food", unit="kg", current_stock=100, min_stock=10, unit_price=1000, is_active=True)
    item2 = Item(item_code="ITM02", item_name_fa="Item B1", hotel_id=hotel2.id, category="Food", unit="kg", current_stock=200, min_stock=20, unit_price=2000, is_active=True)
    
    # Dead stock item (Hotel A)
    dead_item = Item(item_code="ITM03", item_name_fa="Dead Item A", hotel_id=hotel1.id, category="NonFood", unit="pcs", current_stock=50, unit_price=5000, is_active=True, created_at=datetime.now() - timedelta(days=100))
    
    db.session.add_all([item1, item2, dead_item])
    db.session.commit()

    # Create Warehouse Settings
    ws1 = WarehouseSettings(hotel_id=hotel1.id, waste_approval_threshold=100000)
    db.session.add(ws1)
    db.session.commit()

    # Create Import Batch
    ib = ImportBatch(filename="test_import.xlsx", file_hash="hash123", hotel_id=hotel1.id, uploaded_by_id=admin_user.id, status='completed')
    db.session.add(ib)
    db.session.commit()
    
    return {
        'hotel1_id': hotel1.id,
        'hotel2_id': hotel2.id,
        'admin_id': admin_user.id,
        'restricted_id': restricted_user.id,
        'item1_id': item1.id,
        'item2_id': item2.id,
        'dead_item_id': dead_item.id
    }

class TestChatIntegration:
    
    def test_chat_audit_logging(self, app, chat_service, setup_data):
        """Verify chat actions create AuditLog entries"""
        user = User.query.get(setup_data['admin_id'])
        
        # 1. Test Clear History Audit
        chat_service.clear_history(user.id, user=user)
        
        log = AuditLog.query.filter_by(
            user_id=user.id,
            action='clear_history',
            resource_type='chat'
        ).first()
        
        assert log is not None
        assert log.resource_label == 'چت هوشمند'
        assert log.action_label == 'پاک کردن تاریخچه چت'

        # 2. Test Process Message Audit (Mocking GROQ)
        with patch.object(chat_service, '_call_groq', return_value="AI Response"):
            chat_service.process_message("Hello", user_id=user.id, user=user)
            
            msg_log = AuditLog.query.filter_by(
                user_id=user.id,
                action='chat_message',
                resource_type='chat'
            ).first()
            
            assert msg_log is not None
            # Chat logging records metadata (lengths) for privacy, not content
            assert "msg_len=" in msg_log.description

    def test_context_scoping_restricted_user(self, app, chat_service, setup_data):
        """Verify restricted user sees only their hotel data"""
        user = User.query.get(setup_data['restricted_id'])
        
        # Generate context
        context = chat_service._get_full_database_context(user=user)
        
        # Checks
        assert "Hotel A" in context
        # Debug output if assertion fails
        if "Hotel B" in context:
            print("\nFAILED CONTEXT:\n", context)
        assert "Hotel B" not in context  # Should not see Hotel B
        assert "Item A1" in context      # Belongs to Hotel A
        assert "Item B1" not in context  # Belongs to Hotel B
        assert "Dead Item A" in context  # Belongs to Hotel A
        
        # Verify Warehouse Settings
        assert "آستانه تایید ضایعات" in context # From Hotel A settings

    def test_context_scoping_admin(self, app, chat_service, setup_data):
        """Verify admin sees all data"""
        user = User.query.get(setup_data['admin_id'])
        
        context = chat_service._get_full_database_context(user=user)
        
        assert "Hotel A" in context
        assert "Hotel B" in context
        assert "Item A1" in context # Only if it's in top lists or stock status, but broadly checking visibility logic
        # Note: Specific item names appear in 'Stock Status' or 'Top Items' if they qualify.
        # We can check total counts or specific sections.
        
        # Check for multi-hotel summary
        assert "توزیع بر اساس هتل" in context

    def test_dead_stock_integration(self, app, chat_service, setup_data):
        """Verify dead stock analysis is included correctly"""
        user = User.query.get(setup_data['restricted_id']) # Hotel A only
        
        # dead_item has no consumption transactions, created > 60 days ago
        context = chat_service._get_full_database_context(user=user)
        
        assert "کالاهای راکد (Dead Stock)" in context
        assert "Dead Item A" in context
        assert "هرگز مصرف نشده" in context

    def test_waste_trend_integration(self, app, chat_service, setup_data):
        """Verify waste trend calculation and integration"""
        user = User.query.get(setup_data['restricted_id'])
        hotel_id = setup_data['hotel1_id']
        item_id = setup_data['item1_id']
        
        # Create transactions in different months
        today = get_iran_today()
        # Month 0 (Current)
        t0 = Transaction(item_id=item_id, hotel_id=hotel_id, transaction_type='ضایعات', quantity=5, total_amount=5000, transaction_date=today, is_deleted=False, user_id=user.id, category='Food')
        # Month -1
        t1 = Transaction(item_id=item_id, hotel_id=hotel_id, transaction_type='ضایعات', quantity=5, total_amount=5000, transaction_date=today - timedelta(days=30), is_deleted=False, user_id=user.id, category='Food')
        
        # Purchase to calculate rate
        p0 = Transaction(item_id=item_id, hotel_id=hotel_id, transaction_type='خرید', quantity=100, total_amount=100000, transaction_date=today, is_deleted=False, user_id=user.id, category='Food')
        
        db.session.add_all([t0, t1, p0])
        db.session.commit()
        
        context = chat_service._get_full_database_context(user=user)
        
        assert "روند ضایعات (Waste Trend - 6 ماه)" in context
        # Should see data for current month
        assert f"{today.strftime('%Y-%m')}" in context

    def test_import_batch_context(self, app, chat_service, setup_data):
        """Verify recent import batches are shown"""
        user = User.query.get(setup_data['restricted_id']) # Hotel A
        
        context = chat_service._get_full_database_context(user=user)
        
        assert "test_import.xlsx" in context
        assert "hash123" not in context # Should be truncated or not shown raw if not implemented to show hash
        assert "وضعیت: completed" in context

    def test_audit_log_context_visibility(self, app, chat_service, setup_data):
        """Verify users see their own logs, admins see all"""
        admin = User.query.get(setup_data['admin_id'])
        user = User.query.get(setup_data['restricted_id'])
        
        # Create logs
        log1 = AuditLog.log(user, 'login', 'user', description="User Login")
        log2 = AuditLog.log(admin, 'update', 'system', description="Admin Update")
        db.session.commit()
        
        # Admin Context
        admin_ctx = chat_service._get_full_database_context(user=admin)
        # Context shows "Action Label + Resource Label", e.g. "ورود کاربر" or "ویرایش سیستم"
        assert "ورود کاربر" in admin_ctx
        assert "ویرایش سیستم" in admin_ctx
        
        # User Context
        user_ctx = chat_service._get_full_database_context(user=user)
        assert "ورود کاربر" in user_ctx
        assert "ویرایش سیستم" not in user_ctx # Should not see admin's logs
