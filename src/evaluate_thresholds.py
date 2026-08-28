import pandas as pd
import numpy as np

from sklearn.model_selection import train_test_split
from sklearn.compose import ColumnTransformer
from sklearn.preprocessing import OneHotEncoder
from sklearn.pipeline import Pipeline

from sklearn.metrics import (
    precision_score,
    recall_score,
    f1_score,
    confusion_matrix
)

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


#
# IMPORTANT:
#
# predict() gives us:
#
#     0 or 1
#
# predict_proba() gives us:
#
#     probability of class 0
#     probability of class 1
#
# We need probability because we want to test
# different thresholds.

probabilities = pipeline.predict_proba(X_test)

abuse_probabilities = probabilities[:, 1]


thresholds = np.arange(
    0.10,
    0.91,
    0.05
)


print("\n========== THRESHOLD ANALYSIS ==========")

print(
    f"{'Threshold':<12}"
    f"{'Precision':<12}"
    f"{'Recall':<12}"
    f"{'F1':<12}"
    f"{'FP':<10}"
    f"{'FN':<10}"
)


for threshold in thresholds:

    # Convert probabilities into predictions
    predictions = (
        abuse_probabilities >= threshold
    ).astype(int)

    # Metrics
    precision = precision_score(
        y_test,
        predictions,
        zero_division=0
    )

    recall = recall_score(
        y_test,
        predictions,
        zero_division=0
    )

    f1 = f1_score(
        y_test,
        predictions,
        zero_division=0
    )

    # Confusion matrix
    tn, fp, fn, tp = confusion_matrix(
        y_test,
        predictions
    ).ravel()

    print(
        f"{threshold:<12.2f}"
        f"{precision:<12.3f}"
        f"{recall:<12.3f}"
        f"{f1:<12.3f}"
        f"{fp:<10}"
        f"{fn:<10}"
    )