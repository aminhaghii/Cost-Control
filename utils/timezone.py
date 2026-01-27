#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
BUG-FIX #10: Centralized timezone handling
"""
from datetime import datetime, timezone, timedelta

# Iran timezone (UTC+03:30)
IRAN_TZ = timezone(timedelta(hours=3, minutes=30))

def get_iran_now():
    """Get current datetime in Iran timezone"""
    return datetime.now(IRAN_TZ)

def get_iran_today():
    """Get current date in Iran timezone"""
    return get_iran_now().date()

def utc_to_iran(dt):
    """Convert UTC datetime to Iran timezone"""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(IRAN_TZ)

def iran_to_utc(dt):
    """Convert Iran datetime to UTC"""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=IRAN_TZ)
    return dt.astimezone(timezone.utc)
