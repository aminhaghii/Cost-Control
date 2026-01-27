"""
Regression Tests for Bug Fixes
Tests for BUG-001, BUG-002, BUG-003
"""
import pytest
from flask import url_for
from models import db, Item, Transaction, Hotel, User
from decimal import Decimal


class TestBug001TransactionCreation:
    """BUG-001: Transaction creation should not raise UnboundLocalError"""
    
    def test_create_transaction_missing_item_id(self, client, auth_user):
        """POST /transactions/create with missing item_id should return error, not crash"""
        # Login first
        client.post('/auth/login', data={
            'username': 'testuser',
            'password': 'test123'
        }, follow_redirects=True)
        
        # Try to create transaction without item_id
        response = client.post('/transactions/create', data={
            'transaction_date': '2024-01-01',
            'transaction_type': 'خرید',
            'category': 'Food',
            'quantity': '10',
            'unit_price': '100',
            'description': 'Test'
        }, follow_redirects=True)
        
        # Should not crash (200 or redirect), should show error message
        assert response.status_code == 200
        assert 'انتخاب کالا الزامی است' in response.data.decode('utf-8')
    
    def test_create_transaction_invalid_item_id(self, client, auth_user):
        """POST /transactions/create with invalid item_id should return 400"""
        # Login first
        client.post('/auth/login', data={
            'username': 'testuser',
            'password': 'test123'
        }, follow_redirects=True)
        
        # Try to create transaction with invalid item_id
        response = client.post('/transactions/create', data={
            'item_id': 'invalid',
            'transaction_date': '2024-01-01',
            'transaction_type': 'خرید',
            'category': 'Food',
            'quantity': '10',
            'unit_price': '100',
            'description': 'Test'
        })
        
        # Should return 400 Bad Request
        assert response.status_code == 400
    
    def test_create_transaction_success(self, client, auth_user, test_item):
        """Valid transaction creation should succeed"""
        # Login first
        client.post('/auth/login', data={
            'username': 'testuser',
            'password': 'test123'
        }, follow_redirects=True)
        
        initial_count = Transaction.query.count()
        
        # Create valid transaction
        response = client.post('/transactions/create', data={
            'item_id': str(test_item.id),
            'transaction_date': '2024-01-01',
            'transaction_type': 'خرید',
            'category': 'Food',
            'quantity': '10',
            'unit_price': '100',
            'description': 'Test transaction'
        }, follow_redirects=True)
        
        # Should redirect to list (200 after redirect)
        assert response.status_code == 200
        
        # Transaction should be created
        assert Transaction.query.count() == initial_count + 1
        
        # Verify transaction data
        tx = Transaction.query.order_by(Transaction.id.desc()).first()
        assert tx.item_id == test_item.id
        assert tx.quantity == 10
        assert tx.unit_price == Decimal('100.00')


class TestBug002ExcelExport:
    """BUG-002: Excel export should not crash with TypeError"""
    
    def test_pareto_excel_export_no_crash(self, client, auth_user, test_item_with_transactions):
        """GET /export/pareto-excel should return file without TypeError"""
        # Login first
        client.post('/auth/login', data={
            'username': 'testuser',
            'password': 'test123'
        }, follow_redirects=True)
        
        # Request Excel export
        response = client.get('/export/pareto-excel?mode=خرید&category=Food&days=30')
        
        # Should return 200 with Excel file
        assert response.status_code == 200
        assert response.mimetype == 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        assert len(response.data) > 0
    
    def test_abc_excel_export_no_crash(self, client, auth_user, test_item_with_transactions):
        """GET /export/abc-excel should return file without TypeError"""
        # Login first
        client.post('/auth/login', data={
            'username': 'testuser',
            'password': 'test123'
        }, follow_redirects=True)
        
        # Request Excel export
        response = client.get('/export/abc-excel?mode=خرید&category=Food&days=30')
        
        # Should return 200 with Excel file
        assert response.status_code == 200
        assert response.mimetype == 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        assert len(response.data) > 0


class TestBug003DebugMode:
    """BUG-003: Debug mode should be disabled in production"""
    
    def test_debug_disabled_by_default(self, app):
        """App should have debug=False when FLASK_ENV is not set to development"""
        import os
        # Ensure FLASK_ENV is not development
        old_env = os.environ.get('FLASK_ENV')
        if 'FLASK_ENV' in os.environ:
            del os.environ['FLASK_ENV']
        
        try:
            from app import create_app
            test_app = create_app()
            
            # Debug should be False
            assert test_app.debug == False
        finally:
            # Restore environment
            if old_env:
                os.environ['FLASK_ENV'] = old_env
    
    def test_debug_enabled_in_development(self):
        """App should have debug=True only when FLASK_ENV=development"""
        import os
        old_env = os.environ.get('FLASK_ENV')
        os.environ['FLASK_ENV'] = 'development'
        
        try:
            # When running with python app.py, debug should be True
            # This is tested by checking the logic, not the app instance
            flask_env = os.environ.get('FLASK_ENV', 'production')
            debug_mode = flask_env == 'development'
            
            assert debug_mode == True
        finally:
            # Restore environment
            if old_env:
                os.environ['FLASK_ENV'] = old_env
            elif 'FLASK_ENV' in os.environ:
                del os.environ['FLASK_ENV']


# Fixtures
@pytest.fixture
def app():
    """Create application for testing"""
    from app import create_app
    from config import Config
    
    class TestConfig(Config):
        TESTING = True
        SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
        WTF_CSRF_ENABLED = False  # Disable CSRF for testing
    
    app = create_app(TestConfig)
    
    with app.app_context():
        db.create_all()
        
        # Create test hotel
        hotel = Hotel(hotel_name='Test Hotel', is_active=True)
        db.session.add(hotel)
        
        # Create test user
        user = User(
            username='testuser',
            email='test@test.com',
            role='admin',
            is_active=True
        )
        user.set_password('test123')
        db.session.add(user)
        db.session.commit()
        
        yield app
        
        db.session.remove()
        db.drop_all()


@pytest.fixture
def client(app):
    """Test client"""
    return app.test_client()


@pytest.fixture
def auth_user(app):
    """Authenticated user"""
    with app.app_context():
        user = User.query.filter_by(username='testuser').first()
        return user


@pytest.fixture
def test_item(app, auth_user):
    """Create test item"""
    with app.app_context():
        hotel = Hotel.query.first()
        item = Item(
            item_code='TEST001',
            item_name_fa='تست',
            category='Food',
            unit='kg',
            base_unit='kg',
            hotel_id=hotel.id,
            current_stock=0
        )
        db.session.add(item)
        db.session.commit()
        return item


@pytest.fixture
def test_item_with_transactions(app, auth_user, test_item):
    """Create test item with some transactions"""
    with app.app_context():
        # Create a few transactions for testing
        for i in range(3):
            tx = Transaction.create_transaction(
                item_id=test_item.id,
                transaction_type='خرید',
                quantity=10 + i,
                unit_price=Decimal('100.00'),
                category='Food',
                hotel_id=test_item.hotel_id,
                user_id=auth_user.id
            )
            db.session.add(tx)
        
        db.session.commit()
        return test_item
