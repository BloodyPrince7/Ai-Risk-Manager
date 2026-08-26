from fastapi.middleware.cors import CORSMiddleware

from fastapi import (
    FastAPI,
    Depends,
    HTTPException
)

from pydantic import BaseModel, Field

from sqlalchemy.orm import Session

import sys
from pathlib import Path


# ============================================================
# Project paths
# ============================================================

ROOT_DIR = Path(__file__).resolve().parent.parent
SRC_DIR = ROOT_DIR / "src"

sys.path.append(str(SRC_DIR))


# ============================================================
# ML imports
# ============================================================

from predict import (
    load_model,
    predict_return
)


# ============================================================
# AI Investigation Agent
# ============================================================

from agent.investigator import investigate_case


# ============================================================
# Database imports
# ============================================================

sys.path.append(
    str(ROOT_DIR)
)

from database.database import (
    Base,
    engine,
    get_db
)

from database.models import RiskCase


# ============================================================
# Create database tables
# ============================================================

Base.metadata.create_all(
    bind=engine
)


# ============================================================
# FastAPI
# ============================================================

app = FastAPI(
    title="AI Risk Manager API",
    description=(
        "AI-powered ecommerce return-abuse "
        "risk management API."
    ),
    version="0.3.0"
)


# ============================================================
# CORS
# ============================================================

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================
# Load model once
# ============================================================

print("Loading risk model...")

model = load_model()

print("Risk model loaded successfully!")


# ============================================================
# Request schema
# ============================================================

class ReturnRequest(BaseModel):

    customer_age_days: int = Field(
        ...,
        ge=0
    )

    previous_orders: int = Field(
        ...,
        ge=0
    )

    previous_returns: int = Field(
        ...,
        ge=0
    )

    previous_refunds: int = Field(
        ...,
        ge=0
    )

    return_ratio: float = Field(
        ...,
        ge=0,
        le=1
    )

    refund_ratio: float = Field(
        ...,
        ge=0,
        le=1
    )

    order_value: float = Field(
        ...,
        ge=0
    )

    days_since_purchase: int = Field(
        ...,
        ge=0
    )

    account_count: int = Field(
        ...,
        ge=1
    )

    address_reuse_count: int = Field(
        ...,
        ge=0
    )

    device_reuse_count: int = Field(
        ...,
        ge=0
    )

    payment_failures: int = Field(
        ...,
        ge=0
    )

    claim_type: str

    product_category: str


# ============================================================
# Merchant decision schema
# ============================================================

class MerchantDecision(BaseModel):

    decision: str


# ============================================================
# Root
# ============================================================

@app.get("/")
def root():

    return {
        "name": "AI Risk Manager API",
        "status": "running",
        "version": "0.3.0"
    }


# ============================================================
# Health
# ============================================================

@app.get("/health")
def health():

    return {
        "status": "healthy",
        "model_loaded": model is not None
    }


# ============================================================
# Predict only
# ============================================================

@app.post("/predict")
def predict(
    request: ReturnRequest
):

    request_data = request.model_dump()

    result = predict_return(
        model,
        request_data
    )

    return {
        "success": True,
        "prediction": result
    }


# ============================================================
# Create a risk case
# ============================================================

@app.post("/cases")
def create_case(
    request: ReturnRequest,
    db: Session = Depends(get_db)
):

    # --------------------------------------------------------
    # Convert request to dictionary
    # --------------------------------------------------------

    request_data = request.model_dump()


    # --------------------------------------------------------
    # Run ML prediction
    # --------------------------------------------------------

    result = predict_return(
        model,
        request_data
    )


    # --------------------------------------------------------
    # Create database record
    # --------------------------------------------------------

    case = RiskCase(

        customer_age_days=request.customer_age_days,

        previous_orders=request.previous_orders,

        previous_returns=request.previous_returns,

        previous_refunds=request.previous_refunds,

        return_ratio=request.return_ratio,

        refund_ratio=request.refund_ratio,

        order_value=request.order_value,

        days_since_purchase=request.days_since_purchase,

        account_count=request.account_count,

        address_reuse_count=request.address_reuse_count,

        device_reuse_count=request.device_reuse_count,

        payment_failures=request.payment_failures,

        claim_type=request.claim_type,

        product_category=request.product_category,

        abuse_probability=result[
            "abuse_probability"
        ],

        risk_score=result[
            "risk_score"
        ],

        risk_level=result[
            "risk_level"
        ],

        recommended_action=result[
            "action"
        ]
    )


    # --------------------------------------------------------
    # Save
    # --------------------------------------------------------

    db.add(case)

    db.commit()

    db.refresh(case)


    # --------------------------------------------------------
    # Return
    # --------------------------------------------------------

    return {
        "success": True,

        "case": {
            "id": case.id,

            "abuse_probability":
                case.abuse_probability,

            "risk_score":
                case.risk_score,

            "risk_level":
                case.risk_level,

            "recommended_action":
                case.recommended_action,

            "merchant_decision":
                case.merchant_decision,

            "created_at":
                case.created_at
        }
    }


# ============================================================
# Get all cases
# ============================================================

@app.get("/cases")
def get_cases(
    db: Session = Depends(get_db)
):

    cases = (
        db.query(RiskCase)
        .order_by(
            RiskCase.created_at.desc()
        )
        .all()
    )


    return {
        "success": True,

        "count": len(cases),

        "cases": [

            {
                "id": case.id,

                "risk_score":
                    case.risk_score,

                "risk_level":
                    case.risk_level,

                "recommended_action":
                    case.recommended_action,

                "merchant_decision":
                    case.merchant_decision,

                "claim_type":
                    case.claim_type,

                "product_category":
                    case.product_category,

                "order_value":
                    case.order_value,

                "created_at":
                    case.created_at
            }

            for case in cases
        ]
    }


# ============================================================
# Get a single case
# ============================================================

@app.get("/cases/{case_id}")
def get_case(
    case_id: int,
    db: Session = Depends(get_db)
):

    case = (
        db.query(RiskCase)
        .filter(
            RiskCase.id == case_id
        )
        .first()
    )


    if case is None:

        raise HTTPException(
            status_code=404,
            detail="Case not found"
        )


    return {
        "success": True,

        "case": {

            "id": case.id,

            "customer_age_days":
                case.customer_age_days,

            "previous_orders":
                case.previous_orders,

            "previous_returns":
                case.previous_returns,

            "previous_refunds":
                case.previous_refunds,

            "return_ratio":
                case.return_ratio,

            "refund_ratio":
                case.refund_ratio,

            "order_value":
                case.order_value,

            "days_since_purchase":
                case.days_since_purchase,

            "account_count":
                case.account_count,

            "address_reuse_count":
                case.address_reuse_count,

            "device_reuse_count":
                case.device_reuse_count,

            "payment_failures":
                case.payment_failures,

            "claim_type":
                case.claim_type,

            "product_category":
                case.product_category,

            "abuse_probability":
                case.abuse_probability,

            "risk_score":
                case.risk_score,

            "risk_level":
                case.risk_level,

            "recommended_action":
                case.recommended_action,

            "merchant_decision":
                case.merchant_decision,

            "created_at":
                case.created_at
        }
    }


# ============================================================
# AI Investigation
# ============================================================

@app.post("/cases/{case_id}/investigate")
def investigate(
    case_id: int,
    db: Session = Depends(get_db)
):

    # --------------------------------------------------------
    # Find case
    # --------------------------------------------------------

    case = (
        db.query(RiskCase)
        .filter(
            RiskCase.id == case_id
        )
        .first()
    )


    if case is None:

        raise HTTPException(
            status_code=404,
            detail="Case not found"
        )


    # --------------------------------------------------------
    # Convert database case into dictionary
    # --------------------------------------------------------

    case_data = {

        "id": case.id,

        "customer_age_days":
            case.customer_age_days,

        "previous_orders":
            case.previous_orders,

        "previous_returns":
            case.previous_returns,

        "previous_refunds":
            case.previous_refunds,

        "return_ratio":
            case.return_ratio,

        "refund_ratio":
            case.refund_ratio,

        "order_value":
            case.order_value,

        "days_since_purchase":
            case.days_since_purchase,

        "account_count":
            case.account_count,

        "address_reuse_count":
            case.address_reuse_count,

        "device_reuse_count":
            case.device_reuse_count,

        "payment_failures":
            case.payment_failures,

        "claim_type":
            case.claim_type,

        "product_category":
            case.product_category,

        "abuse_probability":
            case.abuse_probability,

        "risk_score":
            case.risk_score,

        "risk_level":
            case.risk_level,

        "recommended_action":
            case.recommended_action
    }


    # --------------------------------------------------------
    # Send case to Gemini Investigator
    # --------------------------------------------------------

    try:

        investigation = investigate_case(
            case_data
        )

    except Exception as error:

        print(
            f"AI investigation failed: {error}"
        )

        raise HTTPException(
            status_code=503,
            detail=(
                "AI investigation service "
                "is temporarily unavailable."
            )
        )


    # --------------------------------------------------------
    # Return investigation
    # --------------------------------------------------------

    return {

        "success": True,

        "case_id": case.id,

        "investigation": investigation

    }


# ============================================================
# Update merchant decision
# ============================================================

@app.patch(
    "/cases/{case_id}/decision"
)
def update_decision(
    case_id: int,
    decision: MerchantDecision,
    db: Session = Depends(get_db)
):

    case = (
        db.query(RiskCase)
        .filter(
            RiskCase.id == case_id
        )
        .first()
    )


    if case is None:

        raise HTTPException(
            status_code=404,
            detail="Case not found"
        )


    allowed_decisions = [
        "APPROVED",
        "REJECTED",
        "ESCALATED"
    ]


    if decision.decision not in allowed_decisions:

        raise HTTPException(
            status_code=400,
            detail=(
                "Invalid decision. "
                "Use APPROVED, REJECTED, "
                "or ESCALATED."
            )
        )


    case.merchant_decision = (
        decision.decision
    )


    db.commit()

    db.refresh(case)


    return {
        "success": True,

        "case_id": case.id,

        "merchant_decision":
            case.merchant_decision
    }