#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Quick script to check transaction count"""
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import create_app
from models import Transaction

app = create_app()

with app.app_context():
    total = Transaction.query.count()
    not_deleted = Transaction.query.filter_by(is_deleted=False).count()
    print(f"Total transactions: {total}")
    print(f"Active (not deleted): {not_deleted}")
