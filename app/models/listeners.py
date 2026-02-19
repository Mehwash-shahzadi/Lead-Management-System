from datetime import datetime, timezone
from sqlalchemy import event
from app.models.lead import Lead
from app.models.agent import Agent
from app.models.task import FollowUpTask

@event.listens_for(Lead, "before_update")
@event.listens_for(Agent, "before_update")
@event.listens_for(FollowUpTask, "before_update")
def update_timestamp(mapper, connection, target):
    target.updated_at = datetime.now(timezone.utc)
