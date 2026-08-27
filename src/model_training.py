"""Shared validation, evaluation, and artifact helpers for risk models."""

from datetime import datetime, timezone
from pathlib import Path
import tempfile

import joblib
import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.metrics import confusion_matrix, roc_auc_score
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder
from xgboost import XGBClassifier


FALSE_POSITIVE_COST = 500
FALSE_NEGATIVE_COST = 1500
CATEGORICAL_FEATURES = ["claim_type", "product_category"]
NUMERICAL_FEATURES = [
    "customer_age_days", "previous_orders", "previous_returns",
    "previous_refunds", "return_ratio", "refund_ratio", "order_value",
    "days_since_purchase", "account_count", "address_reuse_count",
    "device_reuse_count", "payment_failures",
]
FEATURE_COLUMNS = NUMERICAL_FEATURES + CATEGORICAL_FEATURES
TARGET_COLUMN = "is_abuse"
REQUIRED_COLUMNS = FEATURE_COLUMNS + [TARGET_COLUMN]


def validate_training_data(frame: pd.DataFrame) -> pd.DataFrame:
    missing = [column for column in REQUIRED_COLUMNS if column not in frame.columns]
    extra = [column for column in frame.columns if column not in REQUIRED_COLUMNS]
    if missing:
        raise ValueError(f"Missing required columns: {', '.join(missing)}")
    if extra:
        raise ValueError(f"Unexpected columns: {', '.join(extra)}")
    if len(frame) < 20:
        raise ValueError("Upload at least 20 labeled rows so the model can be evaluated safely.")
    if frame[REQUIRED_COLUMNS].isnull().any().any():
        raise ValueError("The CSV contains blank values. Every required field must be populated.")

    clean = frame[REQUIRED_COLUMNS].copy()
    for column in NUMERICAL_FEATURES + [TARGET_COLUMN]:
        try:
            clean[column] = pd.to_numeric(clean[column], errors="raise")
        except (TypeError, ValueError):
            raise ValueError(f"Column '{column}' must contain numbers only.") from None

    integer_columns = [
        "customer_age_days", "previous_orders", "previous_returns",
        "previous_refunds", "days_since_purchase", "account_count",
        "address_reuse_count", "device_reuse_count", "payment_failures",
    ]
    if (clean[integer_columns] < 0).any().any():
        raise ValueError("Count and day columns cannot contain negative values.")
    if (clean[integer_columns] % 1 != 0).any().any():
        raise ValueError("Count and day columns must contain whole numbers.")
    if (clean["previous_orders"] < 1).any():
        raise ValueError("previous_orders must be at least 1.")
    if (clean["account_count"] < 1).any():
        raise ValueError("account_count must be at least 1.")
    if (clean["previous_returns"] > clean["previous_orders"]).any():
        raise ValueError("previous_returns cannot exceed previous_orders.")
    if (clean["previous_refunds"] > clean["previous_orders"]).any():
        raise ValueError("previous_refunds cannot exceed previous_orders.")
    if ((clean[["return_ratio", "refund_ratio"]] < 0) | (clean[["return_ratio", "refund_ratio"]] > 1)).any().any():
        raise ValueError("return_ratio and refund_ratio must be between 0 and 1.")
    if not np.allclose(clean["return_ratio"], clean["previous_returns"] / clean["previous_orders"], atol=0.001):
        raise ValueError("return_ratio must equal previous_returns / previous_orders.")
    if not np.allclose(clean["refund_ratio"], clean["previous_refunds"] / clean["previous_orders"], atol=0.001):
        raise ValueError("refund_ratio must equal previous_refunds / previous_orders.")
    if (clean["order_value"] < 0).any():
        raise ValueError("order_value cannot be negative.")
    if not set(clean[TARGET_COLUMN].unique()).issubset({0, 1}):
        raise ValueError("is_abuse must contain only 0 (legitimate) or 1 (abuse).")
    if clean[TARGET_COLUMN].nunique() != 2:
        raise ValueError("is_abuse must include examples of both legitimate and abusive cases.")
    if clean[TARGET_COLUMN].value_counts().min() < 2:
        raise ValueError("Each is_abuse class needs at least 2 rows.")
    if (clean[CATEGORICAL_FEATURES].astype(str).apply(lambda values: values.str.strip().eq(""))).any().any():
        raise ValueError("claim_type and product_category cannot be empty.")

    clean[CATEGORICAL_FEATURES] = clean[CATEGORICAL_FEATURES].astype(str).apply(lambda values: values.str.strip())
    clean[TARGET_COLUMN] = clean[TARGET_COLUMN].astype(int)
    return clean


def build_pipeline() -> Pipeline:
    preprocessor = ColumnTransformer(
        [("categorical", OneHotEncoder(handle_unknown="ignore"), CATEGORICAL_FEATURES)],
        remainder="passthrough",
    )
    return Pipeline([
        ("preprocessor", preprocessor),
        ("model", XGBClassifier(
            n_estimators=300, max_depth=5, learning_rate=0.05,
            subsample=0.8, colsample_bytree=0.8,
            objective="binary:logistic", eval_metric="logloss", random_state=42,
        )),
    ])


def select_cost_threshold(performance: list[dict], false_positive_cost: int, false_negative_cost: int) -> dict:
    cost_rows = [{
        **row,
        "false_positive_cost": row["fp"] * false_positive_cost,
        "false_negative_cost": row["fn"] * false_negative_cost,
        "total_cost": row["fp"] * false_positive_cost + row["fn"] * false_negative_cost,
    } for row in performance]
    return min(cost_rows, key=lambda row: (row["total_cost"], row["threshold"]))


def metrics_from_counts(counts: dict, roc_auc: float) -> dict:
    tn, fp, fn, tp = (counts[key] for key in ("tn", "fp", "fn", "tp"))
    total = tn + fp + fn + tp
    precision = tp / (tp + fp) if tp + fp else 0
    recall = tp / (tp + fn) if tp + fn else 0
    return {
        "accuracy": round((tn + tp) / total if total else 0, 4),
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "f1": round(2 * precision * recall / (precision + recall) if precision + recall else 0, 4),
        "roc_auc": round(float(roc_auc), 4),
    }


def apply_cost_settings(metadata: dict, false_positive_cost: int, false_negative_cost: int) -> dict:
    updated = dict(metadata)
    selected = select_cost_threshold(updated["threshold_performance"], false_positive_cost, false_negative_cost)
    high_threshold = selected["threshold"]
    low_threshold = round(max(0.01, high_threshold / 2), 2)
    counts = {key: selected[key] for key in ("tn", "fp", "fn", "tp")}
    approve_all_cost = (counts["fn"] + counts["tp"]) * false_negative_cost
    review_all_cost = (counts["tn"] + counts["fp"]) * false_positive_cost
    best_baseline_cost = min(approve_all_cost, review_all_cost)
    updated.update({
        "metrics": metrics_from_counts(counts, updated["metrics"]["roc_auc"]),
        "confusion_matrix": counts,
        "cost_analysis": {
            "false_positive_unit_cost": false_positive_cost,
            "false_negative_unit_cost": false_negative_cost,
            "false_positive_cost": selected["false_positive_cost"],
            "false_negative_cost": selected["false_negative_cost"],
            "total_cost": selected["total_cost"],
            "currency": "INR",
        },
        "business_impact": {
            "approve_all_cost": approve_all_cost,
            "review_all_cost": review_all_cost,
            "ai_policy_cost": selected["total_cost"],
            "savings_vs_best_baseline": best_baseline_cost - selected["total_cost"],
            "best_baseline": "approve_all" if approve_all_cost <= review_all_cost else "review_all",
        },
        "routing_thresholds": {"low": low_threshold, "high": high_threshold},
    })
    return updated


def evaluate_predictions(y_test, probabilities) -> dict:
    candidates = np.arange(0.05, 0.96, 0.05)
    performance = []
    for threshold in candidates:
        predictions = (probabilities >= threshold).astype(int)
        tn, fp, fn, tp = confusion_matrix(y_test, predictions, labels=[0, 1]).ravel()
        performance.append({
            "threshold": round(float(threshold), 2),
            "tn": int(tn), "fp": int(fp), "fn": int(fn), "tp": int(tp),
        })
    base = {
        "metrics": {"roc_auc": round(float(roc_auc_score(y_test, probabilities)), 4)},
        "threshold_performance": performance,
        "threshold_selection": "Minimum FP/FN cost on the held-out set; low threshold is half the review threshold.",
    }
    return apply_cost_settings(base, FALSE_POSITIVE_COST, FALSE_NEGATIVE_COST)


def save_model_artifact(pipeline: Pipeline, metadata: dict, model_path: Path) -> None:
    model_path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=model_path.parent, suffix=".pkl", delete=False) as handle:
        temporary_path = Path(handle.name)
    try:
        joblib.dump({"model": pipeline, "metadata": metadata}, temporary_path)
        temporary_path.replace(model_path)
    finally:
        temporary_path.unlink(missing_ok=True)


def train_model(frame: pd.DataFrame, model_path: Path, source: str, dataset_name: str):
    clean = validate_training_data(frame)
    x_train, x_test, y_train, y_test = train_test_split(
        clean[FEATURE_COLUMNS], clean[TARGET_COLUMN], test_size=0.2,
        random_state=42, stratify=clean[TARGET_COLUMN],
    )
    pipeline = build_pipeline()
    pipeline.fit(x_train, y_train)
    probabilities = pipeline.predict_proba(x_test)[:, 1]
    metadata = {
        "model_source": source,
        "dataset_name": dataset_name,
        "trained_at": datetime.now(timezone.utc).isoformat(),
        "rows": len(clean),
        "training_rows": len(x_train),
        "test_rows": len(x_test),
        **evaluate_predictions(y_test, probabilities),
    }
    save_model_artifact(pipeline, metadata, model_path)
    return pipeline, metadata


def train_custom_model(frame: pd.DataFrame, model_path: Path, dataset_name: str = "merchant-upload.csv"):
    return train_model(frame, model_path, "merchant_trained", dataset_name)
