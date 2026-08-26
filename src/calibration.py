
import pandas as pd
import numpy as np

from sklearn.model_selection import train_test_split
from sklearn.compose import ColumnTransformer
from sklearn.preprocessing import OneHotEncoder
from sklearn.pipeline import Pipeline

from sklearn.metrics import (
    brier_score_loss,
    roc_auc_score
)

from sklearn.calibration import calibration_curve

from xgboost import XGBClassifier


# ============================================================
# 1. Load dataset
# ============================================================

DATA_PATH = "data/raw/return_abuse_dataset.csv"

df = pd.read_csv(DATA_PATH)


# ============================================================
# 2. Separate features and target
# ============================================================

X = df.drop("is_abuse", axis=1)
y = df["is_abuse"]


# ============================================================
# 3. Feature definitions
# ============================================================

categorical_features = [
    "claim_type",
    "product_category"
]

numerical_features = [
    "customer_age_days",
    "previous_orders",
    "previous_returns",
    "previous_refunds",
    "return_ratio",
    "refund_ratio",
    "order_value",
    "days_since_purchase",
    "account_count",
    "address_reuse_count",
    "device_reuse_count",
    "payment_failures"
]


# ============================================================
# 4. Train/Test Split
# ============================================================

X_train, X_test, y_train, y_test = train_test_split(
    X,
    y,
    test_size=0.20,
    random_state=42,
    stratify=y
)


# ============================================================
# 5. Preprocessing
# ============================================================

preprocessor = ColumnTransformer(
    transformers=[
        (
            "categorical",
            OneHotEncoder(handle_unknown="ignore"),
            categorical_features
        )
    ],
    remainder="passthrough"
)


# ============================================================
# 6. XGBoost model
# ============================================================

model = XGBClassifier(
    n_estimators=300,
    max_depth=5,
    learning_rate=0.05,
    subsample=0.8,
    colsample_bytree=0.8,
    objective="binary:logistic",
    eval_metric="logloss",
    random_state=42
)


# ============================================================
# 7. Pipeline
# ============================================================

pipeline = Pipeline(
    steps=[
        ("preprocessor", preprocessor),
        ("model", model)
    ]
)


# ============================================================
# 8. Train
# ============================================================

print("\n========== TRAINING MODEL ==========")

pipeline.fit(X_train, y_train)

print("Training complete!")


# ============================================================
# 9. Get probabilities
# ============================================================

probabilities = pipeline.predict_proba(X_test)

abuse_probabilities = probabilities[:, 1]


# ============================================================
# 10. Brier Score
# ============================================================
#
# Brier score measures how close predicted probabilities
# are to the actual outcomes.
#
# Lower = better
#
# Perfect score = 0
# ============================================================

brier = brier_score_loss(
    y_test,
    abuse_probabilities
)


print("\n========== CALIBRATION METRICS ==========")

print(
    f"Brier Score: {brier:.4f}"
)


# ============================================================
# 11. ROC-AUC
# ============================================================
#
# ROC-AUC measures how well the model ranks abusive
# cases above legitimate cases.
#
# 1.0 = perfect ranking
# 0.5 = random ranking
# ============================================================

auc = roc_auc_score(
    y_test,
    abuse_probabilities
)


print(
    f"ROC-AUC:     {auc:.4f}"
)


# ============================================================
# 12. Calibration curve
# ============================================================
#
# We divide predictions into probability bins.
#
# Example:
#
# Model predicts around 0.8
# Actual abuse rate = 0.76
#
# That's reasonably calibrated.
# ============================================================

prob_true, prob_pred = calibration_curve(
    y_test,
    abuse_probabilities,
    n_bins=10,
    strategy="uniform"
)


print("\n========== CALIBRATION CURVE ==========")

print(
    f"{'Predicted':<15}"
    f"{'Actual':<15}"
)

for predicted, actual in zip(
    prob_pred,
    prob_true
):

    print(
        f"{predicted:<15.3f}"
        f"{actual:<15.3f}"
    )


# ============================================================
# 13. Calibration interpretation
# ============================================================

print("\n========== INTERPRETATION ==========")

print(
    "If Predicted and Actual values are close, "
    "the model is well calibrated."
)

print(
    "Example: Predicted 0.70 / Actual 0.68 "
    "is reasonably calibrated."
)
