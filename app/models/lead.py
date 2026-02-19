from sqlalchemy import (
    Column,
    String,
    Numeric,
    Integer,
    DateTime,
    CheckConstraint,
    Index,
    ARRAY,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.models.base import Base
from sqlalchemy.sql import func
from sqlalchemy import text

from app.core.constants import SOURCE_TYPE_CHECK_CLAUSE


class Lead(Base):
    """Real-estate prospect captured from portals, referrals, or walk-ins.

    Tracks buyer/renter contact details, budget range, property preferences,
    and an engagement score (0–100).  Source types match the canonical
    ``SourceType`` enum.  Status follows a strict transition matrix enforced
    by both application-level validation and a PostgreSQL trigger.
    """

    __tablename__ = "leads"
    lead_id = Column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    source_type = Column(String(50), nullable=False)
    first_name = Column(String(100), nullable=False)
    last_name = Column(String(100), nullable=False)
    email = Column(String(255))
    phone = Column(String(20), nullable=False)
    nationality = Column(String(50))
    language_preference = Column(String(20))
    budget_min = Column(Numeric(15, 2))
    budget_max = Column(Numeric(15, 2))
    property_type = Column(String(50))
    preferred_areas = Column(ARRAY(String))
    status = Column(String(50), nullable=False, server_default="new")
    score = Column(Integer, nullable=False, server_default=text("0"))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    assignments = relationship(
        "LeadAssignment", back_populates="lead", cascade="all, delete-orphan"
    )
    activities = relationship(
        "LeadActivity", back_populates="lead", cascade="all, delete-orphan"
    )
    property_interests = relationship(
        "LeadPropertyInterest", back_populates="lead", cascade="all, delete-orphan"
    )
    conversion_history = relationship(
        "LeadConversionHistory",
        back_populates="lead",
        cascade="all, delete-orphan",
        foreign_keys="[LeadConversionHistory.lead_id]",
    )
    sources = relationship(
        "LeadSource", back_populates="lead", cascade="all, delete-orphan"
    )

    __table_args__ = (
        # NOTE: There is deliberately NO UNIQUE(phone, source_type) constraint.
        # Duplicate detection is enforced at the APPLICATION level with a
        # 24-hour window.  The same lead may be re-submitted from the same
        # source after 24 hours and should be treated as a new lead entry.
        # See ThinkRealty Backend Assessment: Error Handling, Duplicate Lead
        # Detection.
        Index(
            "idx_leads_phone_source_created",
            "phone",
            "source_type",
            "created_at",
        ),
        CheckConstraint("score BETWEEN 0 AND 100", name="ck_score_range"),
        CheckConstraint(
            "status IN ('new', 'contacted', 'qualified', 'viewing_scheduled', 'negotiation', 'converted', 'lost')",
            name="ck_lead_status",
        ),
        CheckConstraint(
            SOURCE_TYPE_CHECK_CLAUSE,
            name="ck_source_type",
        ),
        CheckConstraint(
            "budget_min IS NULL OR budget_max IS NULL OR budget_min < budget_max",
            name="ck_budget_min_lt_max",
        ),
    )
