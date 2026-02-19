import logging
from typing import Dict, Any
from uuid import UUID

from app.core.exceptions import (
    FollowUpConflictError,
    LeadNotFoundError,
    NoAgentAssignedError,
)
from app.dependencies import LeadValidator
from app.repositories.activity_repository import ActivityRepository
from app.repositories.assignment_repository import AssignmentRepository
from app.repositories.lead_repository import LeadRepository
from app.repositories.property_interest_repository import PropertyInterestRepository
from app.repositories.task_repository import TaskRepository
from app.schemas.lead import LeadUpdate
from app.services.lead_scoring import LeadScoringEngine

logger = logging.getLogger(__name__)


class LeadUpdateService:
    """Orchestrates the lead-update workflow.

    All database operations are delegated to injected repositories.
    """

    def __init__(self, scoring_engine: LeadScoringEngine) -> None:
        self._scoring_engine = scoring_engine

    async def update_lead(
        self,
        lead_id: UUID,
        update_data: LeadUpdate,
        lead_repo: LeadRepository,
        assignment_repo: AssignmentRepository,
        activity_repo: ActivityRepository,
        task_repo: TaskRepository,
        interest_repo: PropertyInterestRepository,
    ) -> Dict[str, Any]:
        # 1. Fetch the lead
        lead = await lead_repo.get_by_id(lead_id)
        if not lead:
            raise LeadNotFoundError("Lead not found")

        # 2. Status transition
        if update_data.status:
            await LeadValidator.validate_status_transition(
                lead.status, update_data.status
            )
            await lead_repo.update_status(lead, update_data.status.value)

        # 3. Activity logging + score recalculation
        if update_data.activity:
            agent_id = await assignment_repo.get_agent_id_for_lead(lead_id)
            if not agent_id:
                raise NoAgentAssignedError("No agent assigned to lead")

            await activity_repo.create(
                lead_id=lead_id,
                agent_id=agent_id,
                type=update_data.activity.type.value,
                notes=update_data.activity.notes,
                outcome=update_data.activity.outcome.value,
            )

            last_activity_at = await activity_repo.get_last_activity_at(lead_id)
            await self._scoring_engine.update_lead_score(
                lead_id,
                {
                    "type": update_data.activity.type.value,
                    "outcome": update_data.activity.outcome.value,
                },
                lead_repo,
                last_activity_at=last_activity_at,
            )
            if update_data.activity.next_follow_up:
                next_follow_up_dt = update_data.activity.next_follow_up

                # Check for scheduling conflicts
                conflicts = await task_repo.find_conflicts(agent_id, next_follow_up_dt)
                if conflicts:
                    raise FollowUpConflictError(
                        "Agent has %d conflicting "
                        "follow-up(s) within 30 minutes" % len(conflicts)
                    )

                # Update existing or create new pending task
                existing_task = await task_repo.get_pending_for_lead(lead_id)
                if existing_task:
                    existing_task.due_date = next_follow_up_dt
                else:
                    await task_repo.create(
                        lead_id=lead_id,
                        agent_id=agent_id,
                        type="call",
                        due_date=next_follow_up_dt,
                        priority="high",
                        status="pending",
                    )

        # 5. Property interests
        if update_data.property_interests:
            for pi in update_data.property_interests:
                await interest_repo.create(
                    lead_id=lead_id,
                    property_id=pi.property_id,
                    interest_level=pi.interest_level.value,
                )

        await lead_repo.commit()

        # Re-fetch to get the latest score/status after all changes
        updated_lead = await lead_repo.get_by_id(lead_id)
        return {
            "lead_id": updated_lead.lead_id,
            "status": updated_lead.status,
            "score": updated_lead.score,
        }
