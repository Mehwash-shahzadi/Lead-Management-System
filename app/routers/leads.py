from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, func
from datetime import datetime, timedelta, timezone
from uuid import uuid4, UUID
from typing import Optional

from app.database import get_db
from app.schemas.lead import LeadCaptureRequest, LeadCaptureResponse, LeadUpdate, LeadUpdateResponse
from app.services.lead_scoring import LeadScoringEngine
from app.services.lead_assignment import LeadAssignmentManager
from app.models.lead import Lead
from app.models.agent import Agent
from app.models.assignment import LeadAssignment
from app.models.lead_source import LeadSource
from app.models.task import FollowUpTask
from app.models.activity import LeadActivity
from app.models.property_interest import LeadPropertyInterest
from app.dependencies import LeadValidator
from app.exceptions import AgentOverloadError

router = APIRouter(prefix="/api/v1/leads")


@router.post("/capture", response_model=LeadCaptureResponse)
async def capture_lead(
    request: LeadCaptureRequest,
    db: AsyncSession = Depends(get_db)
) -> LeadCaptureResponse:
    # Validate lead data
    await LeadValidator.validate_lead_data(request.lead_data.dict())

    # Check for duplicate lead (same phone + source_type within 24h)
    await LeadValidator.check_duplicate_lead(request.lead_data.phone, request.source_type, db)

    # Check property service availability
    await LeadValidator.check_property_service()

    # Calculate lead score
    scoring_engine = LeadScoringEngine()
    lead_score = await scoring_engine.calculate_lead_score(request.lead_data.dict(), request.source_details.dict(), db)

    # Assign agent
    assignment_manager = LeadAssignmentManager()
    agent_id = await assignment_manager.assign_lead(request.lead_data.dict(), db)
    if not agent_id:
        raise AgentOverloadError()

    # Validate agent capacity
    await LeadValidator.validate_agent_capacity(agent_id, db)

    # Create lead record
    lead_id = uuid4()
    lead = Lead(
        lead_id=lead_id,
        source_type=request.source_type,
        first_name=request.lead_data.first_name,
        last_name=request.lead_data.last_name,
        email=request.lead_data.email,
        phone=request.lead_data.phone,
        nationality=request.lead_data.nationality,
        language_preference=request.lead_data.language_preference,
        budget_min=request.lead_data.budget_min,
        budget_max=request.lead_data.budget_max,
        property_type=request.lead_data.property_type,
        preferred_areas=request.lead_data.preferred_areas,
        status="new",
        score=lead_score
    )
    db.add(lead)

    # Validate referrer_agent_id if provided
    referrer_agent_id = None
    if request.source_details.referrer_agent_id:
        # Check if the agent exists
        agent_query = select(Agent).where(Agent.agent_id == request.source_details.referrer_agent_id)
        agent_result = await db.execute(agent_query)
        agent = agent_result.scalar_one_or_none()
        if agent:
            referrer_agent_id = request.source_details.referrer_agent_id

    # Create lead_sources record
    lead_source = LeadSource(
        lead_id=lead_id,
        source_type=request.source_type,
        campaign_id=request.source_details.campaign_id,
        referrer_agent_id=referrer_agent_id,
        property_id=request.source_details.property_id,
        utm_source=request.source_details.utm_source
    )
    db.add(lead_source)

    # Create initial FollowUpTask
    follow_up_task = FollowUpTask(
        lead_id=lead_id,
        agent_id=agent_id,
        type="call",
        due_date=datetime.now(timezone.utc) + timedelta(hours=24),
        priority="high",
        status="pending"
    )
    db.add(follow_up_task)

    # Create LeadAssignment record and update agent count
    lead_assignment = LeadAssignment(
        lead_id=lead_id,
        agent_id=agent_id,
        reason="Initial assignment"
    )
    db.add(lead_assignment)
    
    # Update agent active leads count
    await db.execute(update(Agent).where(Agent.agent_id == agent_id).values(active_leads_count=Agent.active_leads_count + 1))

    # Get assigned agent details
    agent_query = select(Agent).where(Agent.agent_id == agent_id)
    agent_result = await db.execute(agent_query)
    agent = agent_result.scalar_one()

    await db.commit()

    return LeadCaptureResponse(
        lead_id=lead_id,
        assigned_agent={
            "agent_id": agent.agent_id,
            "name": agent.full_name,
            "phone": agent.phone
        },
        lead_score=lead_score,
        next_follow_up=follow_up_task.due_date
    )


@router.put("/{lead_id}/update", response_model=LeadUpdateResponse)
async def update_lead(
    lead_id: UUID,
    update_data: LeadUpdate,
    db: AsyncSession = Depends(get_db)
) -> LeadUpdateResponse:
    # Get the lead
    lead_query = select(Lead).where(Lead.lead_id == lead_id)
    result = await db.execute(lead_query)
    lead = result.scalar_one_or_none()
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")

    # Validate status transition if status is being updated
    if update_data.status:
        await LeadValidator.validate_status_transition(lead.status, update_data.status)
        lead.status = update_data.status.value

    # If activity provided, create LeadActivity
    if update_data.activity:
        # Get agent_id from assignment
        agent_query = select(LeadAssignment.agent_id).where(LeadAssignment.lead_id == lead_id)
        agent_result = await db.execute(agent_query)
        agent_id = agent_result.scalar_one_or_none()
        if not agent_id:
            raise HTTPException(status_code=422, detail="No agent assigned to lead")

        activity = LeadActivity(
            lead_id=lead_id,
            agent_id=agent_id,
            type=update_data.activity.type.value,
            notes=update_data.activity.notes,
            outcome=update_data.activity.outcome.value
        )
        db.add(activity)

        # Update lead score
        scoring_engine = LeadScoringEngine()
        await scoring_engine.update_lead_score(lead_id, {"type": update_data.activity.type.value, "outcome": update_data.activity.outcome.value}, db)

        # If next_follow_up, check for conflicts and update or create FollowUpTask
        if update_data.activity.next_follow_up:
            from datetime import datetime
            next_follow_up_dt = datetime.fromisoformat(update_data.activity.next_follow_up.replace('Z', '+00:00'))

            # Check for follow-up conflicts
            await LeadValidator.check_follow_up_conflicts(agent_id, next_follow_up_dt, db=db)

            # Check if there's an existing pending task
            task_query = select(FollowUpTask).where(
                FollowUpTask.lead_id == lead_id,
                FollowUpTask.status == "pending"
            )
            task_result = await db.execute(task_query)
            existing_task = task_result.scalar_one_or_none()
            if existing_task:
                existing_task.due_date = next_follow_up_dt
            else:
                new_task = FollowUpTask(
                    lead_id=lead_id,
                    agent_id=agent_id,
                    type="call",
                    due_date=next_follow_up_dt,
                    priority="high",
                    status="pending"
                )
                db.add(new_task)

    # If property_interests provided, create LeadPropertyInterest
    if update_data.property_interests:
        for pi in update_data.property_interests:
            interest = LeadPropertyInterest(
                lead_id=lead_id,
                property_id=pi.property_id,
                interest_level=pi.interest_level.value
            )
            db.add(interest)

    await db.commit()
    return LeadUpdateResponse()
