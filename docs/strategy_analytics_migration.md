# Strategy Analytics Migration Notes

## Summary
This migration refactors the strategy analytics stack to improve methodology accuracy, data-quality visibility, and operational actionability.

## What Changed

### 1) XYZ methodology switched to consumption-based
- `analyse_xyz` now uses daily `transaction_type='مصرف'` data.
- CV thresholds remain:
  - X: CV < 0.5
  - Y: 0.5 <= CV < 1.0
  - Z: CV >= 1.0
- Minimum data threshold added: `min_days_threshold = 14`.

### 2) ABC-XYZ matrix validation layer added
- Duplicate item detection.
- Missing XYZ class handling (fallback to Z).
- Multi-cell assignment guard.
- `errors` payload added to return structure.

### 3) Demand proxy replaced with consumption trend logic
- Backward-compatible function name kept: `analyse_demand_proxy`.
- Internally uses consumption transactions and weekly regression trend.
- Output includes `rising_consumption`, `stable_consumption`, `falling_consumption`.
- Legacy aliases (`rising_demand`, etc.) remain for template compatibility.

### 4) Forecast upgraded
- `analyse_forecast` now supports optional:
  - `occupancy_forecast`
  - `events`
- Method: linear trend + weighted baseline + optional occupancy/event multipliers.

### 5) KPI alert levels and actions
Applied to:
- Budget burndown
- Anomalies
- Price volatility
- Spend trend

Each summary can now include:
- `alert_level` (green/yellow/red)
- `actions` (list of recommended operational actions)

### 6) Infrastructure additions
- New: `services/strategy_validation.py`
  - Validates critical data issues before overview analytics.
- New: `utils/currency.py`
  - Adds standardized amount formatting helpers.

### 7) Overview behavior
- `get_strategy_overview` now runs validation first.
- If critical validation fails, returns `has_data=False` with validation details.

## Backward Compatibility
- Existing function signatures are preserved.
- Existing route names remain unchanged.
- Existing `data`, `summary`, `chart` return pattern is preserved.

## Verification
Run:

```bash
python scripts/verify_strategy_analyses.py
```

Expected result:
- All strategy checks pass.
- Consumption seed data is auto-generated in the verifier.
