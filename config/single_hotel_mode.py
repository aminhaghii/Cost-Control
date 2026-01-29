"""
Single Hotel Mode Configuration
================================
This module enables single-hotel mode for the entire system.
When enabled, all hotel scoping and filtering is bypassed.

Usage:
    from config.single_hotel_mode import SINGLE_HOTEL_MODE, get_default_hotel_id
    
    if SINGLE_HOTEL_MODE:
        # Skip hotel filtering
        query = Item.query.all()
    else:
        # Apply hotel filtering
        query = Item.query.filter_by(hotel_id=hotel_id)
"""

# Enable single hotel mode (set to True to disable multi-hotel features)
SINGLE_HOTEL_MODE = True

# Default hotel ID to use for all operations (when creating new records)
DEFAULT_HOTEL_ID = 1


def get_default_hotel_id():
    """
    Get the default hotel ID for single hotel mode
    
    Returns:
        int: Default hotel ID (always 1 in single hotel mode)
    """
    return DEFAULT_HOTEL_ID


def should_filter_by_hotel():
    """
    Check if hotel filtering should be applied
    
    Returns:
        bool: False in single hotel mode, True in multi-hotel mode
    """
    return not SINGLE_HOTEL_MODE


def get_hotel_filter(hotel_id=None):
    """
    Get hotel filter for queries
    
    Args:
        hotel_id: Hotel ID to filter by (ignored in single hotel mode)
    
    Returns:
        dict: Empty dict in single hotel mode, {'hotel_id': hotel_id} otherwise
    """
    if SINGLE_HOTEL_MODE:
        return {}
    return {'hotel_id': hotel_id} if hotel_id else {}
