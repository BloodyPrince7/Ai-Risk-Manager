import os
import pandas as pd
import joblib
from xgboost import DMatrix

from decision_engine import make_decision


MODEL_PATH = "models/risk_model.pkl"


def load_model():

    if not os.path.exists(MODEL_PATH):

        raise FileNotFoundError(
            "Trained model not found. "
            "Run 'py src/train.py' first."
        )

    artifact = joblib.load(
        MODEL_PATH
    )

    if isinstance(artifact, dict) and "model" in artifact:
        return artifact["model"]

    return artifact


def load_model_metadata():
    artifact = joblib.load(MODEL_PATH)
    if isinstance(artifact, dict):
        return artifact.get("metadata", {})
    return {}


def predict_return(
    model,
    return_request,
    thresholds=None
):

    # Convert dictionary into a one-row DataFrame
    input_df = pd.DataFrame(
        [return_request]
    )


    # Get abuse probability
    probabilities = model.predict_proba(
        input_df
    )

    abuse_probability = float(
        probabilities[0][1]
    )


    # Apply decision policy
    decision = make_decision(
        abuse_probability,
        thresholds=thresholds
    )


    return {
        "abuse_probability": round(
            abuse_probability,
            4
        ),
        **decision
    }


def explain_prediction(model, return_request, limit=8):
    """Return XGBoost feature contributions in log-odds space."""
    input_df = pd.DataFrame([return_request])
    preprocessor = model.named_steps["preprocessor"]
    estimator = model.named_steps["model"]
    transformed = preprocessor.transform(input_df)
    feature_names = preprocessor.get_feature_names_out()
    contributions = estimator.get_booster().predict(
        DMatrix(transformed),
        pred_contribs=True
    )[0][:-1]
    rows = []
    for name, contribution in zip(feature_names, contributions):
        clean_name = name.replace("categorical__", "").replace("remainder__", "")
        rows.append({
            "feature": clean_name,
            "contribution": round(float(contribution), 4),
            "direction": "increases_risk" if contribution >= 0 else "reduces_risk",
        })
    return sorted(rows, key=lambda row: abs(row["contribution"]), reverse=True)[:limit]


if __name__ == "__main__":

    print(
        "\n========== LOADING MODEL =========="
    )

    model = load_model()

    print(
        "Model loaded successfully!"
    )


    low_risk_request = {

        "customer_age_days": 700,

        "previous_orders": 15,

        "previous_returns": 1,

        "previous_refunds": 0,

        "return_ratio": 1 / 15,

        "refund_ratio": 0,

        "order_value": 1800,

        "days_since_purchase": 12,

        "account_count": 1,

        "address_reuse_count": 1,

        "device_reuse_count": 1,

        "payment_failures": 0,

        "claim_type": "changed_mind",

        "product_category": "grocery"
    }


    suspicious_request = {

        "customer_age_days": 400,

        "previous_orders": 10,

        "previous_returns": 6,

        "previous_refunds": 4,

        "return_ratio": 6 / 10,

        "refund_ratio": 4 / 10,

        "order_value": 8500,

        "days_since_purchase": 5,

        "account_count": 3,

        "address_reuse_count": 4,

        "device_reuse_count": 5,

        "payment_failures": 2,

        "claim_type": "missing_item",

        "product_category": "electronics"
    }


    cases = [
        (
            "LOW-RISK CASE",
            low_risk_request
        ),
        (
            "SUSPICIOUS CASE",
            suspicious_request
        )
    ]


    for name, request in cases:

        result = predict_return(
            model,
            request
        )


        print(
            f"\n========== {name} =========="
        )

        print(
            f"Abuse Probability: "
            f"{result['abuse_probability'] * 100:.2f}%"
        )

        print(
            f"Risk Score: "
            f"{result['risk_score']:.2f}%"
        )

        print(
            f"Risk Level: "
            f"{result['risk_level']}"
        )

        print(
            f"Action: "
            f"{result['action']}"
        )

        print(
            f"Message: "
            f"{result['message']}"
        )
