#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
BUG-FIX #3: Create login_attempts table
"""
from app import app
from models import db
from services.rate_limit_service import LoginAttempt

with app.app_context():
    db.create_all()
    print('✅ Migration table created successfully')
    print('✅ login_attempts table is ready')
