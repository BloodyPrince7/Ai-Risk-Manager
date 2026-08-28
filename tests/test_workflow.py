"""End-to-end API checks using isolated storage."""

import tempfile
import unittest
import os
import uuid
from datetime import timedelta
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

os.environ["RISK_DATABASE_URL"] = "sqlite://"
import api.main as api
from api.sentinel import monitor
from api.request_monitoring import traffic_snapshot
from database.models import IntakePause, RequestArrival


LOW_RISK_CASE = {
    "external_reference": "ORDER-TEST-001",
    "customer_age_days": 900,
    "previous_orders": 24,
    "previous_returns": 1,
    "previous_refunds": 0,
    "return_ratio": 1 / 24,
    "refund_ratio": 0,
    "order_value": 1299,
    "days_since_purchase": 12,
    "account_count": 1,
    "address_reuse_count": 1,
    "device_reuse_count": 1,
    "payment_failures": 0,
    "claim_type": "changed_mind",
    "product_category": "fashion",
}

EVIDENCE_RESULT = {
    "evidence_type": "delivery proof",
    "document_summary": "The image shows a delivery confirmation.",
    "claim_consistency": "SUPPORTS_CLAIM",
    "verified_facts": ["A delivery status is visible."],
    "inconsistencies": [],
    "authenticity_signals": ["Tracking reference is visible."],
    "missing_information": ["Carrier API confirmation."],
    "recommended_action": "MANUAL_REVIEW",
    "confidence": 0.81,
    "limitations": "The image alone cannot prove authenticity.",
}


class WorkflowTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        api.Base.metadata.create_all(engine)
        cls.engine = engine
        cls.session_factory = sessionmaker(bind=engine)
        def isolated_db():
            with cls.session_factory() as db:
                yield db
        api.app.dependency_overrides[api.get_db] = isolated_db
        api.MODEL_PATH = Path(cls.temp.name) / "risk_model.pkl"
        api.EVIDENCE_DIR = Path(cls.temp.name) / "evidence"
        cls.client = TestClient(api.app)

    def setUp(self):
        with self.session_factory() as db:
            for table in reversed(api.Base.metadata.sorted_tables):
                db.execute(table.delete())
            db.commit()

    def create(self, **identity):
        payload = {**LOW_RISK_CASE, "external_reference": uuid.uuid4().hex, **identity}
        with patch("api.main.predict_return", return_value={"abuse_probability": .01, "risk_score": 1, "risk_level": "LOW", "action": "AUTO_APPROVE"}) as prediction:
            response = self.client.post("/cases", json=payload)
            self.assertEqual(response.status_code, 200, response.text)
            self.assertEqual(set(prediction.call_args.args[1]), set(api.ReturnRequest.model_fields))
        return response.json()["case"]

    def burst(self, **identity):
        return [self.create(**identity) for _ in range(10)]

    def pause(self, is_test=False, scope="linked"):
        status = self.client.get(f"/monitoring/sentinel?is_test={str(is_test).lower()}").json()
        response = self.client.post("/monitoring/sentinel/restrictions", json={
            "alert_id": status["alerts"][0]["id"], "duration_minutes": 15,
            "scope": scope, "is_test": is_test,
        })
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()

    def test_identity_roundtrip_normalization_and_validation(self):
        case = self.create(account_id=" account-a ", device_id="device-a", ip_address="::ffff:203.0.113.10", payment_token="token-p", address_token="token-a")
        for item in (case, self.client.get(f"/cases/{case['id']}").json()["case"], self.client.get("/cases").json()["cases"][0]):
            self.assertEqual(item["ip_address"], "203.0.113.10")
            self.assertEqual(item["account_id"], "account-a")
            self.assertEqual(item["device_id"], "device-a")
            self.assertEqual(item["payment_token"], "token-p")
            self.assertEqual(item["address_token"], "token-a")
        self.assertIsNone(self.create(device_id="   ")["device_id"])
        for invalid in ("not-an-ip", "203.0.113.999", "fe80::1%eth0"):
            self.assertEqual(self.client.post("/cases", json={**LOW_RISK_CASE, "ip_address": invalid}).status_code, 422)

    def test_each_identity_triggers_at_exact_limit(self):
        for field, value in (("ip_address", "203.0.113.11"), ("device_id", "device-b"), ("account_id", "account-b")):
            with self.subTest(field=field):
                for _ in range(9):
                    self.create(**{field: value})
                before = self.client.get("/monitoring/sentinel").json()["alerts"]
                self.assertFalse(any(t["field"] == field for a in before for t in a["triggers"]))
                self.create(**{field: value})
                after = self.client.get("/monitoring/sentinel").json()["alerts"]
                alert = next(a for a in after if a["triggers"][0]["field"] == field)
                self.assertEqual(alert["count"], 10)
                self.assertEqual(alert["classification"], "Unusual return velocity")

    def test_missing_and_unrelated_identities_do_not_link(self):
        self.burst()
        for index in range(10):
            self.create(account_id=f"unique-{index}", device_id=f"device-{index}")
        status = self.client.get("/monitoring/sentinel").json()
        self.assertEqual(status["alerts"], [])
        self.assertEqual(status["request_count"], 20)
        self.assertEqual(status["identified_count"], 10)

    def test_rolling_window_excludes_boundary_and_future_requests(self):
        cases = self.burst(ip_address="203.0.113.20")
        now = api.utc_now()
        with self.session_factory() as db:
            db.get(api.RiskCase, cases[0]["id"]).created_at = now - timedelta(minutes=10)
            db.get(api.RiskCase, cases[1]["id"]).created_at = now + timedelta(seconds=1)
            db.commit()
            status = monitor(db, now=now)
        self.assertEqual(status["request_count"], 8)
        self.assertEqual(status["alerts"], [])

    def test_overlapping_ring_has_one_alert_with_evidence(self):
        for index in range(10):
            self.create(account_id=f"ring-{index}", device_id="ring-device", ip_address="203.0.113.30", payment_token="ring-payment", address_token="ring-address")
        status = self.client.get("/monitoring/sentinel").json()
        self.assertEqual(len(status["alerts"]), 1)
        alert = status["alerts"][0]
        self.assertEqual(alert["classification"], "Possible coordinated abuse")
        self.assertEqual(alert["account_count"], 10)
        self.assertEqual(len(alert["cases"]), 10)
        self.assertEqual({t["field"] for t in alert["triggers"]}, {"device_id", "ip_address"})
        self.assertTrue(any(s["field"] == "payment_token" and s["count"] == 10 for s in alert["similarities"]))
        self.assertEqual(status["restrictions"], [])

    def test_settings_are_persisted_and_validated(self):
        self.create(device_id="configured")
        self.create(device_id="configured")
        self.assertEqual(self.client.get("/monitoring/sentinel").json()["alerts"], [])
        response = self.client.patch("/monitoring/sentinel/settings", json={"threshold": 2, "window_minutes": 5})
        self.assertEqual(response.status_code, 200)
        status = self.client.get("/monitoring/sentinel").json()
        self.assertEqual(status["settings"], {"threshold": 2, "window_minutes": 5})
        self.assertEqual(len(status["alerts"]), 1)
        self.assertEqual(self.client.patch("/monitoring/sentinel/settings", json={"threshold": 0, "window_minutes": 0}).status_code, 422)

    def test_linked_pause_blocks_manual_and_automatic_approvals(self):
        cases = self.burst(device_id="held-device")
        restriction = self.pause()
        new_case = self.create(device_id="held-device")
        unrelated = self.create(device_id="unrelated")
        self.assertIsNotNone(new_case["gateway_restriction"])
        self.assertIsNone(unrelated["gateway_restriction"])
        with self.session_factory() as db:
            for item in (cases[0], unrelated):
                db.get(api.RiskCase, item["id"]).decision_due_at = api.utc_now() - timedelta(seconds=1)
            db.commit()
        listed = {item["id"]: item for item in self.client.get("/cases").json()["cases"]}
        self.assertEqual(listed[cases[0]["id"]]["system_decision"], "PENDING_AUTO_APPROVAL")
        self.assertEqual(listed[unrelated["id"]]["system_decision"], "AUTO_APPROVED")
        self.assertEqual(self.client.patch(f"/cases/{new_case['id']}/decision", json={"decision": "APPROVED"}).status_code, 409)
        # Review/rejection still works after the original approval deadline.
        self.assertEqual(self.client.patch(f"/cases/{cases[0]['id']}/decision", json={"decision": "REJECTED"}).status_code, 200)
        self.assertEqual(self.client.patch(f"/cases/{cases[0]['id']}/decision", json={"decision": "APPROVED"}).status_code, 409)
        resumed = self.client.post(f"/monitoring/sentinel/restrictions/{restriction['id']}/resume")
        self.assertEqual(resumed.json()["status"], "RESUMED")
        self.assertEqual(self.client.patch(f"/cases/{new_case['id']}/decision", json={"decision": "APPROVED"}).status_code, 200)
        events = self.client.get(f"/cases/{new_case['id']}/review").json()["events"]
        self.assertTrue(any(event["event_type"] == "GATEWAY_RESUMED" for event in events))

    def test_expiry_resumes_overdue_approvals_and_survives_session_changes(self):
        cases = self.burst(account_id="expiry")
        restriction = self.pause()
        with self.session_factory() as db:
            db.get(api.RiskCase, cases[0]["id"]).decision_due_at = api.utc_now() - timedelta(seconds=2)
            db.commit()
        self.assertIsNotNone(self.client.get(f"/cases/{cases[0]['id']}").json()["case"]["gateway_restriction"])
        with self.session_factory() as db:
            db.get(api.GatewayRestriction, restriction["id"]).expires_at = api.utc_now() - timedelta(seconds=1)
            db.commit()
        case = self.client.get(f"/cases/{cases[0]['id']}").json()["case"]
        self.assertEqual(case["system_decision"], "AUTO_APPROVED")
        self.assertIsNone(case["gateway_restriction"])
        self.assertEqual(self.client.get("/monitoring/sentinel").json()["history"][0]["status"], "EXPIRED")

    def test_demo_scenarios_and_gateway_pause_are_isolated_from_live(self):
        with patch("api.main.predict_return", return_value={"abuse_probability": .01, "risk_score": 1, "risk_level": "LOW", "action": "AUTO_APPROVE"}):
            demo = self.client.post("/monitoring/sentinel/demo", json={"scenario": "ring", "count": 10})
        self.assertEqual(demo.status_code, 200, demo.text)
        self.assertEqual(len(demo.json()["monitoring"]["alerts"]), 1)
        self.assertEqual(self.client.get("/monitoring/sentinel").json()["request_count"], 0)
        restriction = self.pause(is_test=True, scope="gateway")
        self.assertIsNone(self.create(device_id="live")["gateway_restriction"])
        self.assertIsNotNone(self.create(is_test=True, device_id="unrelated-demo")["gateway_restriction"])
        self.assertEqual(self.client.get("/monitoring/sentinel").json()["restrictions"], [])
        self.assertEqual(restriction["scope"], "gateway")

    def test_stale_alert_and_invalid_restriction_are_rejected(self):
        response = self.client.post("/monitoring/sentinel/restrictions", json={"alert_id": "missing", "duration_minutes": 15})
        self.assertEqual(response.status_code, 409)
        self.assertEqual(self.client.post("/monitoring/sentinel/restrictions", json={"alert_id": "missing", "duration_minutes": 999}).status_code, 422)
        self.assertEqual(self.client.post("/monitoring/sentinel/demo", json={"count": 101}).status_code, 422)

    def test_additive_migration_preserves_legacy_cases_and_is_repeatable(self):
        legacy = create_engine("sqlite://")
        with legacy.begin() as connection:
            connection.execute(text("CREATE TABLE risk_cases (id INTEGER PRIMARY KEY, created_at DATETIME, merchant_decision VARCHAR, recommended_action VARCHAR)"))
            connection.execute(text("INSERT INTO risk_cases VALUES (1, '2026-08-01 12:00:00', NULL, 'AUTO_APPROVE')"))
        with patch("api.main.engine", legacy):
            api.migrate_local_schema()
            api.migrate_local_schema()
        columns = {item["name"] for item in inspect(legacy).get_columns("risk_cases")}
        self.assertTrue(set(api.IDENTITY_FIELDS).issubset(columns))
        with legacy.connect() as connection:
            row = connection.execute(text("SELECT is_test, device_id, system_decision FROM risk_cases WHERE id=1")).one()
        self.assertEqual(tuple(row), (0, None, "PENDING_AUTO_APPROVAL"))
        legacy.dispose()

    def test_overlapping_pauses_require_all_to_end(self):
        case = self.burst(device_id="overlap")[0]
        first = self.pause()
        second = self.pause(scope="gateway")
        unrelated = self.create(device_id="another-device")
        self.assertIsNotNone(unrelated["gateway_restriction"])
        self.client.post(f"/monitoring/sentinel/restrictions/{first['id']}/resume")
        self.assertEqual(self.client.patch(f"/cases/{case['id']}/decision", json={"decision": "APPROVED"}).status_code, 409)
        self.client.post(f"/monitoring/sentinel/restrictions/{second['id']}/resume")
        self.assertEqual(self.client.patch(f"/cases/{case['id']}/decision", json={"decision": "APPROVED"}).status_code, 200)

    def test_all_demo_variants_and_negative_control(self):
        with patch("api.main.predict_return", return_value={"abuse_probability": .01, "risk_score": 1, "risk_level": "LOW", "action": "AUTO_APPROVE"}):
            normal = self.client.post("/monitoring/sentinel/demo", json={"scenario": "normal"}).json()
            self.assertEqual(normal["monitoring"]["alerts"], [])
            below = self.client.post("/monitoring/sentinel/demo", json={"scenario": "ring", "count": 9}).json()
            self.assertEqual(below["monitoring"]["alerts"], [])
            for scenario, field in (("ip", "ip_address"), ("device", "device_id"), ("account", "account_id")):
                with self.subTest(scenario=scenario):
                    result = self.client.post("/monitoring/sentinel/demo", json={"scenario": scenario}).json()
                    alert = next(a for a in result["monitoring"]["alerts"] if result["case_ids"][0] in [c["id"] for c in a["cases"]])
                    self.assertEqual([t["field"] for t in alert["triggers"]], [field])
                    self.assertEqual(alert["classification"], "Unusual return velocity")

    def test_case_details_include_local_ring_explanation(self):
        case = self.burst(device_id="explain-this")[0]
        detail = self.client.get(f"/cases/{case['id']}").json()["case"]
        self.assertEqual(detail["linked_alerts"][0]["count"], 10)
        self.assertIn("explain-this", detail["linked_alerts"][0]["summary"])

    def test_gateway_pause_never_reopens_completed_auto_approval(self):
        case = self.burst(device_id="already-final")[0]
        with self.session_factory() as db:
            db.get(api.RiskCase, case["id"]).decision_due_at = api.utc_now() - timedelta(seconds=1)
            db.commit()
        self.assertEqual(self.client.get(f"/cases/{case['id']}").json()["case"]["system_decision"], "AUTO_APPROVED")
        self.pause()
        self.assertEqual(self.client.patch(f"/cases/{case['id']}/decision", json={"decision": "REJECTED"}).status_code, 409)
        self.assertIsNone(self.client.get(f"/cases/{case['id']}").json()["case"]["gateway_restriction"])

    def test_changed_alert_membership_requires_new_confirmation(self):
        self.burst(device_id="membership")
        original = self.client.get("/monitoring/sentinel").json()["alerts"][0]["id"]
        self.create(device_id="membership", account_id="new-account")
        response = self.client.post("/monitoring/sentinel/restrictions", json={"alert_id": original})
        self.assertEqual(response.status_code, 409)
        self.assertEqual(self.client.get("/monitoring/sentinel").json()["restrictions"], [])

    def test_continuous_patterns_do_not_require_a_burst_or_recent_window(self):
        self.create(device_id="shared-quiet", location="Pune")
        self.create(device_id="shared-quiet", location="pune")
        with self.session_factory() as db:
            for row in db.query(RequestArrival).all():
                row.created_at = api.utc_now() - timedelta(days=30)
            db.commit()
        result = self.client.get("/monitoring/patterns").json()
        self.assertEqual(result["request_count"], 2)
        self.assertEqual(result["linked_request_count"], 2)
        self.assertEqual({p["field"] for p in result["patterns"]}, {"device_id", "location"})
        self.assertEqual(next(p for p in result["patterns"] if p["field"] == "location")["strength"], "Context only")

    def test_patterns_keep_demo_and_live_identities_separate(self):
        self.create(ip_address="203.0.113.9", is_test=False)
        self.create(ip_address="203.0.113.9", is_test=True)
        self.assertEqual(self.client.get("/monitoring/patterns").json()["patterns"], [])
        self.create(ip_address="203.0.113.9", is_test=True)
        result = self.client.get("/monitoring/patterns").json()
        self.assertEqual(len(result["patterns"]), 1)
        self.assertTrue(result["patterns"][0]["is_test"])
        self.assertEqual(result["patterns"][0]["count"], 2)

    def test_traffic_counts_test_cases_by_default_without_identity_matches(self):
        for index in range(10):
            self.create(is_test=True, account_id=f"independent-{index}")
        result = self.client.get("/monitoring/traffic").json()
        self.assertEqual(result["request_count"], 10)
        self.assertEqual(result["demo_count"], 10)
        self.assertEqual(sum(b["count"] for b in result["buckets"]), 10)
        self.assertEqual(result["active_pauses"], [])
        self.assertEqual(self.client.get("/monitoring/traffic?source=live").json()["request_count"], 0)
        self.assertEqual(self.client.get("/monitoring/patterns").json()["patterns"], [])

    def test_traffic_time_bucket_boundaries_and_scales(self):
        for _ in range(4):
            self.create()
        now = api.utc_now().replace(minute=30, second=30, microsecond=0)
        current = now.replace(second=0)
        start = current - timedelta(minutes=59)
        with self.session_factory() as db:
            rows = db.query(RequestArrival).order_by(RequestArrival.id).all()
            for row, created in zip(rows, (start - timedelta(seconds=1), start, current, now + timedelta(seconds=1))):
                row.created_at = created
            db.commit()
            result = traffic_snapshot(db, now=now)
            self.assertEqual(result["request_count"], 2)
            self.assertEqual(result["buckets"][0]["count"], 1)
            self.assertEqual(result["buckets"][-1]["count"], 1)
            self.assertEqual(len(traffic_snapshot(db, scale="hour", now=now)["buckets"]), 24)
            self.assertEqual(len(traffic_snapshot(db, scale="five_minutes", now=now)["buckets"]), 72)

    def test_volume_spike_compares_prior_intervals_and_handles_zero_history(self):
        for _ in range(13):
            self.create()
        now = api.utc_now().replace(second=45, microsecond=0)
        current = now.replace(second=0)
        with self.session_factory() as db:
            rows = db.query(RequestArrival).order_by(RequestArrival.id).all()
            for index, row in enumerate(rows):
                row.created_at = current if index < 10 else current - timedelta(minutes=1)
            db.commit()
            result = traffic_snapshot(db, now=now)
            self.assertTrue(result["buckets"][-1]["spike"])
            self.assertEqual(result["buckets"][-1]["comparison"], "relative")
            self.assertEqual(result["buckets"][-1]["baseline"], .25)

    def test_research_is_on_demand_scoped_and_never_pauses_intake(self):
        for _ in range(2):
            self.create(device_id="research-pair", is_test=True)
        now = api.utc_now()
        result = self.client.post("/monitoring/traffic/research", json={"source": "demo", "start": api.utc_iso(now - timedelta(minutes=1)), "end": api.utc_iso(now + timedelta(seconds=1))})
        self.assertEqual(result.status_code, 200, result.text)
        self.assertEqual(result.json()["request_count"], 2)
        self.assertEqual(result.json()["patterns"][0]["field"], "device_id")
        self.assertEqual(self.client.get("/monitoring/traffic").json()["active_pauses"], [])
        self.assertEqual(self.client.post("/monitoring/traffic/research", json={"start": "2026-08-29T10:00:00", "end": "2026-08-29T11:00:00"}).status_code, 422)

    def test_intake_pause_refuses_new_cases_but_preserves_existing_approvals(self):
        existing = self.create()
        due = self.create()
        paused = self.client.post("/monitoring/intake/pauses", json={"scope": "all", "duration_minutes": 15, "reason": "Merchant investigating traffic"})
        self.assertEqual(paused.status_code, 200)
        response = self.client.post("/cases", json=LOW_RISK_CASE)
        self.assertEqual(response.status_code, 503)
        self.assertGreater(int(response.headers["Retry-After"]), 0)
        with self.session_factory() as db:
            self.assertEqual(db.query(api.RiskCase).count(), 2)
            self.assertEqual(db.query(RequestArrival).filter(RequestArrival.status == "paused").count(), 1)
            db.get(api.RiskCase, due["id"]).decision_due_at = api.utc_now() - timedelta(seconds=1)
            db.commit()
        self.assertEqual(self.client.patch(f"/cases/{existing['id']}/decision", json={"decision": "APPROVED"}).status_code, 200)
        self.assertEqual(self.client.get(f"/cases/{due['id']}").json()["case"]["system_decision"], "AUTO_APPROVED")
        traffic = self.client.get("/monitoring/traffic").json()
        self.assertEqual(traffic["request_count"], 3)
        self.assertEqual(traffic["paused_count"], 1)

    def test_intake_pause_scope_batch_rejection_resume_and_expiry(self):
        pause = self.client.post("/monitoring/intake/pauses", json={"scope": "demo", "reason": "Demo pause"}).json()
        self.create(is_test=False)
        response = self.client.post("/monitoring/sentinel/demo", json={"count": 10})
        self.assertEqual(response.status_code, 503)
        traffic = self.client.get("/monitoring/traffic").json()
        self.assertEqual(traffic["demo_count"], 10)
        self.assertEqual(traffic["paused_count"], 10)
        self.assertEqual(self.client.get("/cases").json()["count"], 1)
        result = self.client.post(f"/monitoring/intake/pauses/{pause['id']}/resume").json()
        self.assertEqual(result["status"], "RESUMED")
        self.create(is_test=True)
        second = self.client.post("/monitoring/intake/pauses", json={"scope": "all", "reason": "Expiry check"}).json()
        with self.session_factory() as db:
            db.get(IntakePause, second["id"]).expires_at = api.utc_now() - timedelta(seconds=1)
            db.commit()
        self.create(is_test=True)
        self.assertEqual(self.client.get("/monitoring/traffic").json()["pause_history"][0]["status"], "EXPIRED")

    def test_overlapping_intake_pauses_and_invalid_controls(self):
        first = self.client.post("/monitoring/intake/pauses", json={"scope": "all", "reason": "Investigating"}).json()
        self.client.post("/monitoring/intake/pauses", json={"scope": "demo", "reason": "Demo investigation"})
        self.client.post(f"/monitoring/intake/pauses/{first['id']}/resume")
        self.assertEqual(self.client.post("/cases", json={**LOW_RISK_CASE, "is_test": True}).status_code, 503)
        self.create(is_test=False)
        self.assertEqual(self.client.post("/monitoring/intake/pauses", json={"scope": "all", "duration_minutes": 900, "reason": "invalid"}).status_code, 422)
        self.assertEqual(self.client.post("/monitoring/intake/pauses", json={"scope": "all", "reason": "   "}).status_code, 422)
        self.assertEqual(self.client.get("/monitoring/traffic?scale=seconds").status_code, 422)
        self.assertEqual(self.client.post("/monitoring/intake/pauses/999/resume").status_code, 404)

    def test_delete_anonymizes_arrival_but_preserves_traffic_count(self):
        case = self.create(account_id="remove-identity", location="Pune")
        self.assertEqual(self.client.delete(f"/cases/{case['id']}").status_code, 200)
        self.create(account_id="new-identity")
        result = self.client.get("/monitoring/patterns").json()
        self.assertEqual(result["request_count"], 2)
        with self.session_factory() as db:
            old = db.query(RequestArrival).filter(RequestArrival.case_id.is_(None)).one()
            self.assertIsNone(old.account_id)
            self.assertIsNone(old.location)

    def test_legacy_arrivals_backfill_once_with_original_time_and_identity(self):
        case = self.create(account_id="legacy-account", location="Pune")
        with self.session_factory() as db:
            stored = db.get(api.RiskCase, case["id"])
            stored.created_at = api.utc_now() - timedelta(days=2)
            original_time = stored.created_at
            db.query(RequestArrival).delete()
            db.commit()
        with patch("api.main.engine", self.engine):
            api.backfill_arrival_history()
            api.backfill_arrival_history()
        with self.session_factory() as db:
            row = db.query(RequestArrival).one()
            self.assertEqual(row.case_id, case["id"])
            self.assertEqual(row.created_at, original_time)
            self.assertEqual(row.account_id, "legacy-account")
            self.assertEqual(row.location, "Pune")

    @classmethod
    def tearDownClass(cls):
        api.app.dependency_overrides.clear()
        cls.temp.cleanup()

    def test_review_workflow(self):
        created = self.client.post("/cases", json=LOW_RISK_CASE)
        self.assertEqual(created.status_code, 200)
        case_id = created.json()["case"]["id"]
        self.assertEqual(created.json()["case"]["external_reference"], "ORDER-TEST-001")
        self.assertEqual(created.json()["case"]["system_decision"], "PENDING_AUTO_APPROVAL")
        self.assertIsNotNone(created.json()["case"]["decision_due_at"])

        listed = self.client.get("/cases").json()["cases"]
        order = next(item for item in listed if item["id"] == case_id)
        self.assertEqual(order["system_decision"], "PENDING_AUTO_APPROVAL")

        explanation = self.client.get(f"/cases/{case_id}/explanation")
        self.assertEqual(explanation.status_code, 200)
        self.assertGreater(len(explanation.json()["explanation"]), 0)

        decision = self.client.patch(f"/cases/{case_id}/decision", json={"decision": "APPROVED"})
        self.assertEqual(decision.json()["merchant_decision"], "APPROVED")
        self.assertEqual(decision.json()["system_decision"], "MERCHANT_OVERRIDE")

        evidence = self.client.post(
            f"/cases/{case_id}/evidence",
            content=b"demo-image",
            headers={"content-type": "image/png", "x-filename": "delivery.png"},
        )
        self.assertEqual(evidence.status_code, 200)
        evidence_id = evidence.json()["evidence_id"]

        with patch("api.main.verify_evidence_file", return_value=EVIDENCE_RESULT):
            verified = self.client.post(f"/cases/{case_id}/evidence/{evidence_id}/verify")
        self.assertEqual(verified.status_code, 200)
        self.assertEqual(verified.json()["verification"]["result"]["claim_consistency"], "SUPPORTS_CLAIM")

        outcome = self.client.post(
            f"/cases/{case_id}/outcome",
            json={"outcome": "CONFIRMED_LEGITIMATE", "note": "Delivery proof matched."},
        )
        self.assertEqual(outcome.status_code, 200)

        review = self.client.get(f"/cases/{case_id}/review").json()
        self.assertEqual(len(review["evidence"]), 1)
        self.assertEqual(review["evidence"][0]["verification"]["result"]["confidence"], 0.81)
        self.assertEqual(len(review["events"]), 5)
        feedback = self.client.get("/feedback/summary").json()
        self.assertEqual(feedback["verified_cases"], 1)
        self.assertEqual(feedback["human_decisions"], 1)

    def test_due_auto_approval_and_closed_override_window(self):
        payload = {**LOW_RISK_CASE, "external_reference": "ORDER-TEST-002"}
        created = self.client.post("/cases", json=payload)
        self.assertEqual(created.status_code, 200)
        case_id = created.json()["case"]["id"]

        with self.session_factory() as db:
            case = db.query(api.RiskCase).filter(api.RiskCase.id == case_id).first()
            case.decision_due_at = api.utc_now() - timedelta(seconds=1)
            db.commit()

        listed = self.client.get("/cases").json()["cases"]
        order = next(item for item in listed if item["id"] == case_id)
        self.assertEqual(order["system_decision"], "AUTO_APPROVED")

        too_late = self.client.patch(f"/cases/{case_id}/decision", json={"decision": "REJECTED"})
        self.assertEqual(too_late.status_code, 409)

    def test_delete_case_removes_related_review_data_and_file(self):
        payload = {**LOW_RISK_CASE, "external_reference": "ORDER-DELETE-001"}
        case_id = self.client.post("/cases", json=payload).json()["case"]["id"]
        evidence = self.client.post(
            f"/cases/{case_id}/evidence",
            content=b"delete-me",
            headers={"content-type": "image/png", "x-filename": "delete.png"},
        )
        evidence_id = evidence.json()["evidence_id"]
        with patch("api.main.verify_evidence_file", return_value=EVIDENCE_RESULT):
            self.client.post(f"/cases/{case_id}/evidence/{evidence_id}/verify")

        with self.session_factory() as db:
            item = db.query(api.CaseEvidence).filter(api.CaseEvidence.id == evidence_id).first()
            storage_path = Path(item.storage_path)
        self.assertTrue(storage_path.exists())

        deleted = self.client.delete(f"/cases/{case_id}")
        self.assertEqual(deleted.status_code, 200)
        self.assertFalse(storage_path.exists())
        self.assertEqual(self.client.get(f"/cases/{case_id}").status_code, 404)
        with self.session_factory() as db:
            self.assertEqual(db.query(api.CaseEvent).filter(api.CaseEvent.case_id == case_id).count(), 0)
            self.assertEqual(db.query(api.CaseEvidence).filter(api.CaseEvidence.case_id == case_id).count(), 0)
            self.assertEqual(db.query(api.EvidenceVerification).filter(api.EvidenceVerification.case_id == case_id).count(), 0)

    def test_cost_recalculation_and_ratio_validation(self):
        costs = self.client.patch(
            "/model/cost-settings",
            json={"false_positive_cost": 600, "false_negative_cost": 1600},
        )
        self.assertEqual(costs.status_code, 200)
        self.assertIn("business_impact", costs.json()["model"])
        self.assertGreater(len(costs.json()["model"]["cost_curve"]), 0)

        invalid = {**LOW_RISK_CASE, "return_ratio": 0.9}
        self.assertEqual(self.client.post("/predict", json=invalid).status_code, 422)


if __name__ == "__main__":
    unittest.main()
