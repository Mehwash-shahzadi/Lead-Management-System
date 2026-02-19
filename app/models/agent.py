from sqlalchemy import Column, String, Integer, DateTime, CheckConstraint, ARRAY
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.models.base import Base
from sqlalchemy.sql import func


class Agent(Base):
    """Real-estate agent who handles lead interactions and conversions.

    Stores specialisation in property types and geographic areas, language
    skills, and a rolling ``active_leads_count`` that is kept in sync by a
    PostgreSQL trigger.  A hard cap of 50 active leads is enforced by both
    a CHECK constraint and a database trigger.
    """

    __tablename__ = "agents"
    agent_id = Column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    full_name = Column(String(200), nullable=False)
    email = Column(String(255), unique=True, nullable=False)
    phone = Column(String(20), unique=True, nullable=False)
    specialization_property_type = Column(ARRAY(String))
    specialization_areas = Column(ARRAY(String))
    language_skills = Column(ARRAY(String))
    active_leads_count = Column(Integer, nullable=False, server_default="0")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    assignments = relationship(
        "LeadAssignment", back_populates="agent", cascade="all, delete-orphan"
    )
    activities = relationship(
        "LeadActivity", back_populates="agent", cascade="all, delete-orphan"
    )
    tasks = relationship(
        "FollowUpTask", back_populates="agent", cascade="all, delete-orphan"
    )
    performance_metrics = relationship(
        "AgentPerformanceMetric", back_populates="agent", cascade="all, delete-orphan"
    )

    __table_args__ = (
        CheckConstraint("active_leads_count <= 50", name="ck_active_leads_max"),
        CheckConstraint("active_leads_count >= 0", name="ck_active_leads_nonneg"),
    )
