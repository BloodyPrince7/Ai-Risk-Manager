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


# ============================================================
# Return Risk Case
# ============================================================

class RiskCase(Base):

    __tablename__ = "risk_cases"


    # --------------------------------------------------------
    # Primary key
    # --------------------------------------------------------

    id = Column(
        Integer,
        primary_key=True,
        index=True
    )


    # --------------------------------------------------------
    # Customer / history
    # --------------------------------------------------------

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


    # --------------------------------------------------------
    # Behavioral features
    # --------------------------------------------------------

    return_ratio = Column(
        Float,
        nullable=False
    )

    refund_ratio = Column(
        Float,
        nullable=False
    )


    # --------------------------------------------------------
    # Transaction
    # --------------------------------------------------------

    order_value = Column(
        Float,
        nullable=False
    )

    days_since_purchase = Column(
        Integer,
        nullable=False
    )


    # --------------------------------------------------------
    # Reuse signals
    # --------------------------------------------------------

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


    # --------------------------------------------------------
    # Categorical features
    # --------------------------------------------------------

    claim_type = Column(
        String,
        nullable=False
    )

    product_category = Column(
        String,
        nullable=False
    )


    # --------------------------------------------------------
    # ML result
    # --------------------------------------------------------

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


    # --------------------------------------------------------
    # Merchant decision
    # --------------------------------------------------------

    merchant_decision = Column(
        String,
        nullable=True
    )


    # --------------------------------------------------------
    # Timestamp
    # --------------------------------------------------------

    created_at = Column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        nullable=False
    )


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
