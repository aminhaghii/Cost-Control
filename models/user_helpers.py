"""
User helper methods for password history management
BUG #24 FIX: Safe password history parsing
"""
import json
import logging

logger = logging.getLogger(__name__)


def get_password_history(user):
    """
    Parse password history safely
    BUG #24 FIX: Handle None and corrupted JSON
    """
    if not hasattr(user, 'password_history') or not user.password_history:
        return []
    
    try:
        return json.loads(user.password_history)
    except (json.JSONDecodeError, TypeError) as e:
        logger.error(f"Corrupted password_history for user {user.id}: {e}")
        return []


def add_to_password_history(user, password_hash, max_history=5):
    """
    Add new password hash to history
    BUG #24 FIX: Safe history management
    """
    history = get_password_history(user)
    history.insert(0, password_hash)
    history = history[:max_history]  # Keep last 5
    user.password_history = json.dumps(history)


def is_password_in_history(user, password_hash):
    """
    Check if password hash exists in history
    """
    history = get_password_history(user)
    return password_hash in history
