from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from app.services.auto_reassign import (
    auto_reassign_stale_leads,
    _STALE_HOURS,
)


def _make_mock_assignment(lead_id=None, agent_id=None, assigned_at=None):
    """Create a mock LeadAssignment object."""
    assignment = MagicMock()
    assignment.lead_id = lead_id or uuid4()
    assignment.agent_id = agent_id or uuid4()
    assignment.assigned_at = assigned_at or (
        datetime.now(timezone.utc) - timedelta(hours=_STALE_HOURS + 1)
    )
    return assignment


class TestAutoReassignStaleLeads:
    """Verify the auto-reassignment one-shot function."""

    @pytest.mark.asyncio
    async def test_no_stale_assignments_returns_zero(self):
        """When no stale assignments exist, nothing is reassigned."""
        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)

        session_factory = MagicMock(return_value=mock_session)

        with patch(
            "app.services.auto_reassign._find_stale_assignments",
            new_callable=AsyncMock,
            return_value=[],
        ):
            count = await auto_reassign_stale_leads(session_factory)

        assert count == 0

    @pytest.mark.asyncio
    async def test_stale_assignments_are_reassigned(self):
        """Stale assignments should be reassigned to new agents."""
        stale_assignment = _make_mock_assignment()
        new_agent_id = uuid4()

        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)
        mock_session.commit = AsyncMock()

        session_factory = MagicMock(return_value=mock_session)

        with (
            patch(
                "app.services.auto_reassign._find_stale_assignments",
                new_callable=AsyncMock,
                return_value=[stale_assignment],
            ),
            patch("app.services.auto_reassign.LeadAssignmentManager") as MockManager,
        ):
            mock_manager_instance = MockManager.return_value
            mock_manager_instance.reassign_lead = AsyncMock(return_value=new_agent_id)

            count = await auto_reassign_stale_leads(session_factory)

        assert count == 1
        mock_manager_instance.reassign_lead.assert_awaited_once()
        mock_session.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_failed_reassignment_does_not_crash(self):
        """If one reassignment fails, the loop continues and returns 0."""
        stale_assignment = _make_mock_assignment()

        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)
        mock_session.commit = AsyncMock()

        session_factory = MagicMock(return_value=mock_session)

        with (
            patch(
                "app.services.auto_reassign._find_stale_assignments",
                new_callable=AsyncMock,
                return_value=[stale_assignment],
            ),
            patch("app.services.auto_reassign.LeadAssignmentManager") as MockManager,
        ):
            mock_manager_instance = MockManager.return_value
            mock_manager_instance.reassign_lead = AsyncMock(
                side_effect=Exception("Agent unavailable")
            )

            count = await auto_reassign_stale_leads(session_factory)

        # Failed reassignment should be caught, count stays 0
        assert count == 0

    @pytest.mark.asyncio
    async def test_multiple_stale_assignments(self):
        """Multiple stale leads should each be reassigned."""
        assignments = [_make_mock_assignment() for _ in range(3)]

        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)
        mock_session.commit = AsyncMock()

        session_factory = MagicMock(return_value=mock_session)

        with (
            patch(
                "app.services.auto_reassign._find_stale_assignments",
                new_callable=AsyncMock,
                return_value=assignments,
            ),
            patch("app.services.auto_reassign.LeadAssignmentManager") as MockManager,
        ):
            mock_manager_instance = MockManager.return_value
            mock_manager_instance.reassign_lead = AsyncMock(return_value=uuid4())

            count = await auto_reassign_stale_leads(session_factory)

        assert count == 3
        assert mock_manager_instance.reassign_lead.await_count == 3

    @pytest.mark.asyncio
    async def test_partial_failure_counts_successes_only(self):
        """If 2 of 3 succeed and 1 fails, count should be 2."""
        assignments = [_make_mock_assignment() for _ in range(3)]

        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)
        mock_session.commit = AsyncMock()

        session_factory = MagicMock(return_value=mock_session)

        call_count = 0

        async def side_effect(**kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 2:
                raise Exception("Agent unavailable")
            return uuid4()

        with (
            patch(
                "app.services.auto_reassign._find_stale_assignments",
                new_callable=AsyncMock,
                return_value=assignments,
            ),
            patch("app.services.auto_reassign.LeadAssignmentManager") as MockManager,
        ):
            mock_manager_instance = MockManager.return_value
            mock_manager_instance.reassign_lead = AsyncMock(side_effect=side_effect)

            count = await auto_reassign_stale_leads(session_factory)

        assert count == 2
