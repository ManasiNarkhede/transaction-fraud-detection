# Backend — Real-Time Transaction Fraud Detection Guard

FastAPI backend for the Real-Time Transaction Fraud Detection Guard project.

## Setup

### Prerequisites

- Python 3.11+
- Poetry

### Installation

```bash
cd backend
poetry lock
poetry install --with dev
```

### Environment

Copy `.env` and adjust values as needed:

```bash
cp .env .env.local
```

## Project Structure

```
backend/
├── app/
│   ├── main.py              # FastAPI app factory with lifespan events
│   ├── config.py            # Pydantic Settings class
│   ├── dependencies.py      # DI container (get_db, get_redis)
│   ├── core/
│   │   ├── exceptions.py    # FraudDetectionError hierarchy
│   │   ├── logging_config.py# JSON structured logging
│   │   └── security.py      # Security placeholders
│   ├── infrastructure/
│   │   ├── database.py      # Async SQLAlchemy engine
│   │   └── redis_client.py  # Async Redis client
│   ├── models/              # Pydantic schemas (future phases)
│   ├── routers/
│   │   ├── health.py        # /health endpoint
│   │   ├── auth.py          # authentication endpoints
│   │   ├── rules.py         # fraud rule management
│   │   ├── decisions.py     # decision records
│   │   ├── audit.py         # audit log access
│   │   └── verification.py  # verification workflow
│   └── services/            # Business logic
├── tests/
│   ├── conftest.py          # Pytest fixtures
│   └── integration/
│       └── test_health.py   # Health endpoint test
└── pyproject.toml           # Poetry config + tool settings
```

## Common Commands

```bash
# Run development server
poetry run uvicorn app.main:app --reload

# Run tests
poetry run pytest

# Run linting
poetry run ruff check .
poetry run ruff format .

# Run type checking
poetry run mypy app/

# Run formatting
poetry run black .
```

## Health Endpoint

```bash
curl http://localhost:8000/api/v1/health
```

Returns:

```json
{
  "status": "healthy",
  "service": "fraud-api",
  "version": "0.1.0",
  "checks": {
    "database": "connected",
    "redis": "connected"
  }
}
```
