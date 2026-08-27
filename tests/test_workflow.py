"""End-to-end API checks using isolated storage."""

import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import api.main as api


LOW_RISK_CASE = {
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

        explanation = self.client.get(f"/cases/{case_id}/explanation")
        self.assertEqual(explanation.status_code, 200)
        self.assertGreater(len(explanation.json()["explanation"]), 0)

        decision = self.client.patch(f"/cases/{case_id}/decision", json={"decision": "APPROVED"})
        self.assertEqual(decision.json()["merchant_decision"], "APPROVED")

        evidence = self.client.post(
            f"/cases/{case_id}/evidence",
            content=b"demo-image",
            headers={"content-type": "image/png", "x-filename": "delivery.png"},
        )
        self.assertEqual(evidence.status_code, 200)

        outcome = self.client.post(
            f"/cases/{case_id}/outcome",
            json={"outcome": "CONFIRMED_LEGITIMATE", "note": "Delivery proof matched."},
        )
        self.assertEqual(outcome.status_code, 200)

        review = self.client.get(f"/cases/{case_id}/review").json()
        self.assertEqual(len(review["evidence"]), 1)
        self.assertEqual(len(review["events"]), 3)
        feedback = self.client.get("/feedback/summary").json()
        self.assertEqual(feedback["verified_cases"], 1)
        self.assertEqual(feedback["human_decisions"], 1)

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
