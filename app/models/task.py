from sqlalchemy import Column, String, DateTime, CheckConstraint, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.models.base import Base
from sqlalchemy.sql import func

class FollowUpTask(Base):
    __tablename__ = "follow_up_tasks"
    task_id = Column(UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())
    lead_id = Column(UUID(as_uuid=True), ForeignKey("leads.lead_id", ondelete="CASCADE"), nullable=False)
    agent_id = Column(UUID(as_uuid=True), ForeignKey("agents.agent_id", ondelete="CASCADE"), nullable=False)
    type = Column(String(50), nullable=False)
    due_date = Column(DateTime(timezone=True), nullable=False)
    priority = Column(String(20), nullable=False, server_default="medium")
    status = Column(String(20), nullable=False, server_default="pending")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    lead = relationship("Lead")
    agent = relationship("Agent")

    __table_args__ = (
        CheckConstraint("type IN ('call', 'email', 'whatsapp', 'viewing')", name="ck_task_type"),
        CheckConstraint("priority IN ('high', 'medium', 'low')", name="ck_task_priority"),
        CheckConstraint("status IN ('pending', 'completed', 'overdue')", name="ck_task_status"),
    )