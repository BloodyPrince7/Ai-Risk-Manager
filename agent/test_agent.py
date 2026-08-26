from .investigator import investigate_case


case = {

    "id": 1,

    "customer_age_days": 400,

    "previous_orders": 10,

    "previous_returns": 6,

    "previous_refunds": 4,

    "return_ratio": 0.6,

    "refund_ratio": 0.4,

    "order_value": 8500,

    "days_since_purchase": 5,

    "account_count": 3,

    "address_reuse_count": 4,

    "device_reuse_count": 5,

    "payment_failures": 2,

    "claim_type": "missing_item",

    "product_category": "electronics",

    "abuse_probability": 0.9966,

    "risk_score": 99.66,

    "risk_level": "HIGH",

    "recommended_action": "MANUAL_REVIEW"
}


result = investigate_case(case)


print()
print("========== AI INVESTIGATION ==========")
print()

print("SUMMARY:")
print(result["summary"])

print()

print("RISK FACTORS:")

for factor in result["risk_factors"]:
    print(f"  • {factor}")

print()

print("EVIDENCE TO CHECK:")

for evidence in result["evidence_to_check"]:
    print(f"  • {evidence}")

print()

print("RECOMMENDED ACTION:")
print(result["recommended_action"])

print()

print("AI CONFIDENCE:")
print(
    f"{result['confidence'] * 100:.1f}%"
)