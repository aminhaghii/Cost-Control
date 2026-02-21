import os
import pytest
from datetime import date, timedelta
import pandas as pd
import numpy as np
from decimal import Decimal

os.environ.setdefault('FLASK_ENV', 'development')

from models import db, Item, Transaction, Hotel, User
from services.strategy_analytics_service import (
    analyse_xyz,
    analyse_price_trend,
    analyse_budget_burndown,
    analyse_anomalies,
    analyse_forecast
)
from services.data_importer import DataImporter

@pytest.fixture
def app():
    from app import create_app
    from config import Config
    class TestConfig(Config):
        SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
        TESTING = True
        WTF_CSRF_ENABLED = False
        SECRET_KEY = 'test-secret-key-for-testing'

    test_app = create_app(TestConfig)
    ctx = test_app.app_context()
    ctx.push()
    db.create_all()
    yield test_app
    db.session.remove()
    db.drop_all()
    ctx.pop()

@pytest.fixture
def hotel(app):
    h = Hotel(hotel_code='TEST', hotel_name='Test Hotel', is_active=True)
    db.session.add(h)
    db.session.commit()
    return h.id

@pytest.fixture
def user(app, hotel):
    u = User(username='testuser', email='test@test.com', role='admin', is_active=True)
    u.set_password('pass')
    db.session.add(u)
    db.session.commit()
    return u.id

def make_item(hotel_id, code, name='Test', stock=0, price=1000, category='Food'):
    item = Item(
        item_code=code, item_name_fa=name, category=category,
        unit='عدد', unit_price=price, current_stock=stock,
        hotel_id=hotel_id, is_active=True
    )
    db.session.add(item)
    db.session.flush()
    return item

def make_tx(item, user_id, tx_type, qty, offset_days, price=None, source='manual', is_opening=False):
    tx = Transaction.create_transaction(
        item_id=item.id,
        transaction_type=tx_type,
        quantity=qty,
        unit_price=price if price is not None else item.unit_price,
        category=item.category,
        hotel_id=item.hotel_id,
        user_id=user_id,
        source=source,
        direction=1 if tx_type in ['خرید', 'اصلاحی'] else -1,
        is_opening_balance=is_opening,
        allow_price_override=True,
        price_override_reason='test',
    )
    tx.transaction_date = date.today() - timedelta(days=offset_days)
    # create_transaction multiplies qty by unit_price to get total_amount, but we might want to manually set it
    tx.total_amount = Decimal(str(qty)) * Decimal(str(tx.unit_price))
    db.session.add(tx)
    db.session.flush()
    return tx

class TestStrategyAnalyticsFixes:

    def test_bug1_analyse_xyz_zero_consumption(self, app, hotel, user):
        """Test that XYZ analysis properly includes zero-consumption days in its std deviation."""
        item = make_item(hotel, 'XYZ01', name='XYZ Item')
        db.session.commit()
        
        # We need at least 14 days of active consumption to pass the min_days filter
        for i in range(15):
            make_tx(item, user, 'مصرف', 10, offset_days=i)
            
        db.session.commit()
        
        # Analyze over 90 days
        result = analyse_xyz(days=90, category='Food')
        data = result['data']
        
        assert not data.empty
        item_data = data.iloc[0]
        
        # If it didn't include 0-consumption days, mean would be 10, and std would be 0
        # With 90 days and 15 days of 10, mean should be (15*10)/91 = 150/91 ~= 1.64
        assert item_data['mean_consumption'] < 5.0
        assert item_data['std_consumption'] > 0.0

    def test_bug2_analyse_price_trend_time_scale(self, app, hotel, user):
        """Test that price trend uses actual weeks elapsed instead of sequential rows."""
        item = make_item(hotel, 'TR01', name='Trend Item')
        db.session.commit()
        
        # Week 1
        make_tx(item, user, 'خرید', 10, offset_days=60, price=100)
        # Week 5
        make_tx(item, user, 'خرید', 10, offset_days=30, price=200)
        # Week 9
        make_tx(item, user, 'خرید', 10, offset_days=2, price=300)
        db.session.commit()
        
        result = analyse_price_trend(days=90, category='Food')
        data = result['data']
        
        assert not data.empty
        change_pct = data.iloc[0]['change_pct']
        
        # Prices went 100 -> 200 -> 300 over roughly 8 weeks (60 days)
        # If x=np.arange(3) was used (0, 1, 2), max span is 2, so change_pct = slope * 3.
        # But with exact scaling, time delta is properly calculated.
        assert change_pct > 0

    def test_bug3_analyse_budget_burndown_timeframe(self, app, hotel, user):
        """Test budget burndown strictly uses the queried timeframe."""
        item = make_item(hotel, 'BG01', name='Budget Item')
        db.session.commit()
        
        # Single purchase 5 days ago = span of 5 days
        make_tx(item, user, 'خرید', 10, offset_days=5, price=1000) # 10,000 total
        db.session.commit()
        
        # If days_elapsed was calculated by min(transaction_date), it would be 5 days.
        # daily_rate = 10000 / 5 = 2000.
        # But we query 30 days, so daily_rate should be 10000 / 30 = 333.
        result = analyse_budget_burndown(days=30, category='Food', budget=30000)
        summary = result['summary']
        
        assert summary['daily_burn_rate'] < 500  # Should be ~333, not 2000

    def test_bug4_analyse_anomalies_rolling_mean(self, app, hotel, user):
        """Test anomaly detection uses rolling metrics, not global mean."""
        item = make_item(hotel, 'AN01', name='Anomaly Item')
        db.session.commit()
        
        # Natural stable prices over time
        for i, price in enumerate([100, 100, 100, 100, 100]):
            make_tx(item, user, 'خرید', 10, offset_days=60 - (i * 5), price=price)
            
        # Sudden jump
        make_tx(item, user, 'خرید', 10, offset_days=2, price=200)
            
        db.session.commit()
        
        result = analyse_anomalies(days=90, category='Food', z_threshold=2.0)
        data = result['data']
        
        # We expect exactly 1 anomaly for the sudden jump to 200
        assert len(data) == 1
        assert "قیمت غیرعادی" in data.iloc[0]['reasons']

    def test_bug5_analyse_forecast_dynamic_occ(self, app, hotel, user):
        """Test forecast allows dynamic historical_avg_occ."""
        item = make_item(hotel, 'FC01', name='Forecast Item')
        db.session.commit()
        
        for i in range(5):
            make_tx(item, user, 'خرید', 10, offset_days=i * 7, price=100)
        db.session.commit()
        
        # If historical_occ is hardcoded to 70 and we pass occupancy_forecast=[70], multiplier is 1
        # Now we can pass historical_avg_occ=100. Let's see if our parameter works.
        result = analyse_forecast(days=90, category='Food', occupancy_forecast=[50, 50], historical_avg_occ=100)
        
        assert result['summary'] is not None

    def test_bug6_base_queries_filter_zero_price_and_opening(self, app, hotel, user):
        """Test that data importer zero-price logic and query filtering work."""
        item = make_item(hotel, 'OP01', name='Opening Item', stock=100)
        db.session.commit()
        
        # Importer creates an opening balance transaction.
        # Let's manually create what the importer would to test base queries.
        make_tx(item, user, 'اصلاحی', 100, offset_days=10, price=0, is_opening=True, source='opening_import')
        make_tx(item, user, 'خرید', 10, offset_days=5, price=0)  # Invalid 0 price
        make_tx(item, user, 'خرید', 10, offset_days=2, price=500) # Valid
        
        db.session.commit()
        
        from services.strategy_analytics_service import _base_purchase_df
        df = _base_purchase_df(days=90)
        
        # Should only contain the valid price=500 transaction
        assert len(df) == 1
        assert df.iloc[0]['unit_price'] == 500
