# Pareto System Analysis - Index

## Table of Contents
1. [01-system-overview.md](01-system-overview.md)
2. [02-architecture.md](02-architecture.md)
3. [03-runtime-and-deployment.md](03-runtime-and-deployment.md)
4. [04-data-model-and-storage.md](04-data-model-and-storage.md)
5. [05-apis-and-integrations.md](05-apis-and-integrations.md)
6. [06-security-and-threat-model.md](06-security-and-threat-model.md)
7. [07-reliability-performance-observability.md](07-reliability-performance-observability.md)
8. [08-testing-and-quality.md](08-testing-and-quality.md)
9. [09-recommendations-roadmap.md](09-recommendations-roadmap.md)

## Executive Summary
The Pareto system is a robust, enterprise-ready inventory management platform specifically tailored for hotel chains. Built on a Flask/SQLite/GROQ-AI stack, it emphasizes data integrity through a transaction-led stock model, multi-hotel isolation, and advanced financial analytics (Pareto/ABC). The system bridges traditional inventory tracking with modern AI-powered natural language insights, providing stakeholders with both granular control and high-level strategic summaries.

## What the System Is
*   **Multi-Hotel Ready**: Built-in data isolation and role-based access control for complex hotel group hierarchies.
*   **Transaction-Led Integrity**: Enforces 100% stock accuracy by deriving inventory levels from a sum of immutable transactions rather than volatile counters.
*   **AI-Driven Analytics**: Integrates GROQ LLMs for context-aware inventory queries and automated Pareto/ABC classification insights.
*   **Enterprise-Grade Security**: Features 2FA, brute-force protection, account lockout, and comprehensive audit logging.
*   **RTL/Persian Optimized**: Designed specifically for the Iranian market with full Persian date (Jalali) and RTL interface support.
