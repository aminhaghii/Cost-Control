#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Hotel Scope Service - P0-3: Multi-hotel Access Enforcement
Provides functions for scoping queries to allowed hotels per user
"""

from models import db, Hotel, UserHotel


def get_allowed_hotel_ids(user):
    """
    Get list of hotel IDs that user is allowed to access
    
    Args:
        user: User object
    
    Returns:
        List of hotel IDs or None (meaning all hotels for admin)
    """
    if not user:
        return []
    
    # Admin/superuser can access all hotels
    if user.is_admin() or user.role == 'admin':
        return None  # None means no filter (all hotels)
    
    # Get assigned hotels from UserHotel table
    assignments = UserHotel.query.filter_by(user_id=user.id).all()
    hotel_ids = [a.hotel_id for a in assignments]
    
    # If no assignments, return empty list (no access)
    return hotel_ids if hotel_ids else []


def enforce_hotel_scope(query, user, hotel_id_column):
    """
    Apply hotel scope filter to a query
    
    Args:
        query: SQLAlchemy query object
        user: User object
        hotel_id_column: The column to filter on (e.g., Item.hotel_id)
    
    Returns:
        Filtered query
    """
    allowed = get_allowed_hotel_ids(user)
    
    if allowed is None:
        # Admin - no filter
        return query
    
    if not allowed:
        # No access - return impossible condition
        return query.filter(hotel_id_column == -1)
    
    # Filter by allowed hotels
    return query.filter(hotel_id_column.in_(allowed))


def user_can_access_hotel(user, hotel_id):
    """
    Check if user can access a specific hotel
    
    Args:
        user: User object
        hotel_id: Hotel ID to check
    
    Returns:
        Boolean
    """
    allowed = get_allowed_hotel_ids(user)
    
    if allowed is None:
        return True  # Admin
    
    return hotel_id in allowed


def get_user_hotels(user):
    """
    Get list of Hotel objects that user can access
    
    Args:
        user: User object
    
    Returns:
        List of Hotel objects
    """
    allowed = get_allowed_hotel_ids(user)
    
    if allowed is None:
        return Hotel.query.filter_by(is_active=True).all()
    
    if not allowed:
        return []
    
    return Hotel.query.filter(Hotel.id.in_(allowed), Hotel.is_active == True).all()


def assign_user_to_hotel(user_id, hotel_id, role='viewer', created_by_id=None):
    """
    Assign a user to a hotel
    
    Args:
        user_id: User ID
        hotel_id: Hotel ID
        role: Role in hotel (viewer, editor, manager)
        created_by_id: User who created this assignment
    
    Returns:
        UserHotel object or None if already exists
    """
    existing = UserHotel.query.filter_by(user_id=user_id, hotel_id=hotel_id).first()
    if existing:
        # Update role if different
        if existing.role != role:
            existing.role = role
            db.session.commit()
        return existing
    
    assignment = UserHotel(
        user_id=user_id,
        hotel_id=hotel_id,
        role=role,
        created_by_id=created_by_id
    )
    db.session.add(assignment)
    db.session.commit()
    return assignment


def remove_user_from_hotel(user_id, hotel_id):
    """
    Remove user from hotel
    
    Args:
        user_id: User ID
        hotel_id: Hotel ID
    
    Returns:
        Boolean indicating if assignment was removed
    """
    assignment = UserHotel.query.filter_by(user_id=user_id, hotel_id=hotel_id).first()
    if assignment:
        db.session.delete(assignment)
        db.session.commit()
        return True
    return False


def get_scoped_items_query(user):
    """
    Get items query scoped to user's allowed hotels
    
    Args:
        user: User object
    
    Returns:
        SQLAlchemy query for Item
    """
    from models import Item
    query = Item.query
    return enforce_hotel_scope(query, user, Item.hotel_id)


def get_scoped_transactions_query(user):
    """
    Get transactions query scoped to user's allowed hotels
    
    Args:
        user: User object
    
    Returns:
        SQLAlchemy query for Transaction
    """
    from models import Transaction
    query = Transaction.query.filter(Transaction.is_deleted != True)
    return enforce_hotel_scope(query, user, Transaction.hotel_id)


def require_hotel_access(user, hotel_id):
    """
    P1-1: Check and raise error if user cannot access hotel
    Use this in detail views/endpoints
    
    Args:
        user: User object
        hotel_id: Hotel ID to check
    
    Raises:
        PermissionError if user cannot access hotel
    
    Returns:
        True if access granted
    """
    if not user_can_access_hotel(user, hotel_id):
        raise PermissionError(f"User {user.id} cannot access hotel {hotel_id}")
    return True


def get_user_role_for_hotel(user, hotel_id):
    """
    P1-2: Get user's role for a specific hotel
    
    Args:
        user: User object
        hotel_id: Hotel ID
    
    Returns:
        Role string ('admin', 'manager', 'editor', 'viewer') or None
    """
    if not user:
        return None
    
    # Global admin has full access
    if user.is_admin() or user.role == 'admin':
        return 'admin'
    
    # Check hotel-specific assignment
    assignment = UserHotel.query.filter_by(user_id=user.id, hotel_id=hotel_id).first()
    if assignment:
        return assignment.role
    
    return None


def user_can_edit_in_hotel(user, hotel_id):
    """
    P1-2: Check if user can edit data in a specific hotel
    
    Args:
        user: User object
        hotel_id: Hotel ID
    
    Returns:
        Boolean
    """
    role = get_user_role_for_hotel(user, hotel_id)
    return role in ('admin', 'manager', 'editor')


def user_can_manage_hotel(user, hotel_id):
    """
    P1-2: Check if user can manage a specific hotel (admin actions)
    
    Args:
        user: User object
        hotel_id: Hotel ID
    
    Returns:
        Boolean
    """
    role = get_user_role_for_hotel(user, hotel_id)
    return role in ('admin', 'manager')


def check_record_access(user, record, abort_on_fail=True):
    """
    P1-1: Check if user can access a record based on its hotel_id
    
    Args:
        user: User object
        record: Any model with hotel_id attribute
        abort_on_fail: If True, abort with 403; else return False
    
    Returns:
        True if access granted, False if not (when abort_on_fail=False)
    """
    from flask import abort
    
    hotel_id = getattr(record, 'hotel_id', None)
    if hotel_id is None:
        return True  # No hotel restriction
    
    if not user_can_access_hotel(user, hotel_id):
        if abort_on_fail:
            abort(403, description="You do not have access to this hotel's data")
        return False
    
    return True
