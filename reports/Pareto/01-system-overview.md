# 01-system-overview.md

## Purpose
The Hotel Inventory Pareto Analysis System (Pareto) is designed to solve the critical business challenge of managing high-value, high-volume inventory across multiple hotel properties. It focuses on identifying "Class A" items (the 20% of items contributing to 80% of costs) to optimize procurement, reduce waste, and improve operational transparency.

## Scope
*   **Inventory Lifecycle**: From initial import (opening balance) to purchases, consumption, and waste tracking.
*   **Multi-Hotel Isolation**: Ensuring that hotel managers only see data for properties they are assigned to.
*   **AI Analytics**: Providing a natural language interface for non-technical users to query complex inventory metrics.
*   **Warehouse Management**: Handling waste reasons, departments, and adjustment workflows.

## Personas & Workflows
| Persona | Goals | Primary Workflows |
| :--- | :--- | :--- |
| **Admin** | System health, user management, global audit. | Creating users, assigning hotels, performing massive data imports. |
| **Manager** | Inventory accuracy, cost control, trend analysis. | Reviewing ABC reports, approving waste transactions, AI-powered reorder suggestions. |
| **Staff** | Daily operations, data entry. | Logging purchases/consumption, reporting waste, checking current stock. |

## Key Constraints
*   **Integrity (P0)**: Stock must always match the sum of transactions. No manual overwriting of stock levels is allowed.
*   **Isolation (P0-3)**: Multi-hotel data must never leak between properties.
*   **Localization**: Full support for Persian (FA) UI, RTL layout, and Jalali (Shamsi) dates.
*   **Connectivity**: AI features depend on external GROQ API availability.

## Glossary
*   **Pareto Analysis**: A technique based on the 80/20 rule to identify items with the highest financial impact.
*   **ABC Classification**: Categorizing inventory into A (vital), B (important), and C (trivial) based on value and volume.
*   **WAL Mode**: Write-Ahead Logging; an SQLite configuration allowing concurrent readers and a single writer for production performance.
*   **Signed Quantity**: The quantity multiplied by direction (+1 for buy, -1 for consume), used to rebuild stock totals.
*   **Base Unit**: The normalized unit (e.g., grams to kilograms) used for all internal stock calculations.
