"""Currency formatting and summary standardization utilities."""


def format_amount(amount, unit="ریال", scale="auto"):
    """Format amount with a consistent Persian-friendly currency suffix."""
    if amount is None:
        return "-"

    amount = float(amount)

    if unit == "تومان":
        amount = amount / 10

    if scale == "auto":
        if amount >= 1_000_000_000:
            scale = "میلیارد"
        elif amount >= 1_000_000:
            scale = "میلیون"

    if scale == "میلیارد":
        value = amount / 1_000_000_000
        return f"{value:,.1f} میلیارد {unit}"
    if scale == "میلیون":
        value = amount / 1_000_000
        return f"{value:,.1f} میلیون {unit}"
    return f"{amount:,.0f} {unit}"


def standardize_summary_amounts(summary, keys=None):
    """Preserve raw numeric values and add formatted *_formatted fields."""
    if not isinstance(summary, dict):
        return summary

    if keys is None:
        keys = [
            key
            for key in summary.keys()
            if any(token in key.lower() for token in ["amount", "spend", "budget", "cost", "total", "value"])
        ]

    for key in keys:
        if key in summary and summary[key] is not None:
            raw_key = f"{key}_raw"
            formatted_key = f"{key}_formatted"
            summary[raw_key] = summary[key]
            summary[formatted_key] = format_amount(summary[key])

    return summary
