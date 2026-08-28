"""Independent request-pattern analysis, traffic telemetry, and intake controls."""

from collections import defaultdict
from datetime import datetime, timedelta, timezone
import hashlib
import math
import threading

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, model_validator, field_validator
from sqlalchemy.orm import Session
from typing import Literal

from database.database import get_db
from database.models import IntakePause, RequestArrival
from api.sentinel import IDENTITY_FIELDS, iso, now_utc


router = APIRouter(prefix="/monitoring", tags=["Request monitoring"])
intake_lock = threading.RLock()  # Serialize pause/accept transitions in this local process.
Source = Literal["all", "live", "demo"]
Scale = Literal["minute", "five_minutes", "hour"]
SCALES = {"minute": (60, 60), "five_minutes": (300, 72), "hour": (3600, 24)}
LABELS = {"account_id": "account", "device_id": "device", "ip_address": "IP address",
          "payment_token": "payment token", "address_token": "address token", "location": "location"}


def source_query(db, source):
    query = db.query(RequestArrival)
    return query if source == "all" else query.filter(RequestArrival.is_test == int(source == "demo"))


def arrival_payload(row):
    return {"id": row.id, "case_id": row.case_id, "external_reference": row.external_reference,
            **{field: getattr(row, field) for field in IDENTITY_FIELDS},
            "status": row.status, "is_test": bool(row.is_test), "created_at": iso(row.created_at),
            "claim_type": row.claim_type, "product_category": row.product_category}


def record_arrival(db, request, status, case_id=None):
    row = RequestArrival(case_id=case_id, external_reference=request.external_reference,
                         **{field: getattr(request, field) for field in IDENTITY_FIELDS},
                         claim_type=request.claim_type, product_category=request.product_category,
                         is_test=int(request.is_test), status=status, created_at=now_utc())
    db.add(row)
    return row


def pause_payload(row, now=None):
    return {"id": row.id, "scope": row.scope, "reason": row.reason,
            "created_at": iso(row.created_at), "expires_at": iso(row.expires_at),
            "resumed_at": iso(row.resumed_at),
            "status": "RESUMED" if row.resumed_at else "ACTIVE" if row.expires_at > (now or now_utc()) else "EXPIRED"}


def intake_pauses(db, now=None):
    return db.query(IntakePause).filter(IntakePause.resumed_at.is_(None),
                                      IntakePause.expires_at > (now or now_utc())).all()


def ensure_intake_open(db, requests):
    """Reject a batch atomically, recording refused arrivals without creating risk cases."""
    now = now_utc()
    matching = [pause for pause in intake_pauses(db, now)
                if pause.scope in ("all", "demo" if requests[0].is_test else "live")]
    if matching:
        end = max(pause.expires_at for pause in matching)
        for request in requests:
            record_arrival(db, request, "paused")
        db.commit()
        raise HTTPException(status_code=503, detail=f"Incoming requests are paused until {iso(end)}. No return case was created. Retry after the pause ends.",
                            headers={"Retry-After": str(max(1, math.ceil((end - now).total_seconds())))})


def patterns_for(rows):
    # One explainable group per shared value. A common city is deliberately NOT
    # used to merge many unrelated accounts into a supposed abuse ring.
    buckets = defaultdict(list)
    for row in rows:
        for field in IDENTITY_FIELDS:
            value = getattr(row, field)
            if value:
                normalized = value.casefold() if field == "location" else value
                buckets[(bool(row.is_test), field, normalized)].append(row)
    groups = []
    for (is_test, field, value), members in buckets.items():
        if len(members) < 2:
            continue
        other = []
        for other_field in (*IDENTITY_FIELDS, "claim_type", "product_category"):
            if other_field == field:
                continue
            values = defaultdict(int)
            for row in members:
                item = getattr(row, other_field)
                if item:
                    values[item.casefold() if other_field == "location" else item] += 1
            other.extend({"field": other_field, "value": item, "count": count}
                         for item, count in values.items() if count > 1)
        groups.append({"id": hashlib.sha256(f"{is_test}:{field}:{value}".encode()).hexdigest()[:20],
                       "field": field, "value": value, "count": len(members), "is_test": is_test,
                       "summary": f"{len(members)} requests share the same {LABELS[field]}.",
                       "strength": "Context only" if field == "location" else "Shared signal",
                       "account_count": len({row.account_id for row in members if row.account_id}),
                       "similarities": sorted(other, key=lambda item: -item["count"]),
                       "first_seen": iso(min(row.created_at for row in members)),
                       "last_seen": iso(max(row.created_at for row in members)),
                       "requests": [arrival_payload(row) for row in members]})
    return sorted(groups, key=lambda group: (-group["count"], group["field"], group["value"]))


@router.get("/patterns")
def pattern_status(source: Source = "all", db: Session = Depends(get_db)):
    now = now_utc()
    rows = source_query(db, source).filter(RequestArrival.created_at <= now).order_by(RequestArrival.created_at.desc()).all()
    patterns = patterns_for(rows)
    linked = {row["id"] for group in patterns for row in group["requests"]}
    return {"source": source, "checked_at": iso(now), "request_count": len(rows),
            "linked_request_count": len(linked), "patterns": patterns,
            "identified_count": sum(any(getattr(row, field) for field in IDENTITY_FIELDS) for row in rows),
            "recent_requests": [arrival_payload(row) for row in rows[:50]],
            "note": "All recorded requests are compared, including paused attempts. Two matching requests are enough; no spike is required. Demo and live identities are never grouped together."}


def case_patterns(db, case_id, is_test):
    rows = source_query(db, "demo" if is_test else "live").filter(RequestArrival.created_at <= now_utc()).all()
    return [{"id": group["id"], "classification": f"Shared {LABELS[group['field']]}",
             "count": group["count"], "summary": f"{group['summary']} Value: {group['value']}",
             "caution": "Shared signals are not proof of abuse; locations are context only."}
            for group in patterns_for(rows) if any(row["case_id"] == case_id for row in group["requests"])]


def traffic_snapshot(db, source="all", scale="minute", now=None):
    now = now or now_utc()
    seconds, count = SCALES[scale]
    epoch = datetime(1970, 1, 1)
    latest = epoch + timedelta(seconds=int((now - epoch).total_seconds()) // seconds * seconds)
    start = latest - timedelta(seconds=seconds * (count - 1))
    rows = source_query(db, source).filter(RequestArrival.created_at >= start,
                                         RequestArrival.created_at <= now).order_by(RequestArrival.created_at).all()
    buckets = [{"start": iso(start + timedelta(seconds=i * seconds)),
                "end": iso(start + timedelta(seconds=(i + 1) * seconds)),
                "count": 0, "live": 0, "demo": 0, "paused": 0} for i in range(count)]
    for row in rows:
        index = int((row.created_at - start).total_seconds()) // seconds
        buckets[index]["count"] += 1
        buckets[index]["demo" if row.is_test else "live"] += 1
        buckets[index]["paused"] += row.status == "paused"
    for index, bucket in enumerate(buckets):
        previous = [item["count"] for item in buckets[max(0, index - 12):index]]
        baseline = sum(previous) / len(previous) if previous else 0
        bucket["baseline"] = round(baseline, 2)
        bucket["spike"] = bucket["count"] >= 10 and bucket["count"] >= 3 * baseline
        bucket["comparison"] = "relative" if baseline else "no_prior_traffic"
    pauses = intake_pauses(db, now)
    history = db.query(IntakePause).order_by(IntakePause.created_at.desc()).limit(20).all()
    return {"source": source, "scale": scale, "checked_at": iso(now), "window_start": iso(start),
            "bucket_seconds": seconds, "buckets": buckets, "request_count": len(rows),
            "demo_count": sum(bool(row.is_test) for row in rows),
            "paused_count": sum(row.status == "paused" for row in rows),
            "active_pauses": [pause_payload(row, now) for row in pauses],
            "pause_history": [pause_payload(row, now) for row in history],
            "note": "Highlighted intervals have at least 10 arrivals and at least 3× the mean of up to 12 earlier intervals. With no earlier traffic, this is only a volume flag. The latest interval is incomplete. Volume does not establish fraud."}


@router.get("/traffic")
def traffic_status(source: Source = "all", scale: Scale = "minute", db: Session = Depends(get_db)):
    return traffic_snapshot(db, source, scale)


class ResearchRequest(BaseModel):
    source: Source = "all"
    start: datetime
    end: datetime

    @model_validator(mode="after")
    def validate_period(self):
        for field in ("start", "end"):
            value = getattr(self, field)
            if value.tzinfo is None:
                raise ValueError("Research timestamps must include a timezone")
            setattr(self, field, value.astimezone(timezone.utc).replace(tzinfo=None))
        if not timedelta(0) < self.end - self.start <= timedelta(days=7):
            raise ValueError("Choose a period between zero and seven days")
        return self


@router.post("/traffic/research")
def research_traffic(request: ResearchRequest, db: Session = Depends(get_db)):
    now = now_utc()
    rows = source_query(db, request.source).filter(RequestArrival.created_at >= request.start,
              RequestArrival.created_at < request.end, RequestArrival.created_at <= now).order_by(RequestArrival.created_at.desc()).all()
    patterns = patterns_for(rows)
    return {"source": request.source, "start": iso(request.start), "end": iso(request.end),
            "researched_at": iso(now), "request_count": len(rows), "patterns": patterns,
            "summary": f"Examined {len(rows)} incoming requests and found {len(patterns)} shared-value patterns. " +
                       ("Review the matches below; shared details are not proof of abuse." if patterns else "No repeated identity or location was found in the available signals."),
            "requests": [arrival_payload(row) for row in rows],
            "method": "On-demand comparison of recorded account, device, IP, location, payment and address tokens. No external AI or geolocation lookup."}


class PauseRequest(BaseModel):
    scope: Source = "all"
    duration_minutes: Literal[5, 15, 30, 60] = 15
    reason: str = Field(min_length=3, max_length=500)

    @field_validator("reason", mode="before")
    @classmethod
    def clean_reason(cls, value):
        return value.strip() if isinstance(value, str) else value


@router.post("/intake/pauses")
def pause_intake(request: PauseRequest, db: Session = Depends(get_db)):
    with intake_lock:
        now = now_utc()
        pause = IntakePause(scope=request.scope, reason=request.reason, created_at=now,
                            expires_at=now + timedelta(minutes=request.duration_minutes))
        db.add(pause)
        db.commit()
        return pause_payload(pause)


@router.post("/intake/pauses/{pause_id}/resume")
def resume_intake(pause_id: int, db: Session = Depends(get_db)):
    with intake_lock:
        pause = db.get(IntakePause, pause_id)
        if pause is None:
            raise HTTPException(status_code=404, detail="Intake pause not found")
        if pause.resumed_at is None and pause.expires_at > now_utc():
            pause.resumed_at = now_utc()
            db.commit()
        return pause_payload(pause)
