from decimal import Decimal, ROUND_HALF_UP
import re

PERSIAN_DIGIT_MAP = str.maketrans({
    '۰': '0', '۱': '1', '۲': '2', '۳': '3', '۴': '4',
    '۵': '5', '۶': '6', '۷': '7', '۸': '8', '۹': '9',
    '٠': '0', '١': '1', '٢': '2', '٣': '3', '٤': '4',
    '٥': '5', '٦': '6', '٧': '7', '٨': '8', '٩': '9',
})

NUMERIC_REGEX = re.compile(r'^-?\d+(\.\d+)?$')

THOUSANDS_SEPARATORS = [
    ' ', '\u00A0', '\u202F', '\u2007', '\u066C', '٬'
]


def normalize_numeric_input(value):
    """Normalize Persian/Arabic digits and separators to ASCII decimal string."""
    if value is None:
        raise ValueError('مقدار خالی است')
    
    normalized = str(value).strip()
    if not normalized:
        raise ValueError('مقدار خالی است')
    
    # Convert Persian/Arabic digits to Latin
    normalized = normalized.translate(PERSIAN_DIGIT_MAP)
    
    # Normalize decimal separators (Persian/Arabic decimal point to ASCII)
    normalized = normalized.replace('٫', '.').replace('/', '.')
    
    # Remove thousand separators (including commas, Persian commas, spaces)
    # Comma is treated as thousand separator, NOT decimal separator
    for sep in THOUSANDS_SEPARATORS:
        normalized = normalized.replace(sep, '')
    normalized = normalized.replace(',', '')  # Remove English comma
    normalized = normalized.replace('،', '')  # Remove Persian comma
    
    return normalized


def parse_decimal_input(value, allow_negative=False, quantize=None, error_label='مقدار'):
    """
    Robust parser for numeric form inputs with Persian/Arabic support.
    Returns Decimal value (optionally quantized).
    """
    normalized = normalize_numeric_input(value)
    
    if normalized.count('.') > 1:
        raise ValueError(f'{error_label} نامعتبر است')
    
    if normalized.startswith('-'):
        if not allow_negative:
            raise ValueError(f'{error_label} نمی‌تواند منفی باشد')
    elif normalized and normalized[0] == '+':
        normalized = normalized[1:]
    
    if not NUMERIC_REGEX.match(normalized):
        raise ValueError(f'{error_label} نامعتبر است')
    
    decimal_value = Decimal(normalized)
    
    if quantize:
        decimal_value = decimal_value.quantize(Decimal(quantize), rounding=ROUND_HALF_UP)
    
    return decimal_value


def to_decimal(value, quantize='0.01'):
    """
    تبدیل امن به Decimal با دودویی Round Half Up.
    مقدار None یا خالی را صفر می‌کند.
    """
    if value is None or value == '':
        value = 0

    decimal_value = Decimal(str(value))

    if quantize:
        decimal_value = decimal_value.quantize(Decimal(quantize), rounding=ROUND_HALF_UP)

    return decimal_value
