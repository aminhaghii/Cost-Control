
from app import app
from models import db, Item, WarehouseSettings, Transaction, Hotel, Alert
from decimal import Decimal
from datetime import date
from services.warehouse_service import WarehouseService

def verify_fix():
    with app.app_context():
        print("Starting verification of approval workflow fix...")
        
        # 1. Setup: Ensure we have a hotel with settings
        hotel = Hotel.query.filter_by(hotel_name='لاله تهران').first()
        if not hotel:
            hotel = Hotel.query.first()
        if not hotel:
            print("No hotel found in database")
            return
        
        settings = WarehouseSettings.get_or_create(hotel.id)
        settings.waste_approval_threshold = Decimal('500.00') # Low threshold for testing
        db.session.commit()
        print(f"Hotel: {hotel.hotel_name}, Threshold: {settings.waste_approval_threshold}")
        
        # 2. Setup: Find an item with stock
        item = Item.query.filter_by(hotel_id=hotel.id, is_active=True).first()
        if not item:
            print("No active item found for this hotel")
            return
            
        initial_stock = item.current_stock or 0
        print(f"Item: {item.item_name_fa}, Initial Stock: {initial_stock}")
        
        # 3. Create a waste transaction that EXCEEDS threshold
        # Using the same logic as in the route
        qty = 100
        price = 10 # total = 1000 > 500
        total_decimal = Decimal(str(qty)) * Decimal(str(price))
        
        print(f"Simulating waste transaction: qty={qty}, price={price}, total={total_decimal}")
        
        # This part mimics routes/transactions.py logic
        transaction = Transaction.create_transaction(
            item_id=item.id,
            transaction_type='ضایعات',
            quantity=qty,
            unit_price=price,
            category=item.category,
            hotel_id=item.hotel_id,
            user_id=1, # Admin
            description="Test waste approval fix"
        )
        transaction.transaction_date = date.today()
        transaction.waste_reason = 'damage'
        
        requires_approval = settings.check_waste_approval_needed(float(total_decimal))
        if requires_approval:
            transaction.requires_approval = True
            transaction.approval_status = 'pending'
            print("Transaction marked as pending approval")
        
        db.session.add(transaction)
        
        # CRITICAL: Logic from route
        if not requires_approval:
            item.current_stock = (item.current_stock or 0) + transaction.signed_quantity
        
        db.session.commit()
        
        # Verification Part 1: Stock should NOT have changed
        item_after = Item.query.get(item.id)
        print(f"Stock after creation (before approval): {item_after.current_stock}")
        if item_after.current_stock == initial_stock:
            print("SUCCESS: Stock did not change before approval.")
        else:
            print(f"FAILURE: Stock changed! Initial: {initial_stock}, Now: {item_after.current_stock}")
            return

        # Verification Part 2: Pending approval should exist
        pending = WarehouseService.get_pending_approvals(hotel.id)
        found = any(tx.id == transaction.id for tx in pending)
        if found:
            print("SUCCESS: Transaction found in pending approvals.")
        else:
            print("FAILURE: Transaction NOT found in pending approvals.")
            return

        # Verification Part 3: Approve and check stock
        print("Approving transaction...")
        WarehouseService.approve_transaction(transaction.id, 1)
        
        item_final = Item.query.get(item.id)
        expected_stock = initial_stock + transaction.signed_quantity
        print(f"Stock after approval: {item_final.current_stock}, Expected: {expected_stock}")
        
        if abs(float(item_final.current_stock) - float(expected_stock)) < 0.001:
            print("SUCCESS: Stock correctly updated after approval.")
        else:
            print("FAILURE: Stock not updated correctly after approval.")
            return

        print("\nALL VERIFICATION STEPS PASSED!")

if __name__ == "__main__":
    verify_fix()
