# ThinkRealty Lead Management System

A comprehensive lead management backend system designed specifically for the UAE real estate market. The system provides intelligent lead capture with automated scoring and agent assignment, built using FastAPI, PostgreSQL, Docker, and Redis technologies.

## Technology Stack

The application leverages modern, production-ready technologies to ensure scalability and reliability:

- **Backend Framework**: FastAPI with Python for high-performance API development
- **Database**: PostgreSQL with async SQLAlchemy for robust data persistence
- **Caching**: Redis for session management and performance optimization
- **Containerization**: Docker and Docker Compose for consistent deployment
- **Migration Management**: Alembic for database schema versioning
- **API Documentation**: Automatic OpenAPI/Swagger generation

## Key Features

The ThinkRealty system delivers essential functionality for real estate lead management operations:

**Lead Capture with Intelligent Scoring**: Automatically evaluates incoming leads using sophisticated algorithms that consider budget ranges, source quality, client nationality, and property preferences to generate quality scores from 0 to 100.

**Smart Agent Assignment**: Matches leads to the most suitable agents based on property type specialization, geographic area expertise, and language skills while maintaining balanced workloads across the team.

**Comprehensive Agent Dashboard**: Provides real-time insights into agent performance including active lead counts, conversion metrics, overdue follow-ups, and response time analytics with customizable filtering options.

**Lead Update and Activity Tracking**: Enables status progression management, activity logging, and property interest recording while enforcing business rules and maintaining data integrity.

**Advanced Analytics Queries**: Supports complex reporting requirements with SQL-based insights into lead sources, conversion patterns, agent performance, and market trends.

## Setup and Running Instructions

### Prerequisites

Ensure your development environment has Docker and Docker Compose installed. No local Python or PostgreSQL installation is required as all services run in containers.

### Installation Steps

Clone the repository and navigate to the project directory:

```bash
git clone <repository-url>
cd thinkreality
```

Create an optional environment configuration file for custom settings:

```bash
# Create .env file (optional, defaults provided)
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/thinkreality_db
DEBUG=true
LOG_LEVEL=INFO
```

Start all services using Docker Compose:

```bash
docker-compose up -d
```

Initialize the database with schema and sample data:

```bash
docker-compose exec app alembic upgrade head
docker-compose exec app python -m app.scripts.seed
```

Verify all services are running correctly:

```bash
docker-compose ps
```

Access the interactive API documentation at `http://localhost:8000/docs` to explore and test all available endpoints.

## Testing the API

The system provides comprehensive API documentation through Swagger UI, accessible at `http://localhost:8000/docs`. For programmatic testing, use the lead capture endpoint as a starting point:

```bash
curl -X POST "http://localhost:8000/api/v1/leads/capture" \
  -H "Content-Type: application/json" \
  -d '{
    "source_type": "website",
    "lead_data": {
      "first_name": "Ahmed",
      "last_name": "Al Mansouri",
      "phone": "+971501234567",
      "nationality": "UAE",
      "language_preference": "arabic",
      "budget_max": 1500000,
      "property_type": "apartment"
    },
    "source_details": {}
  }'
```

The system will automatically score the lead, assign it to the best available agent, and return comprehensive response data including lead ID and agent assignment details.

## Business Rules Implementation

The ThinkRealty system enforces several critical business rules to maintain data quality and operational efficiency:

**Duplicate Detection**: Prevents duplicate lead entries by monitoring phone number and source type combinations within 24-hour windows, ensuring data integrity and avoiding agent confusion.

**Agent Workload Management**: Limits each agent to a maximum of 50 active leads to maintain service quality and prevent agent burnout, with automatic capacity validation during assignment processes.

**Status Flow Control**: Enforces logical lead progression through predefined stages from initial contact to conversion, preventing invalid status transitions and ensuring proper sales process adherence.

**Follow-up Compliance**: Blocks new lead assignments for agents with overdue follow-up tasks, ensuring existing clients receive proper attention before new prospects are assigned.

## UAE Market Specialization

The system includes specialized features designed for the UAE real estate market:

**Arabic Language Support**: Native support for Arabic language preferences in client communications and agent matching, ensuring culturally appropriate service delivery.

**UAE-Specific Lead Scoring**: Enhanced scoring algorithms that recognize UAE nationals and GCC citizens with premium weighting, reflecting their significance in the local market dynamics.

**AED Budget Integration**: All financial calculations and budget ranges are configured for UAE Dirham currency with appropriate validation ranges for local property values.

**Local Source Integration**: Purpose-built connectors for major UAE property platforms including Bayut, PropertyFinder, and Dubizzle with source-specific quality scoring.
