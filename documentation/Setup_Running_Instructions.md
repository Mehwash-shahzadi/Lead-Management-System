# ThinkRealty — Setup & Running Guide

## Prerequisites

| Requirement    | Minimum Version |
| -------------- | --------------- |
| Docker         | 20+             |
| Docker Compose | v2+             |

You don't need Python, PostgreSQL, or Redis installed locally — everything runs inside Docker containers.

---

## 1. Clone Repository

```bash
git clone <repository-url>
cd thinkrealty
```

---

## 2. Environment Configuration (Optional)

Create a `.env` file in the project root to override defaults. **All values have sensible defaults in `docker-compose.yml`**, so this step is optional for local development.

```env
DATABASE_URL=postgresql+asyncpg://postgres:postgres@postgres:5432/thinkrealty_db
REDIS_URL=redis://redis:6379/0
DEBUG=true
LOG_LEVEL=INFO
```

> **Note:** When running outside Docker (local development), replace `postgres` and `redis` hostnames with `localhost`.

---

## 3. Start Services

```bash
docker-compose up -d --build
```

This starts three services:

| Service    | Image              | Port | Purpose                       |
| ---------- | ------------------ | ---- | ----------------------------- |
| `postgres` | postgres:15-alpine | 5433 | PostgreSQL database           |
| `redis`    | redis:7-alpine     | 6379 | Cache and duplicate detection |
| `app`      | python:3.11-slim   | 8000 | FastAPI application           |

The `app` service depends on `postgres` and `redis` — Docker Compose waits for them to pass health checks before starting the app. All services are configured with `restart: always`.

> **Note:** PostgreSQL is exposed on host port **5433** (not 5432) to avoid conflicts with any locally installed PostgreSQL instance. Inside the Docker network, it still listens on the standard port 5432.

---

## 4. Database Initialization

On Docker startup, `entrypoint.sh` automatically runs Alembic migrations and seeds sample data — no manual steps required. To re-run manually:

```bash
docker-compose exec app alembic upgrade head
docker-compose exec app python -m app.scripts.seed
```

**Migrations** create all 10 tables with constraints, indexes, triggers, and foreign keys.

**Seed data** (`app/scripts/seed.py`) populates: 10 agents, 120 leads, 120 assignments, 70 activities, 60 tasks, 60 property interests, 120 lead sources, 40 conversion history records, and 22 scoring rules. The script is idempotent — it truncates existing data before re-seeding.

---

## 5. Verify Services

```bash
docker-compose ps
```

Health check endpoint:

```bash
curl http://localhost:8000/api/v1/health
# {"status": "ok"}
```

---

## 6. Access the Application

| URL                                   | Description                       |
| ------------------------------------- | --------------------------------- |
| `http://localhost:8000/docs`          | Swagger UI — interactive API docs |
| `http://localhost:8000/redoc`         | ReDoc — alternative API docs      |
| `http://localhost:8000/api/v1/health` | Health check                      |

---

## 7. Local Development (Without Docker)

```bash
# Create virtual environment
python -m venv venv
venv\Scripts\activate        # Windows
# source venv/bin/activate   # macOS/Linux

# Install dependencies
pip install -r requirements.txt

# Set environment variables
set DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/thinkrealty_db
set REDIS_URL=redis://localhost:6379/0

# Run migrations and seed
alembic upgrade head
python -m app.scripts.seed

# Start the server
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

**Requirements:** Python 3.11+, PostgreSQL 15+ on localhost:5432, Redis 7+ on localhost:6379.

---

## 8. Running Tests

```bash
# Run all tests
python -m pytest tests/ -q

# Run a specific test file
python -m pytest tests/test_lead_scoring.py -v
```

Test files cover lead scoring, agent assignment, duplicate detection, schema validation, error handling, status transitions, constants consistency, analytics endpoints, property suggestion service, auto-reassignment, and API endpoint integration.

---

## 9. Stop Services

```bash
# Stop services (preserves data)
docker-compose down

# Stop services and remove all data volumes (full reset)
docker-compose down -v
```

---

## Project Structure

```
thinkrealty/
├── app/
│   ├── api/v1/endpoints/    # Route handlers (leads, agents, analytics, health)
│   ├── core/                # Config, database, exceptions, constants, CacheService, rate limiting, scoring rules
│   ├── models/              # SQLAlchemy ORM models (10 tables)
│   ├── repositories/        # Data access layer (11 repositories + base)
│   ├── schemas/             # Pydantic request/response models (with budget cross-field validation)
│   ├── scripts/             # Database seeder
│   └── services/            # Business logic (scoring, assignment, auto-reassignment, analytics, property suggestions)
├── alembic/versions/        # Database migrations (13 revisions)
├── tests/                   # Test suite
├── documentation/           # Project documentation
├── docker-compose.yml       # Container orchestration
├── Dockerfile               # App container definition
└── requirements.txt         # Python dependencies
```
