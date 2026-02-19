from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Query
from uuid import UUID
from typing import Optional

from app.schemas.agent import AgentDashboardResponse
from app.schemas.analytics import DateRange, StatusFilter, SourceFilter
from app.services.agent_dashboard_service import AgentDashboardService
from app.repositories.agent_repository import AgentRepository
from app.repositories.dashboard_repository import DashboardRepository
from app.repositories.task_repository import TaskRepository
from app.repositories.conversion_history_repository import ConversionHistoryRepository
from app.api.deps import (
    get_agent_dashboard_service,
    get_agent_repo,
    get_dashboard_repo,
    get_task_repo,
    get_conversion_repo,
)

router = APIRouter(prefix="/agents", tags=["Agents"])


@router.get("/{agent_id}/dashboard", response_model=AgentDashboardResponse)
async def get_agent_dashboard(
    agent_id: UUID,
    date_range: Optional[DateRange] = Query(None),
    status_filter: Optional[StatusFilter] = Query(None),
    source_filter: Optional[SourceFilter] = Query(None),
    start_date: Optional[datetime] = Query(
        None,
        description="Custom range start (ISO 8601). Required when date_range=custom.",
    ),
    end_date: Optional[datetime] = Query(
        None,
        description="Custom range end (ISO 8601). Required when date_range=custom.",
    ),
    service: AgentDashboardService = Depends(get_agent_dashboard_service),
    agent_repo: AgentRepository = Depends(get_agent_repo),
    dashboard_repo: DashboardRepository = Depends(get_dashboard_repo),
    task_repo: TaskRepository = Depends(get_task_repo),
    conversion_repo: ConversionHistoryRepository = Depends(get_conversion_repo),
) -> AgentDashboardResponse:
    """Return the full agent dashboard.

    When ``date_range=custom``, both ``start_date`` and ``end_date``
    query parameters must be provided.

    Business logic is delegated to :class:`AgentDashboardService`.
    """
    agent = await agent_repo.get_by_id(agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")

    # Validate custom date-range parameters
    if date_range == DateRange.custom:
        if not start_date or not end_date:
            raise HTTPException(
                status_code=400,
                detail="start_date and end_date are required when date_range=custom",
            )
        if start_date >= end_date:
            raise HTTPException(
                status_code=400,
                detail="start_date must be before end_date",
            )

    data = await service.get_dashboard_data(
        agent_id=agent_id,
        date_range=date_range,
        status_filter=status_filter,
        source_filter=source_filter,
        start_date=start_date,
        end_date=end_date,
        dashboard_repo=dashboard_repo,
        task_repo=task_repo,
        conversion_repo=conversion_repo,
    )
    return AgentDashboardResponse(**data)
