# ThinkRealty Lead Management System

A production-ready backend for ThinkRealty, a Dubai-based real estate platform. It handles lead capture from multiple UAE property portals, scores each lead automatically, assigns it to the best-fit agent, and gives you 13 analytics endpoints to understand what's working.

## What It Does

- **Captures leads from 6 sources** — Bayut, PropertyFinder, Dubizzle, website, walk-ins, and referrals
- **Scores leads automatically** — Uses budget size, source quality, nationality (UAE/GCC bonuses), property type, preferred areas, and how fast the agent responds to first contact
- **Assigns leads to the right agent** — Matches by property specialization, area, language, and conversion history. Uses round-robin so no one agent gets all the leads when scores are tied
- **Catches duplicates early** — Same phone + same source within 24 hours? Rejected instantly via Redis, with a DB fallback if Redis is down
- **Enforces a status workflow** — new → contacted → qualified → viewing_scheduled → negotiation → converted/lost. Invalid transitions are blocked
- **Penalizes inactivity** — If nobody touches a lead for 7+ days, the score drops by 10 points
- **Auto-reassigns stale leads** — A background task runs every hour and reassigns any lead that's been sitting for 24+ hours with no activity
- **Validates budgets at the schema level** — budget_min must be less than budget_max, with a 500M AED ceiling, enforced by Pydantic before the request even hits the service layer
- **Agent dashboard** — Shows active leads, overdue tasks, conversion metrics, and performance rankings (cached in Redis for 5 minutes)
- **13 analytics endpoints** — Conversion rates, revenue attribution, workload distribution, follow-up timing, and more. All paginated with accurate total counts
- **Graceful degradation** — If Redis goes down, the system keeps working using database-only paths

## Tech Stack

| Layer            | Technology                              |
| ---------------- | --------------------------------------- |
| Framework        | FastAPI (Python 3.11)                   |
| Database         | PostgreSQL 15                           |
| Cache            | Redis 7                                 |
| ORM              | SQLAlchemy (async) + Alembic migrations |
| Validation       | Pydantic v2                             |
| Containerization | Docker + Docker Compose                 |

## Quick Start

```bash
git clone <repository-url>
cd thinkreality

# Start all services (PostgreSQL, Redis, FastAPI)
docker-compose up -d --build
```

That's it. The `entrypoint.sh` script automatically runs Alembic migrations and seeds sample data (120 leads, 10 agents, 70 activities, 60 property interests, 60 tasks, 40 conversion records) on startup.

If you need to re-run migrations or seeding manually:

```bash
docker-compose exec app alembic upgrade head
docker-compose exec app python -m app.scripts.seed
```

- **API**: http://localhost:8000
- **Swagger docs**: http://localhost:8000/docs
- **Health check**: http://localhost:8000/api/v1/health

> **Note:** PostgreSQL is exposed on port **5433** on the host (mapped to 5432 inside the container) to avoid conflicts with any local PostgreSQL instance.

## API Endpoints

### Core Endpoints (Task 2)

| Method | Path                                  | Description                                               |
| ------ | ------------------------------------- | --------------------------------------------------------- |
| `POST` | `/api/v1/leads/capture`               | Capture a new lead with auto-scoring and agent assignment |
| `PUT`  | `/api/v1/leads/{lead_id}/update`      | Update lead status, log activity, manage follow-ups       |
| `GET`  | `/api/v1/agents/{agent_id}/dashboard` | Agent dashboard with metrics, leads, and pending tasks    |
| `GET`  | `/api/v1/health`                      | Health check                                              |

### Analytics Endpoints (Task 4)

| Method | Path                                          | Description                                 |
| ------ | --------------------------------------------- | ------------------------------------------- |
| `GET`  | `/api/v1/analytics/conversion-rates`          | Conversion rates by source and agent        |
| `GET`  | `/api/v1/analytics/avg-conversion-time`       | Average time to conversion by property type |
| `GET`  | `/api/v1/analytics/monthly-trends`            | Monthly lead volume trends                  |
| `GET`  | `/api/v1/analytics/agent-rankings`            | Agent performance rankings                  |
| `GET`  | `/api/v1/analytics/revenue-attribution`       | Revenue attribution by lead source          |
| `GET`  | `/api/v1/analytics/high-score-not-converted`  | High-scoring leads that didn't convert      |
| `GET`  | `/api/v1/analytics/low-score-converted`       | Low-scoring leads that converted            |
| `GET`  | `/api/v1/analytics/source-quality`            | Source quality comparison over time         |
| `GET`  | `/api/v1/analytics/follow-up-timing`          | Optimal follow-up timing analysis           |
| `GET`  | `/api/v1/analytics/workload-distribution`     | Current agent workload distribution         |
| `GET`  | `/api/v1/analytics/approaching-capacity`      | Agents approaching max capacity             |
| `GET`  | `/api/v1/analytics/specialized-vs-general`    | Specialized vs general agent performance    |
| `GET`  | `/api/v1/analytics/response-time-correlation` | Response time correlation with conversion   |

## Database Tables

| Table                       | Purpose                                            |
| --------------------------- | -------------------------------------------------- |
| `leads`                     | Lead information, status, score, contact details   |
| `agents`                    | Agent profiles, specializations, language skills   |
| `lead_assignments`          | Lead-to-agent 1:1 assignment tracking              |
| `lead_activities`           | Timestamped activity log (calls, emails, viewings) |
| `follow_up_tasks`           | Scheduled follow-ups with priority and status      |
| `lead_property_interests`   | Property preferences per lead                      |
| `lead_sources`              | Source attribution and campaign tracking           |
| `lead_conversion_history`   | Status transition history with deal values         |
| `agent_performance_metrics` | Agent conversion rate, deal size, response time    |
| `lead_scoring_rules`        | Configurable scoring rule definitions              |

## Project Structure

```
thinkreality/
├── alembic.ini
├── docker-compose.yml
├── Dockerfile
├── requirements.txt
├── README.md
│
├── alembic/                              # Database migrations (13 revisions)
│   ├── env.py
│   ├── script.py.mako
│   └── versions/                         # See Database_Schema_Documentation.md for full list
│
├── app/
│   ├── __init__.py
│   ├── main.py                           # FastAPI entrypoint & exception handlers
│   ├── dependencies.py                   # Validators & DI factory functions
│   │
│   ├── core/                             # Core infrastructure
│   │   ├── config.py                     # Settings (DB, Redis, business rules)
│   │   ├── database.py                   # Async SQLAlchemy engine & session
│   │   ├── exceptions.py                 # Custom domain exceptions
│   │   ├── constants.py                  # Business rule constants (derived from SourceType enum)
│   │   ├── default_scoring_rules.py      # Canonical scoring rules seeded into DB
│   │   ├── rate_limit.py                 # Slowapi rate limiter setup
│   │   └── cache.py                      # Redis CacheService (get/set/delete/incr with graceful degradation)
│   │
│   ├── api/                              # API layer
│   │   ├── __init__.py
│   │   ├── deps.py                       # API dependency re-exports
│   │   └── v1/
│   │       ├── __init__.py
│   │       ├── router.py                 # V1 router aggregator
│   │       └── endpoints/
│   │           ├── leads.py              # Lead capture & update endpoints
│   │           ├── agents.py             # Agent dashboard endpoint
│   │           ├── analytics.py          # 13 analytics endpoints (Task 4)
│   │           └── health.py             # Health check endpoint
│   │
│   ├── models/                           # SQLAlchemy ORM models
│   │   ├── base.py                       # Declarative base
│   │   ├── lead.py                       # Lead model
│   │   ├── agent.py                      # Agent model
│   │   ├── assignment.py                 # Lead-Agent assignment
│   │   ├── activity.py                   # Lead activity log
│   │   ├── conversion_history.py         # Status transition & deal history
│   │   ├── lead_source.py                # Lead source tracking
│   │   ├── listeners.py                  # SQLAlchemy event listeners
│   │   ├── performance_metric.py         # Agent performance metrics
│   │   ├── property_interest.py          # Lead property preferences
│   │   ├── scoring_rule.py               # Scoring rule definitions
│   │   └── task.py                       # Follow-up tasks
│   │
│   ├── repositories/                     # Data access layer (all DB queries)
│   │   ├── base.py                       # BaseRepository with session management
│   │   ├── lead_repository.py            # Lead CRUD + duplicate detection
│   │   ├── agent_repository.py           # Agent queries + capacity checks
│   │   ├── assignment_repository.py      # Assignment CRUD + reassignment
│   │   ├── task_repository.py            # Follow-up task management
│   │   ├── activity_repository.py        # Activity logging + inactivity check
│   │   ├── lead_source_repository.py     # Source record creation
│   │   ├── property_interest_repository.py # Property interest tracking + suggestions
│   │   ├── conversion_history_repository.py # Conversion records
│   │   ├── scoring_rule_repository.py    # Scoring rule queries + seeding
│   │   ├── dashboard_repository.py       # Dashboard aggregate queries
│   │   └── analytics_repository.py       # 13 raw SQL analytics queries
│   │
│   ├── schemas/                          # Pydantic request/response schemas
│   │   ├── common.py                     # Shared enums (SourceType, LeadStatus, etc.)
│   │   ├── lead.py                       # Lead capture/update request & response
│   │   ├── agent.py                      # Agent dashboard response schemas
│   │   ├── lead_activity.py              # Activity & property interest updates
│   │   ├── follow_up.py                  # Pending task schema
│   │   └── analytics.py                  # Filter enums (DateRange, StatusFilter)
│   │
│   ├── services/                         # Business logic (no direct DB access)
│   │   ├── lead_capture_service.py       # Lead capture pipeline
│   │   ├── lead_update_service.py        # Lead update orchestration
│   │   ├── lead_scoring.py               # DB-driven scoring + response-time bonus
│   │   ├── lead_assignment.py            # Agent assignment with round-robin
│   │   ├── agent_dashboard_service.py    # Dashboard service with Redis caching
│   │   ├── property_suggestion_service.py # Property suggestions + availability check
│   │   ├── auto_reassign.py              # Background task: reassign stale leads
│   │   └── analytics.py                  # Analytics service with accurate totals
│   │
│   └── scripts/
│       └── seed.py                       # Database seeding (120 leads, 10 agents)
│
└── documentation/
    ├── API_Documentation.md
    ├── Business_Rules_Explanation.md
    ├── Database_Schema_Documentation.md
    └── Setup_Running_Instructions.md
```

## How It's Built

The project uses a **layered architecture** — each layer only talks to the one below it:

```
API endpoints → Services → Repositories → Models
```

- **API endpoints** handle HTTP concerns (status codes, request parsing, response serialization). They don't contain business logic.
- **Services** contain all the business rules — scoring, assignment, duplicate detection, status transitions. They never touch the database directly.
- **Repositories** hold all the SQL. One repository per table. The analytics repository uses raw SQL for the 13 complex queries.
- **Models** define the SQLAlchemy ORM tables. Event listeners handle things like auto-updating timestamps and refreshing workload counters.
- **Core** ties everything together — configuration, database engine, custom exceptions, and the single-source-of-truth constants derived from the `SourceType` enum.

## Running Tests

```bash
# Run all tests
python -m pytest tests/ -q

# Run a specific test file
python -m pytest tests/test_lead_scoring.py -q
```

There are 13 test files covering scoring, assignment, duplicate detection, schema validation, error handling, status transitions, constants consistency, analytics, property suggestions, auto-reassignment, and API endpoint integration.

## Assessment Coverage

| Task   | Area                                                  | Status |
| ------ | ----------------------------------------------------- | ------ |
| Task 1 | Database schema, constraints, migrations, sample data | ✅     |
| Task 2 | Core API endpoints (capture, dashboard, update)       | ✅     |
| Task 3 | Lead scoring engine & agent assignment manager        | ✅     |
| Task 4 | 13 advanced analytics queries with API endpoints      | ✅     |
| Task 5 | Error handling & edge cases (6 error types)           | ✅     |

## Author

Mehwash Shahzadi — Software Engineer
GitHub: @Mehwash-Shahzadi
