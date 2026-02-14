from sqlalchemy import Column, String, Integer, DateTime, CheckConstraint, ARRAY
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.models.base import Base
from sqlalchemy.sql import func

class Agent(Base):
    __tablename__ = "agents"
    agent_id = Column(UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())
    full_name = Column(String(200), nullable=False)
    email = Column(String(255), unique=True, nullable=False)
    phone = Column(String(20), unique=True, nullable=False)
    specialization_property_type = Column(ARRAY(String))
    specialization_areas = Column(ARRAY(String))
    language_skills = Column(ARRAY(String))
    active_leads_count = Column(Integer, nullable=False, server_default="0")

    assignments = relationship("LeadAssignment", back_populates="agent", cascade="all, delete-orphan")
    activities = relationship("LeadActivity", back_populates="agent", cascade="all, delete-orphan")
    tasks = relationship("FollowUpTask", back_populates="agent", cascade="all, delete-orphan")
    performance_metrics = relationship("AgentPerformanceMetric", back_populates="agent", cascade="all, delete-orphan")

    __table_args__ = (
        CheckConstraint("active_leads_count <= 50", name="ck_active_leads_max"),
        CheckConstraint("active_leads_count >= 0", name="ck_active_leads_nonneg"),
    )