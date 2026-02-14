# ThinkRealty Lead Management System

This project is a backend implementation of a lead management system for ThinkRealty, a Dubai-based platform. It is designed to handle intelligent lead capture, automated scoring, agent assignment, and comprehensive analytics for the UAE real estate market.

## Features

- Intelligent lead scoring with business rule enforcement
- Emirates ID and UAE-specific validations
- Historical activity tracking (audit-safe)
- Redis caching for performance
- Smart agent assignment and workload balancing
- FastAPI-based RESTful APIs
- PostgreSQL database with Alembic migrations
- Dockerized for easy local setup

## Tech Stack

- Backend: FastAPI (Python)
- Database: PostgreSQL
- Cache: Redis
- ORM: SQLAlchemy + Alembic
- Containerization: Docker + Docker Compose

## Setup Instructions

### 1. Clone the Repository

```bash
git clone <repository-url>
cd thinkreality
```

### 2. Create .env File

```bash
# .env
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/thinkreality_db
DEBUG=true
LOG_LEVEL=INFO
```

### 3. Start the Application

```bash
docker-compose up -d
```

FastAPI runs on: http://localhost:8000
Swagger docs: http://localhost:8000/docs

## Migrations (Using Alembic)

To generate a new migration:

```bash
docker-compose exec app alembic revision --autogenerate -m "Your message"
```

To apply migrations:

```bash
docker-compose exec app alembic upgrade head
```

## API Endpoints

### Leads

POST /api/v1/leads/capture - Handles lead capture with scoring and assignment.

PUT /api/v1/leads/{lead_id} - Updates lead status and information.

### Agents

GET /api/v1/agents/dashboard - Returns agent dashboard with performance metrics.

## Database Tables

- leads – Lead information and statuses
- agents – Agent profiles and specializations
- assignments – Lead-agent pairings
- activities – Activity logs
- lead_sources – Lead sources
- conversion_history – Conversion records
- performance_metrics – Agent metrics
- property_interests – Property preferences
- scoring_rules – Scoring criteria
- tasks – Follow-up tasks

## Documentation

Once running, visit:
📚 http://localhost:8000/docs (Swagger UI)

## Project Structure

```
app/
├── routers/              # FastAPI routers
├── models/               # SQLAlchemy models
├── schemas/              # Pydantic schemas
├── services/             # Business logic
├── scripts/              # Seed and utility scripts
├── config.py             # Configuration
├── database.py           # DB setup
├── main.py               # FastAPI entrypoint
├── dependencies.py       # Dependencies
├── exceptions.py         # Custom exceptions
alembic/                  # Migrations
documentation/            # Docs
```

## Notes

- All lead transitions maintain historical traceability.
- All validations follow UAE real estate standards.
- Redis is optional but boosts performance for read-heavy endpoints.

## Author

Mehwash Shahzadi – Software Engineer
GitHub: @Mehwash-Shahzadi

## Assessment Coverage

- Task 1 – Database schema + migrations + validations
- Task 2 – API endpoints with business logic
- Task 3 – Lead scoring and agent assignment
- Task 4 – Analytics and dashboard queries
