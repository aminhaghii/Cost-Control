# 06-security-and-threat-model.md

## Asset Inventory
*   **Credential/Session Store**: User passwords (hashed), TOTP secrets, session cookies.
*   **Inventory Data**: Proprietary cost and transaction data for multiple hotels ($$$).
*   **AI Access**: GROQ API Keys (cost and usage risk).

## Trust Boundaries
*   **Public/App**: Public access is limited to the login page.
*   **User Isolation**: Staff from Hotel A must never see data from Hotel B.
*   **Role Isolation**: Staff should not access Admin panels or perform data imports.

## Threat Model & Mitigations
| Threat | Mitigation | Residual Risk |
| :--- | :--- | :--- |
| **SQL Injection** | Use of SQLAlchemy ORM (parameterized queries). | Low |
| **CSRF** | Mandatory Flask-WTF CSRF tokens on all POST requests. | Negligible |
| **Brute Force** | Account lockout after 5 failed attempts (15 min). | Low |
| **Session Hijacking** | Secure, HttpOnly, SameSite=Lax cookies; HSTS in production. | Medium (depends on TLS) |
| **Multi-tenancy Leak** | Centralized `hotel_scope_service` and `enforce_hotel_scope` filter. | Medium (Dev error) |

## Security Findings
### 1. Hardcoded Initial Password [MEDIUM]
*   **Evidence**: `config.py` handles an `ADMIN_INITIAL_PASSWORD`.
*   **Risk**: If not changed immediately via DB, it remains a weak point.
*   **Remediation**: Force password change on first login (noted as implemented in `User` model, but verification is key).

### 2. File Upload Integrity [LOW]
*   **Evidence**: `admin.py` uses `secure_filename`.
*   **Risk**: Maliciously crafted Excel files could trigger vulnerabilities in `openpyxl`.
*   **Remediation**: Sandbox the Excel processing or use a dedicated worker.

## Secrets Handling
*   Secrets live in `.env` (not committed to git).
*   Hashed passwords use `Werkzeug`'s secure hashing.
*   TOTP secrets (32-char base32) are stored in the DB; should ideally be encrypted at rest (currently plain text in SQLite).
