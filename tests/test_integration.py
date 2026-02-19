import asyncio
import os
from datetime import datetime, timedelta, timezone
from typing import AsyncGenerator, Generator
from uuid import uuid4

import asyncpg
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.models.base import Base

_PG_HOST = os.getenv("TEST_PG_HOST", "localhost")
_PG_PORT = int(os.getenv("TEST_PG_PORT", "5433"))
_PG_USER = os.getenv("TEST_PG_USER", "postgres")
_PG_PASS = os.getenv("TEST_PG_PASSWORD", "postgres")
_TEST_DB = "thinkreality_test_db"

_TEST_DB_URL = (
    f"postgresql+asyncpg://{_PG_USER}:{_PG_PASS}@{_PG_HOST}:{_PG_PORT}/{_TEST_DB}"
)

_TEST_ENGINE = create_async_engine(_TEST_DB_URL, echo=False, future=True)

_TestSessionLocal = async_sessionmaker(
    _TEST_ENGINE,
    class_=AsyncSession,
    expire_on_commit=False,
    future=True,
)


async def _override_get_db():
    """Yield a test-scoped async session."""
    async with _TestSessionLocal() as session:
        yield session


@pytest.fixture(scope="session")
def event_loop() -> Generator:
    """Create a single event loop for all async tests in this module."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(scope="session", autouse=True)
async def _ensure_pg_database():
    """Create the test database on docker-compose PostgreSQL if needed.

    Skips every test in this module when PostgreSQL cannot be reached.
    """
    try:
        conn = await asyncpg.connect(
            user=_PG_USER,
            password=_PG_PASS,
            host=_PG_HOST,
            port=_PG_PORT,
            database="postgres",
        )
        exists = await conn.fetchval(
            "SELECT 1 FROM pg_database WHERE datname = $1", _TEST_DB
        )
        if not exists:
            await conn.execute(f'CREATE DATABASE "{_TEST_DB}"')
        await conn.close()
    except (OSError, asyncpg.PostgresError, ConnectionRefusedError) as exc:
        pytest.skip(f"PostgreSQL not available ({_PG_HOST}:{_PG_PORT}): {exc}")


@pytest_asyncio.fixture(autouse=True)
async def _setup_database(_ensure_pg_database):
    """Create all tables before each test and drop them after."""

    async with _TEST_ENGINE.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with _TEST_ENGINE.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """Provide a raw async DB session for direct repository tests."""
    async with _TestSessionLocal() as session:
        yield session


@pytest_asyncio.fixture
async def integration_client() -> AsyncGenerator[AsyncClient, None]:
    """HTTP client wired to the FastAPI app with overridden DB dependency."""
    from app.core.database import get_db
    from app.main import app

    app.dependency_overrides[get_db] = _override_get_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client
    app.dependency_overrides.clear()


async def _seed_agent(session: AsyncSession, **overrides):
    """Insert an agent row and return its UUID."""
    from app.models.agent import Agent

    defaults = {
        "agent_id": uuid4(),
        "full_name": "Test Agent",
        "email": f"agent_{uuid4().hex[:8]}@test.com",
        "phone": f"+9715{uuid4().int % 10**8:08d}",
        "specialization_property_type": ["apartment"],
        "specialization_areas": ["Downtown Dubai"],
        "language_skills": ["english", "arabic"],
        "active_leads_count": 0,
    }
    defaults.update(overrides)
    agent = Agent(**defaults)
    session.add(agent)
    await session.commit()
    return defaults["agent_id"]


async def _seed_lead(session: AsyncSession, **overrides):
    """Insert a lead row and return its UUID."""
    from app.models.lead import Lead

    defaults = {
        "lead_id": uuid4(),
        "source_type": "bayut",
        "first_name": "Test",
        "last_name": "Lead",
        "phone": f"+9715{uuid4().int % 10**8:08d}",
        "nationality": "UAE",
        "language_preference": "english",
        "budget_min": 500000,
        "budget_max": 1500000,
        "property_type": "apartment",
        "preferred_areas": ["Downtown Dubai"],
        "status": "new",
        "score": 50,
    }
    defaults.update(overrides)
    lead = Lead(**defaults)
    session.add(lead)
    await session.commit()
    return defaults["lead_id"]


class TestLeadRepositoryIntegration:
    """Test LeadRepository against a real (in-memory) database."""

    @pytest.mark.asyncio
    async def test_create_and_get_lead(self, db_session: AsyncSession):
        """Round-trip: create a lead via the repo, then read it back."""
        from app.repositories.lead_repository import LeadRepository

        repo = LeadRepository(db_session)
        lead_id = uuid4()

        await repo.create(
            lead_id=lead_id,
            source_type="bayut",
            first_name="Ahmed",
            last_name="Al Mansouri",
            phone="+971501234567",
            nationality="UAE",
            language_preference="english",
            budget_min=800000,
            budget_max=1500000,
            property_type="apartment",
            preferred_areas=["Downtown Dubai", "Marina"],
            status="new",
            score=85,
        )
        await repo.commit()

        fetched = await repo.get_by_id(lead_id)
        assert fetched is not None
        assert fetched.first_name == "Ahmed"
        assert fetched.last_name == "Al Mansouri"
        assert fetched.score == 85
        assert fetched.status == "new"

    @pytest.mark.asyncio
    async def test_update_score(self, db_session: AsyncSession):
        """Verify score update persists correctly."""
        from app.repositories.lead_repository import LeadRepository

        repo = LeadRepository(db_session)
        lead_id = uuid4()

        await repo.create(
            lead_id=lead_id,
            source_type="website",
            first_name="Sara",
            last_name="Khan",
            phone="+971509876543",
            status="new",
            score=40,
        )
        await repo.commit()

        await repo.update_score(lead_id, 75)
        await repo.commit()

        fetched = await repo.get_by_id(lead_id)
        assert fetched.score == 75

    @pytest.mark.asyncio
    async def test_find_duplicate_within_24h(self, db_session: AsyncSession):
        """Duplicate detection should find a lead within the 24h window."""
        from app.repositories.lead_repository import LeadRepository

        repo = LeadRepository(db_session)
        lead_id = uuid4()

        await repo.create(
            lead_id=lead_id,
            source_type="bayut",
            first_name="Dup",
            last_name="Test",
            phone="+971501111111",
            status="new",
            score=50,
        )
        await repo.commit()

        since = datetime.now(timezone.utc) - timedelta(hours=24)
        dup = await repo.find_duplicate("+971501111111", "bayut", since)
        assert dup is not None
        assert dup.lead_id == lead_id


class TestAgentRepositoryIntegration:
    """Test AgentRepository against a real (in-memory) database."""

    @pytest.mark.asyncio
    async def test_create_and_get_agent(self, db_session: AsyncSession):
        from app.repositories.agent_repository import AgentRepository

        repo = AgentRepository(db_session)
        agent_id = await _seed_agent(db_session)

        fetched = await repo.get_by_id(agent_id)
        assert fetched is not None
        assert fetched.full_name == "Test Agent"
        assert fetched.active_leads_count == 0


class TestAssignmentRepositoryIntegration:
    """Test assignment creation and lookup end-to-end."""

    @pytest.mark.asyncio
    async def test_create_assignment(self, db_session: AsyncSession):
        from app.repositories.assignment_repository import AssignmentRepository

        agent_id = await _seed_agent(db_session)
        lead_id = await _seed_lead(db_session)

        repo = AssignmentRepository(db_session)
        await repo.create(
            lead_id=lead_id,
            agent_id=agent_id,
            reason="Integration test",
        )
        await repo.commit()

        fetched = await repo.get_by_lead_id(lead_id)
        assert fetched is not None
        assert fetched.agent_id == agent_id


class TestScoringRuleRepositoryIntegration:
    """Verify scoring rules can be created and read from the DB."""

    @pytest.mark.asyncio
    async def test_read_scoring_rules(self, db_session: AsyncSession):
        from app.models.scoring_rule import LeadScoringRule
        from app.repositories.scoring_rule_repository import ScoringRuleRepository

        # Seed a rule
        rule = LeadScoringRule(
            rule_id=uuid4(),
            rule_name="High budget bonus",
            score_adjustment=20,
            condition={"type": "budget_min", "threshold": 10000000},
        )
        db_session.add(rule)
        await db_session.commit()

        repo = ScoringRuleRepository(db_session)
        rules = await repo.get_active_rules()
        assert len(rules) >= 1
        assert rules[0].rule_name == "High budget bonus"


class TestScoringEngineWithDBRules:
    """Verify LeadScoringEngine reads rules from the DB when available."""

    @pytest.mark.asyncio
    async def test_score_from_db_rules(self, db_session: AsyncSession):
        from app.models.scoring_rule import LeadScoringRule
        from app.repositories.scoring_rule_repository import ScoringRuleRepository
        from app.services.lead_scoring import LeadScoringEngine

        # Seed rules
        rules_data = [
            {
                "rule_name": "Budget > 10M",
                "score_adjustment": 20,
                "condition": {"type": "budget_min", "threshold": 10000000},
            },
            {
                "rule_name": "Budget > 5M",
                "score_adjustment": 15,
                "condition": {"type": "budget_min", "threshold": 5000000},
            },
            {
                "rule_name": "Source Bayut",
                "score_adjustment": 90,
                "condition": {"type": "source", "value": "bayut"},
            },
            {
                "rule_name": "UAE National",
                "score_adjustment": 10,
                "condition": {"type": "nationality", "values": ["uae", "emirati"]},
            },
        ]
        for rd in rules_data:
            rule = LeadScoringRule(rule_id=uuid4(), **rd)
            db_session.add(rule)
        await db_session.commit()

        repo = ScoringRuleRepository(db_session)
        engine = LeadScoringEngine(scoring_rule_repo=repo)

        score = await engine.calculate_lead_score(
            lead_data={
                "budget_max": 12000000,
                "nationality": "UAE",
                "property_type": "villa",
            },
            source_details={"source_type": "bayut"},
        )

        # 20 (budget>10M, first tier) + 90 (bayut) + 10 (UAE) = 120 → clamped to 100
        assert score == 100

    @pytest.mark.asyncio
    async def test_fallback_to_defaults_when_no_rules(self, db_session: AsyncSession):
        """Engine falls back to hardcoded defaults if no DB rules exist."""
        from app.repositories.scoring_rule_repository import ScoringRuleRepository
        from app.services.lead_scoring import LeadScoringEngine

        repo = ScoringRuleRepository(db_session)
        engine = LeadScoringEngine(scoring_rule_repo=repo)

        score = await engine.calculate_lead_score(
            lead_data={
                "budget_max": 1500000,
                "nationality": "UAE",
                "property_type": "apartment",
                "preferred_areas": ["Marina"],
            },
            source_details={"source_type": "bayut"},
        )

        # 5 (budget<2M) + 90 (bayut) + 10 (UAE) + 5 (prop type) + 5 (areas) = 115 → clamped 100
        assert score == 100


class TestHealthEndpointIntegration:
    """Smoke test: verify the health endpoint responds through the full stack."""

    @pytest.mark.asyncio
    async def test_health_returns_200(self, integration_client: AsyncClient):
        resp = await integration_client.get("/api/v1/health")
        assert resp.status_code == 200
