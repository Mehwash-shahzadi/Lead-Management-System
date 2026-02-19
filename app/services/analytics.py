from typing import Any, Dict, List, Optional

from app.repositories.analytics_repository import AnalyticsRepository
from app.schemas.analytics import PaginatedResponse


class LeadAnalytics:
    """Thin service that delegates to ``AnalyticsRepository``."""

    def __init__(self, repo: AnalyticsRepository) -> None:
        self._repo = repo

    @staticmethod
    def _wrap(
        data: List[Dict[str, Any]],
        *,
        total: int,
        skip: int,
        limit: int,
        next_cursor: Optional[str] = None,
    ) -> PaginatedResponse:
        return PaginatedResponse(
            data=data,
            total=total,
            skip=skip,
            limit=limit,
            next_cursor=next_cursor,
        )

    async def get_lead_conversion_rates_by_source_and_agent(
        self,
        *,
        cursor: Optional[str] = None,
        skip: int = 0,
        limit: int = 50,
    ) -> PaginatedResponse:
        (
            data,
            total,
            next_cursor,
        ) = await self._repo.lead_conversion_rates_by_source_and_agent(
            cursor=cursor,
            skip=skip,
            limit=limit,
        )
        return self._wrap(
            data, total=total, skip=skip, limit=limit, next_cursor=next_cursor
        )

    async def get_average_time_to_conversion_by_property_type(
        self,
        *,
        skip: int = 0,
        limit: int = 50,
    ) -> PaginatedResponse:
        data, total = await self._repo.average_time_to_conversion_by_property_type(
            skip=skip, limit=limit
        )
        return self._wrap(data, total=total, skip=skip, limit=limit)

    async def get_monthly_lead_volume_trends(
        self,
        *,
        cursor: Optional[str] = None,
        skip: int = 0,
        limit: int = 50,
    ) -> PaginatedResponse:
        data, total, next_cursor = await self._repo.monthly_lead_volume_trends(
            cursor=cursor,
            skip=skip,
            limit=limit,
        )
        return self._wrap(
            data, total=total, skip=skip, limit=limit, next_cursor=next_cursor
        )

    async def get_agent_performance_rankings(
        self,
        *,
        skip: int = 0,
        limit: int = 50,
    ) -> PaginatedResponse:
        data, total = await self._repo.agent_performance_rankings(
            skip=skip, limit=limit
        )
        return self._wrap(data, total=total, skip=skip, limit=limit)

    async def get_revenue_attribution_by_lead_source(
        self,
        *,
        skip: int = 0,
        limit: int = 50,
    ) -> PaginatedResponse:
        data, total = await self._repo.revenue_attribution_by_lead_source(
            skip=skip, limit=limit
        )
        return self._wrap(data, total=total, skip=skip, limit=limit)

    async def get_high_scoring_leads_not_converted(
        self,
        *,
        skip: int = 0,
        limit: int = 50,
    ) -> PaginatedResponse:
        data, total = await self._repo.high_scoring_leads_not_converted(
            skip=skip, limit=limit
        )
        return self._wrap(data, total=total, skip=skip, limit=limit)

    async def get_low_scoring_leads_converted(
        self,
        *,
        skip: int = 0,
        limit: int = 50,
    ) -> PaginatedResponse:
        data, total = await self._repo.low_scoring_leads_converted(
            skip=skip, limit=limit
        )
        return self._wrap(data, total=total, skip=skip, limit=limit)

    async def get_source_quality_comparison_over_time(
        self,
        *,
        skip: int = 0,
        limit: int = 50,
    ) -> PaginatedResponse:
        data, total = await self._repo.source_quality_comparison_over_time(
            skip=skip, limit=limit
        )
        return self._wrap(data, total=total, skip=skip, limit=limit)

    async def get_optimal_follow_up_timing_analysis(
        self,
        *,
        skip: int = 0,
        limit: int = 50,
    ) -> PaginatedResponse:
        data, total = await self._repo.optimal_follow_up_timing_analysis(
            skip=skip, limit=limit
        )
        return self._wrap(data, total=total, skip=skip, limit=limit)

    async def get_current_workload_distribution(
        self,
        *,
        cursor: Optional[str] = None,
        skip: int = 0,
        limit: int = 50,
    ) -> PaginatedResponse:
        data, total, next_cursor = await self._repo.current_workload_distribution(
            cursor=cursor,
            skip=skip,
            limit=limit,
        )
        return self._wrap(
            data, total=total, skip=skip, limit=limit, next_cursor=next_cursor
        )

    async def get_agents_approaching_maximum_capacity(
        self,
        threshold: int = 40,
        *,
        cursor: Optional[str] = None,
        skip: int = 0,
        limit: int = 50,
    ) -> PaginatedResponse:
        data, total, next_cursor = await self._repo.agents_approaching_maximum_capacity(
            threshold,
            cursor=cursor,
            skip=skip,
            limit=limit,
        )
        return self._wrap(
            data, total=total, skip=skip, limit=limit, next_cursor=next_cursor
        )

    async def get_specialized_vs_general_agent_performance(
        self,
        *,
        skip: int = 0,
        limit: int = 50,
    ) -> PaginatedResponse:
        data, total = await self._repo.specialized_vs_general_agent_performance(
            skip=skip, limit=limit
        )
        return self._wrap(data, total=total, skip=skip, limit=limit)

    async def get_lead_response_time_correlation_with_conversion(
        self,
        *,
        skip: int = 0,
        limit: int = 50,
    ) -> PaginatedResponse:
        data, total = await self._repo.lead_response_time_correlation_with_conversion(
            skip=skip, limit=limit
        )
        return self._wrap(data, total=total, skip=skip, limit=limit)
