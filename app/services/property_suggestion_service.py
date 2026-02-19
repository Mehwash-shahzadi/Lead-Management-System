import logging
from typing import List, Optional

import httpx

from app.core.config import settings
from app.core.exceptions import PropertyServiceUnavailableError
from app.repositories.property_interest_repository import PropertyInterestRepository

logger = logging.getLogger(__name__)

# Timeout for external property-service health checks (seconds).
_HEALTH_CHECK_TIMEOUT = 5.0


class PropertySuggestionService:
    def __init__(
        self,
        interest_repo: PropertyInterestRepository,
        property_service_url: Optional[str] = None,
    ) -> None:
        self._interest_repo = interest_repo
        self._property_service_url: str = (
            property_service_url
            if property_service_url is not None
            else settings.PROPERTY_SERVICE_URL
        )

    async def check_availability(self) -> None:
        if not self._property_service_url:
            # Local mode — collaborative filtering via DB; always available.
            return

        # External micro-service mode — verify reachability.
        try:
            async with httpx.AsyncClient(
                timeout=_HEALTH_CHECK_TIMEOUT,
            ) as client:
                response = await client.get(self._property_service_url)
                response.raise_for_status()
        except httpx.TimeoutException:
            logger.error(
                "Property service health-check timed out: %s",
                self._property_service_url,
            )
            raise PropertyServiceUnavailableError(
                "Property suggestion service timed out"
            )
        except httpx.HTTPStatusError as exc:
            logger.error(
                "Property service returned %s: %s",
                exc.response.status_code,
                self._property_service_url,
            )
            raise PropertyServiceUnavailableError(
                f"Property suggestion service returned {exc.response.status_code}"
            )
        except httpx.HTTPError as exc:
            logger.error(
                "Property service unreachable: %s — %s",
                self._property_service_url,
                exc,
            )
            raise PropertyServiceUnavailableError(
                "Property suggestion service unavailable"
            )

    async def get_suggestions(
        self,
        property_type: Optional[str] = None,
        preferred_areas: Optional[List[str]] = None,
        budget_min: Optional[float] = None,
        budget_max: Optional[float] = None,
        limit: int = 5,
    ) -> List[str]:
        try:
            return await self._interest_repo.find_suggestions(
                property_type=property_type,
                preferred_areas=preferred_areas,
                budget_min=budget_min,
                budget_max=budget_max,
                limit=limit,
            )
        except Exception:
            logger.warning(
                "Property suggestion query failed; returning empty list",
                exc_info=True,
            )
            return []
