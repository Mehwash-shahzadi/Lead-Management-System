from fastapi import APIRouter, Depends, Request
from uuid import UUID

from app.core.rate_limit import limiter
from app.schemas.lead import (
    LeadCaptureRequest,
    LeadCaptureResponse,
    LeadUpdate,
    LeadUpdateResponse,
)
from app.services.lead_capture_service import LeadCaptureService
from app.services.lead_update_service import LeadUpdateService
from app.repositories.lead_repository import LeadRepository
from app.repositories.agent_repository import AgentRepository
from app.repositories.assignment_repository import AssignmentRepository
from app.repositories.lead_source_repository import LeadSourceRepository
from app.repositories.task_repository import TaskRepository
from app.repositories.activity_repository import ActivityRepository
from app.repositories.property_interest_repository import PropertyInterestRepository
from app.api.deps import (
    get_lead_capture_service,
    get_lead_update_service,
    get_lead_repo,
    get_agent_repo,
    get_assignment_repo,
    get_source_repo,
    get_task_repo,
    get_activity_repo,
    get_interest_repo,
)

router = APIRouter(prefix="/leads", tags=["Leads"])


@router.post(
    "/capture",
    response_model=LeadCaptureResponse,
    status_code=201,
)
@limiter.limit("10/minute")
async def capture_lead(
    request: Request,
    request_body: LeadCaptureRequest,
    service: LeadCaptureService = Depends(get_lead_capture_service),
    lead_repo: LeadRepository = Depends(get_lead_repo),
    agent_repo: AgentRepository = Depends(get_agent_repo),
    assignment_repo: AssignmentRepository = Depends(get_assignment_repo),
    source_repo: LeadSourceRepository = Depends(get_source_repo),
    task_repo: TaskRepository = Depends(get_task_repo),
) -> LeadCaptureResponse:
    """Capture a new lead.

    Rate-limited to 10 requests/minute per IP to prevent abuse.
    Business logic is delegated to :class:`LeadCaptureService`.
    Property suggestions are handled by the injected
    :class:`PropertySuggestionService` within the capture service.
    """
    result = await service.capture_lead(
        source_type=request_body.source_type,
        lead_data=request_body.lead_data,
        source_details=request_body.source_details.model_dump(),
        lead_repo=lead_repo,
        agent_repo=agent_repo,
        assignment_repo=assignment_repo,
        source_repo=source_repo,
        task_repo=task_repo,
    )
    return LeadCaptureResponse(**result)


@router.put("/{lead_id}/update", response_model=LeadUpdateResponse)
async def update_lead(
    lead_id: UUID,
    update_data: LeadUpdate,
    service: LeadUpdateService = Depends(get_lead_update_service),
    lead_repo: LeadRepository = Depends(get_lead_repo),
    assignment_repo: AssignmentRepository = Depends(get_assignment_repo),
    activity_repo: ActivityRepository = Depends(get_activity_repo),
    task_repo: TaskRepository = Depends(get_task_repo),
    interest_repo: PropertyInterestRepository = Depends(get_interest_repo),
) -> LeadUpdateResponse:
    """Update an existing lead.

    Business logic is delegated to :class:`LeadUpdateService`.
    """
    result = await service.update_lead(
        lead_id=lead_id,
        update_data=update_data,
        lead_repo=lead_repo,
        assignment_repo=assignment_repo,
        activity_repo=activity_repo,
        task_repo=task_repo,
        interest_repo=interest_repo,
    )
    return LeadUpdateResponse(**result)
