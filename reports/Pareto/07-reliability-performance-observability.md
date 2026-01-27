# 07-reliability-performance-observability.md

## Reliability & Failure Modes
| Failure Mode | Impact | Recovery Mechanism |
| :--- | :--- | :--- |
| **Database Corruption**| Full outage. | Restore from `.db` backup. |
| **GROQ API Down** | Chat/AI Insights fail. | Fallback hardcoded insights (Static fallback). |
| **Concurrent Writes** | SQLite DB Lock Error. | WAL mode + 5s busy timeout configured in `app.py`. |
| **Out of Disk Space** | Cannot upload Excel or save logs. | Health check (configured in Docker) signals failure. |

## Performance & Scaling
*   **Bottlenecks**: Excel processing for large files (>50,000 rows) is done synchronously and will block the worker.
*   **Scalability**: The system is designed for vertical scaling (single node). To scale horizontally, SQLite would need to move to PostgreSQL/MySQL, and uploads would need an S3-like backend.
*   **Critical Path**: Pareto and ABC reports use Pandas for in-memory aggregation. Large historical data sets (years of transactions) may increase memory pressure.

## Observability Strategy
### 1. Logging
*   **App Logs**: `app.log` captures system errors, stack traces, and transactional flows.
*   **Audit Logs**: The `AuditLog` table records all user-driven changes (Create/Update/Delete) with old/new values.
*   **Chat Logs**: Behavioral logs for messages (length, success) but not content (privacy).

### 2. Metrics & Alerting (Proposed)
*   **Missing**: Latency metrics for GROQ API calls.
*   **Missing**: Success/Failure rate of Excel imports.
*   **Proposed Alerts**: 
    - Database busy-timeout frequency > 5% of requests.
    - Low disk space on `./database` volume.

### 3. Idempotency
*   Every `ImportBatch` is tied to a `file_hash`. Re-uploading the same file results in a rejection or an explicit "Replace" prompt, ensuring data accuracy.
