from fastapi.middleware.cors import CORSMiddleware

from fastapi import (
    FastAPI,
    Depends,
    HTTPException,
    Request
)

from pydantic import BaseModel, Field, model_validator

from sqlalchemy import inspect, text
from sqlalchemy.orm import Session

from datetime import datetime, timedelta, timezone
import sys
import io
import json
import os
import threading
import uuid
from pathlib import Path
import pandas as pd
from starlette.concurrency import run_in_threadpool
from fastapi.responses import FileResponse


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
    explain_prediction,
    load_model,
    load_model_metadata,
    predict_return
)
from model_training import REQUIRED_COLUMNS, apply_cost_settings, save_model_artifact, train_custom_model


# ============================================================
# AI Investigation Agent
# ============================================================

from agent.evidence_verifier import verify_evidence_file
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

from database.models import CaseEvent, CaseEvidence, EvidenceVerification, RiskCase


# ============================================================
# Create database tables
# ============================================================

Base.metadata.create_all(
    bind=engine
)


def migrate_local_schema():
    """Apply the small additive migration required by existing SQLite demos."""

    columns = {column["name"] for column in inspect(engine).get_columns("risk_cases")}
    if "external_reference" not in columns:
        with engine.begin() as connection:
            connection.execute(text("ALTER TABLE risk_cases ADD COLUMN external_reference VARCHAR"))
    if "system_decision" not in columns:
        with engine.begin() as connection:
            connection.execute(text("ALTER TABLE risk_cases ADD COLUMN system_decision VARCHAR"))
    if "decision_due_at" not in columns:
        with engine.begin() as connection:
            connection.execute(text("ALTER TABLE risk_cases ADD COLUMN decision_due_at DATETIME"))
    with engine.begin() as connection:
        connection.execute(text(
            "UPDATE risk_cases SET system_decision = CASE "
            "WHEN merchant_decision IS NOT NULL THEN 'MERCHANT_OVERRIDE' "
            "WHEN recommended_action = 'AUTO_APPROVE' THEN 'PENDING_AUTO_APPROVAL' "
            "WHEN recommended_action = 'REQUEST_EVIDENCE' THEN 'EVIDENCE_REQUIRED' "
            "ELSE 'MANUAL_REVIEW' END WHERE system_decision IS NULL"
        ))
        connection.execute(text(
            "UPDATE risk_cases SET decision_due_at = datetime(created_at, '+1 hour') "
            "WHERE recommended_action = 'AUTO_APPROVE' AND decision_due_at IS NULL"
        ))


migrate_local_schema()


# ============================================================
# FastAPI
# ============================================================

app = FastAPI(
    title="AI Risk Manager API",
    description=(
        "AI-powered ecommerce return-abuse "
        "risk management API."
    ),
    version="0.4.0"
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
model_metadata = load_model_metadata()
model_lock = threading.Lock()
training_lock = threading.Lock()
MODEL_PATH = ROOT_DIR / "models" / "risk_model.pkl"
EVIDENCE_DIR = ROOT_DIR / "data" / "evidence"

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
        ge=1
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

    @model_validator(mode="after")
    def validate_history_ratios(self):
        if self.previous_returns > self.previous_orders:
            raise ValueError("previous_returns cannot exceed previous_orders")
        if self.previous_refunds > self.previous_orders:
            raise ValueError("previous_refunds cannot exceed previous_orders")
        if abs(self.return_ratio - self.previous_returns / self.previous_orders) > 0.001:
            raise ValueError("return_ratio must equal previous_returns / previous_orders")
        if abs(self.refund_ratio - self.previous_refunds / self.previous_orders) > 0.001:
            raise ValueError("refund_ratio must equal previous_refunds / previous_orders")
        return self


class CaseCreateRequest(ReturnRequest):
    external_reference: str | None = Field(default=None, min_length=1, max_length=200)


# ============================================================
# Merchant decision schema
# ============================================================

class MerchantDecision(BaseModel):

    decision: str


class CostSettings(BaseModel):
    false_positive_cost: int = Field(..., ge=0, le=1_000_000)
    false_negative_cost: int = Field(..., ge=0, le=10_000_000)


class VerifiedOutcome(BaseModel):
    outcome: str
    note: str | None = Field(default=None, max_length=2000)


# ============================================================
# Root
# ============================================================

@app.get("/")
def root():

    return {
        "name": "AI Risk Manager API",
        "status": "running",
        "version": "0.4.0"
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


@app.get("/model/status")
def model_status():
    return {
        "success": True,
        "model": public_model_metadata()
    }


def public_model_metadata():
    public = {
        key: value for key, value in model_metadata.items()
        if key != "threshold_performance"
    }
    costs = model_metadata.get("cost_analysis", {})
    performance = model_metadata.get("threshold_performance", [])
    public["cost_curve"] = [{
        "threshold": row["threshold"],
        "false_positives": row["fp"],
        "false_negatives": row["fn"],
        "total_cost": (
            row["fp"] * costs.get("false_positive_unit_cost", 0)
            + row["fn"] * costs.get("false_negative_unit_cost", 0)
        ),
    } for row in performance]
    return public


@app.patch("/model/cost-settings")
def update_cost_settings(settings: CostSettings):
    global model_metadata
    if "threshold_performance" not in model_metadata:
        raise HTTPException(status_code=409, detail="Retrain the model before changing cost settings.")
    updated = apply_cost_settings(
        model_metadata,
        settings.false_positive_cost,
        settings.false_negative_cost,
    )
    with model_lock:
        save_model_artifact(model, updated, MODEL_PATH)
        model_metadata = updated
    return {"success": True, "model": public_model_metadata()}


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
        request_data,
        thresholds=model_metadata.get("routing_thresholds")
    )

    return {
        "success": True,
        "prediction": result
    }


def utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def utc_iso(value: datetime | None):
    return value.replace(tzinfo=timezone.utc).isoformat() if value else None


def schedule_case_decision(case: RiskCase, db: Session) -> None:
    if case.recommended_action == "AUTO_APPROVE":
        delay_seconds = max(1, int(os.getenv("AUTO_APPROVAL_DELAY_SECONDS", "3600")))
        case.system_decision = "PENDING_AUTO_APPROVAL"
        case.decision_due_at = utc_now() + timedelta(seconds=delay_seconds)
        event = CaseEvent(
            case_id=case.id,
            event_type="AUTO_APPROVAL_SCHEDULED",
            value="PENDING_AUTO_APPROVAL",
            note=f"Automatic approval is scheduled for {utc_iso(case.decision_due_at)}.",
        )
    elif case.recommended_action == "REQUEST_EVIDENCE":
        case.system_decision = "EVIDENCE_REQUIRED"
        event = CaseEvent(case_id=case.id, event_type="SYSTEM_ROUTING", value="EVIDENCE_REQUIRED", note="Evidence is required before a final decision.")
    else:
        case.system_decision = "MANUAL_REVIEW"
        event = CaseEvent(case_id=case.id, event_type="SYSTEM_ROUTING", value="MANUAL_REVIEW", note="A merchant decision is required.")
    db.add(case)
    db.add(event)
    db.commit()
    db.refresh(case)


def finalize_due_auto_approvals(db: Session) -> None:
    due_cases = (
        db.query(RiskCase)
        .filter(
            RiskCase.system_decision == "PENDING_AUTO_APPROVAL",
            RiskCase.merchant_decision.is_(None),
            RiskCase.decision_due_at.is_not(None),
            RiskCase.decision_due_at <= utc_now(),
        )
        .all()
    )
    for case in due_cases:
        case.system_decision = "AUTO_APPROVED"
        db.add(case)
        db.add(CaseEvent(
            case_id=case.id,
            event_type="AUTO_APPROVED",
            value="APPROVED",
            note="The review window expired without an override; payment was approved automatically.",
        ))
    if due_cases:
        db.commit()


# ============================================================
# Create a risk case
# ============================================================

@app.post("/cases")
def create_case(
    request: CaseCreateRequest,
    db: Session = Depends(get_db)
):

    # --------------------------------------------------------
    # Convert request to dictionary
    # --------------------------------------------------------

    request_data = request.model_dump(exclude={"external_reference"})


    # --------------------------------------------------------
    # Run ML prediction
    # --------------------------------------------------------

    result = predict_return(
        model,
        request_data,
        thresholds=model_metadata.get("routing_thresholds")
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
        ],

        external_reference=request.external_reference
    )


    # --------------------------------------------------------
    # Save
    # --------------------------------------------------------

    db.add(case)

    db.commit()

    db.refresh(case)

    schedule_case_decision(case, db)


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

            "external_reference":
                case.external_reference,

            "system_decision":
                case.system_decision,

            "decision_due_at":
                utc_iso(case.decision_due_at),

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

    finalize_due_auto_approvals(db)

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

                "external_reference":
                    case.external_reference,

                "system_decision":
                    case.system_decision,

                "decision_due_at":
                    utc_iso(case.decision_due_at),

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

    finalize_due_auto_approvals(db)

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

            "external_reference":
                case.external_reference,

            "system_decision":
                case.system_decision,

            "decision_due_at":
                utc_iso(case.decision_due_at),

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

@app.get("/cases/{case_id}/explanation")
def get_model_explanation(case_id: int, db: Session = Depends(get_db)):
    case = db.query(RiskCase).filter(RiskCase.id == case_id).first()
    if case is None:
        raise HTTPException(status_code=404, detail="Case not found")
    request_data = {
        "customer_age_days": case.customer_age_days,
        "previous_orders": case.previous_orders,
        "previous_returns": case.previous_returns,
        "previous_refunds": case.previous_refunds,
        "return_ratio": case.return_ratio,
        "refund_ratio": case.refund_ratio,
        "order_value": case.order_value,
        "days_since_purchase": case.days_since_purchase,
        "account_count": case.account_count,
        "address_reuse_count": case.address_reuse_count,
        "device_reuse_count": case.device_reuse_count,
        "payment_failures": case.payment_failures,
        "claim_type": case.claim_type,
        "product_category": case.product_category,
    }
    return {
        "success": True,
        "case_id": case.id,
        "unit": "log_odds",
        "explanation": explain_prediction(model, request_data),
    }

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

    if (
        case.recommended_action == "AUTO_APPROVE"
        and case.decision_due_at is not None
        and case.decision_due_at <= utc_now()
    ):
        finalize_due_auto_approvals(db)
        raise HTTPException(status_code=409, detail="The one-hour decision window has closed.")


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

    if case.recommended_action == "AUTO_APPROVE":
        case.system_decision = "MERCHANT_OVERRIDE"

    db.add(CaseEvent(
        case_id=case.id,
        event_type="MERCHANT_DECISION",
        value=decision.decision,
        note="Human decision recorded from the case review panel."
    ))

    db.commit()

    db.refresh(case)


    return {
        "success": True,

        "case_id": case.id,

        "merchant_decision":
            case.merchant_decision,

        "system_decision":
            case.system_decision
    }


# ============================================================
# Delete a case and its review data
# ============================================================

@app.delete("/cases/{case_id}")
def delete_case(case_id: int, db: Session = Depends(get_db)):
    case = db.query(RiskCase).filter(RiskCase.id == case_id).first()
    if case is None:
        raise HTTPException(status_code=404, detail="Case not found")

    evidence = db.query(CaseEvidence).filter(CaseEvidence.case_id == case_id).all()
    storage_paths = [Path(item.storage_path) for item in evidence]

    db.query(EvidenceVerification).filter(EvidenceVerification.case_id == case_id).delete(synchronize_session=False)
    db.query(CaseEvent).filter(CaseEvent.case_id == case_id).delete(synchronize_session=False)
    db.query(CaseEvidence).filter(CaseEvidence.case_id == case_id).delete(synchronize_session=False)
    db.delete(case)
    db.commit()

    evidence_root = EVIDENCE_DIR.resolve()
    for storage_path in storage_paths:
        resolved_path = storage_path.resolve()
        if resolved_path.is_relative_to(evidence_root):
            resolved_path.unlink(missing_ok=True)
    case_directory = EVIDENCE_DIR / str(case_id)
    try:
        case_directory.rmdir()
    except OSError:
        pass

    return {"success": True, "case_id": case_id, "deleted": True}


# ============================================================
# Evidence, outcomes, and review audit trail
# ============================================================

@app.get("/cases/{case_id}/review")
def get_case_review(case_id: int, db: Session = Depends(get_db)):
    if db.query(RiskCase).filter(RiskCase.id == case_id).first() is None:
        raise HTTPException(status_code=404, detail="Case not found")
    evidence = db.query(CaseEvidence).filter(CaseEvidence.case_id == case_id).order_by(CaseEvidence.created_at.desc()).all()
    events = db.query(CaseEvent).filter(CaseEvent.case_id == case_id).order_by(CaseEvent.created_at.desc()).all()
    verifications = (
        db.query(EvidenceVerification)
        .filter(EvidenceVerification.case_id == case_id)
        .order_by(EvidenceVerification.created_at.desc())
        .all()
    )
    latest_verification = {}
    for verification in verifications:
        if verification.evidence_id not in latest_verification:
            try:
                result = json.loads(verification.result_json)
            except json.JSONDecodeError:
                result = {"document_summary": "Stored verification could not be decoded."}
            latest_verification[verification.evidence_id] = {
                "id": verification.id,
                "status": verification.status,
                "created_at": verification.created_at,
                "result": result,
            }
    return {
        "success": True,
        "evidence": [{
            "id": item.id,
            "filename": item.filename,
            "content_type": item.content_type,
            "size_bytes": item.size_bytes,
            "created_at": item.created_at,
            "download_url": f"/cases/{case_id}/evidence/{item.id}",
            "verification": latest_verification.get(item.id),
        } for item in evidence],
        "events": [{
            "id": event.id,
            "event_type": event.event_type,
            "value": event.value,
            "note": event.note,
            "created_at": event.created_at,
        } for event in events],
    }


@app.post("/cases/{case_id}/evidence")
async def upload_case_evidence(case_id: int, request: Request, db: Session = Depends(get_db)):
    if db.query(RiskCase).filter(RiskCase.id == case_id).first() is None:
        raise HTTPException(status_code=404, detail="Case not found")
    content_type = request.headers.get("content-type", "").split(";")[0]
    allowed_types = {"application/pdf", "image/jpeg", "image/png", "image/webp"}
    if content_type not in allowed_types:
        raise HTTPException(status_code=415, detail="Evidence must be a PDF, JPEG, PNG, or WebP file.")
    body = await request.body()
    if not body:
        raise HTTPException(status_code=400, detail="Evidence file is empty.")
    if len(body) > 5 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="Evidence files must be 5 MB or smaller.")
    original_name = Path(request.headers.get("x-filename", "evidence")).name
    suffix = Path(original_name).suffix.lower()
    case_directory = EVIDENCE_DIR / str(case_id)
    case_directory.mkdir(parents=True, exist_ok=True)
    storage_path = case_directory / f"{uuid.uuid4().hex}{suffix}"
    storage_path.write_bytes(body)
    item = CaseEvidence(
        case_id=case_id,
        filename=original_name,
        content_type=content_type,
        size_bytes=len(body),
        storage_path=str(storage_path),
    )
    db.add(item)
    db.add(CaseEvent(case_id=case_id, event_type="EVIDENCE_UPLOADED", value=original_name, note=f"{len(body)} bytes"))
    db.commit()
    db.refresh(item)
    return {"success": True, "evidence_id": item.id, "filename": item.filename}


@app.get("/cases/{case_id}/evidence/{evidence_id}")
def download_case_evidence(case_id: int, evidence_id: int, db: Session = Depends(get_db)):
    item = db.query(CaseEvidence).filter(CaseEvidence.id == evidence_id, CaseEvidence.case_id == case_id).first()
    if item is None or not Path(item.storage_path).is_file():
        raise HTTPException(status_code=404, detail="Evidence not found")
    return FileResponse(item.storage_path, media_type=item.content_type, filename=item.filename)


@app.post("/cases/{case_id}/evidence/{evidence_id}/verify")
async def verify_case_evidence(case_id: int, evidence_id: int, db: Session = Depends(get_db)):
    case = db.query(RiskCase).filter(RiskCase.id == case_id).first()
    item = db.query(CaseEvidence).filter(CaseEvidence.id == evidence_id, CaseEvidence.case_id == case_id).first()
    if case is None or item is None or not Path(item.storage_path).is_file():
        raise HTTPException(status_code=404, detail="Case evidence not found")

    try:
        result = await run_in_threadpool(
            verify_evidence_file,
            case,
            Path(item.storage_path).read_bytes(),
            item.content_type,
            item.filename,
        )
    except Exception as error:
        print(f"Evidence verification failed: {error}")
        raise HTTPException(status_code=503, detail="AI evidence verification is temporarily unavailable.") from error

    verification = EvidenceVerification(
        evidence_id=item.id,
        case_id=case.id,
        status="COMPLETED",
        result_json=json.dumps(result),
    )
    db.add(verification)
    db.add(CaseEvent(
        case_id=case.id,
        event_type="EVIDENCE_VERIFIED",
        value=result["claim_consistency"],
        note=f"{item.filename}: {result['recommended_action']} at {result['confidence']:.0%} confidence.",
    ))
    db.commit()
    db.refresh(verification)
    return {
        "success": True,
        "case_id": case.id,
        "evidence_id": item.id,
        "verification": {
            "id": verification.id,
            "status": verification.status,
            "created_at": verification.created_at,
            "result": result,
        },
    }


@app.post("/cases/{case_id}/outcome")
def record_verified_outcome(case_id: int, outcome: VerifiedOutcome, db: Session = Depends(get_db)):
    if db.query(RiskCase).filter(RiskCase.id == case_id).first() is None:
        raise HTTPException(status_code=404, detail="Case not found")
    allowed = {"CONFIRMED_LEGITIMATE", "CONFIRMED_ABUSE", "CHARGEBACK_RECEIVED", "EVIDENCE_ACCEPTED", "DECISION_REVERSED"}
    if outcome.outcome not in allowed:
        raise HTTPException(status_code=400, detail=f"Outcome must be one of: {', '.join(sorted(allowed))}")
    event = CaseEvent(case_id=case_id, event_type="VERIFIED_OUTCOME", value=outcome.outcome, note=outcome.note)
    db.add(event)
    db.commit()
    db.refresh(event)
    return {"success": True, "event_id": event.id, "outcome": event.value}


@app.get("/feedback/summary")
def feedback_summary(db: Session = Depends(get_db)):
    cases = db.query(RiskCase).all()
    verified_events = db.query(CaseEvent).filter(CaseEvent.event_type == "VERIFIED_OUTCOME").order_by(CaseEvent.created_at.desc()).all()
    latest_outcomes = {}
    for event in verified_events:
        latest_outcomes.setdefault(event.case_id, event.value)
    outcome_counts = {}
    for value in latest_outcomes.values():
        outcome_counts[value] = outcome_counts.get(value, 0) + 1

    reviewed = [case for case in cases if case.merchant_decision]
    disagreements = [case for case in reviewed if (
        case.recommended_action == "AUTO_APPROVE" and case.merchant_decision != "APPROVED"
    ) or (
        case.recommended_action == "MANUAL_REVIEW" and case.merchant_decision == "APPROVED"
    )]
    by_id = {case.id: case for case in cases}
    prevented = sum(
        by_id[case_id].order_value for case_id, value in latest_outcomes.items()
        if value == "CONFIRMED_ABUSE" and case_id in by_id
        and by_id[case_id].merchant_decision in {"REJECTED", "ESCALATED"}
    )
    lost = sum(
        by_id[case_id].order_value for case_id, value in latest_outcomes.items()
        if value in {"CONFIRMED_ABUSE", "CHARGEBACK_RECEIVED"} and case_id in by_id
        and by_id[case_id].merchant_decision == "APPROVED"
    )
    return {
        "success": True,
        "verified_cases": len(latest_outcomes),
        "outcome_counts": outcome_counts,
        "human_decisions": len(reviewed),
        "recommendation_disagreement_rate": round(len(disagreements) / len(reviewed), 4) if reviewed else 0,
        "estimated_loss_prevented": round(prevented, 2),
        "estimated_loss_realized": round(lost, 2),
    }


# ============================================================
# Custom model training
# ============================================================

@app.get("/model/training-schema")
def training_schema():
    return {
        "required_columns": REQUIRED_COLUMNS,
        "target": "is_abuse",
        "minimum_rows": 20,
        "labels": {"0": "legitimate", "1": "abuse"}
    }


@app.post("/model/train")
async def train_model(request: Request):
    global model, model_metadata

    content_type = request.headers.get("content-type", "").split(";")[0]
    if content_type not in {"text/csv", "application/csv", "application/vnd.ms-excel"}:
        raise HTTPException(status_code=415, detail="Upload a CSV file with the text/csv content type.")

    body = await request.body()
    if not body:
        raise HTTPException(status_code=400, detail="The uploaded CSV is empty.")
    if len(body) > 10 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="CSV files must be 10 MB or smaller.")

    try:
        csv_text = body.decode("utf-8-sig")
        frame = pd.read_csv(io.StringIO(csv_text))
    except (UnicodeDecodeError, pd.errors.ParserError) as error:
        raise HTTPException(status_code=400, detail=f"Could not read CSV: {error}") from error

    if not training_lock.acquire(blocking=False):
        raise HTTPException(status_code=409, detail="Another model training job is already running.")
    try:
        try:
            trained_model, metadata = await run_in_threadpool(
                train_custom_model,
                frame,
                MODEL_PATH,
                request.headers.get("x-dataset-name", "merchant-upload.csv")
            )
        except ValueError as error:
            raise HTTPException(status_code=422, detail=str(error)) from error
        except Exception as error:
            raise HTTPException(status_code=500, detail=f"Training failed: {error}") from error
    finally:
        training_lock.release()

    with model_lock:
        model = trained_model
        model_metadata = metadata

    return {
        "success": True,
        "message": "Custom model trained and activated.",
        **public_model_metadata(),
    }
