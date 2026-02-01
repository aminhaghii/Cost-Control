"""Price range limits per item category to prevent unreasonable prices."""

CATEGORY_PRICE_LIMITS = {
    'Food': {
        'min_price': 10,          # 10 rials minimum
        'max_price': 50_000,      # 50,000 rials maximum (reasonable for food items)
        'warning_threshold': 10_000  # Warn if price > 10,000 rials
    },
    'Beverage': {
        'min_price': 50,
        'max_price': 15_000,      # 15,000 rials maximum (beverages)
        'warning_threshold': 5_000
    },
    'Cleaning': {
        'min_price': 100,
        'max_price': 100_000,     # 100,000 rials maximum (cleaning supplies)
        'warning_threshold': 25_000
    },
    'Office': {
        'min_price': 20,
        'max_price': 200_000,     # 200,000 rials maximum (office supplies)
        'warning_threshold': 50_000
    },
    'Equipment': {
        'min_price': 1_000,
        'max_price': 10_000_000,  # 10 million rials (equipment can be expensive)
        'warning_threshold': 2_000_000
    },
    'Maintenance': {
        'min_price': 500,
        'max_price': 5_000_000,   # 5 million rials (maintenance items)
        'warning_threshold': 1_000_000
    },
    'Other': {
        'min_price': 10,
        'max_price': 1_000_000,   # 1 million rials (general items)
        'warning_threshold': 200_000
    }
}

DEFAULT_LIMITS = {
    'min_price': 10,
    'max_price': 1_000_000,
    'warning_threshold': 100_000
}


def get_price_limits(category: str):
    """Get price limits for a given category."""
    return CATEGORY_PRICE_LIMITS.get(category, DEFAULT_LIMITS)


def validate_price_for_category(price: float, category: str):
    """
    Validate if price is reasonable for the given category.
    Returns: (is_valid, error_message, is_warning)
    """
    if price is None or price < 0:
        return False, "قیمت نمی‌تواند منفی یا صفر باشد", False

    limits = get_price_limits(category)

    if price < limits['min_price']:
        return False, f"قیمت باید بیشتر از {limits['min_price']:,} ریال باشد", False

    if price > limits['max_price']:
        return False, f"قیمت نمی‌تواند بیشتر از {limits['max_price']:,} ریال باشد", False

    if price > limits['warning_threshold']:
        return True, f"قیمت بالا - مطمئن هستید؟ (بیشتر از {limits['warning_threshold']:,} ریال)", True

    return True, "قیمت معتبر است", False


def get_suggested_price_range(category: str) -> str:
    """Get suggested price range as human-readable string."""
    limits = get_price_limits(category)
    return f"محدوده پیشنهادی: {limits['min_price']:,} تا {limits['warning_threshold']:,} ریال"
