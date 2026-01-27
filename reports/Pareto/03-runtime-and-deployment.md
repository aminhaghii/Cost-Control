# 03-runtime-and-deployment.md

## Process Model
The system is built to run as a single Python process managed by a WSGI server (typically in a container) but developed for native execution on Windows/Linux via Flask's dev server.

### Runtime Boundaries
*   **Web Process**: Handles HTTP requests, template rendering, and business logic.
*   **Database**: SQLite file on disk (`database/inventory.db`). WAL mode enables simultaneous reads.
*   **Filesystem**: Stores Excel uploads (`uploads/`) and generated parity reports (`exports/`).

## Deployment Topology
The system is containerized using Docker and orchestrated with Compose for simplified multi-environment management.

### Docker Configuration
*   **Base Image**: `python:3.11-slim`.
*   **Ports**: Maps internal `8084` to host.
*   **Volumes**:
    *   `./database:/app/database`: Preserves persistent data.
    *   `./exports:/app/exports`: Persistent storage for generated files.
    *   `./app.log:/app/app.log`: Persistent log capture.

## Config & Secrets Strategy
*   **Environment Variables**: Managed via `.env` file (loaded via `python-dotenv`).
*   **Sensitive Seeds**: `SECRET_KEY` (sessions) and `GROQ_API_KEY` (AI).
*   **Audit**: `ADMIN_INITIAL_PASSWORD` is used only on the first run; subsequent changes are handled in the DB.
*   **Security Posture**: CSRF protection is mandatory; `FLASK_ENV` differentiates between debug mode and production hardening.

## CI/CD Pipeline Summary (Assumed)
*Evidence from codebase structure suggesting standard practices:*
*   **Build**: Docker image generated from `Dockerfile`.
*   **Test**: `pytest` executed against the SQLite in-memory database or local file.
*   **Deploy**: Orchestrated via `docker-compose.yml` for simplified rollouts.
*   **Rollback**: Standard container rollback (previous image tag) and database file backup restoration.

## Operational Runbook
### How to Start
1.  Native: `python app.py`
2.  Docker: `docker-compose up -d`

### How to Monitor
1.  Logs: Check `app.log` or `docker logs web -f`.
2.  Health Check: Native `/health` endpoint is configured in both `Dockerfile` and `docker-compose.yml`.

### How to Backup
1.  Copy `database/inventory.db` while the app is stopped OR use `sqlite3 .backup` while running.
2.  Backup the `.env` file separately.
