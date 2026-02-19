from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
from uuid import UUID

from sqlalchemy import select, func, and_

from app.models.task import FollowUpTask
from app.models.lead import Lead
from app.repositories.base import BaseRepository


class TaskRepository(BaseRepository):
    """Encapsulates queries against the ``follow_up_tasks`` table."""

    async def get_pending_for_lead(self, lead_id: UUID) -> Optional[FollowUpTask]:
        """Return the first pending task for a lead, or ``None``."""
        result = await self._db.execute(
            select(FollowUpTask).where(
                FollowUpTask.lead_id == lead_id,
                FollowUpTask.status == "pending",
            )
        )
        return result.scalar_one_or_none()

    async def create(self, **kwargs: Any) -> FollowUpTask:
        """Insert a new follow-up task."""
        task = FollowUpTask(**kwargs)
        self._db.add(task)
        return task

    async def find_conflicts(
        self,
        agent_id: UUID,
        follow_up_time: datetime,
        window_minutes: int = 30,
        exclude_task_id: Optional[UUID] = None,
    ) -> List[FollowUpTask]:
        """Return pending tasks within *window_minutes* of *follow_up_time*."""
        window_start = follow_up_time - timedelta(minutes=window_minutes)
        window_end = follow_up_time + timedelta(minutes=window_minutes)

        query = select(FollowUpTask).where(
            FollowUpTask.agent_id == agent_id,
            FollowUpTask.due_date.between(window_start, window_end),
            FollowUpTask.status == "pending",
        )
        if exclude_task_id:
            query = query.where(FollowUpTask.task_id != exclude_task_id)

        result = await self._db.execute(query)
        return list(result.scalars().all())

    async def count_overdue(self, agent_id: UUID, now: datetime) -> int:
        """Count overdue pending tasks for an agent."""
        query = select(func.count(FollowUpTask.task_id)).where(
            and_(
                FollowUpTask.agent_id == agent_id,
                FollowUpTask.due_date < now,
                FollowUpTask.status == "pending",
            )
        )
        return (await self._db.execute(query)).scalar()

    async def get_pending_tasks_with_lead_name(
        self, agent_id: UUID
    ) -> List[Dict[str, Any]]:
        """Return pending tasks with associated lead names, ordered by due date."""
        query = (
            select(
                FollowUpTask.task_id,
                func.concat(Lead.first_name, " ", Lead.last_name).label("lead_name"),
                FollowUpTask.type.label("task_type"),
                FollowUpTask.due_date,
                FollowUpTask.priority,
            )
            .select_from(FollowUpTask)
            .join(Lead, FollowUpTask.lead_id == Lead.lead_id)
            .where(
                and_(
                    FollowUpTask.agent_id == agent_id,
                    FollowUpTask.status == "pending",
                )
            )
            .order_by(FollowUpTask.due_date.asc())
        )
        rows = await self._db.execute(query)
        return [
            {
                "task_id": str(row.task_id),
                "lead_name": row.lead_name,
                "task_type": row.task_type,
                "due_date": row.due_date.isoformat(),
                "priority": row.priority,
            }
            for row in rows
        ]
