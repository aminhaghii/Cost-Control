# 09-recommendations-roadmap.md

## Priority Roadmap

| Item | Category | Impact | Effort | Risk Reduced | Owner Role | Next Steps |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Async Imports** | Performance | High | Medium | App blocking | SRE/Dev | Move Excel processing to Celery/RQ. |
| **Encrypted 2FA** | Security | Medium | Low | Secret exposure | Security | Encrypt `totp_secret` in DB. |
| **DB Decoupling** | Scalability | High | High | Lock contention | Architect | Provide Postgres support for multi-hotel. |
| **Unit Table** | Maintainability| Medium | Low | Code bloat | Dev | Move hardcoded units to DB. |
| **Custom Alerts** | Reliability | Medium | Medium | Late response | Manager | Allow users to set custom stock alerts. |

## "Golden 3" Recommendations (This Month)
1.  **Async Processing for Imports**: Currently, a 5MB Excel file blocks the entire web server. This should be the #1 priority to ensure system availability during busy times.
2.  **Audit Log UI for Managers**: Managers currently lack a way to see *who* changed stock levels for their specific hotel. Porting the Admin Log UI to the Manager dashboard (scoped) would improve accountability.
3.  **Encrypted Secrets at Rest**: Implement a simple Fernet encryption for `totp_secret` and `GROQ_API_KEY` to protect against local filesystem/DB exposure.

## Strategic Vision
The Pareto system should evolve from a **passive reporting tool** to an **active inventory advisor**. By leveraging the GROQ integration, the roadmap should focus on predictive ordering (predicting when stock runs out based on historical usage) rather than just reporting current status.
