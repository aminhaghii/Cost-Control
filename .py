
from app import app
from models import db, User

with app.app_context():
    db.create_all()
    user = User.query.filter_by(username='admin').first()
    if not user:
        user = User(username='admin', email='admin@example.com', role='admin', is_active=True)
        user.set_password('admin123')
        db.session.add(user)
        db.session.commit()
        print('Created admin user: admin / admin123')
    else:
        print('Admin user already exists')
