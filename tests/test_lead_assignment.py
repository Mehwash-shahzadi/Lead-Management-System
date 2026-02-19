"""Tests for the LeadAssignmentManager – Task 3.2 of the assessment."""

import pytest
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

from app.services.lead_assignment import LeadAssignmentManager
from app.core.cache import CacheService
from app.core.exceptions import AgentOverloadError


def _make_agent(
    *,
    agent_id=None,
    active_leads_count: int = 0,
    specialization_property_type=None,
    specialization_areas=None,
    language_skills=None,
    performance_metrics=None,
):
    """Create a lightweight mock agent."""
    agent = MagicMock()
    agent.agent_id = agent_id or uuid4()
    agent.active_leads_count = active_leads_count
    agent.specialization_property_type = specialization_property_type or []
    agent.specialization_areas = specialization_areas or []
    agent.language_skills = language_skills or []
    agent.performance_metrics = performance_metrics or []
    return agent


def _make_metric(conversion_rate: float, updated_at=None):
    """Create a mock performance-metric record."""
    from datetime import datetime, timezone

    m = MagicMock()
    m.conversion_rate = Decimal(str(conversion_rate))
    m.updated_at = updated_at or datetime.now(timezone.utc)
    return m


class TestAssignLead:
    """Verify the weighted assignment algorithm."""

    @pytest.mark.asyncio
    async def test_raises_when_no_agents_available(self):
        """AgentOverloadError when all agents are at capacity."""
        repo = AsyncMock()
        repo.get_available_agents = AsyncMock(return_value=[])

        manager = LeadAssignmentManager()

        with pytest.raises(AgentOverloadError):
            await manager.assign_lead({}, repo)

    @pytest.mark.asyncio
    async def test_specialization_match_preferred(self):
        """Agent with matching property type scores higher."""
        agent_match = _make_agent(
            specialization_property_type=["villa"],
            specialization_areas=["Downtown Dubai"],
        )
        agent_no_match = _make_agent(
            specialization_property_type=["commercial"],
            specialization_areas=["Business Bay"],
        )

        repo = AsyncMock()
        repo.get_available_agents = AsyncMock(
            return_value=[agent_no_match, agent_match]
        )

        manager = LeadAssignmentManager()
        selected = await manager.assign_lead(
            {"property_type": "villa", "preferred_areas": ["Downtown Dubai"]},
            repo,
        )

        assert selected == agent_match.agent_id

    @pytest.mark.asyncio
    async def test_language_match_boosts_score(self):
        """Agent with matching language preference gets priority."""
        agent_arabic = _make_agent(language_skills=["arabic", "english"])
        agent_english = _make_agent(language_skills=["english"])

        repo = AsyncMock()
        repo.get_available_agents = AsyncMock(
            return_value=[agent_english, agent_arabic]
        )

        manager = LeadAssignmentManager()
        selected = await manager.assign_lead({"language_preference": "arabic"}, repo)

        assert selected == agent_arabic.agent_id

    @pytest.mark.asyncio
    async def test_performance_metric_bonus(self):
        """Agent with higher conversion rate is preferred (other factors equal)."""
        high_perf = _make_agent(
            performance_metrics=[_make_metric(35.0)],
            language_skills=["english"],
        )
        low_perf = _make_agent(
            performance_metrics=[_make_metric(5.0)],
            language_skills=["english"],
        )

        repo = AsyncMock()
        repo.get_available_agents = AsyncMock(return_value=[low_perf, high_perf])

        manager = LeadAssignmentManager()
        selected = await manager.assign_lead({"language_preference": "english"}, repo)

        assert selected == high_perf.agent_id

    @pytest.mark.asyncio
    async def test_workload_balancing_tiebreaker(self):
        """Among equally scored agents, the one with fewer leads wins."""
        agent_busy = _make_agent(active_leads_count=30)
        agent_free = _make_agent(active_leads_count=5)

        repo = AsyncMock()
        repo.get_available_agents = AsyncMock(return_value=[agent_busy, agent_free])

        manager = LeadAssignmentManager()
        selected = await manager.assign_lead({}, repo)

        assert selected == agent_free.agent_id

    @pytest.mark.asyncio
    async def test_round_robin_rotates_among_tied_agents(self):
        """Tied agents should be selected in rotating order."""
        ids = [uuid4() for _ in range(3)]
        agents = [_make_agent(agent_id=uid, active_leads_count=0) for uid in ids]

        repo = AsyncMock()
        repo.get_available_agents = AsyncMock(return_value=agents)

        manager = LeadAssignmentManager()
        # Reset the fallback counter
        LeadAssignmentManager._fallback_counter = 0

        selections = []
        for _ in range(6):
            selected = await manager.assign_lead({}, repo)
            selections.append(selected)

        # Should cycle: ids[0], ids[1], ids[2], ids[0], ids[1], ids[2]
        assert selections == ids + ids

    @pytest.mark.asyncio
    async def test_round_robin_uses_redis_when_available(self):
        """When Redis is available, the counter is read/incremented via CacheService."""
        mock_redis = AsyncMock()
        mock_redis.incr = AsyncMock(return_value=1)
        mock_redis.expire = AsyncMock()

        agents = [_make_agent(active_leads_count=0) for _ in range(3)]
        repo = AsyncMock()
        repo.get_available_agents = AsyncMock(return_value=agents)

        cache = CacheService(redis_client=mock_redis)
        manager = LeadAssignmentManager(cache=cache)
        await manager.assign_lead({}, repo)

        mock_redis.incr.assert_awaited_once()
        mock_redis.expire.assert_awaited_once()


# ---------------------------------------------------------------------------
# Round-robin with workload balancing (Task 3.2 — fixed)
# ---------------------------------------------------------------------------


class TestRoundRobinWorkloadBalancing:
    """Verify round-robin rotates among ALL agents sharing the top score,
    regardless of individual workload differences.
    """

    @pytest.mark.asyncio
    async def test_three_agents_same_score_different_workloads(self):
        """Three agents all score 8 with workloads 10, 12, 15:
        Round-robin should cycle through all three sorted by workload.

        Assignment 1 → workload 10 (first in sorted order)
        Assignment 2 → workload 12
        Assignment 3 → workload 15
        Assignment 4 → workload 10 (wraps around)
        """
        id_10 = uuid4()
        id_12 = uuid4()
        id_15 = uuid4()

        # All three agents score identically (no specialization/language/perf
        # match → score = 0 for all), but have different workloads.
        agents = [
            _make_agent(agent_id=id_15, active_leads_count=15),
            _make_agent(agent_id=id_10, active_leads_count=10),
            _make_agent(agent_id=id_12, active_leads_count=12),
        ]

        repo = AsyncMock()
        repo.get_available_agents = AsyncMock(return_value=agents)

        manager = LeadAssignmentManager()
        LeadAssignmentManager._fallback_counter = 0

        selections = []
        for _ in range(4):
            selected = await manager.assign_lead({}, repo)
            selections.append(selected)

        # Sorted by workload: id_10, id_12, id_15 — round-robin cycles
        assert selections == [id_10, id_12, id_15, id_10]

    @pytest.mark.asyncio
    async def test_higher_score_agent_always_wins(self):
        """Agent scoring 9 vs two agents scoring 7:
        All assignments go to the score-9 agent because round-robin
        only applies within the top-score group.
        """
        high_agent = _make_agent(
            specialization_property_type=["villa"],
            specialization_areas=["Downtown Dubai"],
            language_skills=["arabic"],
            performance_metrics=[_make_metric(35.0)],
            active_leads_count=20,
        )
        low_agent_a = _make_agent(active_leads_count=0)
        low_agent_b = _make_agent(active_leads_count=0)

        repo = AsyncMock()
        repo.get_available_agents = AsyncMock(
            return_value=[low_agent_a, high_agent, low_agent_b]
        )

        manager = LeadAssignmentManager()
        LeadAssignmentManager._fallback_counter = 0

        lead_data = {
            "property_type": "villa",
            "preferred_areas": ["Downtown Dubai"],
            "language_preference": "arabic",
        }

        selections = set()
        for _ in range(5):
            selected = await manager.assign_lead(lead_data, repo)
            selections.add(selected)

        # All 5 assignments go to the same high-scoring agent
        assert selections == {high_agent.agent_id}

    @pytest.mark.asyncio
    async def test_redis_unavailable_graceful_degradation(self):
        """Redis unavailable → always selects lowest workload agent
        from the top-score group (graceful degradation, no exception).
        """
        id_low = uuid4()
        id_mid = uuid4()
        id_high = uuid4()

        agents = [
            _make_agent(agent_id=id_high, active_leads_count=25),
            _make_agent(agent_id=id_low, active_leads_count=5),
            _make_agent(agent_id=id_mid, active_leads_count=15),
        ]

        repo = AsyncMock()
        repo.get_available_agents = AsyncMock(return_value=agents)

        # Redis client that fails on every operation
        broken_redis = AsyncMock()
        broken_redis.incr = AsyncMock(side_effect=ConnectionError("Redis down"))
        broken_redis.expire = AsyncMock(side_effect=ConnectionError("Redis down"))

        cache = CacheService(redis_client=broken_redis)
        manager = LeadAssignmentManager(cache=cache)
        LeadAssignmentManager._fallback_counter = 0

        selections = []
        for _ in range(3):
            selected = await manager.assign_lead({}, repo)
            selections.append(selected)

        # Fallback round-robin cycles through agents sorted by workload
        assert selections[0] == id_low  # lowest-workload agent goes first
