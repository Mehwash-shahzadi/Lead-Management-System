import pytest
import pytest_asyncio
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import AsyncGenerator
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

from httpx import ASGITransport, AsyncClient

from app.main import app
from app.dependencies import (
    get_agent_repo,
    get_dashboard_repo,
    get_task_repo,
    get_conversion_repo,
    get_agent_dashboard_service,
)


def _make_mock_agent(agent_id=None, active_leads_count=5):
    """Return a mock Agent with realistic attributes."""
    agent = MagicMock()
    agent.agent_id = agent_id or uuid4()
    agent.full_name = "Test Agent"
    agent.email = "test@thinkrealty.ae"
    agent.phone = "+971501234500"
    agent.specialization_property_type = ["apartment"]
    agent.specialization_areas = ["Downtown Dubai"]
    agent.language_skills = ["arabic", "english"]
    agent.active_leads_count = active_leads_count
    return agent


def _make_mock_lead(lead_id=None, status="new", score=50):
    """Return a mock Lead with realistic attributes."""
    lead = MagicMock()
    lead.lead_id = lead_id or uuid4()
    lead.status = status
    lead.score = score
    lead.phone = "+971501234567"
    lead.source_type = "bayut"
    lead.first_name = "Ahmed"
    lead.last_name = "Al Mansoori"
    lead.email = "ahmed@example.com"
    lead.nationality = "UAE"
    lead.language_preference = "arabic"
    lead.budget_min = Decimal("500000")
    lead.budget_max = Decimal("900000")
    lead.property_type = "apartment"
    lead.preferred_areas = ["Downtown Dubai"]
    lead.created_at = datetime.now(timezone.utc) - timedelta(days=5)
    lead.updated_at = datetime.now(timezone.utc)
    return lead


def _make_mock_task(task_id=None, lead_id=None, agent_id=None):
    """Return a mock FollowUpTask."""
    task = MagicMock()
    task.task_id = task_id or uuid4()
    task.lead_id = lead_id or uuid4()
    task.agent_id = agent_id or uuid4()
    task.type = "call"
    task.due_date = datetime.now(timezone.utc) + timedelta(hours=24)
    task.priority = "high"
    task.status = "pending"
    task.created_at = datetime.now(timezone.utc)
    return task


@pytest_asyncio.fixture
async def client() -> AsyncGenerator[AsyncClient, None]:
    """Yield an httpx.AsyncClient wired to the FastAPI app."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


class TestLeadCaptureEndpoint:
    """Integration tests for the lead capture endpoint."""

    @pytest.mark.asyncio
    async def test_capture_lead_success(self, client: AsyncClient):
        """A valid lead capture request should return 201 with all required fields."""
        lead_id = uuid4()
        agent = _make_mock_agent()
        task = _make_mock_task(lead_id=lead_id, agent_id=agent.agent_id)
        _make_mock_lead(lead_id=lead_id)

        with patch(
            "app.dependencies.get_redis_client",
            return_value=AsyncMock(
                get=AsyncMock(return_value=None),
                setex=AsyncMock(),
                ping=AsyncMock(),
                incr=AsyncMock(return_value=1),
            ),
        ):
            with patch(
                "app.services.lead_capture_service.LeadCaptureService.capture_lead"
            ) as mock_capture:
                mock_capture.return_value = {
                    "lead_id": lead_id,
                    "assigned_agent": {
                        "agent_id": agent.agent_id,
                        "name": agent.full_name,
                        "phone": agent.phone,
                    },
                    "lead_score": 75,
                    "next_follow_up": task.due_date,
                    "suggested_properties": [],
                }

                response = await client.post(
                    "/api/v1/leads/capture",
                    json={
                        "source_type": "bayut",
                        "lead_data": {
                            "first_name": "Ahmed",
                            "last_name": "Al Mansoori",
                            "phone": "+971501234567",
                            "nationality": "UAE",
                            "language_preference": "arabic",
                            "budget_min": 500000,
                            "budget_max": 900000,
                            "property_type": "apartment",
                            "preferred_areas": ["Downtown Dubai"],
                        },
                        "source_details": {},
                    },
                )

                assert response.status_code == 201
                data = response.json()
                assert "lead_id" in data
                assert "assigned_agent" in data
                assert "lead_score" in data
                assert "next_follow_up" in data
                assert "suggested_properties" in data

    @pytest.mark.asyncio
    async def test_capture_lead_validation_error(self, client: AsyncClient):
        """Invalid phone format should return 422."""
        response = await client.post(
            "/api/v1/leads/capture",
            json={
                "source_type": "bayut",
                "lead_data": {
                    "first_name": "Ahmed",
                    "last_name": "Al Mansoori",
                    "phone": "12345",  # Invalid phone
                    "nationality": "UAE",
                    "language_preference": "arabic",
                    "budget_min": 500000,
                    "budget_max": 900000,
                    "property_type": "apartment",
                    "preferred_areas": ["Downtown Dubai"],
                },
                "source_details": {},
            },
        )

        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_capture_lead_invalid_source_type(self, client: AsyncClient):
        """Invalid source type should return 422."""
        response = await client.post(
            "/api/v1/leads/capture",
            json={
                "source_type": "invalid_source",
                "lead_data": {
                    "first_name": "Ahmed",
                    "last_name": "Al Mansoori",
                    "phone": "+971501234567",
                    "nationality": "UAE",
                    "language_preference": "arabic",
                    "budget_min": 500000,
                    "budget_max": 900000,
                    "property_type": "apartment",
                    "preferred_areas": ["Downtown Dubai"],
                },
                "source_details": {},
            },
        )

        assert response.status_code == 422


class TestLeadUpdateEndpoint:
    """Integration tests for the lead update endpoint."""

    @pytest.mark.asyncio
    async def test_update_lead_status_success(self, client: AsyncClient):
        """A valid status transition should return 200."""
        lead_id = uuid4()

        with patch(
            "app.services.lead_update_service.LeadUpdateService.update_lead"
        ) as mock_update:
            mock_update.return_value = {
                "lead_id": lead_id,
                "status": "contacted",
                "score": 50,
            }

            response = await client.put(
                f"/api/v1/leads/{lead_id}/update",
                json={
                    "status": "contacted",
                },
            )

            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert data["status"] == "contacted"
            assert data["score"] == 50

    @pytest.mark.asyncio
    async def test_update_lead_with_activity(self, client: AsyncClient):
        """An update with activity data should return 200."""
        lead_id = uuid4()

        with patch(
            "app.services.lead_update_service.LeadUpdateService.update_lead"
        ) as mock_update:
            mock_update.return_value = {
                "lead_id": lead_id,
                "status": "new",
                "score": 55,
            }

            response = await client.put(
                f"/api/v1/leads/{lead_id}/update",
                json={
                    "activity": {
                        "type": "call",
                        "outcome": "positive",
                        "notes": "Discussed property options",
                    },
                },
            )

            assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_update_lead_invalid_status(self, client: AsyncClient):
        """An invalid status value should return 422."""
        lead_id = uuid4()

        response = await client.put(
            f"/api/v1/leads/{lead_id}/update",
            json={
                "status": "invalid_status",
            },
        )

        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_update_lead_not_found(self, client: AsyncClient):
        """Updating a non-existent lead should return 404."""
        from app.core.exceptions import LeadNotFoundError

        lead_id = uuid4()

        with patch(
            "app.services.lead_update_service.LeadUpdateService.update_lead"
        ) as mock_update:
            mock_update.side_effect = LeadNotFoundError("Lead not found")

            response = await client.put(
                f"/api/v1/leads/{lead_id}/update",
                json={
                    "status": "contacted",
                },
            )

            assert response.status_code == 404


class TestAgentDashboardEndpoint:
    """HTTP-level tests for the agent dashboard endpoint.

    Uses FastAPI ``dependency_overrides`` to inject mock repositories
    and service so the tests are independent of a running database.
    """

    def _apply_overrides(self, agent=None, dashboard_data=None):
        """Set dependency overrides for the dashboard endpoint."""
        mock_agent_repo = AsyncMock()
        mock_agent_repo.get_by_id = AsyncMock(return_value=agent)

        mock_service = AsyncMock()
        if dashboard_data is not None:
            mock_service.get_dashboard_data = AsyncMock(return_value=dashboard_data)

        app.dependency_overrides[get_agent_repo] = lambda: mock_agent_repo
        app.dependency_overrides[get_dashboard_repo] = lambda: AsyncMock()
        app.dependency_overrides[get_task_repo] = lambda: AsyncMock()
        app.dependency_overrides[get_conversion_repo] = lambda: AsyncMock()
        app.dependency_overrides[get_agent_dashboard_service] = lambda: mock_service

    def _clear_overrides(self):
        """Remove all dependency overrides."""
        app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_dashboard_success(self, client: AsyncClient):
        """A valid dashboard request should return 200 with all sections."""
        agent_id = uuid4()
        agent = _make_mock_agent(agent_id=agent_id)

        self._apply_overrides(
            agent=agent,
            dashboard_data={
                "agent_summary": {
                    "total_active_leads": 10,
                    "overdue_follow_ups": 2,
                    "this_month_conversions": 3,
                    "average_response_time": "2.5 hours",
                    "lead_score_average": 65,
                },
                "recent_leads": [],
                "pending_tasks": [],
                "performance_metrics": {
                    "conversion_rate": 0.25,
                    "average_deal_size": 1500000,
                    "response_time_rank": 3,
                },
            },
        )
        try:
            response = await client.get(f"/api/v1/agents/{agent_id}/dashboard")

            assert response.status_code == 200
            data = response.json()
            assert "agent_summary" in data
            assert "recent_leads" in data
            assert "pending_tasks" in data
            assert "performance_metrics" in data
        finally:
            self._clear_overrides()

    @pytest.mark.asyncio
    async def test_dashboard_agent_not_found(self, client: AsyncClient):
        """Dashboard for a non-existent agent should return 404."""
        agent_id = uuid4()

        self._apply_overrides(agent=None)
        try:
            response = await client.get(f"/api/v1/agents/{agent_id}/dashboard")

            assert response.status_code == 404
        finally:
            self._clear_overrides()

    @pytest.mark.asyncio
    async def test_dashboard_custom_date_range_missing_dates(self, client: AsyncClient):
        """Custom date range without start/end should return 400."""
        agent_id = uuid4()
        agent = _make_mock_agent(agent_id=agent_id)

        self._apply_overrides(agent=agent)
        try:
            response = await client.get(
                f"/api/v1/agents/{agent_id}/dashboard",
                params={"date_range": "custom"},
            )

            assert response.status_code == 400
        finally:
            self._clear_overrides()

    @pytest.mark.asyncio
    async def test_dashboard_with_filters(self, client: AsyncClient):
        """Dashboard with status and source filters should return 200."""
        agent_id = uuid4()
        agent = _make_mock_agent(agent_id=agent_id)

        self._apply_overrides(
            agent=agent,
            dashboard_data={
                "agent_summary": {
                    "total_active_leads": 5,
                    "overdue_follow_ups": 0,
                    "this_month_conversions": 1,
                    "average_response_time": "1.0 hours",
                    "lead_score_average": 70,
                },
                "recent_leads": [],
                "pending_tasks": [],
                "performance_metrics": {
                    "conversion_rate": 0.15,
                    "average_deal_size": 1200000,
                    "response_time_rank": 5,
                },
            },
        )
        try:
            response = await client.get(
                f"/api/v1/agents/{agent_id}/dashboard",
                params={
                    "date_range": "7d",
                    "status_filter": "active",
                    "source_filter": "bayut",
                },
            )

            assert response.status_code == 200
        finally:
            self._clear_overrides()
