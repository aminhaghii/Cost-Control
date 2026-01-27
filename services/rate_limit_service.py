#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Rate Limiting Service
BUG-FIX #3: Multi-process safe login attempt tracking
"""

from datetime import datetime, timedelta
from models import db
from sqlalchemy import Column, Integer, String, DateTime

class LoginAttempt(db.Model):
    """Track login attempts in database for multi-process safety"""
    __tablename__ = 'login_attempts'
    
    id = Column(Integer, primary_key=True)
    identifier = Column(String(100), nullable=False, index=True)  # username or IP
    attempt_count = Column(Integer, default=1)
    last_attempt = Column(DateTime, default=datetime.utcnow)
    locked_until = Column(DateTime, nullable=True)
    
    @classmethod
    def record_failed_attempt(cls, identifier, max_attempts=5, lockout_minutes=5):
        """
        Record a failed login attempt
        Returns: (is_locked, attempts_remaining)
        """
        attempt = cls.query.filter_by(identifier=identifier).first()
        
        now = datetime.utcnow()
        
        if attempt:
            # Check if lockout expired
            if attempt.locked_until and now > attempt.locked_until:
                # Reset after lockout
                attempt.attempt_count = 1
                attempt.last_attempt = now
                attempt.locked_until = None
            else:
                # Increment attempts
                attempt.attempt_count += 1
                attempt.last_attempt = now
                
                # Lock if exceeded
                if attempt.attempt_count >= max_attempts:
                    attempt.locked_until = now + timedelta(minutes=lockout_minutes)
        else:
            # First attempt
            attempt = cls(
                identifier=identifier,
                attempt_count=1,
                last_attempt=now
            )
            db.session.add(attempt)
        
        db.session.commit()
        
        is_locked = attempt.locked_until and now < attempt.locked_until
        remaining = max(0, max_attempts - attempt.attempt_count)
        
        return (is_locked, remaining)
    
    @classmethod
    def clear_attempts(cls, identifier):
        """Clear attempts after successful login"""
        cls.query.filter_by(identifier=identifier).delete()
        db.session.commit()
    
    @classmethod
    def is_locked(cls, identifier):
        """Check if identifier is currently locked"""
        attempt = cls.query.filter_by(identifier=identifier).first()
        if not attempt:
            return False
        
        if attempt.locked_until and datetime.utcnow() < attempt.locked_until:
            return True
        
        return False
    
    @classmethod
    def cleanup_old_attempts(cls, days=7):
        """Cleanup old attempts (run via cron)"""
        cutoff = datetime.utcnow() - timedelta(days=days)
        cls.query.filter(cls.last_attempt < cutoff).delete()
        db.session.commit()
