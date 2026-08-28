from datetime import datetime, timezone

from sqlalchemy import (
    Column,
    Integer,
    Float,
    String,
    DateTime,
    ForeignKey,
    Text
)

from .database import Base


class RiskCase(Base):

    __tablename__ = "risk_cases"


    id = Column(
        Integer,
        primary_key=True,
        index=True
    )


    customer_age_days = Column(
        Integer,
        nullable=False
    )

    previous_orders = Column(
        Integer,
        nullable=False
    )

    previous_returns = Column(
        Integer,
        nullable=False
    )

    previous_refunds = Column(
        Integer,
        nullable=False
    )


    return_ratio = Column(
        Float,
        nullable=False
    )

    refund_ratio = Column(
        Float,
        nullable=False
    )


    order_value = Column(
        Float,
        nullable=False
    )

    days_since_purchase = Column(
        Integer,
        nullable=False
    )


    account_count = Column(
        Integer,
        nullable=False
    )

    address_reuse_count = Column(
        Integer,
        nullable=False
    )

    device_reuse_count = Column(
        Integer,
        nullable=False
    )

    payment_failures = Column(
        Integer,
        nullable=False
    )


    claim_type = Column(
        String,
        nullable=False
    )

    product_category = Column(
        String,
        nullable=False
    )


    abuse_probability = Column(
        Float,
        nullable=False
    )

    risk_score = Column(
        Float,
        nullable=False
    )

    risk_level = Column(
        String,
        nullable=False
    )

    recommended_action = Column(
        String,
        nullable=False
    )

    external_reference = Column(
        String,
        nullable=True
    )

    account_id = Column(String, nullable=True)
    device_id = Column(String, nullable=True)
    ip_address = Column(String, nullable=True)
    payment_token = Column(String, nullable=True)
    address_token = Column(String, nullable=True)
    location = Column(String, nullable=True)
    is_test = Column(Integer, nullable=False, default=0, server_default="0")

    system_decision = Column(
        String,
        nullable=True
    )

    decision_due_at = Column(
        DateTime,
        nullable=True
    )


    merchant_decision = Column(
        String,
        nullable=True
    )


    created_at = Column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        nullable=False
    )


class RequestArrival(Base):
    __tablename__ = "request_arrivals"

    id = Column(Integer, primary_key=True)
    case_id = Column(Integer, nullable=True, unique=True)
    external_reference = Column(String, nullable=True)
    account_id = Column(String, nullable=True)
    device_id = Column(String, nullable=True)
    ip_address = Column(String, nullable=True)
    payment_token = Column(String, nullable=True)
    address_token = Column(String, nullable=True)
    location = Column(String, nullable=True)
    claim_type = Column(String, nullable=True)
    product_category = Column(String, nullable=True)
    is_test = Column(Integer, nullable=False, default=0)
    status = Column(String, nullable=False)
    created_at = Column(DateTime, nullable=False, index=True)


class IntakePause(Base):
    __tablename__ = "intake_pauses"

    id = Column(Integer, primary_key=True)
    scope = Column(String, nullable=False)
    reason = Column(Text, nullable=False)
    created_at = Column(DateTime, nullable=False)
    expires_at = Column(DateTime, nullable=False)
    resumed_at = Column(DateTime, nullable=True)


class SentinelSettings(Base):
    __tablename__ = "sentinel_settings"

    id = Column(Integer, primary_key=True)
    threshold = Column(Integer, nullable=False, default=10)
    window_minutes = Column(Integer, nullable=False, default=10)


class GatewayRestriction(Base):
    __tablename__ = "gateway_restrictions"

    id = Column(Integer, primary_key=True)
    scope = Column(String, nullable=False)
    is_test = Column(Integer, nullable=False, default=0)
    identities_json = Column(Text, nullable=False)
    evidence_json = Column(Text, nullable=False)
    reason = Column(Text, nullable=False)
    created_at = Column(DateTime, nullable=False)
    expires_at = Column(DateTime, nullable=False)
    resumed_at = Column(DateTime, nullable=True)


class CaseEvidence(Base):
    __tablename__ = "case_evidence"

    id = Column(Integer, primary_key=True, index=True)
    case_id = Column(Integer, ForeignKey("risk_cases.id"), nullable=False, index=True)
    filename = Column(String, nullable=False)
    content_type = Column(String, nullable=False)
    size_bytes = Column(Integer, nullable=False)
    storage_path = Column(String, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)


class CaseEvent(Base):
    __tablename__ = "case_events"

    id = Column(Integer, primary_key=True, index=True)
    case_id = Column(Integer, ForeignKey("risk_cases.id"), nullable=False, index=True)
    event_type = Column(String, nullable=False)
    value = Column(String, nullable=False)
    note = Column(Text, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)


class EvidenceVerification(Base):
    __tablename__ = "evidence_verifications"

    id = Column(Integer, primary_key=True, index=True)
    evidence_id = Column(Integer, ForeignKey("case_evidence.id"), nullable=False, index=True)
    case_id = Column(Integer, ForeignKey("risk_cases.id"), nullable=False, index=True)
    status = Column(String, nullable=False)
    result_json = Column(Text, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
