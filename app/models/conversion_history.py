from sqlalchemy import (
    CheckConstraint,
    Column,
    String,
    Text,
    DateTime,
    ForeignKey,
    Numeric,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.models.base import Base
from sqlalchemy.sql import func

from app.core.constants import LEAD_STATUSES

# SQL CHECK clause for status columns — derived from LEAD_STATUSES constant
_STATUS_CHECK_CLAUSE: str = (
    f"{{col}} IN ({', '.join(repr(s) for s in sorted(LEAD_STATUSES))})"
)


class LeadConversionHistory(Base):
    """Audit trail for lead status transitions and deal outcomes.

    Records from/to status, timestamp, responsible agent, deal value,
    conversion type (sale/rental/lost), and associated property.  Used
    by analytics queries for conversion-rate and revenue-attribution
    reports.
    """

    __tablename__ = "lead_conversion_history"
    history_id = Column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    lead_id = Column(
        UUID(as_uuid=True),
        ForeignKey("leads.lead_id", ondelete="CASCADE"),
        nullable=False,
    )
    status_from = Column(String(50))
    status_to = Column(String(50))
    changed_at = Column(DateTime(timezone=True), server_default=func.now())
    agent_id = Column(
        UUID(as_uuid=True), ForeignKey("agents.agent_id", ondelete="SET NULL")
    )
    notes = Column(Text)

    deal_value = Column(Numeric(15, 2), nullable=True)
    conversion_type = Column(String(20), nullable=True)  # 'sale', 'rental', or 'lost'
    property_id = Column(
        UUID(as_uuid=True),
        nullable=True,
    )

    __table_args__ = (
        CheckConstraint(
            "conversion_type IN ('sale', 'rental', 'lost')",
            name="ck_conversion_type",
        ),
        CheckConstraint(
            _STATUS_CHECK_CLAUSE.format(col="status_from"),
            name="ck_conversion_status_from",
        ),
        CheckConstraint(
            _STATUS_CHECK_CLAUSE.format(col="status_to"),
            name="ck_conversion_status_to",
        ),
    )

    lead = relationship(
        "Lead", back_populates="conversion_history", foreign_keys=[lead_id]
    )
