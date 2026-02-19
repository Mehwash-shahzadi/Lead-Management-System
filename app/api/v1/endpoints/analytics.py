from typing import Optional

from fastapi import APIRouter, Depends, Query

from app.schemas.analytics import PaginatedResponse
from app.services.analytics import LeadAnalytics
from app.api.deps import get_analytics_service

router = APIRouter(prefix="/analytics", tags=["Analytics"])


# --- Task 4.1: Lead Performance Analytics ---


@router.get("/conversion-rates", response_model=PaginatedResponse)
async def lead_conversion_rates(
    cursor: Optional[str] = Query(None, description="Keyset cursor for next page"),
    skip: int = Query(0, ge=0, description="Number of rows to skip"),
    limit: int = Query(50, ge=1, le=500, description="Max rows to return"),
    service: LeadAnalytics = Depends(get_analytics_service),
) -> PaginatedResponse:
    """Lead conversion rates by source and agent."""
    return await service.get_lead_conversion_rates_by_source_and_agent(
        cursor=cursor,
        skip=skip,
        limit=limit,
    )


@router.get("/avg-conversion-time", response_model=PaginatedResponse)
async def avg_conversion_time(
    skip: int = Query(0, ge=0, description="Number of rows to skip"),
    limit: int = Query(50, ge=1, le=500, description="Max rows to return"),
    service: LeadAnalytics = Depends(get_analytics_service),
) -> PaginatedResponse:
    """Average time to conversion by property type."""
    return await service.get_average_time_to_conversion_by_property_type(
        skip=skip, limit=limit
    )


@router.get("/monthly-trends", response_model=PaginatedResponse)
async def monthly_lead_trends(
    cursor: Optional[str] = Query(None, description="Keyset cursor for next page"),
    skip: int = Query(0, ge=0, description="Number of rows to skip"),
    limit: int = Query(50, ge=1, le=500, description="Max rows to return"),
    service: LeadAnalytics = Depends(get_analytics_service),
) -> PaginatedResponse:
    """Monthly lead volume trends."""
    return await service.get_monthly_lead_volume_trends(
        cursor=cursor,
        skip=skip,
        limit=limit,
    )


@router.get("/agent-rankings", response_model=PaginatedResponse)
async def agent_rankings(
    skip: int = Query(0, ge=0, description="Number of rows to skip"),
    limit: int = Query(50, ge=1, le=500, description="Max rows to return"),
    service: LeadAnalytics = Depends(get_analytics_service),
) -> PaginatedResponse:
    """Agent performance rankings."""
    return await service.get_agent_performance_rankings(skip=skip, limit=limit)


@router.get("/revenue-attribution", response_model=PaginatedResponse)
async def revenue_attribution(
    skip: int = Query(0, ge=0, description="Number of rows to skip"),
    limit: int = Query(50, ge=1, le=500, description="Max rows to return"),
    service: LeadAnalytics = Depends(get_analytics_service),
) -> PaginatedResponse:
    """Revenue attribution by lead source."""
    return await service.get_revenue_attribution_by_lead_source(skip=skip, limit=limit)


# --- Task 4.2: Lead Quality Analysis ---


@router.get("/high-score-not-converted", response_model=PaginatedResponse)
async def high_score_not_converted(
    skip: int = Query(0, ge=0, description="Number of rows to skip"),
    limit: int = Query(50, ge=1, le=500, description="Max rows to return"),
    service: LeadAnalytics = Depends(get_analytics_service),
) -> PaginatedResponse:
    """High-scoring leads that did not convert."""
    return await service.get_high_scoring_leads_not_converted(skip=skip, limit=limit)


@router.get("/low-score-converted", response_model=PaginatedResponse)
async def low_score_converted(
    skip: int = Query(0, ge=0, description="Number of rows to skip"),
    limit: int = Query(50, ge=1, le=500, description="Max rows to return"),
    service: LeadAnalytics = Depends(get_analytics_service),
) -> PaginatedResponse:
    """Low-scoring leads that converted."""
    return await service.get_low_scoring_leads_converted(skip=skip, limit=limit)


@router.get("/source-quality", response_model=PaginatedResponse)
async def source_quality(
    skip: int = Query(0, ge=0, description="Number of rows to skip"),
    limit: int = Query(50, ge=1, le=500, description="Max rows to return"),
    service: LeadAnalytics = Depends(get_analytics_service),
) -> PaginatedResponse:
    """Source quality comparison over time."""
    return await service.get_source_quality_comparison_over_time(skip=skip, limit=limit)


@router.get("/follow-up-timing", response_model=PaginatedResponse)
async def follow_up_timing(
    skip: int = Query(0, ge=0, description="Number of rows to skip"),
    limit: int = Query(50, ge=1, le=500, description="Max rows to return"),
    service: LeadAnalytics = Depends(get_analytics_service),
) -> PaginatedResponse:
    """Optimal follow-up timing analysis."""
    return await service.get_optimal_follow_up_timing_analysis(skip=skip, limit=limit)


# --- Task 4.3: Agent Workload Optimization ---


@router.get("/workload-distribution", response_model=PaginatedResponse)
async def workload_distribution(
    cursor: Optional[str] = Query(None, description="Keyset cursor for next page"),
    skip: int = Query(0, ge=0, description="Number of rows to skip"),
    limit: int = Query(50, ge=1, le=500, description="Max rows to return"),
    service: LeadAnalytics = Depends(get_analytics_service),
) -> PaginatedResponse:
    """Current workload distribution."""
    return await service.get_current_workload_distribution(
        cursor=cursor,
        skip=skip,
        limit=limit,
    )


@router.get("/approaching-capacity", response_model=PaginatedResponse)
async def approaching_capacity(
    threshold: int = Query(40, ge=1, le=50),
    cursor: Optional[str] = Query(None, description="Keyset cursor for next page"),
    skip: int = Query(0, ge=0, description="Number of rows to skip"),
    limit: int = Query(50, ge=1, le=500, description="Max rows to return"),
    service: LeadAnalytics = Depends(get_analytics_service),
) -> PaginatedResponse:
    """Agents approaching maximum capacity."""
    return await service.get_agents_approaching_maximum_capacity(
        threshold,
        cursor=cursor,
        skip=skip,
        limit=limit,
    )


@router.get("/specialized-vs-general", response_model=PaginatedResponse)
async def specialized_vs_general(
    skip: int = Query(0, ge=0, description="Number of rows to skip"),
    limit: int = Query(50, ge=1, le=500, description="Max rows to return"),
    service: LeadAnalytics = Depends(get_analytics_service),
) -> PaginatedResponse:
    """Specialized vs general agent performance."""
    return await service.get_specialized_vs_general_agent_performance(
        skip=skip, limit=limit
    )


@router.get("/response-time-correlation", response_model=PaginatedResponse)
async def response_time_correlation(
    skip: int = Query(0, ge=0, description="Number of rows to skip"),
    limit: int = Query(50, ge=1, le=500, description="Max rows to return"),
    service: LeadAnalytics = Depends(get_analytics_service),
) -> PaginatedResponse:
    """Lead response time correlation with conversion."""
    return await service.get_lead_response_time_correlation_with_conversion(
        skip=skip, limit=limit
    )
