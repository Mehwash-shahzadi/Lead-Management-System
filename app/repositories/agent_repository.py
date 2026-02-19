from typing import List, Optional
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.orm import selectinload

from app.models.agent import Agent
from app.repositories.base import BaseRepository


class AgentRepository(BaseRepository):
    """Encapsulates every SQL query that touches the ``agents`` table."""

    async def get_by_id(self, agent_id: UUID) -> Optional[Agent]:
        """Return a single agent by primary key, or ``None``."""
        result = await self._db.execute(select(Agent).where(Agent.agent_id == agent_id))
        return result.scalar_one_or_none()

    async def get_active_leads_count(self, agent_id: UUID) -> Optional[int]:
        """Return the ``active_leads_count`` for an agent, or ``None``."""
        result = await self._db.execute(
            select(Agent.active_leads_count).where(Agent.agent_id == agent_id)
        )
        return result.scalar_one_or_none()

    async def get_available_agents(self, max_leads: int = 50) -> List[Agent]:
        """Return agents whose active lead count is below *max_leads*.

        Eagerly loads ``performance_metrics`` so the assignment manager
        can factor in conversion rates without extra queries.
        """
        result = await self._db.execute(
            select(Agent)
            .where(Agent.active_leads_count < max_leads)
            .options(selectinload(Agent.performance_metrics))
        )
        return list(result.scalars().all())

    async def increment_active_leads(self, agent_id: UUID) -> None:
        """Increment ``active_leads_count`` by 1."""
        await self._db.execute(
            update(Agent)
            .where(Agent.agent_id == agent_id)
            .values(active_leads_count=Agent.active_leads_count + 1)
        )

    async def decrement_active_leads(self, agent_id: UUID) -> None:
        """Decrement ``active_leads_count`` by 1."""
        await self._db.execute(
            update(Agent)
            .where(Agent.agent_id == agent_id)
            .values(active_leads_count=Agent.active_leads_count - 1)
        )
