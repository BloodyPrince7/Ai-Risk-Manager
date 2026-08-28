
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


DATA_PATH = "data/raw/return_abuse_dataset.csv"

df = pd.read_csv(DATA_PATH)


X = df.drop("is_abuse", axis=1)
y = df["is_abuse"]


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


X_train, X_test, y_train, y_test = train_test_split(
    X,
    y,
    test_size=0.20,
    random_state=42,
    stratify=y
)


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


pipeline = Pipeline(
    steps=[
        ("preprocessor", preprocessor),
        ("model", model)
    ]
)


print("\n========== TRAINING MODEL ==========")

pipeline.fit(X_train, y_train)

print("Training complete!")


probabilities = pipeline.predict_proba(X_test)

abuse_probabilities = probabilities[:, 1]


#
# Brier score measures how close predicted probabilities
# are to the actual outcomes.
#
# Lower = better
#
# Perfect score = 0

brier = brier_score_loss(
    y_test,
    abuse_probabilities
)


print("\n========== CALIBRATION METRICS ==========")

print(
    f"Brier Score: {brier:.4f}"
)


#
# ROC-AUC measures how well the model ranks abusive
# cases above legitimate cases.
#
# 1.0 = perfect ranking
# 0.5 = random ranking

auc = roc_auc_score(
    y_test,
    abuse_probabilities
)


print(
    f"ROC-AUC:     {auc:.4f}"
)


#
# We divide predictions into probability bins.
#
# Example:
#
# Model predicts around 0.8
# Actual abuse rate = 0.76
#
# That's reasonably calibrated.

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


print("\n========== INTERPRETATION ==========")

print(
    "If Predicted and Actual values are close, "
    "the model is well calibrated."
)

print(
    "Example: Predicted 0.70 / Actual 0.68 "
    "is reasonably calibrated."
)
