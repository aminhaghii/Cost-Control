#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Production Database Initialization Script
Creates database schema and default admin user for fresh deployments
"""

import os
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app import create_app
from models import db, User, Hotel
from config import Config
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def init_database():
    """Initialize database schema and create default data"""
    app = create_app(Config)
    
    with app.app_context():
        logger.info("Initializing database schema...")
        
        # Create all tables
        db.create_all()
        logger.info("✅ Database schema created successfully")
        
        # Check if admin user exists
        admin = User.query.filter_by(username='admin').first()
        if not admin:
            logger.info("Creating default admin user...")
            
            # Get admin password from environment or use temporary password
            admin_password = os.environ.get('ADMIN_INITIAL_PASSWORD')
            if not admin_password:
                admin_password = 'Admin@123456'
                logger.warning("⚠️  No ADMIN_INITIAL_PASSWORD set in environment!")
                logger.warning("⚠️  Using temporary password: Admin@123456")
                logger.warning("⚠️  CHANGE THIS IMMEDIATELY after first login!")
            
            admin = User(
                username='admin',
                email='admin@hotel.local',
                full_name='System Administrator',
                role='admin',
                is_active=True
            )
            admin.set_password(admin_password)
            db.session.add(admin)
            db.session.commit()
            
            logger.info("✅ Admin user created successfully")
            logger.info(f"   Username: admin")
            logger.info(f"   Email: admin@hotel.local")
            if not os.environ.get('ADMIN_INITIAL_PASSWORD'):
                logger.info(f"   Temporary Password: Admin@123456")
        else:
            logger.info("ℹ️  Admin user already exists, skipping creation")
        
        # Check if default hotel exists
        hotel = Hotel.query.filter_by(hotel_code='MAIN').first()
        if not hotel:
            logger.info("Creating default hotel...")
            hotel = Hotel(
                hotel_code='MAIN',
                hotel_name='Main Hotel',
                is_active=True
            )
            db.session.add(hotel)
            db.session.commit()
            logger.info("✅ Default hotel created successfully")
        else:
            logger.info("ℹ️  Default hotel already exists, skipping creation")
        
        logger.info("\n" + "="*60)
        logger.info("🎉 Database initialization completed successfully!")
        logger.info("="*60)
        logger.info("\nNext steps:")
        logger.info("1. Access the application at http://localhost:8084")
        logger.info("2. Login with admin credentials")
        logger.info("3. Change admin password immediately")
        logger.info("4. Create additional users as needed")
        logger.info("="*60 + "\n")


if __name__ == '__main__':
    try:
        init_database()
    except Exception as e:
        logger.error(f"❌ Database initialization failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
