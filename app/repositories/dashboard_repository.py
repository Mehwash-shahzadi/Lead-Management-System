from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from sqlalchemy import select, func, and_, case, text

from app.models.lead import Lead
from app.models.assignment import LeadAssignment
from app.models.task import FollowUpTask
from app.models.activity import LeadActivity
from app.repositories.base import BaseRepository


class DashboardRepository(BaseRepository):
    """All database queries needed by the agent dashboard."""

    @staticmethod
    def build_filters(
        agent_id: UUID,
        date_cutoff: Optional[datetime] = None,
        status_filter: Optional[str] = None,
        source_filter: Optional[str] = None,
        *,
        date_upper: Optional[datetime] = None,
    ) -> list:
        """Build SQLAlchemy column-level filter expressions for dashboard queries.

        This encapsulates all ORM filter construction inside the repository
        layer, keeping the service free of SQLAlchemy model references.

        Args:
            agent_id: The agent whose dashboard is being built.
            date_cutoff: Lower-bound datetime for the date range filter.
            status_filter: Raw status-filter value (``"active"``, ``"converted"``,
                ``"lost"``, or ``None``/``"all"`` for no filter).
            source_filter: Raw source-filter value (e.g. ``"bayut"``) or
                ``None``/``"all"`` for no filter.
            date_upper: Upper-bound datetime for custom date ranges.

        Returns:
            A list of SQLAlchemy ``BinaryExpression`` objects suitable for
            passing to ``.where(and_(*filters))``.
        """
        filters = [LeadAssignment.agent_id == agent_id]
        if date_cutoff:
            filters.append(Lead.created_at >= date_cutoff)
        if date_upper:
            filters.append(Lead.created_at <= date_upper)
        if status_filter and status_filter != "all":
            if status_filter == "active":
                filters.append(Lead.status.notin_(["converted", "lost"]))
            elif status_filter == "converted":
                filters.append(Lead.status == "converted")
            elif status_filter == "lost":
                filters.append(Lead.status == "lost")
        if source_filter and source_filter != "all":
            filters.append(Lead.source_type == source_filter)
        return filters

    async def get_summary_metrics(self, agent_id: UUID, filters: list) -> Any:
        """Return active-lead count and average score in one query."""
        query = (
            select(
                func.count(
                    case((Lead.status.notin_(["converted", "lost"]), Lead.lead_id))
                ).label("total_active_leads"),
                func.coalesce(func.avg(Lead.score), 0).label("lead_score_average"),
            )
            .select_from(Lead)
            .join(LeadAssignment, Lead.lead_id == LeadAssignment.lead_id)
            .where(and_(*filters))
        )
        return (await self._db.execute(query)).one()

    async def get_average_response_time(self, agent_id: UUID) -> float:
        """Return average response time in hours for an agent."""
        query = (
            select(
                func.avg(
                    func.extract(
                        "epoch",
                        LeadActivity.activity_at - LeadAssignment.assigned_at,
                    )
                    / 3600
                )
            )
            .select_from(LeadActivity)
            .join(LeadAssignment, LeadActivity.lead_id == LeadAssignment.lead_id)
            .where(LeadAssignment.agent_id == agent_id)
        )
        return (await self._db.execute(query)).scalar() or 0

    async def get_recent_leads(
        self, agent_id: UUID, filters: list, limit: int = 10
    ) -> List[Dict[str, Any]]:
        """Return the most recently active leads with follow-up info."""
        query = (
            select(
                Lead.lead_id,
                func.concat(Lead.first_name, " ", Lead.last_name).label("name"),
                Lead.phone,
                Lead.source_type.label("source"),
                Lead.status,
                Lead.score,
                func.max(LeadActivity.activity_at).label("last_activity"),
                func.min(
                    case(
                        (FollowUpTask.status == "pending", FollowUpTask.due_date),
                        else_=None,
                    )
                ).label("next_follow_up"),
            )
            .select_from(Lead)
            .join(LeadAssignment, Lead.lead_id == LeadAssignment.lead_id)
            .outerjoin(LeadActivity, Lead.lead_id == LeadActivity.lead_id)
            .outerjoin(
                FollowUpTask,
                and_(
                    Lead.lead_id == FollowUpTask.lead_id,
                    FollowUpTask.agent_id == agent_id,
                ),
            )
            .where(and_(*filters))
            .group_by(Lead.lead_id)
            .order_by(func.max(LeadActivity.activity_at).desc())
            .limit(limit)
        )
        rows = await self._db.execute(query)
        return [
            {
                "lead_id": str(row.lead_id),
                "name": row.name,
                "phone": row.phone,
                "source": row.source,
                "status": row.status,
                "score": row.score,
                "last_activity": (
                    row.last_activity.isoformat() if row.last_activity else None
                ),
                "next_follow_up": (
                    row.next_follow_up.isoformat() if row.next_follow_up else None
                ),
            }
            for row in rows
        ]

    async def get_performance_metrics(self, agent_id: UUID) -> Dict[str, Any]:
        """Return conversion rate, average deal size, and response-time rank."""
        # Conversion rate + deal size
        perf_query = (
            select(
                func.count(Lead.lead_id).label("total_leads"),
                func.count(case((Lead.status == "converted", Lead.lead_id))).label(
                    "converted_leads"
                ),
                func.coalesce(
                    func.avg(case((Lead.status == "converted", Lead.budget_max))),
                    0,
                ).label("average_deal_size"),
            )
            .select_from(Lead)
            .join(LeadAssignment, Lead.lead_id == LeadAssignment.lead_id)
            .where(LeadAssignment.agent_id == agent_id)
        )
        perf_row = (await self._db.execute(perf_query)).one()

        total_leads: int = perf_row.total_leads
        converted_leads: int = perf_row.converted_leads
        conversion_rate: float = (
            (converted_leads / total_leads) * 100 if total_leads > 0 else 0.0
        )

        # Response-time rank
        rank_query = text("""
            SELECT rank FROM (
                SELECT la2.agent_id,
                       AVG(EXTRACT(EPOCH FROM (la.activity_at - la2.assigned_at)) / 3600)
                           AS avg_response,
                       RANK() OVER (
                           ORDER BY AVG(EXTRACT(EPOCH FROM
                               (la.activity_at - la2.assigned_at)) / 3600) ASC
                       ) AS rank
                FROM lead_activities la
                JOIN lead_assignments la2 ON la.lead_id = la2.lead_id
                GROUP BY la2.agent_id
            ) ranks WHERE agent_id = :agent_id
        """)
        rank_result = await self._db.execute(rank_query, {"agent_id": agent_id})
        response_time_rank: int = rank_result.scalar() or 0

        return {
            "conversion_rate": conversion_rate,
            "average_deal_size": int(perf_row.average_deal_size),
            "response_time_rank": response_time_rank,
        }
