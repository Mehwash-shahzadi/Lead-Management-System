from sqlalchemy import Column, String, Numeric, Integer, DateTime, CheckConstraint, UniqueConstraint, ARRAY, ForeignKey, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.models.base import Base
from sqlalchemy.sql import func
from sqlalchemy import text

class Lead(Base):
    __tablename__ = "leads"
    lead_id = Column(UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())
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
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    assignments = relationship("LeadAssignment", back_populates="lead", cascade="all, delete-orphan")
    activities = relationship("LeadActivity", back_populates="lead", cascade="all, delete-orphan")
    property_interests = relationship("LeadPropertyInterest", back_populates="lead", cascade="all, delete-orphan")
    conversion_history = relationship("LeadConversionHistory", back_populates="lead", cascade="all, delete-orphan")
    sources = relationship("LeadSource", back_populates="lead", cascade="all, delete-orphan")

    __table_args__ = (
        UniqueConstraint("phone", "source_type", name="uq_phone_source"),
        CheckConstraint("score BETWEEN 0 AND 100", name="ck_score_range"),
        CheckConstraint("status IN ('new', 'contacted', 'qualified', 'viewing_scheduled', 'negotiation', 'converted', 'lost')", name="ck_lead_status"),
        CheckConstraint("source_type IN ('bayut', 'propertyFinder', 'dubizzle', 'website', 'walk_in', 'referral')", name="ck_source_type"),
    )