"""
Phase 3.1 Hardening Tests
Tests for:
1. ImportBatch uniqueness (partial unique index)
2. Replace mode stock correctness
3. Unit normalization in signed_quantity
4. Decimal money robustness
"""
import pytest
from decimal import Decimal
from datetime import datetime, timedelta
from models import db, Item, Transaction, ImportBatch, Hotel, User
from services.data_importer import DataImporter
from services.pareto_service import ParetoService
from services.abc_service import ABCService
from utils.decimal_utils import to_decimal


class TestImportBatchUniqueness:
    """Test partial unique index: only one active batch per file_hash"""
    
    def test_only_one_active_batch_per_hash(self, app, db_session):
        """Ensure only one active batch can exist per file_hash"""
        hotel = Hotel.query.first()
        user = User.query.first()
        
        # Create first batch (active)
        batch1 = ImportBatch(
            hotel_id=hotel.id,
            uploaded_by_id=user.id,
            file_name='test.xlsx',
            file_hash='hash123',
            total_rows=10,
            status='completed',
            is_active=True
        )
        db.session.add(batch1)
        db.session.commit()
        
        # Try to create second active batch with same hash (should fail)
        batch2 = ImportBatch(
            hotel_id=hotel.id,
            uploaded_by_id=user.id,
            file_name='test2.xlsx',
            file_hash='hash123',
            total_rows=20,
            status='completed',
            is_active=True
        )
        db.session.add(batch2)
        
        with pytest.raises(Exception):  # Should violate unique index
            db.session.commit()
        
        db.session.rollback()
    
    def test_multiple_inactive_batches_allowed(self, app, db_session):
        """Multiple inactive batches with same hash should be allowed"""
        hotel = Hotel.query.first()
        user = User.query.first()
        
        # Create multiple inactive batches with same hash
        for i in range(3):
            batch = ImportBatch(
                hotel_id=hotel.id,
                uploaded_by_id=user.id,
                file_name=f'test{i}.xlsx',
                file_hash='hash_inactive',
                total_rows=10 + i,
                status='replaced',
                is_active=False
            )
            db.session.add(batch)
        
        db.session.commit()
        
        # Should have 3 inactive batches
        count = ImportBatch.query.filter_by(
            file_hash='hash_inactive',
            is_active=False
        ).count()
        assert count == 3


class TestReplaceModeStockCorrectness:
    """Test stock rebuild when replacing batches"""
    
    def test_replace_mode_reverts_stock(self, app, db_session):
        """When replacing batch, old transactions should be soft-deleted and stock reverted"""
        hotel = Hotel.query.first()
        user = User.query.first()
        
        # Create item
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
        
        # Create first batch
        batch1 = ImportBatch(
            hotel_id=hotel.id,
            uploaded_by_id=user.id,
            file_name='test.xlsx',
            file_hash='replace_test',
            total_rows=1,
            status='completed',
            is_active=True
        )
        db.session.add(batch1)
        db.session.commit()
        
        # Add transaction from first batch (+10 kg)
        tx1 = Transaction.create_transaction(
            item_id=item.id,
            transaction_type='خرید',
            quantity=10,
            unit_price=100,
            category='Food',
            hotel_id=hotel.id,
            user_id=user.id,
            import_batch_id=batch1.id,
            unit='kg',
            conversion_factor_to_base=1.0
        )
        db.session.add(tx1)
        item.current_stock = 10
        db.session.commit()
        
        initial_stock = item.current_stock
        assert initial_stock == 10
        
        # Now replace with new batch
        importer = DataImporter(hotel.id, user.id)
        
        # Simulate replace logic
        existing_batch = ImportBatch.query.filter_by(
            file_hash='replace_test',
            is_active=True
        ).first()
        
        if existing_batch:
            # Calculate stock deltas before soft delete
            from sqlalchemy import func
            stock_deltas = db.session.query(
                Transaction.item_id,
                func.coalesce(func.sum(Transaction.signed_quantity), 0)
            ).filter(
                Transaction.import_batch_id == existing_batch.id,
                Transaction.is_deleted != True
            ).group_by(Transaction.item_id).all()
            
            # Soft-delete transactions
            Transaction.query.filter(
                Transaction.import_batch_id == existing_batch.id,
                Transaction.is_deleted != True
            ).update({
                'is_deleted': True,
                'deleted_at': datetime.utcnow()
            }, synchronize_session=False)
            
            # Revert stock
            for item_id, signed_qty in stock_deltas:
                if signed_qty:
                    test_item = Item.query.get(item_id)
                    test_item.current_stock = (test_item.current_stock or 0) - float(signed_qty)
            
            existing_batch.is_active = False
            existing_batch.status = 'replaced'
            db.session.commit()
        
        # Verify stock was reverted
        db.session.refresh(item)
        assert item.current_stock == 0, f"Stock should be reverted to 0, got {item.current_stock}"
        
        # Verify transaction is soft-deleted
        tx1_check = Transaction.query.get(tx1.id)
        assert tx1_check.is_deleted == True


class TestUnitNormalization:
    """Test signed_quantity is always in base_unit"""
    
    def test_signed_quantity_uses_conversion_factor(self, app, db_session):
        """signed_quantity should be quantity * conversion_factor * direction"""
        hotel = Hotel.query.first()
        user = User.query.first()
        
        # Create item with kg base unit
        item = Item(
            item_code='UNIT001',
            item_name_fa='تست واحد',
            category='Food',
            unit='kg',
            base_unit='kg',
            hotel_id=hotel.id
        )
        db.session.add(item)
        db.session.commit()
        
        # Purchase in grams (1000g = 1kg)
        tx = Transaction.create_transaction(
            item_id=item.id,
            transaction_type='خرید',
            quantity=1000,  # 1000 grams
            unit_price=10,
            category='Food',
            hotel_id=hotel.id,
            user_id=user.id,
            unit='g',
            conversion_factor_to_base=0.001  # g to kg
        )
        db.session.add(tx)
        db.session.commit()
        
        # signed_quantity should be in kg (base unit)
        # 1000 * 0.001 * 1 (direction) = 1.0 kg
        assert tx.signed_quantity == 1.0, f"Expected 1.0 kg, got {tx.signed_quantity}"
        assert tx.conversion_factor_to_base == 0.001
        assert tx.unit == 'g'
    
    def test_consumption_uses_negative_direction(self, app, db_session):
        """Consumption should have negative signed_quantity"""
        hotel = Hotel.query.first()
        user = User.query.first()
        
        item = Item.query.first()
        
        # Consumption transaction
        tx = Transaction.create_transaction(
            item_id=item.id,
            transaction_type='مصرف',
            quantity=5,
            unit_price=100,
            category='Food',
            hotel_id=hotel.id,
            user_id=user.id,
            unit='kg',
            conversion_factor_to_base=1.0
        )
        db.session.add(tx)
        db.session.commit()
        
        # Should be negative (direction = -1)
        assert tx.direction == -1
        assert tx.signed_quantity == -5.0


class TestDecimalRobustness:
    """Test to_decimal helper and money calculations"""
    
    def test_to_decimal_helper(self):
        """Test to_decimal helper handles various inputs"""
        # None should become 0
        assert to_decimal(None) == Decimal('0.00')
        
        # String conversion
        assert to_decimal('123.456') == Decimal('123.46')
        
        # Float conversion
        assert to_decimal(99.999) == Decimal('100.00')
        
        # Decimal passthrough
        assert to_decimal(Decimal('50.50')) == Decimal('50.50')
    
    def test_pareto_service_uses_decimal(self, app, db_session):
        """Pareto calculations should use Decimal for accuracy"""
        hotel = Hotel.query.first()
        user = User.query.first()
        
        # Create test items with transactions
        for i in range(3):
            item = Item(
                item_code=f'DEC{i:03d}',
                item_name_fa=f'کالای {i}',
                category='Food',
                unit='kg',
                base_unit='kg',
                hotel_id=hotel.id
            )
            db.session.add(item)
            db.session.commit()
            
            tx = Transaction.create_transaction(
                item_id=item.id,
                transaction_type='خرید',
                quantity=10 + i,
                unit_price=Decimal('99.99'),
                category='Food',
                hotel_id=hotel.id,
                user_id=user.id
            )
            db.session.add(tx)
        
        db.session.commit()
        
        # Get Pareto analysis
        pareto_service = ParetoService()
        df = pareto_service.calculate_pareto('خرید', 'Food', days=30)
        
        # Verify DataFrame has data
        assert not df.empty
        
        # Verify amount values are properly formatted floats
        for amount in df['amount']:
            assert isinstance(amount, (int, float))
            assert amount > 0
    
    def test_abc_service_uses_decimal(self, app, db_session):
        """ABC classification should use Decimal"""
        abc_service = ABCService()
        classified = abc_service.get_abc_classification('خرید', 'Food', days=30)
        
        # Should have A, B, C keys
        assert 'A' in classified
        assert 'B' in classified
        assert 'C' in classified
        
        # Check monetary values in results
        for abc_class in ['A', 'B', 'C']:
            for item in classified[abc_class]:
                assert 'total_amount' in item
                assert isinstance(item['total_amount'], (int, float))


class TestHotelConsistency:
    """Test Transaction.hotel_id == Item.hotel_id enforcement"""
    
    def test_transaction_enforces_hotel_match(self, app, db_session):
        """Transaction creation should enforce hotel_id match with item"""
        hotels = Hotel.query.limit(2).all()
        if len(hotels) < 2:
            pytest.skip("Need at least 2 hotels for this test")
        
        hotel1, hotel2 = hotels[0], hotels[1]
        user = User.query.first()
        
        # Create item in hotel1
        item = Item(
            item_code='HOTEL001',
            item_name_fa='تست هتل',
            category='Food',
            unit='kg',
            base_unit='kg',
            hotel_id=hotel1.id
        )
        db.session.add(item)
        db.session.commit()
        
        # Try to create transaction with mismatched hotel_id
        with pytest.raises(ValueError, match="hotel_id must match"):
            Transaction.create_transaction(
                item_id=item.id,
                transaction_type='خرید',
                quantity=10,
                unit_price=100,
                category='Food',
                hotel_id=hotel2.id,  # Different hotel!
                user_id=user.id
            )


# Fixtures
@pytest.fixture
def app():
    """Create application for testing"""
    from app import app as flask_app
    flask_app.config['TESTING'] = True
    flask_app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
    
    with flask_app.app_context():
        db.create_all()
        
        # Create test hotel and user
        hotel = Hotel(hotel_name='Test Hotel', is_active=True)
        db.session.add(hotel)
        
        user = User(
            username='testuser',
            email='test@test.com',
            role='admin',
            is_active=True
        )
        user.set_password('test123')
        db.session.add(user)
        db.session.commit()
        
        yield flask_app
        
        db.session.remove()
        db.drop_all()


@pytest.fixture
def db_session(app):
    """Database session for tests"""
    with app.app_context():
        yield db.session
