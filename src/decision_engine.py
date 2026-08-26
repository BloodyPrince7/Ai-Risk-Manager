
# ============================================================
# AI Risk Manager — Decision Engine
# ============================================================
#
# The ML model answers:
#
#     "How risky is this return request?"
#
# The Decision Engine answers:
#
#     "What should the merchant do about it?"
#
# Keeping these two responsibilities separate makes our
# architecture easier to test and modify.
# ============================================================


# ============================================================
# Risk thresholds
# ============================================================

LOW_RISK_THRESHOLD = 0.20
HIGH_RISK_THRESHOLD = 0.60


# ============================================================
# Main decision function
# ============================================================

def make_decision(risk_probability):
    """
    Convert an ML risk probability into a merchant action.

    Parameters
    ----------
    risk_probability : float
        Probability predicted by the ML model.
        Expected range: 0.0 to 1.0

    Returns
    -------
    dict
        Risk level, score, action and explanation.
    """

    # --------------------------------------------------------
    # Validate probability
    # --------------------------------------------------------

    if not 0 <= risk_probability <= 1:
        raise ValueError(
            "Risk probability must be between 0 and 1."
        )


    # --------------------------------------------------------
    # LOW RISK
    # --------------------------------------------------------

    if risk_probability < LOW_RISK_THRESHOLD:

        return {
            "risk_score": float(
    round(
        risk_probability * 100,
        2
    )
),
            "risk_level": "LOW",
            "action": "AUTO_APPROVE",
            "message": (
                "Return request appears low risk. "
                "Automatically approve."
            )
        }


    # --------------------------------------------------------
    # MEDIUM RISK
    # --------------------------------------------------------

    if risk_probability < HIGH_RISK_THRESHOLD:

        return {
            "risk_score": float(
    round(
        risk_probability * 100,
        2
    )
),
            "risk_level": "MEDIUM",
            "action": "REQUEST_EVIDENCE",
            "message": (
                "Return request has moderate risk. "
                "Request additional evidence before "
                "processing the refund."
            )
        }


    # --------------------------------------------------------
    # HIGH RISK
    # --------------------------------------------------------

    return {
        "risk_score": float(
    round(
        risk_probability * 100,
        2
    )
),
        "risk_level": "HIGH",
        "action": "MANUAL_REVIEW",
        "message": (
            "Return request has high abuse risk. "
            "Send the case for manual review."
        )
    }


# ============================================================
# Test the Decision Engine
# ============================================================

if __name__ == "__main__":

    test_probabilities = [
        0.08,
        0.19,
        0.35,
        0.59,
        0.60,
        0.83,
        0.97
    ]

    print(
        "\n========== DECISION ENGINE TEST ==========\n"
    )

    for probability in test_probabilities:

        decision = make_decision(
            probability
        )

        print(
            f"Probability: {probability:.2f}"
        )

        print(
            f"Risk Score:  {decision['risk_score']}%"
        )

        print(
            f"Risk Level:  {decision['risk_level']}"
        )

        print(
            f"Action:      {decision['action']}"
        )

        print(
            f"Message:     {decision['message']}"
        )

        print("-" * 50)
