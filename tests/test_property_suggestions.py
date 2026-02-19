from typing import List
from unittest.mock import AsyncMock, patch

import httpx
import pytest

from app.core.exceptions import PropertyServiceUnavailableError
from app.services.property_suggestion_service import PropertySuggestionService


def _make_service(
    *,
    suggestions: List[str] | None = None,
    repo_side_effect: Exception | None = None,
    property_service_url: str = "",
) -> PropertySuggestionService:
    """Build a service with a mocked ``PropertyInterestRepository``."""
    mock_repo = AsyncMock()
    if repo_side_effect:
        mock_repo.find_suggestions = AsyncMock(side_effect=repo_side_effect)
    else:
        mock_repo.find_suggestions = AsyncMock(return_value=suggestions or [])
    return PropertySuggestionService(
        interest_repo=mock_repo,
        property_service_url=property_service_url,
    )


class TestCheckAvailability:
    """Tests for ``PropertySuggestionService.check_availability()``."""

    @pytest.mark.asyncio
    async def test_local_mode_always_succeeds(self):
        """When ``PROPERTY_SERVICE_URL`` is empty, check passes immediately."""
        service = _make_service(property_service_url="")
        # Should not raise
        await service.check_availability()

    @pytest.mark.asyncio
    async def test_external_service_reachable(self):
        """When external URL is configured and healthy, check passes."""
        service = _make_service(
            property_service_url="http://property-service:8000/health",
        )
        mock_response = httpx.Response(200, request=httpx.Request("GET", "http://x"))
        with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_response
            # Should not raise
            await service.check_availability()
            mock_get.assert_called_once_with("http://property-service:8000/health")

    @pytest.mark.asyncio
    async def test_external_service_timeout_raises(self):
        """Timeout when checking external service raises PropertyServiceUnavailableError."""
        service = _make_service(
            property_service_url="http://property-service:8000/health",
        )
        with patch(
            "httpx.AsyncClient.get",
            new_callable=AsyncMock,
            side_effect=httpx.TimeoutException("timed out"),
        ):
            with pytest.raises(PropertyServiceUnavailableError, match="timed out"):
                await service.check_availability()

    @pytest.mark.asyncio
    async def test_external_service_connection_error_raises(self):
        """Connection error raises PropertyServiceUnavailableError."""
        service = _make_service(
            property_service_url="http://property-service:8000/health",
        )
        with patch(
            "httpx.AsyncClient.get",
            new_callable=AsyncMock,
            side_effect=httpx.ConnectError("Connection refused"),
        ):
            with pytest.raises(PropertyServiceUnavailableError, match="unavailable"):
                await service.check_availability()

    @pytest.mark.asyncio
    async def test_external_service_500_raises(self):
        """Non-2xx response from external service raises PropertyServiceUnavailableError."""
        service = _make_service(
            property_service_url="http://property-service:8000/health",
        )
        mock_response = httpx.Response(
            503,
            request=httpx.Request("GET", "http://property-service:8000/health"),
        )
        with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_response
            with pytest.raises(PropertyServiceUnavailableError, match="503"):
                await service.check_availability()


class TestGetSuggestions:
    """Tests for ``PropertySuggestionService.get_suggestions()``."""

    @pytest.mark.asyncio
    async def test_delegates_to_repository(self):
        """get_suggestions() passes params to PropertyInterestRepository.find_suggestions()."""
        expected = ["uuid-1", "uuid-2", "uuid-3"]
        service = _make_service(suggestions=expected)

        result = await service.get_suggestions(
            property_type="apartment",
            preferred_areas=["Downtown Dubai", "Marina"],
            budget_min=500_000,
            budget_max=1_500_000,
            limit=3,
        )

        assert result == expected
        service._interest_repo.find_suggestions.assert_called_once_with(
            property_type="apartment",
            preferred_areas=["Downtown Dubai", "Marina"],
            budget_min=500_000,
            budget_max=1_500_000,
            limit=3,
        )

    @pytest.mark.asyncio
    async def test_returns_list_of_strings(self):
        """Return type must be List[str] matching assessment spec."""
        service = _make_service(suggestions=["abc-123", "def-456"])
        result = await service.get_suggestions(property_type="villa")
        assert isinstance(result, list)
        assert all(isinstance(item, str) for item in result)

    @pytest.mark.asyncio
    async def test_returns_empty_list_when_no_matches(self):
        """When no matching property data exists, returns empty list gracefully."""
        service = _make_service(suggestions=[])
        result = await service.get_suggestions(
            property_type="commercial",
            preferred_areas=["Al Ain"],
            budget_min=10_000_000,
            budget_max=50_000_000,
        )
        assert result == []

    @pytest.mark.asyncio
    async def test_graceful_degradation_on_repo_failure(self):
        """When the repository query raises, returns empty list (not exception)."""
        service = _make_service(repo_side_effect=RuntimeError("DB connection lost"))
        result = await service.get_suggestions(property_type="apartment")
        assert result == []

    @pytest.mark.asyncio
    async def test_default_limit_is_five(self):
        """When limit is not specified, defaults to 5."""
        service = _make_service(suggestions=["a", "b", "c", "d", "e"])
        await service.get_suggestions()
        service._interest_repo.find_suggestions.assert_called_once_with(
            property_type=None,
            preferred_areas=None,
            budget_min=None,
            budget_max=None,
            limit=5,
        )

    @pytest.mark.asyncio
    async def test_custom_limit(self):
        """Custom limit is forwarded to repository."""
        service = _make_service(suggestions=["a", "b", "c"])
        await service.get_suggestions(limit=3)
        call_kwargs = service._interest_repo.find_suggestions.call_args[1]
        assert call_kwargs["limit"] == 3

    @pytest.mark.asyncio
    async def test_no_filters_returns_most_popular(self):
        """With no filters, repository is called with all-None params."""
        service = _make_service(suggestions=["popular-1", "popular-2"])
        result = await service.get_suggestions()
        assert len(result) == 2
        service._interest_repo.find_suggestions.assert_called_once_with(
            property_type=None,
            preferred_areas=None,
            budget_min=None,
            budget_max=None,
            limit=5,
        )
