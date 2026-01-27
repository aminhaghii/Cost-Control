#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Stock Service - P0-1: Stock as Single Source of Truth
Provides functions for recalculating and rebuilding stock from transactions
"""

from datetime import datetime
from sqlalchemy import func, update
from models import db, Item, Transaction, TRANSACTION_DIRECTION


def recalculate_stock(item_id=None, hotel_id=None):
    """
    Calculate stock from transactions and compare with current_stock
    
    Args:
        item_id: Optional, recalculate for specific item
        hotel_id: Optional, recalculate for specific hotel
    
    Returns:
        dict with items_checked and mismatches list
    """
    query = Item.query
    
    if hotel_id:
        query = query.filter_by(hotel_id=hotel_id)
    if item_id:
        query = query.filter_by(id=item_id)
    
    items = query.all()
    mismatches = []
    
    for item in items:
        # Calculate stock from transactions
        calculated = db.session.query(
            func.coalesce(func.sum(Transaction.signed_quantity), 0)
        ).filter(
            Transaction.item_id == item.id,
            Transaction.is_deleted != True
        ).scalar()
        
        calculated = float(calculated or 0)
        current = float(item.current_stock or 0)
        
        if abs(calculated - current) > 0.001:  # Float comparison tolerance
            mismatches.append({
                'item_id': item.id,
                'item_code': item.item_code,
                'item_name': item.item_name_fa,
                'hotel_id': item.hotel_id,
                'calculated': calculated,
                'stored': current,
                'diff': calculated - current
            })
    
    return {
        'items_checked': len(items),
        'mismatches': mismatches,
        'mismatch_count': len(mismatches)
    }


def rebuild_stock(item_id=None, hotel_id=None, auto_fix=True):
    """
    Rebuild stock from transactions
    
    Args:
        item_id: Optional, rebuild for specific item
        hotel_id: Optional, rebuild for specific hotel
        auto_fix: If True, update current_stock to match calculated
    
    Returns:
        dict with results
    """
    result = recalculate_stock(item_id, hotel_id)
    
    if auto_fix and result['mismatches']:
        for m in result['mismatches']:
            item = Item.query.get(m['item_id'])
            if item:
                item.current_stock = m['calculated']
        
        db.session.commit()
        result['fixed'] = len(result['mismatches'])
    else:
        result['fixed'] = 0
    
    return result


def adjust_stock(item_id, delta_quantity, reason, user_id, hotel_id=None):
    """
    P0-3: Create an adjustment transaction to modify stock
    This is the ONLY way to change stock (no direct edits to current_stock)
    
    Args:
        item_id: Item to adjust
        delta_quantity: Amount to adjust (SIGNED value)
                       - Positive: increase stock
                       - Negative: decrease stock
        reason: Description/reason for adjustment
        user_id: User making the adjustment
        hotel_id: Optional hotel ID
    
    Returns:
        Transaction object
    
    Example:
        adjust_stock(1, +10, "Found extra items", user_id=1)  # Add 10
        adjust_stock(1, -5, "Damaged goods", user_id=1)       # Remove 5
    """
    item = Item.query.get(item_id)
    if not item:
        raise ValueError(f"Item {item_id} not found")
    
    # P0-3: delta_quantity is signed, we convert to quantity + direction
    direction = 1 if delta_quantity >= 0 else -1
    quantity = abs(delta_quantity)  # quantity is always positive
    signed_qty = quantity * direction  # This equals delta_quantity
    
    tx = Transaction(
        item_id=item_id,
        transaction_type='اصلاحی',
        category=item.category,
        hotel_id=hotel_id or item.hotel_id,
        quantity=quantity,  # P0-3: Always positive
        direction=direction,  # P0-3: +1 or -1
        signed_quantity=signed_qty,
        unit_price=0,
        total_amount=0,
        source='adjustment',
        description=reason,
        user_id=user_id,
        transaction_date=datetime.now().date()
    )
    
    db.session.add(tx)
    
    # P1-FIX: Atomic stock update to prevent race conditions
    db.session.execute(
        update(Item).where(Item.id == item_id)
        .values(current_stock=Item.current_stock + delta_quantity)
    )
    
    db.session.commit()
    return tx


def create_stock_transaction(item_id, transaction_type, quantity, unit_price, 
                              user_id, hotel_id=None, description=None, 
                              source='manual', is_opening_balance=False,
                              import_batch_id=None):
    """
    P0-2/P0-3: Centralized function to create any stock transaction
    Use this instead of creating Transaction objects directly.
    
    Args:
        item_id: Item to transact
        transaction_type: 'خرید', 'مصرف', 'ضایعات', 'اصلاحی'
        quantity: Amount (always positive)
        unit_price: Price per unit
        user_id: User creating the transaction
        hotel_id: Hotel ID (optional, derived from item)
        description: Optional description
        source: 'manual', 'import', 'opening_import', 'adjustment'
        is_opening_balance: True if opening balance
        import_batch_id: Link to import batch (optional)
    
    Returns:
        Transaction object (not committed)
    """
    item = Item.query.get(item_id)
    if not item:
        raise ValueError(f"Item {item_id} not found")
    
    # Use the centralized factory method
    tx = Transaction.create_transaction(
        item_id=item_id,
        transaction_type=transaction_type,
        quantity=quantity,
        unit_price=unit_price,
        category=item.category,
        hotel_id=hotel_id or item.hotel_id,
        user_id=user_id,
        description=description,
        source=source,
        is_opening_balance=is_opening_balance,
        import_batch_id=import_batch_id
    )
    
    db.session.add(tx)
    
    # P1-FIX: Atomic stock update to prevent race conditions
    db.session.execute(
        update(Item).where(Item.id == item_id)
        .values(current_stock=Item.current_stock + tx.signed_quantity)
    )
    
    return tx


def backfill_signed_quantity():
    """
    Backfill signed_quantity for existing transactions that don't have it
    
    Returns:
        Number of transactions updated
    """
    transactions = Transaction.query.filter(
        Transaction.signed_quantity == None
    ).all()
    
    updated = 0
    for tx in transactions:
        tx.calculate_signed_quantity()
        updated += 1
    
    if updated > 0:
        db.session.commit()
    
    return updated


def get_stock_history(item_id, limit=50):
    """
    Get stock movement history for an item
    
    Args:
        item_id: Item ID
        limit: Max records to return
    
    Returns:
        List of transactions with running stock
    """
    transactions = Transaction.query.filter(
        Transaction.item_id == item_id,
        Transaction.is_deleted != True
    ).order_by(Transaction.transaction_date.asc(), Transaction.id.asc()).limit(limit).all()
    
    running_stock = 0
    history = []
    
    for tx in transactions:
        running_stock += (tx.signed_quantity or 0)
        history.append({
            'id': tx.id,
            'date': tx.transaction_date.isoformat() if tx.transaction_date else None,
            'type': tx.transaction_type,
            'quantity': tx.quantity,
            'direction': tx.direction,
            'signed_quantity': tx.signed_quantity,
            'running_stock': running_stock,
            'source': tx.source,
            'is_opening': tx.is_opening_balance
        })
    
    return history
