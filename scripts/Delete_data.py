from app import create_app
from models import db, Item, Transaction, Alert, User

app = create_app()
with app.app_context():
    # حذف تراکنش‌ها و هشدارها و کالاها
    db.session.query(Transaction).delete()
    db.session.query(Alert).delete()
    db.session.query(Item).delete()
    db.session.commit()
    print("✅ همهٔ کالاها/تراکنش‌ها/هشدارها پاک شدند.")
