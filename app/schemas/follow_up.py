from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class PendingTask(BaseModel):
    """A single pending follow-up task shown on the dashboard."""

    task_id: UUID
    lead_name: str
    task_type: str  # "call|email|whatsapp|viewing"
    due_date: datetime
    priority: str  # "high|medium|low"
