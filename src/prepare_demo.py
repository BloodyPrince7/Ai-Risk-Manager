"""Create a deterministic, internally consistent dataset and demo cases."""

import json
from pathlib import Path

import numpy as np
import pandas as pd


ROOT_DIR = Path(__file__).resolve().parent.parent
OUTPUT_DIR = ROOT_DIR / "data" / "demo"
RANDOM_SEED = 20260826
ROWS = 500


def build_training_data() -> pd.DataFrame:
    rng = np.random.default_rng(RANDOM_SEED)
    previous_orders = np.maximum(rng.poisson(12, ROWS), 1)
    previous_returns = np.minimum(rng.poisson(2, ROWS), previous_orders)
    previous_refunds = np.minimum(rng.poisson(1.3, ROWS), previous_orders)
    return_ratio = previous_returns / previous_orders
    refund_ratio = previous_refunds / previous_orders
    account_count = rng.choice([1, 2, 3, 4], ROWS, p=[0.80, 0.13, 0.05, 0.02])
    address_reuse = rng.poisson(1.2, ROWS)
    device_reuse = rng.poisson(1.5, ROWS)
    payment_failures = rng.poisson(0.5, ROWS)
    order_value = np.clip(rng.lognormal(7.5, 0.75, ROWS), 300, 100000)
    claim_type = rng.choice(["damaged", "wrong_item", "not_as_described", "changed_mind", "missing_item"], ROWS)
    category = rng.choice(["electronics", "fashion", "home", "beauty", "grocery"], ROWS)

    latent_risk = (
        2.5 * return_ratio + 2.0 * refund_ratio
        + 0.45 * np.maximum(account_count - 1, 0)
        + 0.20 * address_reuse + 0.20 * device_reuse
        + 0.15 * payment_failures
        + 0.000015 * np.maximum(order_value - 5000, 0)
        + 2.5 * return_ratio * refund_ratio
        + 0.8 * return_ratio * device_reuse
        + rng.normal(0, 0.20, ROWS)
    )
    probability = 1 / (1 + np.exp(-(latent_risk - 2.8)))
    labels = rng.binomial(1, probability)

    return pd.DataFrame({
        "customer_age_days": rng.integers(30, 1500, ROWS),
        "previous_orders": previous_orders,
        "previous_returns": previous_returns,
        "previous_refunds": previous_refunds,
        "return_ratio": return_ratio,
        "refund_ratio": refund_ratio,
        "order_value": order_value.round(2),
        "days_since_purchase": rng.integers(1, 60, ROWS),
        "account_count": account_count,
        "address_reuse_count": address_reuse,
        "device_reuse_count": device_reuse,
        "payment_failures": payment_failures,
        "claim_type": claim_type,
        "product_category": category,
        "is_abuse": labels,
    })


DEMO_CASES = [
    {
        "scenario": "Loyal customer, ordinary change-of-mind return",
        "expected_route": "LOW / AUTO_APPROVE",
        "request": {"customer_age_days": 900, "previous_orders": 24, "previous_returns": 1, "previous_refunds": 0, "return_ratio": 1 / 24, "refund_ratio": 0, "order_value": 1299, "days_since_purchase": 12, "account_count": 1, "address_reuse_count": 1, "device_reuse_count": 1, "payment_failures": 0, "claim_type": "changed_mind", "product_category": "fashion"},
    },
    {
        "scenario": "Repeat returner requiring evidence",
        "expected_route": "MEDIUM / REQUEST_EVIDENCE",
        "request": {"customer_age_days": 600, "previous_orders": 12, "previous_returns": 2, "previous_refunds": 0, "return_ratio": 2 / 12, "refund_ratio": 0, "order_value": 3000, "days_since_purchase": 8, "account_count": 1, "address_reuse_count": 1, "device_reuse_count": 2, "payment_failures": 0, "claim_type": "damaged", "product_category": "home"},
    },
    {
        "scenario": "Linked-account missing-item claim for a high-value order",
        "expected_route": "HIGH / MANUAL_REVIEW",
        "request": {"customer_age_days": 45, "previous_orders": 5, "previous_returns": 4, "previous_refunds": 3, "return_ratio": 0.8, "refund_ratio": 0.6, "order_value": 14999, "days_since_purchase": 2, "account_count": 4, "address_reuse_count": 5, "device_reuse_count": 6, "payment_failures": 3, "claim_type": "missing_item", "product_category": "electronics"},
    },
]


if __name__ == "__main__":
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    dataset = build_training_data()
    dataset.to_csv(OUTPUT_DIR / "demo_training.csv", index=False)
    (OUTPUT_DIR / "demo_cases.json").write_text(json.dumps(DEMO_CASES, indent=2), encoding="utf-8")
    print(f"Created {len(dataset)} training rows with seed {RANDOM_SEED}.")
    print(f"Abuse rate: {dataset['is_abuse'].mean():.1%}")
    print(f"Demo files: {OUTPUT_DIR}")
