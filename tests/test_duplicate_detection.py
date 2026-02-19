from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.core.exceptions import DuplicateLeadError
from app.core.cache import CacheService
from app.models.lead import Lead
from app.repositories.lead_repository import LeadRepository
from app.services.lead_capture_service import LeadCaptureService
from app.services.lead_scoring import LeadScoringEngine
from app.services.lead_assignment import LeadAssignmentManager


def _make_lead(**overrides) -> Lead:
    """Return a minimal Lead-like object for testing."""
    defaults = {
        "lead_id": "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
        "phone": "+971501234567",
        "source_type": "bayut",
        "first_name": "Ahmed",
        "last_name": "Al Mansouri",
        "status": "new",
        "score": 50,
        "created_at": datetime.now(timezone.utc),
    }
    defaults.update(overrides)
    lead = MagicMock(spec=Lead)
    for k, v in defaults.items():
        setattr(lead, k, v)
    return lead


def _mock_lead_repo(duplicate_lead=None):
    """Return an AsyncMock ``LeadRepository`` with configurable duplicate."""
    repo = AsyncMock(spec=LeadRepository)
    repo.find_duplicate = AsyncMock(return_value=duplicate_lead)
    return repo


class TestDuplicateDetectionService:
    """Integration-style tests for ``LeadCaptureService._check_duplicate()``."""

    @pytest.fixture
    def service(self) -> LeadCaptureService:
        """Return a service with mocked dependencies and no Redis."""
        engine = AsyncMock(spec=LeadScoringEngine)
        manager = AsyncMock(spec=LeadAssignmentManager)
        return LeadCaptureService(
            scoring_engine=engine,
            assignment_manager=manager,
        )

    @pytest.mark.asyncio
    async def test_duplicate_same_phone_same_source_within_24h(self, service):
        """Phone+source that exist within 24 h must raise DuplicateLeadError."""
        existing = _make_lead(
            created_at=datetime.now(timezone.utc) - timedelta(hours=1),
        )
        repo = _mock_lead_repo(duplicate_lead=existing)

        with pytest.raises(DuplicateLeadError):
            await service._check_duplicate("+971501234567", "bayut", repo)

    @pytest.mark.asyncio
    async def test_no_duplicate_after_24h(self, service):
        """Phone+source older than 24 h → no error, treated as new lead."""
        repo = _mock_lead_repo(duplicate_lead=None)  # DB returns nothing

        # Should NOT raise
        await service._check_duplicate("+971501234567", "bayut", repo)

    @pytest.mark.asyncio
    async def test_different_source_not_duplicate(self, service):
        """Same phone from a different source → allowed."""
        repo = _mock_lead_repo(duplicate_lead=None)

        # Should NOT raise
        await service._check_duplicate("+971501234567", "propertyFinder", repo)

    @pytest.mark.asyncio
    async def test_redis_hit_raises_duplicate(self, service):
        """If Redis cache contains the key, raise without hitting DB."""
        mock_redis = AsyncMock()
        mock_redis.get = AsyncMock(return_value=b"some-lead-id")
        service._cache = CacheService(redis_client=mock_redis)

        repo = _mock_lead_repo(duplicate_lead=None)

        with pytest.raises(DuplicateLeadError):
            await service._check_duplicate("+971501234567", "bayut", repo)

        # DB should NOT have been queried — Redis was sufficient
        repo.find_duplicate.assert_not_called()

    @pytest.mark.asyncio
    async def test_redis_down_falls_back_to_db(self, service):
        """If Redis is unavailable the DB query must still run."""
        mock_redis = AsyncMock()
        mock_redis.get = AsyncMock(side_effect=ConnectionError("Redis down"))
        service._cache = CacheService(redis_client=mock_redis)

        existing = _make_lead(
            created_at=datetime.now(timezone.utc) - timedelta(hours=2),
        )
        repo = _mock_lead_repo(duplicate_lead=existing)

        with pytest.raises(DuplicateLeadError):
            await service._check_duplicate("+971501234567", "bayut", repo)

        # DB fallback must have been called
        repo.find_duplicate.assert_called_once()

    @pytest.mark.asyncio
    async def test_redis_down_no_db_duplicate_passes(self, service):
        """Redis down + no DB duplicate → no error (detection not skipped)."""
        mock_redis = AsyncMock()
        mock_redis.get = AsyncMock(side_effect=ConnectionError("Redis down"))
        service._cache = CacheService(redis_client=mock_redis)

        repo = _mock_lead_repo(duplicate_lead=None)

        # Should NOT raise
        await service._check_duplicate("+971501234567", "bayut", repo)

        # DB fallback must have been called
        repo.find_duplicate.assert_called_once()


class TestDuplicateDetectionRedisCache:
    """Verify the Redis cache key uses 24-hour TTL (86400 seconds)."""

    @pytest.mark.asyncio
    async def test_cache_key_ttl_is_86400(self):
        """The duplicate-detection cache must use exactly 86400s TTL."""
        engine = AsyncMock(spec=LeadScoringEngine)
        manager = AsyncMock(spec=LeadAssignmentManager)
        mock_redis = AsyncMock()
        mock_redis.setex = AsyncMock()

        cache = CacheService(redis_client=mock_redis)
        service = LeadCaptureService(
            scoring_engine=engine,
            assignment_manager=manager,
            cache=cache,
        )

        await service._cache_lead_duplicate_key(
            "+971501234567", "bayut", "some-lead-id"
        )

        mock_redis.setex.assert_called_once()
        call_args = mock_redis.setex.call_args
        # setex(key, ttl, value)
        ttl = call_args[0][1]
        assert ttl == 86400, f"Expected TTL of 86400 (24h), got {ttl}"
