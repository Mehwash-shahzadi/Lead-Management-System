import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional
from uuid import UUID

from app.core.cache import CacheService
from app.core.config import settings
from app.repositories.dashboard_repository import DashboardRepository
from app.repositories.task_repository import TaskRepository
from app.repositories.conversion_history_repository import (
    ConversionHistoryRepository,
)
from app.schemas.analytics import (
    DateRange,
    StatusFilter,
    SourceFilter,
)

logger = logging.getLogger(__name__)


class AgentDashboardService:
    """Builds agent dashboard data with Redis caching.

    Dependencies are injected via the constructor so the class remains
    stateless and easily testable.
    """

    def __init__(self, cache: Optional[CacheService] = None) -> None:
        self._cache: CacheService = cache or CacheService()

    async def get_dashboard_data(
        self,
        agent_id: UUID,
        date_range: Optional[DateRange],
        status_filter: Optional[StatusFilter],
        source_filter: Optional[SourceFilter],
        dashboard_repo: DashboardRepository,
        task_repo: TaskRepository,
        conversion_repo: ConversionHistoryRepository,
        *,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        """Return the full agent dashboard payload.

        When *date_range* is ``DateRange.custom``, the caller must supply
        both *start_date* and *end_date* to define the window.

        Results are cached in Redis for ``REDIS_CACHE_TTL`` seconds.
        """
        # Try cache first
        cache_key = self._build_cache_key(
            agent_id,
            date_range,
            status_filter,
            source_filter,
            start_date=start_date,
            end_date=end_date,
        )
        cached = await self._get_cached(cache_key)
        if cached is not None:
            return cached

        # Compute fresh data
        now = datetime.now(timezone.utc)
        date_cutoff = self._resolve_date_cutoff(
            date_range,
            now,
            start_date=start_date,
        )
        # For custom ranges we also need an upper bound
        date_upper = end_date if date_range == DateRange.custom else None
        filters = DashboardRepository.build_filters(
            agent_id,
            date_cutoff=date_cutoff,
            status_filter=status_filter.value
            if status_filter and status_filter != StatusFilter.all
            else None,
            source_filter=source_filter.value
            if source_filter and source_filter != SourceFilter.all
            else None,
            date_upper=date_upper,
        )

        # Consolidated queries via repositories
        agent_summary = await self._build_agent_summary(
            agent_id, filters, now, dashboard_repo, task_repo, conversion_repo
        )
        recent_leads = await dashboard_repo.get_recent_leads(agent_id, filters)
        pending_tasks = await task_repo.get_pending_tasks_with_lead_name(agent_id)
        performance_metrics = await dashboard_repo.get_performance_metrics(agent_id)

        result: Dict[str, Any] = {
            "agent_summary": agent_summary,
            "recent_leads": recent_leads,
            "pending_tasks": pending_tasks,
            "performance_metrics": performance_metrics,
        }

        # Cache the response
        await self._set_cached(cache_key, result)
        return result

    async def _build_agent_summary(
        self,
        agent_id: UUID,
        filters: list,
        now: datetime,
        dashboard_repo: DashboardRepository,
        task_repo: TaskRepository,
        conversion_repo: ConversionHistoryRepository,
    ) -> Dict[str, Any]:
        """Assemble the agent-summary section from repository data."""
        summary_row = await dashboard_repo.get_summary_metrics(agent_id, filters)
        total_active_leads: int = summary_row.total_active_leads
        lead_score_average: int = int(summary_row.lead_score_average)

        overdue_follow_ups: int = await task_repo.count_overdue(agent_id, now)

        month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        this_month_conversions: int = await conversion_repo.count_conversions_since(
            agent_id, month_start
        )

        avg_hours = await dashboard_repo.get_average_response_time(agent_id)
        average_response_time = f"{avg_hours:.1f} hours"

        return {
            "total_active_leads": total_active_leads,
            "overdue_follow_ups": overdue_follow_ups,
            "this_month_conversions": this_month_conversions,
            "average_response_time": average_response_time,
            "lead_score_average": lead_score_average,
        }

    @staticmethod
    def _resolve_date_cutoff(
        date_range: Optional[DateRange],
        now: datetime,
        *,
        start_date: Optional[datetime] = None,
    ) -> Optional[datetime]:
        """Return the lower-bound datetime for the requested range.

        For ``DateRange.custom`` the caller-supplied *start_date* is used
        directly; for the predefined windows a timedelta is subtracted
        from *now*.
        """
        if date_range is None:
            return None
        if date_range == DateRange.custom:
            return start_date  # already validated at endpoint layer
        mapping = {
            DateRange.seven_days: timedelta(days=7),
            DateRange.thirty_days: timedelta(days=30),
            DateRange.ninety_days: timedelta(days=90),
        }
        delta = mapping.get(date_range)
        return (now - delta) if delta else None

    @staticmethod
    def _build_cache_key(
        agent_id: UUID,
        date_range: Optional[DateRange],
        status_filter: Optional[StatusFilter],
        source_filter: Optional[SourceFilter],
        *,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> str:
        dr = date_range.value if date_range else "all"
        sf = status_filter.value if status_filter else "all"
        src = source_filter.value if source_filter else "all"
        key = f"dashboard:{agent_id}:{dr}:{sf}:{src}"
        if date_range == DateRange.custom and start_date and end_date:
            key += f":{start_date.isoformat()}:{end_date.isoformat()}"
        return key

    async def _get_cached(self, key: str) -> Optional[Dict[str, Any]]:
        return await self._cache.get_json(key)

    async def _set_cached(self, key: str, data: Dict[str, Any]) -> None:
        await self._cache.set_json(key, data, ttl=settings.REDIS_CACHE_TTL)
