import asyncio
import os
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import AsyncGenerator, Generator
from uuid import uuid4

import asyncpg
import pytest
import pytest_asyncio
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
_TEST_DB = "thinkrealty_analytics_test_db"

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


@pytest.fixture(scope="session")
def event_loop() -> Generator:
    """Create a single event loop for all async tests in this module."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(scope="session", autouse=True)
async def _ensure_pg_database():
    """Create the test database on docker-compose PostgreSQL if needed."""
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
    """Provide a raw async DB session for repository tests."""
    async with _TestSessionLocal() as session:
        yield session


async def _seed_agent(session: AsyncSession, **overrides):
    """Insert an agent and return its UUID."""
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
    await session.flush()
    return defaults["agent_id"]


async def _seed_lead(session: AsyncSession, **overrides):
    """Insert a lead and return its UUID."""
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
    await session.flush()
    return defaults["lead_id"]


async def _seed_assignment(session: AsyncSession, lead_id, agent_id, **overrides):
    """Insert a lead assignment."""
    from app.models.assignment import LeadAssignment

    defaults = {
        "assignment_id": uuid4(),
        "lead_id": lead_id,
        "agent_id": agent_id,
        "reason": "test assignment",
    }
    defaults.update(overrides)
    assignment = LeadAssignment(**defaults)
    session.add(assignment)
    await session.flush()


async def _seed_activity(session: AsyncSession, lead_id, agent_id, **overrides):
    """Insert a lead activity."""
    from app.models.activity import LeadActivity

    defaults = {
        "activity_id": uuid4(),
        "lead_id": lead_id,
        "agent_id": agent_id,
        "type": "call",
        "outcome": "positive",
        "activity_at": datetime.now(timezone.utc),
    }
    defaults.update(overrides)
    activity = LeadActivity(**defaults)
    session.add(activity)
    await session.flush()


async def _seed_conversion_history(session: AsyncSession, lead_id, **overrides):
    """Insert a conversion history record."""
    from app.models.conversion_history import LeadConversionHistory

    defaults = {
        "history_id": uuid4(),
        "lead_id": lead_id,
        "status_from": "negotiation",
        "status_to": "converted",
        "changed_at": datetime.now(timezone.utc),
        "deal_value": Decimal("1500000.00"),
        "conversion_type": "sale",
    }
    defaults.update(overrides)
    history = LeadConversionHistory(**defaults)
    session.add(history)
    await session.flush()


class TestConversionRates:
    """Verify conversion rate aggregation by source and agent."""

    @pytest.mark.asyncio
    async def test_conversion_rates_basic(self, db_session: AsyncSession):
        """Two agents, multiple leads — verify rates are computed correctly."""
        from app.repositories.analytics_repository import AnalyticsRepository

        # Seed agents
        agent1_id = await _seed_agent(
            db_session,
            full_name="Agent Alpha",
            active_leads_count=5,
        )
        agent2_id = await _seed_agent(
            db_session,
            full_name="Agent Beta",
            active_leads_count=3,
        )

        # Seed leads: 3 from bayut (2 converted, 1 new), 2 from website (1 converted)
        lead1 = await _seed_lead(db_session, source_type="bayut", status="converted")
        lead2 = await _seed_lead(db_session, source_type="bayut", status="converted")
        lead3 = await _seed_lead(db_session, source_type="bayut", status="new")
        lead4 = await _seed_lead(db_session, source_type="website", status="converted")
        lead5 = await _seed_lead(db_session, source_type="website", status="new")

        # Assign leads to agents
        await _seed_assignment(db_session, lead1, agent1_id)
        await _seed_assignment(db_session, lead2, agent1_id)
        await _seed_assignment(db_session, lead3, agent1_id)
        await _seed_assignment(db_session, lead4, agent2_id)
        await _seed_assignment(db_session, lead5, agent2_id)

        await db_session.commit()

        repo = AnalyticsRepository(db_session)
        rows, total, _ = await repo.lead_conversion_rates_by_source_and_agent(
            skip=0, limit=50
        )

        assert total >= 2  # at least 2 source/agent combos

        # Find Agent Alpha's bayut stats
        alpha_bayut = [
            r
            for r in rows
            if r["source_type"] == "bayut" and r["agent_name"] == "Agent Alpha"
        ]
        assert len(alpha_bayut) == 1
        row = alpha_bayut[0]
        assert row["total_leads"] == 3
        assert row["converted_leads"] == 2
        # Conversion rate = 2/3 * 100 ≈ 66.67
        assert float(row["conversion_rate"]) == pytest.approx(66.67, abs=0.01)

    @pytest.mark.asyncio
    async def test_conversion_rates_empty_db(self, db_session: AsyncSession):
        """No leads → empty result with total=0."""
        from app.repositories.analytics_repository import AnalyticsRepository

        repo = AnalyticsRepository(db_session)
        rows, total, _ = await repo.lead_conversion_rates_by_source_and_agent(
            skip=0, limit=50
        )

        assert total == 0
        assert rows == []

    @pytest.mark.asyncio
    async def test_conversion_rates_pagination(self, db_session: AsyncSession):
        """Verify offset pagination works on conversion-rate results."""
        from app.repositories.analytics_repository import AnalyticsRepository

        # Seed enough data for multiple pages — 3 agents, 2 sources = 6 combos
        agents = []
        for i in range(3):
            aid = await _seed_agent(
                db_session,
                full_name=f"Agent {i}",
            )
            agents.append(aid)

        for source in ("bayut", "website"):
            for agent_id in agents:
                lid = await _seed_lead(
                    db_session,
                    source_type=source,
                    status="converted" if source == "bayut" else "new",
                )
                await _seed_assignment(db_session, lid, agent_id)

        await db_session.commit()

        repo = AnalyticsRepository(db_session)

        # Page 1: limit=2
        rows_p1, total, _ = await repo.lead_conversion_rates_by_source_and_agent(
            skip=0, limit=2
        )
        assert total == 6
        assert len(rows_p1) == 2

        # Page 2
        rows_p2, total2, _ = await repo.lead_conversion_rates_by_source_and_agent(
            skip=2, limit=2
        )
        assert total2 == 6
        assert len(rows_p2) == 2

        # IDs should differ between pages
        keys_p1 = {(r["source_type"], r["agent_name"]) for r in rows_p1}
        keys_p2 = {(r["source_type"], r["agent_name"]) for r in rows_p2}
        assert keys_p1.isdisjoint(keys_p2)


class TestAgentPerformanceRankings:
    """Verify agent ranking aggregation with LATERAL join and conversion calc."""

    @pytest.mark.asyncio
    async def test_rankings_basic(self, db_session: AsyncSession):
        """Two agents with different conversion rates — verify ordering."""
        from app.repositories.analytics_repository import AnalyticsRepository

        agent1_id = await _seed_agent(db_session, full_name="Top Performer")
        agent2_id = await _seed_agent(db_session, full_name="Average Performer")

        # Agent 1: 3 leads, 2 converted → 66.67%
        for i in range(3):
            lid = await _seed_lead(
                db_session,
                status="converted" if i < 2 else "new",
            )
            await _seed_assignment(db_session, lid, agent1_id)
            if i < 2:
                await _seed_conversion_history(
                    db_session,
                    lid,
                    deal_value=Decimal("2000000.00"),
                    agent_id=agent1_id,
                )

        # Agent 2: 4 leads, 1 converted → 25%
        for i in range(4):
            lid = await _seed_lead(
                db_session,
                status="converted" if i == 0 else "contacted",
            )
            await _seed_assignment(db_session, lid, agent2_id)
            if i == 0:
                await _seed_conversion_history(
                    db_session,
                    lid,
                    deal_value=Decimal("800000.00"),
                    agent_id=agent2_id,
                )

        await db_session.commit()

        repo = AnalyticsRepository(db_session)
        rows, total = await repo.agent_performance_rankings(skip=0, limit=50)

        assert total == 2
        assert len(rows) == 2

        # Ordered by conversion_rate DESC
        assert rows[0]["full_name"] == "Top Performer"
        assert float(rows[0]["conversion_rate"]) == pytest.approx(66.67, abs=0.01)
        assert rows[0]["conversions"] == 2
        assert rows[0]["leads_assigned"] == 3

        assert rows[1]["full_name"] == "Average Performer"
        assert float(rows[1]["conversion_rate"]) == pytest.approx(25.0, abs=0.01)
        assert rows[1]["conversions"] == 1
        assert rows[1]["leads_assigned"] == 4

    @pytest.mark.asyncio
    async def test_rankings_exclude_agents_with_no_leads(
        self, db_session: AsyncSession
    ):
        """Agents with zero assigned leads should be excluded from rankings."""
        from app.repositories.analytics_repository import AnalyticsRepository

        # Agent with leads
        active = await _seed_agent(db_session, full_name="Active Agent")
        lid = await _seed_lead(db_session, status="contacted")
        await _seed_assignment(db_session, lid, active)

        # Agent with no leads
        await _seed_agent(db_session, full_name="Idle Agent")

        await db_session.commit()

        repo = AnalyticsRepository(db_session)
        rows, total = await repo.agent_performance_rankings(skip=0, limit=50)

        assert total == 1
        assert rows[0]["full_name"] == "Active Agent"

    @pytest.mark.asyncio
    async def test_rankings_deal_size_tiebreaker(self, db_session: AsyncSession):
        """Same conversion rate → higher average deal size ranks first."""
        from app.repositories.analytics_repository import AnalyticsRepository

        agent1_id = await _seed_agent(db_session, full_name="Big Deals")
        agent2_id = await _seed_agent(db_session, full_name="Small Deals")

        # Both: 1 lead, 1 converted → 100%
        for agent_id, deal_val in [
            (agent1_id, Decimal("5000000.00")),
            (agent2_id, Decimal("500000.00")),
        ]:
            lid = await _seed_lead(db_session, status="converted")
            await _seed_assignment(db_session, lid, agent_id)
            await _seed_conversion_history(
                db_session, lid, deal_value=deal_val, agent_id=agent_id
            )

        await db_session.commit()

        repo = AnalyticsRepository(db_session)
        rows, total = await repo.agent_performance_rankings(skip=0, limit=50)

        assert total == 2
        # Same conversion_rate (100%), ordered by average_deal_size DESC
        assert rows[0]["full_name"] == "Big Deals"
        assert rows[1]["full_name"] == "Small Deals"


class TestWorkloadDistribution:
    """Verify current workload distribution query."""

    @pytest.mark.asyncio
    async def test_workload_ordering(self, db_session: AsyncSession):
        """Agents should be ordered by active_leads_count DESC."""
        from app.repositories.analytics_repository import AnalyticsRepository

        await _seed_agent(db_session, full_name="Busy Agent", active_leads_count=40)
        await _seed_agent(db_session, full_name="Free Agent", active_leads_count=5)
        await _seed_agent(db_session, full_name="Mid Agent", active_leads_count=20)
        await db_session.commit()

        repo = AnalyticsRepository(db_session)
        rows, total, _ = await repo.current_workload_distribution(skip=0, limit=50)

        assert total == 3
        assert len(rows) == 3
        # Ordered DESC by active_leads_count
        assert rows[0]["full_name"] == "Busy Agent"
        assert rows[0]["active_leads_count"] == 40
        assert rows[1]["full_name"] == "Mid Agent"
        assert rows[1]["active_leads_count"] == 20
        assert rows[2]["full_name"] == "Free Agent"
        assert rows[2]["active_leads_count"] == 5

    @pytest.mark.asyncio
    async def test_workload_includes_specialization_data(
        self, db_session: AsyncSession
    ):
        """Workload rows should include specialization arrays."""
        from app.repositories.analytics_repository import AnalyticsRepository

        await _seed_agent(
            db_session,
            full_name="Specialist",
            specialization_property_type=["villa", "townhouse"],
            specialization_areas=["Palm Jumeirah", "Marina"],
            active_leads_count=15,
        )
        await db_session.commit()

        repo = AnalyticsRepository(db_session)
        rows, total, _ = await repo.current_workload_distribution(skip=0, limit=50)

        assert total == 1
        row = rows[0]
        assert "villa" in row["specialization_property_type"]
        assert "Palm Jumeirah" in row["specialization_areas"]

    @pytest.mark.asyncio
    async def test_approaching_capacity_threshold(self, db_session: AsyncSession):
        """Only agents above the threshold appear in approaching-capacity results."""
        from app.repositories.analytics_repository import AnalyticsRepository

        await _seed_agent(db_session, full_name="At Risk", active_leads_count=45)
        await _seed_agent(db_session, full_name="Safe", active_leads_count=10)
        await _seed_agent(db_session, full_name="Borderline", active_leads_count=41)
        await db_session.commit()

        repo = AnalyticsRepository(db_session)
        rows, total, _ = await repo.agents_approaching_maximum_capacity(
            threshold=40, skip=0, limit=50
        )

        # Only agents with active_leads_count > 40 should appear
        assert total == 2
        names = {r["full_name"] for r in rows}
        assert "At Risk" in names
        assert "Borderline" in names
        assert "Safe" not in names

        # Verify remaining_capacity
        at_risk = [r for r in rows if r["full_name"] == "At Risk"][0]
        assert at_risk["remaining_capacity"] == 5  # 50 - 45


class TestRevenueAttribution:
    """Verify revenue attribution aggregation by lead source."""

    @pytest.mark.asyncio
    async def test_revenue_by_source(self, db_session: AsyncSession):
        """Two sources with different deal values — verify aggregation."""
        from app.repositories.analytics_repository import AnalyticsRepository

        agent_id = await _seed_agent(db_session, full_name="Deal Closer")

        # 2 bayut leads converted with deals
        for val in [Decimal("2000000.00"), Decimal("3000000.00")]:
            lid = await _seed_lead(db_session, source_type="bayut", status="converted")
            await _seed_assignment(db_session, lid, agent_id)
            await _seed_conversion_history(
                db_session, lid, deal_value=val, agent_id=agent_id
            )

        # 1 website lead converted
        lid = await _seed_lead(db_session, source_type="website", status="converted")
        await _seed_assignment(db_session, lid, agent_id)
        await _seed_conversion_history(
            db_session,
            lid,
            deal_value=Decimal("1000000.00"),
            agent_id=agent_id,
        )

        await db_session.commit()

        repo = AnalyticsRepository(db_session)
        rows, total = await repo.revenue_attribution_by_lead_source(skip=0, limit=50)

        assert total == 2  # bayut and website
        # Ordered by total_revenue DESC
        assert rows[0]["source_type"] == "bayut"
        assert float(rows[0]["total_revenue"]) == pytest.approx(5_000_000.0, abs=1)
        assert rows[0]["converted_leads"] == 2
        assert float(rows[0]["average_deal_size"]) == pytest.approx(2_500_000.0, abs=1)

        assert rows[1]["source_type"] == "website"
        assert float(rows[1]["total_revenue"]) == pytest.approx(1_000_000.0, abs=1)
        assert rows[1]["converted_leads"] == 1

    @pytest.mark.asyncio
    async def test_revenue_excludes_null_deal_values(self, db_session: AsyncSession):
        """Conversion history with NULL deal_value should be excluded."""
        from app.repositories.analytics_repository import AnalyticsRepository

        agent_id = await _seed_agent(db_session)

        lid = await _seed_lead(db_session, source_type="bayut", status="converted")
        await _seed_assignment(db_session, lid, agent_id)
        await _seed_conversion_history(
            db_session, lid, deal_value=None, agent_id=agent_id
        )

        await db_session.commit()

        repo = AnalyticsRepository(db_session)
        rows, total = await repo.revenue_attribution_by_lead_source(skip=0, limit=50)

        # NULL deal_value is excluded by WHERE clause
        assert total == 0
        assert rows == []


class TestSourceQualityOverTime:
    """Verify source quality aggregation over monthly periods."""

    @pytest.mark.asyncio
    async def test_source_quality_monthly_aggregation(self, db_session: AsyncSession):
        """Multiple sources across different months — verify grouping."""
        from app.repositories.analytics_repository import AnalyticsRepository

        now = datetime.now(timezone.utc)
        last_month = now - timedelta(days=35)

        # Current month: 2 bayut leads (scores 80, 90), 1 converted
        for i, (score, status) in enumerate([(80, "converted"), (90, "new")]):
            await _seed_lead(
                db_session,
                source_type="bayut",
                score=score,
                status=status,
                created_at=now - timedelta(hours=i),
            )

        # Last month: 1 website lead (score 60), 1 converted
        await _seed_lead(
            db_session,
            source_type="website",
            score=60,
            status="converted",
            created_at=last_month,
        )

        await db_session.commit()

        repo = AnalyticsRepository(db_session)
        rows, total = await repo.source_quality_comparison_over_time(skip=0, limit=50)

        assert total >= 2  # at least 2 month/source combos

        # Find bayut row for current month
        bayut_current = [
            r
            for r in rows
            if r["source_type"] == "bayut" and r["month"].month == now.month
        ]
        assert len(bayut_current) == 1
        assert bayut_current[0]["lead_count"] == 2
        assert float(bayut_current[0]["avg_score"]) == pytest.approx(85.0, abs=0.01)
        assert bayut_current[0]["converted_count"] == 1

    @pytest.mark.asyncio
    async def test_source_quality_empty(self, db_session: AsyncSession):
        """No leads → empty result."""
        from app.repositories.analytics_repository import AnalyticsRepository

        repo = AnalyticsRepository(db_session)
        rows, total = await repo.source_quality_comparison_over_time(skip=0, limit=50)

        assert total == 0
        assert rows == []


async def _override_get_db():
    """Yield a test-scoped async session."""
    async with _TestSessionLocal() as session:
        yield session


class TestAnalyticsEndpoints:
    """Smoke tests for analytics HTTP endpoints against PostgreSQL.

    Verifies that the endpoint → service → repository → DB pipeline
    works end-to-end and returns properly structured PaginatedResponse
    payloads.
    """

    @pytest_asyncio.fixture
    async def client(self) -> AsyncGenerator:
        """HTTP client wired to the FastAPI app with test DB."""
        from httpx import ASGITransport, AsyncClient
        from app.core.database import get_db
        from app.main import app

        app.dependency_overrides[get_db] = _override_get_db
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as c:
            yield c
        app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_conversion_rates_endpoint(self, client, db_session: AsyncSession):
        """GET /api/v1/analytics/conversion-rates returns PaginatedResponse."""
        # Seed minimal data
        agent_id = await _seed_agent(db_session)
        lid = await _seed_lead(db_session, status="converted")
        await _seed_assignment(db_session, lid, agent_id)
        await db_session.commit()

        resp = await client.get("/api/v1/analytics/conversion-rates")
        assert resp.status_code == 200

        body = resp.json()
        assert "data" in body
        assert "total" in body
        assert "skip" in body
        assert "limit" in body
        assert body["total"] >= 1

    @pytest.mark.asyncio
    async def test_agent_rankings_endpoint(self, client, db_session: AsyncSession):
        """GET /api/v1/analytics/agent-rankings returns PaginatedResponse."""
        agent_id = await _seed_agent(db_session, full_name="Ranked Agent")
        lid = await _seed_lead(db_session, status="converted")
        await _seed_assignment(db_session, lid, agent_id)
        await db_session.commit()

        resp = await client.get("/api/v1/analytics/agent-rankings")
        assert resp.status_code == 200

        body = resp.json()
        assert body["total"] >= 1
        assert any(r["full_name"] == "Ranked Agent" for r in body["data"])

    @pytest.mark.asyncio
    async def test_workload_distribution_endpoint(
        self, client, db_session: AsyncSession
    ):
        """GET /api/v1/analytics/workload-distribution returns PaginatedResponse."""
        await _seed_agent(db_session, full_name="Loaded Agent", active_leads_count=30)
        await db_session.commit()

        resp = await client.get("/api/v1/analytics/workload-distribution")
        assert resp.status_code == 200

        body = resp.json()
        assert body["total"] >= 1
        assert any(r["full_name"] == "Loaded Agent" for r in body["data"])

    @pytest.mark.asyncio
    async def test_revenue_attribution_endpoint(self, client, db_session: AsyncSession):
        """GET /api/v1/analytics/revenue-attribution returns PaginatedResponse."""
        agent_id = await _seed_agent(db_session)
        lid = await _seed_lead(db_session, source_type="bayut", status="converted")
        await _seed_assignment(db_session, lid, agent_id)
        await _seed_conversion_history(
            db_session,
            lid,
            deal_value=Decimal("3000000.00"),
            agent_id=agent_id,
        )
        await db_session.commit()

        resp = await client.get("/api/v1/analytics/revenue-attribution")
        assert resp.status_code == 200

        body = resp.json()
        assert body["total"] >= 1

    @pytest.mark.asyncio
    async def test_workload_pagination_params(self, client, db_session: AsyncSession):
        """Pagination query params (skip, limit) are respected."""
        for i in range(5):
            await _seed_agent(
                db_session,
                full_name=f"Agent {i}",
                active_leads_count=i * 5,
            )
        await db_session.commit()

        resp = await client.get(
            "/api/v1/analytics/workload-distribution",
            params={"skip": 0, "limit": 2},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] == 5
        assert len(body["data"]) == 2
        assert body["limit"] == 2
