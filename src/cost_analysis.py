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


# ============================================================
# 1. Merchant cost assumptions
# ============================================================

FALSE_POSITIVE_COST = 100
FALSE_NEGATIVE_COST = 1500


# ============================================================
# 2. Load dataset
# ============================================================

DATA_PATH = "data/raw/return_abuse_dataset.csv"

df = pd.read_csv(DATA_PATH)


# ============================================================
# 3. Separate features and target
# ============================================================

X = df.drop("is_abuse", axis=1)
y = df["is_abuse"]


# ============================================================
# 4. Feature definitions
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
# 5. Train/Test Split
# ============================================================

X_train, X_test, y_train, y_test = train_test_split(
    X,
    y,
    test_size=0.20,
    random_state=42,
    stratify=y
)


# ============================================================
# 6. Preprocessing
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
# 7. Model
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
# 8. Pipeline
# ============================================================

pipeline = Pipeline(
    steps=[
        ("preprocessor", preprocessor),
        ("model", model)
    ]
)


# ============================================================
# 9. Train
# ============================================================

print("\n========== TRAINING MODEL ==========")

pipeline.fit(X_train, y_train)

print("Training complete!")


# ============================================================
# 10. Get abuse probabilities
# ============================================================

probabilities = pipeline.predict_proba(X_test)

abuse_probabilities = probabilities[:, 1]


# ============================================================
# 11. Analyze thresholds
# ============================================================

thresholds = np.arange(
    0.10,
    0.91,
    0.05
)


results = []


print("\n========== COST ANALYSIS ==========")

print(
    f"{'Threshold':<12}"
    f"{'Precision':<12}"
    f"{'Recall':<12}"
    f"{'FP':<10}"
    f"{'FN':<10}"
    f"{'Cost':<15}"
)


for threshold in thresholds:

    predictions = (
        abuse_probabilities >= threshold
    ).astype(int)


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


    tn, fp, fn, tp = confusion_matrix(
        y_test,
        predictions
    ).ravel()


    total_cost = (
        fp * FALSE_POSITIVE_COST
        +
        fn * FALSE_NEGATIVE_COST
    )


    results.append({
        "threshold": threshold,
        "precision": precision,
        "recall": recall,
        "fp": fp,
        "fn": fn,
        "cost": total_cost
    })


    print(
        f"{threshold:<12.2f}"
        f"{precision:<12.3f}"
        f"{recall:<12.3f}"
        f"{fp:<10}"
        f"{fn:<10}"
        f"₹{total_cost:<14,.0f}"
    )


# ============================================================
# 12. Find minimum-cost threshold
# ============================================================

results_df = pd.DataFrame(results)

best_result = results_df.loc[
    results_df["cost"].idxmin()
]


print("\n========== OPTIMAL THRESHOLD ==========")

print(
    f"Threshold: {best_result['threshold']:.2f}"
)

print(
    f"Precision: {best_result['precision']:.3f}"
)

print(
    f"Recall:    {best_result['recall']:.3f}"
)

print(
    f"False Positives: {int(best_result['fp'])}"
)

print(
    f"False Negatives: {int(best_result['fn'])}"
)

print(
    f"Expected Cost: ₹{best_result['cost']:,.0f}"
)