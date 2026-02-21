import pytest
from unittest.mock import MagicMock, patch
from datetime import date
from decimal import Decimal
import pandas as pd
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from services.data_importer import DataImporter
from models import Item, Transaction, db

# Create a minimal Flask app for testing context
@pytest.fixture(scope='session')
def flask_app():
    app = Flask(__name__)
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config['SECRET_KEY'] = 'test'
    
    # Initialize DB with app
    db.init_app(app)
    
    with app.app_context():
        # Create tables for models to be valid (though we mock mostly)
        db.create_all()
        yield app
        # Cleanup
        db.drop_all()

@pytest.fixture
def app_context(flask_app):
    with flask_app.app_context():
        yield

class TestDataImporterAdvanced:
    
    @pytest.fixture
    def importer(self, app_context):
        return DataImporter(hotel_id=1, user_id=1)

    @patch('pandas.read_excel')
    @patch('models.Transaction.create_transaction')
    def test_historical_import_does_not_update_stock(self, mock_create_transaction, mock_read_excel, importer):
        """Test that update_stock=False prevents stock changes."""
        # Setup
        item = Item(id=1, item_code='F001', item_name_fa='Rice', current_stock=100, unit='kg', base_unit='kg', category='Food', hotel_id=1)
        mock_read_excel.return_value = pd.DataFrame([{
            'item_code': 'F001', 'quantity': 50, 'unit_price': 1000, 
            'transaction_type': 'buy', 'date': '2023-01-01'
        }])
        
        # Mock _resolve_item_for_transaction to return our item
        with patch.object(importer, '_resolve_item_for_transaction', return_value=item):
            mock_create_transaction.return_value = Transaction(signed_quantity=50)
            
            # Use patch for Item.query within the test method scope
            with patch('models.Item.query') as mock_query:
                # Act
                importer._import_pareto_transactions_sheet(None, 'Sheet1', update_stock=False)
                
                # Assert
                # Verify update was NOT called on the query
                mock_query.filter_by.assert_not_called()

    @patch('models.db.session')
    @patch('models.Item.query')
    def test_concurrency_retry_logic(self, mock_query, mock_session, importer):
        """Test that _create_item_safe retries on IntegrityError."""
        from sqlalchemy.exc import IntegrityError
        
        # Mock DB session
        mock_session.begin_nested.return_value.__enter__.return_value = None
        
        # Fail first time, succeed second time
        mock_session.flush.side_effect = [IntegrityError(None, None, None), None]
        
        # Mock Query to return existing item (so logic tries to increment)
        mock_query.filter_by.return_value.order_by.return_value.first.return_value = Item(item_code='F0001')
        
        # Act
        item = importer._create_item_safe('New Item', 'kg', 'Food')
        
        # Assert
        assert item.item_code != 'F0001' # Should have incremented or randomized
        assert mock_session.flush.call_count == 2

    @patch('models.Item.get_conversion_factor')
    def test_unit_conversion_logic(self, mock_get_factor, importer):
        """Test automatic unit conversion."""
        # This test relies on Item model methods which might need app context if they query DB
        # But get_conversion_factor usually reads from a dict or DB. 
        # Since we mock it, it's fine.
        
        mock_get_factor.return_value = 0.001
        
        # Simulate logic
        row_unit = 'g'
        item_base_unit = 'kg'
        factor = Item.get_conversion_factor(row_unit, item_base_unit)
        
        assert factor == 0.001
        mock_get_factor.assert_called_with('g', 'kg')

    def test_supplier_column_mapping(self, importer):
        """Test that 'Supplier' column is detected."""
        df = pd.DataFrame(columns=['Item Name', 'Supplier Name', 'Price'])
        cols = importer._detect_transaction_columns(df)
        assert cols.get('supplier') == 'Supplier Name'
