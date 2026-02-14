# ThinkRealty Project Setup & Run Guide

## Prerequisites

Before setting up the ThinkRealty Lead Management System, ensure your development environment has Docker and Docker Compose installed. The system is designed to run entirely in containers, eliminating the need for local Python or PostgreSQL installations. VS Code is recommended for development work, though any text editor will suffice for basic operations.

## Clone Repository

Begin by cloning the project repository to your local machine and navigating to the project directory. The repository contains all necessary configuration files, database migrations, and application code required for a complete deployment.

```bash
git clone <repository-url>
cd thinkreality
```

## Environment Configuration

Create a `.env` file in the root directory to customize database settings and application configuration. The system provides sensible defaults, so this step is optional for development purposes.

```env
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/thinkreality_db
DEBUG=true
LOG_LEVEL=INFO
REDIS_URL=redis://localhost:6379/0
```

## Start Services

Launch all required services using Docker Compose, which will start PostgreSQL database, Redis cache, and the FastAPI application in coordinated containers.

```bash
docker-compose up -d
```

This command starts three services: PostgreSQL database on port 5432, Redis cache on port 6379, and the FastAPI application on port 8000. All services run in the background and are configured to restart automatically if they encounter issues.

## Database Initialization

Apply database migrations to create all necessary tables and constraints, then populate the system with sample data for testing and development purposes.

```bash
docker-compose exec app alembic upgrade head
docker-compose exec app python -m app.scripts.seed
```

The migration process creates the complete database schema with all business rules enforced through constraints and triggers. The seed script adds sample agents, leads, and activities to provide immediate testing data.

## Verification

Confirm all services are running correctly and the system is ready for use by checking service status and accessing the API documentation.

```bash
docker-compose ps
```

You should see three healthy services: `thinkreality_db` (PostgreSQL), `thinkreality_redis` (Redis), and `thinkreality_app` (FastAPI) all showing as running or healthy status.

## Access Application

The ThinkRealty system provides comprehensive API documentation and testing interfaces through Swagger UI. Open your web browser and navigate to `http://localhost:8000/docs` to access the interactive API documentation where you can test all endpoints directly. The health check endpoint at `http://localhost:8000/health` provides system status verification.

## Stop System

When finished with development or testing, stop all services and optionally remove associated volumes to completely reset the system state.

```bash
# Stop services only
docker-compose down

# Stop services and remove data volumes (complete reset)
docker-compose down -v
```

The first command preserves all data for future sessions, while the second command completely resets the system by removing database contents and cached data. Use the volume removal option when you need a fresh start for testing purposes.
