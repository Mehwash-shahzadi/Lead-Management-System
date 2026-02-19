from sqlalchemy import Column, Index, String, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.models.base import Base
from sqlalchemy.sql import func
from sqlalchemy import CheckConstraint, DateTime

from app.core.constants import SOURCE_TYPE_CHECK_CLAUSE


class LeadSource(Base):
    """Metadata about the originating source for a lead capture event.

    Tracks the marketing campaign, referrer agent, property context, and
    UTM parameters.  Source type is constrained to the canonical
    ``SourceType`` enum values via a CHECK constraint.
    """

    __tablename__ = "lead_sources"
    source_id = Column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    lead_id = Column(
        UUID(as_uuid=True),
        ForeignKey("leads.lead_id", ondelete="CASCADE"),
        nullable=False,
    )
    source_type = Column(String(50), nullable=False)
    campaign_id = Column(String(100))
    referrer_agent_id = Column(
        UUID(as_uuid=True), ForeignKey("agents.agent_id", ondelete="SET NULL")
    )
    property_id = Column(UUID(as_uuid=True))
    utm_source = Column(String(100))
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    lead = relationship("Lead", back_populates="sources")
    referrer_agent = relationship("Agent")

    __table_args__ = (
        CheckConstraint(
            SOURCE_TYPE_CHECK_CLAUSE,
            name="ck_lead_source_source_type",
        ),
        Index("ix_lead_sources_source_type", "source_type"),
    )
