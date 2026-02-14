"""Dependencies and validation functions for ThinkRealty application."""

from fastapi import HTTPException, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from datetime import datetime, timedelta, timezone
from typing import Dict, Any
from uuid import UUID

from app.database import get_db
from app.models.lead import Lead
from app.models.agent import Agent
from app.models.task import FollowUpTask
from app.models.assignment import LeadAssignment
from app.exceptions import (
    DuplicateLeadError,
    AgentOverloadError,
    InvalidLeadDataError,
    FollowUpConflictError,
    InvalidStatusTransitionError,
    PropertyServiceUnavailableError
)
from app.schemas.lead import LeadStatus


class LeadValidator:
    """Validation logic for leads."""

    @staticmethod
    async def check_duplicate_lead(phone: str, source_type: str, db: AsyncSession) -> None:
        """Check for duplicate leads within 24 hours."""
        twenty_four_hours_ago = datetime.now(timezone.utc) - timedelta(hours=24)
        duplicate_query = select(Lead).where(
            Lead.phone == phone,
            Lead.source_type == source_type,
            Lead.created_at >= twenty_four_hours_ago
        )
        result = await db.execute(duplicate_query)
        if result.scalar_one_or_none():
            raise DuplicateLeadError()

    @staticmethod
    async def validate_status_transition(current_status: str, new_status: LeadStatus) -> None:
        """Validate status transitions."""
        valid_transitions = {
            "new": ["contacted", "lost"],
            "contacted": ["qualified", "lost"],
            "qualified": ["viewing_scheduled", "lost"],
            "viewing_scheduled": ["negotiation", "qualified", "lost"],
            "negotiation": ["converted", "lost"],
            "converted": [],  # Terminal state
            "lost": []  # Terminal state
        }

        if new_status.value not in valid_transitions.get(current_status, []):
            raise InvalidStatusTransitionError(
                f"Cannot transition from {current_status} to {new_status.value}"
            )

    @staticmethod
    async def validate_agent_capacity(agent_id: UUID, db: AsyncSession) -> None:
        """Check if agent has capacity for new leads."""
        agent_query = select(Agent.active_leads_count).where(Agent.agent_id == agent_id)
        result = await db.execute(agent_query)
        active_count = result.scalar_one_or_none()

        if active_count is None:
            raise HTTPException(status_code=404, detail="Agent not found")

        if active_count >= 50:
            raise AgentOverloadError()

    @staticmethod
    async def check_follow_up_conflicts(
        agent_id: UUID,
        follow_up_time: datetime,
        exclude_task_id: UUID = None,
        db: AsyncSession = None
    ) -> None:
        """Check for conflicting follow-up schedules."""
        # Check for tasks within 30 minutes of the scheduled time
        time_window_start = follow_up_time - timedelta(minutes=30)
        time_window_end = follow_up_time + timedelta(minutes=30)

        query = select(FollowUpTask).where(
            FollowUpTask.agent_id == agent_id,
            FollowUpTask.due_date.between(time_window_start, time_window_end),
            FollowUpTask.status == "pending"
        )

        if exclude_task_id:
            query = query.where(FollowUpTask.task_id != exclude_task_id)

        result = await db.execute(query)
        conflicting_tasks = result.scalars().all()

        if conflicting_tasks:
            raise FollowUpConflictError(
                f"Agent has {len(conflicting_tasks)} conflicting follow-up(s) within 30 minutes"
            )

    @staticmethod
    async def validate_lead_data(lead_data: Dict[str, Any]) -> None:
        """Validate lead data fields."""
        errors = []

        # Budget validation
        if lead_data.get("budget_min") and lead_data.get("budget_max"):
            if lead_data["budget_min"] >= lead_data["budget_max"]:
                errors.append("budget_min must be less than budget_max")

        # Phone format is already validated by Pydantic pattern

        # Required fields are validated by Pydantic

        if errors:
            raise InvalidLeadDataError("; ".join(errors))

    @staticmethod
    async def check_property_service() -> None:
        """Mock check for property service availability."""
        import random
        if random.random() < 0.1:
            raise PropertyServiceUnavailableError()


# Dependency functions
async def get_validated_db() -> AsyncSession:
    """Get database session with validation setup."""
    return Depends(get_db)