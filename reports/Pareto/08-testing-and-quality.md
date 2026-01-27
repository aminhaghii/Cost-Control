# 08-testing-and-quality.md

## Test Strategy
The system follows a pragmatic testing approach with a focus on regression and hardening.

### Test Pyramid (Current State)
*   **Unit Tests**: High coverage in `services/` (Stock calculations, ABC classification).
*   **Integration Tests**: Comprehensive tests in `tests/test_phase_3_hardening.py` covering the import pipeline and stock rebuilds.
*   **E2E Tests**: Manual verification via screenshots and walkthroughs (observed in recent dev cycles).

## Hard-to-Test Areas
*   **AI Chat Logic**: Non-deterministic LLM responses make automated testing difficult. Recommendation: Use "Golden Sets" or LLM-judges.
*   **Excel Rendering**: Visual validation of Persian RTL charts requires manual review.
*   **Production Concurrency**: Difficult to simulate 50 simultaneous hotel managers in a local SQLite environment.

## Code Quality Hotspots
1.  **Large Routes**: `routes/transactions.py` (500+ lines) and `routes/admin.py` (900+ lines) are candidates for refactoring into smaller blueprint modules or view classes.
2.  **Duplicate Logic**: Pareto logic is partially duplicated between `services/pareto_service.py` and the `chat_service.py` context builder.
3.  **Hardcoded Mapping**: `item.py` contains large mapping dictionaries for units. These should move to a DB table for easier management.

## Static Analysis Suggestions
*   **Linting**: Run `flake8` or `ruff` to standardize Persian/English comment formatting.
*   **Type Checking**: Add `mypy` type hints to the `services/` layer to prevent floating-point/decimal mixup bugs.
*   **Security Scanning**: Use `bandit` for Python security checks and `safety` for dependency vulnerability scanning.
