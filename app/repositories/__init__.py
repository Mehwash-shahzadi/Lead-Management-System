"""Repository layer – all database access goes through here.

Repositories encapsulate SQLAlchemy queries and raw SQL so that the
service layer only contains business logic.
"""

from app.repositories.lead_repository import LeadRepository
from app.repositories.agent_repository import AgentRepository
from app.repositories.assignment_repository import AssignmentRepository
from app.repositories.task_repository import TaskRepository
from app.repositories.activity_repository import ActivityRepository
from app.repositories.lead_source_repository import LeadSourceRepository
from app.repositories.property_interest_repository import PropertyInterestRepository
from app.repositories.conversion_history_repository import ConversionHistoryRepository
from app.repositories.analytics_repository import AnalyticsRepository
from app.repositories.scoring_rule_repository import ScoringRuleRepository

__all__ = [
    "LeadRepository",
    "AgentRepository",
    "AssignmentRepository",
    "TaskRepository",
    "ActivityRepository",
    "LeadSourceRepository",
    "PropertyInterestRepository",
    "ConversionHistoryRepository",
    "AnalyticsRepository",
    "ScoringRuleRepository",
]
