import os
import pandas as pd
import joblib

from decision_engine import make_decision


# ============================================================
# Configuration
# ============================================================

MODEL_PATH = "models/risk_model.pkl"


# ============================================================
# Load trained model
# ============================================================

def load_model():

    if not os.path.exists(MODEL_PATH):

        raise FileNotFoundError(
            "Trained model not found. "
            "Run 'py src/train.py' first."
        )

    model = joblib.load(
        MODEL_PATH
    )

    return model


# ============================================================
# Predict a new return request
# ============================================================

def predict_return(
    model,
    return_request
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
        abuse_probability
    )


    return {
        "abuse_probability": round(
            abuse_probability,
            4
        ),
        **decision
    }


# ============================================================
# Test
# ============================================================

if __name__ == "__main__":

    print(
        "\n========== LOADING MODEL =========="
    )

    model = load_model()

    print(
        "Model loaded successfully!"
    )


    # ========================================================
    # New LOW-RISK request
    # ========================================================

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


    # ========================================================
    # New HIGH-RISK request
    # ========================================================

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