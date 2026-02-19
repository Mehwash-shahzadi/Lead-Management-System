"""API-layer dependency functions.

Re-exports all dependency factories from ``app.dependencies`` so that
endpoint modules only need to import from ``app.api.deps``.
"""

from app.dependencies import (
    # Repository factories
    get_lead_repo,
    get_agent_repo,
    get_assignment_repo,
    get_task_repo,
    get_activity_repo,
    get_source_repo,
    get_interest_repo,
    get_conversion_repo,
    get_dashboard_repo,
    get_analytics_repo,
    # Service factories
    get_scoring_engine,
    get_assignment_manager,
    get_lead_capture_service,
    get_lead_update_service,
    get_agent_dashboard_service,
    get_analytics_service,
    get_property_suggestion_service,
    # Redis
    get_redis_client,
)

__all__ = [
    "get_lead_repo",
    "get_agent_repo",
    "get_assignment_repo",
    "get_task_repo",
    "get_activity_repo",
    "get_source_repo",
    "get_interest_repo",
    "get_conversion_repo",
    "get_dashboard_repo",
    "get_analytics_repo",
    "get_scoring_engine",
    "get_assignment_manager",
    "get_lead_capture_service",
    "get_lead_update_service",
    "get_agent_dashboard_service",
    "get_analytics_service",
    "get_property_suggestion_service",
    "get_redis_client",
]
