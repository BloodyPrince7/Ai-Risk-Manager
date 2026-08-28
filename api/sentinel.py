"""Deterministic return velocity monitoring; shared identities are evidence, not proof."""

from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
import hashlib
import json

from database.models import GatewayRestriction, RiskCase, SentinelSettings


IDENTITY_FIELDS = ("account_id", "device_id", "ip_address", "payment_token", "address_token", "location")
LINK_FIELDS = IDENTITY_FIELDS[:3]


def now_utc():
    return datetime.now(timezone.utc).replace(tzinfo=None)


def iso(value):
    return value.replace(tzinfo=timezone.utc).isoformat() if value else None


def settings_for(db):
    settings = db.get(SentinelSettings, 1)
    return {"threshold": settings.threshold if settings else 10,
            "window_minutes": settings.window_minutes if settings else 10}


def active_restrictions(db, now=None):
    return db.query(GatewayRestriction).filter(
        GatewayRestriction.resumed_at.is_(None),
        GatewayRestriction.expires_at > (now or now_utc()),
    ).all()


def restriction_for(case, restrictions, include_completed=False):
    if not include_completed and (case.system_decision == "AUTO_APPROVED" or case.merchant_decision in ("APPROVED", "REJECTED")):
        return None
    matches = [item for item in restrictions if bool(item.is_test) == bool(case.is_test) and (
        item.scope == "gateway" or any(
            getattr(case, field) and getattr(case, field) in values
            for field, values in json.loads(item.identities_json).items()
        )
    )]
    return max(matches, key=lambda item: item.expires_at) if matches else None


def restriction_payload(item, now=None):
    now = now or now_utc()
    return {"id": item.id, "scope": item.scope, "is_test": bool(item.is_test),
            "identities": json.loads(item.identities_json), "reason": item.reason,
            "created_at": iso(item.created_at), "expires_at": iso(item.expires_at),
            "resumed_at": iso(item.resumed_at),
            "status": "RESUMED" if item.resumed_at else "ACTIVE" if item.expires_at > now else "EXPIRED"}


def case_identity_payload(case, restrictions):
    restriction = restriction_for(case, restrictions)
    return {**{field: getattr(case, field) for field in IDENTITY_FIELDS},
            "is_test": bool(case.is_test),
            "gateway_restriction": restriction_payload(restriction) if restriction else None}


def monitor(db, is_test=False, now=None):
    now = now or now_utc()
    settings = settings_for(db)
    start = now - timedelta(minutes=settings["window_minutes"])
    rows = db.query(RiskCase).filter(
        RiskCase.is_test == int(is_test), RiskCase.created_at > start,
        RiskCase.created_at <= now,
    ).order_by(RiskCase.created_at, RiskCase.id).all()

    # Missing identifiers never connect customers. Union overlapping groups so a
    # device/IP/account burst is one investigation, not three duplicate alerts.
    buckets = defaultdict(list)
    parent = {row.id: row.id for row in rows}

    def root(case_id):
        while parent[case_id] != case_id:
            parent[case_id] = parent[parent[case_id]]
            case_id = parent[case_id]
        return case_id

    for row in rows:
        for field in LINK_FIELDS:
            value = getattr(row, field)
            if value:
                buckets[(field, value)].append(row.id)
    for ids in buckets.values():
        for case_id in ids[1:]:
            parent[root(case_id)] = root(ids[0])
    groups = defaultdict(list)
    for row in rows:
        groups[root(row.id)].append(row)

    alerts = []
    for members in groups.values():
        ids = {row.id for row in members}
        triggers = [{"field": field, "value": value, "count": len(case_ids)}
                    for (field, value), case_ids in buckets.items()
                    if len(case_ids) >= settings["threshold"] and case_ids[0] in ids]
        if not triggers:
            continue
        similarities = []
        for field in (*IDENTITY_FIELDS, "claim_type", "product_category"):
            counts = Counter(getattr(row, field) for row in members if getattr(row, field))
            similarities.extend({"field": field, "value": value, "count": count}
                                for value, count in counts.most_common() if count > 1)
        accounts = {row.account_id for row in members if row.account_id}
        shared_kinds = {item["field"] for item in similarities if item["field"] in LINK_FIELDS}
        possible_ring = len(accounts) > 1 and "device_id" in shared_kinds and len(shared_kinds) > 1
        explanation = "; ".join(f'{t["count"]} returns share {t["field"]} {t["value"]}' for t in triggers)
        # Confirmation must refer to exactly the membership and rule reviewed;
        # new linked identities require a refreshed merchant confirmation.
        signature = json.dumps([sorted((t["field"], t["value"]) for t in triggers), sorted(ids), settings])
        alerts.append({
            "id": hashlib.sha256(signature.encode()).hexdigest()[:20],
            "classification": "Possible coordinated abuse" if possible_ring else "Unusual return velocity",
            "severity": "HIGH" if possible_ring else "WARNING",
            "summary": f'{explanation} within {settings["window_minutes"]} minutes. '
                       f'The configured limit is {settings["threshold"]} returns.',
            "caution": "Shared networks or devices can be legitimate. This rule is not proof of abuse or a learned normal baseline.",
            "count": len(members), "account_count": len(accounts),
            "first_seen": iso(members[0].created_at), "last_seen": iso(members[-1].created_at),
            "triggers": triggers, "similarities": similarities,
            "cases": [{"id": row.id, "external_reference": row.external_reference,
                       "account_id": row.account_id, "device_id": row.device_id,
                       "ip_address": row.ip_address, "created_at": iso(row.created_at),
                       "claim_type": row.claim_type, "order_value": row.order_value} for row in members],
            "identities": {field: sorted({getattr(row, field) for row in members if getattr(row, field)})
                           for field in LINK_FIELDS},
        })
    history = db.query(GatewayRestriction).filter(GatewayRestriction.is_test == int(is_test)).order_by(
        GatewayRestriction.created_at.desc()).limit(20).all()
    return {"settings": settings, "is_test": is_test, "checked_at": iso(now),
            "window_start": iso(start), "request_count": len(rows),
            "identified_count": sum(any(getattr(row, field) for field in LINK_FIELDS) for row in rows),
            "alerts": sorted(alerts, key=lambda item: (-item["count"], item["id"])),
            "restrictions": [restriction_payload(item, now) for item in active_restrictions(db, now)
                             if bool(item.is_test) == is_test],
            "history": [restriction_payload(item, now) for item in history]}
