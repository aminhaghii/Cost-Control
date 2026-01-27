# 02-architecture.md

## High-Level Architecture
The Pareto system follows a layered monolithic architecture with a clear separation of concerns, optimized for deployment in containerized environments.

### Component Diagram
```mermaid
graph TD
    User((User)) -->|HTTPS| Flask[Flask Web App]
    
    subgraph "Application Layer"
        Flask --> Blueprints[Routes/Blueprints]
        Blueprints --> Auth[Auth/Security]
        Blueprints --> Trans[Transactions]
        Blueprints --> AI[AI Analysis]
    end
    
    subgraph "Service Layer (Logic)"
        Blueprints --> ServiceLayer[Services]
        ServiceLayer --> ParetoSvc[Pareto Service]
        ServiceLayer --> StockSvc[Stock Service]
        ServiceLayer --> ChatSvc[Chat Service]
        ServiceLayer --> ScopeSvc[Hotel Scope Service]
    end
    
    subgraph "Data Layer"
        ServiceLayer --> SQLAlchemy[SQLAlchemy ORM]
        SQLAlchemy --> SQLite[(SQLite WAL)]
    end
    
    subgraph "External Integrations"
        ChatSvc --> GroqAPI[GROQ LLM API]
    end
```

### Sequence Diagram: Transaction Creation (Critical Workflow)
```mermaid
sequenceDiagram
    participant U as User
    participant R as Transaction Route
    participant S as Stock Service
    participant M as Transaction Model
    participant D as SQLite (WAL)

    U->>R: POST /transactions/create
    R->>R: Validate CSRF & Session
    R->>M: create_transaction(item_id, qty, price)
    M->>M: Calculate signed_quantity (qty * direction)
    M-->>R: Transaction Object
    R->>S: update_current_stock(item_id, delta)
    S->>D: DB.Commit (Transaction + Item Cache)
    D-->>S: Success
    S-->>R: Success
    R-->>U: 200 OK / Redirect
```

## Dependency List
### Core Internal Modules
*   `services/hotel_scope_service.py`: Centralized permission enforcement.
*   `models/transaction.py`: Core logic for stock integrity.
*   `services/chat_service.py`: Orchestrates AI context retrieval.

### Major External Libraries
*   **Flask (3.0.0)**: Web framework.
*   **SQLAlchemy (2.0.23)**: ORM for persistence.
*   **Pandas (2.1.4)**: Data processing for Pareto/ABC.
*   **OpenAI (GROQ)**: AI analysis capabilities.
*   **Jdatetime (4.1.1)**: Jalali calendar support.

## Architectural Risks
| Risk | Severity | Description |
| :--- | :--- | :--- |
| **SQLite Concurrency** | Medium | While WAL mode helps, heavy concurrent write loads from multiple hotels could hit lock contention. |
| **AI API Latency** | Low | GROQ API outages or latency would degrade the chatbot and analysis features. |
| **Soft Delete Exposure** | Medium | Many queries rely on `filter(is_deleted != True)`. If a developer forgets this in a new report, deleted data could leak. |
| **Unit Normalization** | Medium | Conversion factors rely on hardcoded mappings in `item.py`. Incorrect factors lead to invalid stock levels. |
