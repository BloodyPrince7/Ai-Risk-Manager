import pandas as pd
import joblib

from sklearn.model_selection import train_test_split
from sklearn.compose import ColumnTransformer
from sklearn.preprocessing import OneHotEncoder
from sklearn.pipeline import Pipeline

from sklearn.metrics import (
    precision_score,
    recall_score,
    f1_score,
    classification_report,
    confusion_matrix
)

from xgboost import XGBClassifier


# ============================================================
# Configuration
# ============================================================

DATA_PATH = "data/raw/return_abuse_dataset.csv"
MODEL_PATH = "models/risk_model.pkl"


# ============================================================
# Load dataset
# ============================================================

df = pd.read_csv(DATA_PATH)


# ============================================================
# Separate features and target
# ============================================================

X = df.drop("is_abuse", axis=1)
y = df["is_abuse"]


# ============================================================
# Feature definitions
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
# Train/Test Split
# ============================================================

X_train, X_test, y_train, y_test = train_test_split(
    X,
    y,
    test_size=0.20,
    random_state=42,
    stratify=y
)


print("\n========== DATA SPLIT ==========")

print(
    f"Training samples: {len(X_train)}"
)

print(
    f"Testing samples:  {len(X_test)}"
)

print("\nTraining class distribution:")

print(
    y_train.value_counts(normalize=True)
)

print("\nTesting class distribution:")

print(
    y_test.value_counts(normalize=True)
)


# ============================================================
# Preprocessing
# ============================================================

preprocessor = ColumnTransformer(
    transformers=[
        (
            "categorical",
            OneHotEncoder(
                handle_unknown="ignore"
            ),
            categorical_features
        )
    ],
    remainder="passthrough"
)


# ============================================================
# XGBoost model
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
# Complete ML pipeline
# ============================================================

pipeline = Pipeline(
    steps=[
        (
            "preprocessor",
            preprocessor
        ),
        (
            "model",
            model
        )
    ]
)


# ============================================================
# Train
# ============================================================

print("\n========== TRAINING MODEL ==========")

pipeline.fit(
    X_train,
    y_train
)

print("Training complete!")


# ============================================================
# Predictions
# ============================================================

y_pred = pipeline.predict(
    X_test
)


# ============================================================
# Model evaluation
# ============================================================

precision = precision_score(
    y_test,
    y_pred
)

recall = recall_score(
    y_test,
    y_pred
)

f1 = f1_score(
    y_test,
    y_pred
)


print("\n========== MODEL PERFORMANCE ==========")

print(
    f"Precision: {precision:.4f}"
)

print(
    f"Recall:    {recall:.4f}"
)

print(
    f"F1 Score:  {f1:.4f}"
)


print("\n========== CLASSIFICATION REPORT ==========")

print(
    classification_report(
        y_test,
        y_pred,
        target_names=[
            "Legitimate",
            "Abuse"
        ]
    )
)


print("\n========== CONFUSION MATRIX ==========")

print(
    confusion_matrix(
        y_test,
        y_pred
    )
)


# ============================================================
# Feature importance
# ============================================================

feature_names = (
    pipeline
    .named_steps["preprocessor"]
    .get_feature_names_out()
)

importances = (
    pipeline
    .named_steps["model"]
    .feature_importances_
)


feature_importance = pd.DataFrame({
    "feature": feature_names,
    "importance": importances
})


feature_importance = (
    feature_importance
    .sort_values(
        "importance",
        ascending=False
    )
)


print("\n========== FEATURE IMPORTANCE ==========")

print(
    feature_importance.to_string(
        index=False
    )
)


# ============================================================
# Save trained pipeline
# ============================================================
#
# We save:
#
#     preprocessing
#          +
#     XGBoost model
#
# together.
#
# This guarantees that prediction uses the same feature
# transformation that training used.
# ============================================================

joblib.dump(
    pipeline,
    MODEL_PATH
)


print("\n========== MODEL SAVED ==========")

print(
    f"Model saved to: {MODEL_PATH}"
)