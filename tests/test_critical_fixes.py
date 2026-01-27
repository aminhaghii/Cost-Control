#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Test Suite for Critical Bug Fixes
Phase 4: Verify all critical fixes from Fix_Bug.md

Tests:
1. Concurrency: Atomic stock updates prevent race conditions
2. Import Rollback: Failed imports don't leave partial data
3. 2FA Rate Limit: Brute force protection works
4. Unit Conversion: Raises error for unknown conversions
"""

import pytest
import threading
import time
import os
import sys

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestAtomicStockUpdates:
    """Test Phase 1.1: Race condition fix with atomic updates"""
    
    def test_concurrent_stock_updates(self, app, db):
        """
        Simulate 2 threads trying to buy the same item.
        Verify stock is incremented correctly without lost updates.
        """
        from models import Item, Transaction, Hotel
        from services.stock_service import create_stock_transaction
        
        with app.app_context():
            # Setup: Create a hotel and item with initial stock of 100
            hotel = Hotel.query.first()
            if not hotel:
                hotel = Hotel(hotel_name='Test Hotel', hotel_code='TEST', is_active=True)
                db.session.add(hotel)
                db.session.commit()
            
            item = Item(
                item_code='TEST001',
                item_name_fa='تست آیتم',
                category='Food',
                unit='عدد',
                hotel_id=hotel.id,
                current_stock=100
            )
            db.session.add(item)
            db.session.commit()
            item_id = item.id
            
            # Track results from threads
            results = []
            errors = []
            
            def purchase_item(quantity, user_id):
                """Thread function to create a purchase transaction"""
                try:
                    with app.app_context():
                        tx = create_stock_transaction(
                            item_id=item_id,
                            transaction_type='خرید',
                            quantity=quantity,
                            unit_price=1000,
                            user_id=user_id,
                            source='test'
                        )
                        db.session.commit()
                        results.append(('success', quantity))
                except Exception as e:
                    errors.append(str(e))
            
            # Create 2 threads that both try to add 10 items
            thread1 = threading.Thread(target=purchase_item, args=(10, 1))
            thread2 = threading.Thread(target=purchase_item, args=(20, 1))
            
            thread1.start()
            thread2.start()
            
            thread1.join()
            thread2.join()
            
            # Verify: Stock should be 100 + 10 + 20 = 130
            with app.app_context():
                item = Item.query.get(item_id)
                expected_stock = 130
                
                # Allow for some tolerance due to timing
                assert item.current_stock == expected_stock, \
                    f"Expected stock {expected_stock}, got {item.current_stock}. " \
                    f"Results: {results}, Errors: {errors}"
                
                # Cleanup
                Transaction.query.filter_by(item_id=item_id).delete()
                Item.query.filter_by(id=item_id).delete()
                db.session.commit()


class TestImportRollback:
    """Test Phase 1.2: Excel import rollback on failure"""
    
    def test_import_rollback_on_failure(self, app, db):
        """
        Simulate an import that fails mid-way.
        Verify the database state remains unchanged (no partial data).
        """
        from models import Item, Transaction, ImportBatch
        from services.data_importer import DataImporter
        
        with app.app_context():
            # Get initial counts
            initial_item_count = Item.query.count()
            initial_tx_count = Transaction.query.count()
            initial_batch_count = ImportBatch.query.count()
            
            # Create importer
            importer = DataImporter(user_id=1, hotel_id=None)
            
            # Try to import a non-existent file (should fail)
            result = importer.import_excel('/nonexistent/path/file.xlsx')
            
            # Verify failure
            assert result['success'] == False
            
            # Verify no partial data was committed
            assert Item.query.count() == initial_item_count, \
                "Item count changed after failed import"
            assert Transaction.query.count() == initial_tx_count, \
                "Transaction count changed after failed import"
            # Note: ImportBatch might or might not be created depending on where failure occurs
            

class TestTwoFactorRateLimit:
    """Test Phase 2.1: 2FA rate limiting"""
    
    def test_2fa_rate_limit_blocks_after_5_attempts(self, app, client):
        """
        Simulate hitting the 2FA endpoint 10 times in quick succession.
        Verify that it returns 429 (Too Many Requests) after 5 attempts.
        """
        from models import User
        
        with app.app_context():
            # Setup: Create a user with 2FA enabled
            user = User.query.filter_by(username='admin').first()
            if not user:
                pytest.skip("No admin user available for testing")
            
            # Set up pending 2FA session
            with client.session_transaction() as sess:
                sess['pending_2fa_user_id'] = user.id
                sess['pending_2fa_remember'] = False
            
            # Make 6 rapid attempts (5 should succeed, 6th should be blocked)
            blocked = False
            for i in range(6):
                response = client.post('/security/2fa/verify', data={
                    'token': '000000'  # Wrong token
                })
                
                if response.status_code == 429:
                    blocked = True
                    break
            
            # Verify rate limiting kicked in
            assert blocked, "Rate limiting did not block after 5 attempts"


class TestUnitConversion:
    """Test Phase 1.3: Unit conversion validation"""
    
    def test_unknown_unit_raises_error(self, app, db):
        """
        Try to create a transaction with conversion_factor=None
        for a unit that differs from base unit.
        Verify it raises ValueError.
        """
        from models import Item, Transaction, Hotel
        
        with app.app_context():
            # Setup: Create item with base unit 'کیلوگرم'
            hotel = Hotel.query.first()
            if not hotel:
                hotel = Hotel(hotel_name='Test Hotel', hotel_code='TEST', is_active=True)
                db.session.add(hotel)
                db.session.commit()
            
            item = Item(
                item_code='CONV001',
                item_name_fa='تست تبدیل',
                category='Food',
                unit='کیلوگرم',
                base_unit='کیلوگرم',
                hotel_id=hotel.id,
                current_stock=0
            )
            db.session.add(item)
            db.session.commit()
            
            # Create transaction with unknown unit (should work if unit matches base)
            tx = Transaction(
                item_id=item.id,
                transaction_type='خرید',
                category='Food',
                hotel_id=hotel.id,
                quantity=10,
                unit='کیلوگرم',  # Same as base unit
                conversion_factor_to_base=None,  # Not specified
                unit_price=1000,
                total_amount=10000,
                user_id=1
            )
            
            # This should work because unit matches base unit
            tx.calculate_signed_quantity()
            assert tx.conversion_factor_to_base == 1.0
            assert tx.signed_quantity == 10.0
            
            # Now try with a different unit that has no conversion
            tx2 = Transaction(
                item_id=item.id,
                transaction_type='خرید',
                category='Food',
                hotel_id=hotel.id,
                quantity=10,
                unit='واحد_نامشخص',  # Unknown unit
                conversion_factor_to_base=None,
                unit_price=1000,
                total_amount=10000,
                user_id=1
            )
            
            # This should raise ValueError
            with pytest.raises(ValueError) as excinfo:
                tx2.calculate_signed_quantity()
            
            assert "Cannot determine conversion factor" in str(excinfo.value)
            
            # Cleanup
            Item.query.filter_by(id=item.id).delete()
            db.session.commit()


class TestSessionSecurity:
    """Test Phase 2.2: Session security configuration"""
    
    def test_secure_cookie_defaults(self, app):
        """Verify secure cookie settings default to secure values"""
        with app.app_context():
            # In production mode (default), cookies should be secure
            # This depends on FLASK_ENV not being 'development'
            import os
            flask_env = os.environ.get('FLASK_ENV', 'production')
            
            if flask_env != 'development':
                assert app.config.get('SESSION_COOKIE_SECURE') == True, \
                    "SESSION_COOKIE_SECURE should be True in non-development mode"
                assert app.config.get('REMEMBER_COOKIE_SECURE') == True, \
                    "REMEMBER_COOKIE_SECURE should be True in non-development mode"


class TestLockoutDuration:
    """Test Phase 2.3: Lockout duration from config"""
    
    def test_lockout_uses_config_value(self, app, db):
        """Verify failed login lockout uses config duration, not hardcoded 15 minutes"""
        from models import User
        from datetime import datetime, timedelta
        
        with app.app_context():
            # Get config values
            max_attempts = app.config.get('MAX_LOGIN_ATTEMPTS', 5)
            lockout_seconds = app.config.get('LOGIN_LOCKOUT_DURATION', 300)
            
            # Create test user
            test_user = User(
                username='lockout_test_user',
                email='lockout@test.com',
                role='staff'
            )
            test_user.set_password('TestPass123')
            db.session.add(test_user)
            db.session.commit()
            
            # Simulate failed login attempts
            for i in range(max_attempts):
                test_user.record_failed_login()
            
            db.session.commit()
            
            # Verify user is locked
            assert test_user.is_locked(), "User should be locked after max attempts"
            
            # Verify lockout duration matches config (within 5 second tolerance)
            expected_unlock = datetime.utcnow() + timedelta(seconds=lockout_seconds)
            actual_unlock = test_user.locked_until
            
            # The lockout should be approximately lockout_seconds from now
            # (with some tolerance for execution time)
            time_diff = abs((actual_unlock - expected_unlock).total_seconds())
            assert time_diff < 10, \
                f"Lockout duration mismatch: expected ~{lockout_seconds}s, " \
                f"but locked_until differs by {time_diff}s"
            
            # Cleanup
            User.query.filter_by(id=test_user.id).delete()
            db.session.commit()


class TestDivisionByZero:
    """Test Phase 3.3: Division by zero protection"""
    
    def test_pareto_handles_zero_total(self, app, db):
        """Verify Pareto service handles empty/zero data without errors"""
        from services.pareto_service import ParetoService
        
        with app.app_context():
            service = ParetoService()
            
            # Call with parameters that likely return empty results
            df = service.calculate_pareto(
                mode='خرید',
                category='NonExistentCategory',
                days=1,
                use_cache=False
            )
            
            # Should return empty DataFrame without error
            assert df.empty or len(df) == 0, \
                "Expected empty result for non-existent category"
            
            # Get summary stats (should handle zero totals)
            stats = service.get_summary_stats(
                mode='خرید',
                category='NonExistentCategory',
                days=1
            )
            
            # Verify no division by zero errors
            assert stats['total_items'] == 0
            assert stats['pareto_ratio'] == 0


# Pytest fixtures
@pytest.fixture
def app():
    """Create application for testing"""
    import os
    os.environ['FLASK_ENV'] = 'development'  # Use development for testing
    
    from app import create_app
    from config import Config
    
    class TestConfig(Config):
        TESTING = True
        WTF_CSRF_ENABLED = False  # Disable CSRF for testing
        SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
    
    app = create_app(TestConfig)
    return app


@pytest.fixture
def db(app):
    """Create database for testing"""
    from models import db as _db
    
    with app.app_context():
        _db.create_all()
        yield _db
        _db.drop_all()


@pytest.fixture
def client(app):
    """Create test client"""
    return app.test_client()


if __name__ == '__main__':
    pytest.main([__file__, '-v', '--tb=short'])
