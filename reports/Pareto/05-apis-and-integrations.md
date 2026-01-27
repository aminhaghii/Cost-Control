# 05-apis-and-integrations.md

## API Inventory
The system primarily exposes a web-based interface with AJAX endpoints for chat and analytics.

| Endpoint | Method | Auth | Purpose | Inputs/Outputs |
| :--- | :--- | :--- | :--- | :--- |
| `/chat/api/message` | POST | Login | Send message to AI chatbot. | JSON (msg) / JSON (response, history) |
| `/ai/daily-insights` | GET | Login | Get dashboard KPI insights. | None / JSON (insight cards) |
| `/transactions/api/list`| GET | Login | Paginated transaction list. | Query Params / JSON (record list) |
| `/admin/api/hotel-stats`| GET | Admin | Stats for specific hotel. | hotel_id / JSON (counts) |
| `/auth/login` | POST | None | Authenticate user. | Credentials / Session + Redirect |

## External Integrations
### 1. GROQ API (via OpenAI SDK)
*   **Purpose**: powers the analytics chatbot and intelligent insights.
*   **Auth**: Bearer token (`GROQ_API_KEY`).
*   **Failure Handling**: The UI (seen in `ai_analysis.py`) checks `analyzer.is_available()` and provides hardcoded fallback insights if the API is down.

### 2. Excel Library (OpenPyXL / Pandas)
*   **Purpose**: Data ingestion and reporting.
*   **Auth**: N/A (local file processing).
*   **Constraint**: Max file size enforced by Flask `MAX_CONTENT_LENGTH`.

## Contract Assumptions
*   **Hotel Isolation**: All API responses MUST be filtered by `hotel_id` scoped to the current user.
*   **Backward Compatibility**: The system uses a manual migration approach (`migrate_new_changes.py`). API changes should consider existing items that might lack `base_unit` definitions.
*   **Security**: All state-changing APIs (POST/PUT/DELETE) require a valid CSRF token.
