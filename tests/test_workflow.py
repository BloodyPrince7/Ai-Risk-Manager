"""End-to-end API checks using isolated storage."""

import tempfile
import unittest
from datetime import timedelta
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import api.main as api


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
        cls.session_factory = sessionmaker(bind=engine)
        api.app.dependency_overrides[api.get_db] = lambda: cls.session_factory()
        api.MODEL_PATH = Path(cls.temp.name) / "risk_model.pkl"
        api.EVIDENCE_DIR = Path(cls.temp.name) / "evidence"
        cls.client = TestClient(api.app)

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
