
import numpy as np
import pandas as pd


NUM_SAMPLES = 20_000
RANDOM_SEED = 42

np.random.seed(RANDOM_SEED)


customer_age_days = np.random.randint(
    30,
    1500,
    NUM_SAMPLES
)

previous_orders = np.random.poisson(
    lam=12,
    size=NUM_SAMPLES
)

# Make sure every customer has at least 1 previous order
previous_orders = np.maximum(previous_orders, 1)


previous_returns = np.random.poisson(
    lam=2,
    size=NUM_SAMPLES
)

previous_refunds = np.random.poisson(
    lam=1.5,
    size=NUM_SAMPLES
)

# A customer cannot have more historical returns or refunds than orders.
# Enforcing this before ratios are calculated keeps every generated row
# compatible with the API and custom-training schema.
previous_returns = np.minimum(
    previous_returns,
    previous_orders
)

previous_refunds = np.minimum(
    previous_refunds,
    previous_orders
)


order_value = np.random.lognormal(
    mean=7.5,
    sigma=0.8,
    size=NUM_SAMPLES
)

order_value = np.clip(
    order_value,
    300,
    100_000
)

days_since_purchase = np.random.randint(
    1,
    60,
    NUM_SAMPLES
)


return_ratio = (
    previous_returns /
    np.maximum(previous_orders, 1)
)

refund_ratio = (
    previous_refunds /
    np.maximum(previous_orders, 1)
)


account_count = np.random.choice(
    [1, 2, 3, 4],
    size=NUM_SAMPLES,
    p=[0.82, 0.12, 0.04, 0.02]
)

address_reuse_count = np.random.poisson(
    lam=1.2,
    size=NUM_SAMPLES
)

device_reuse_count = np.random.poisson(
    lam=1.5,
    size=NUM_SAMPLES
)


payment_failures = np.random.poisson(
    lam=0.5,
    size=NUM_SAMPLES
)


claim_type = np.random.choice(
    [
        "damaged",
        "wrong_item",
        "not_as_described",
        "changed_mind",
        "missing_item"
    ],
    size=NUM_SAMPLES,
    p=[
        0.25,
        0.15,
        0.20,
        0.25,
        0.15
    ]
)


product_category = np.random.choice(
    [
        "electronics",
        "fashion",
        "home",
        "beauty",
        "grocery"
    ],
    size=NUM_SAMPLES,
    p=[
        0.25,
        0.30,
        0.20,
        0.10,
        0.15
    ]
)


#
# IMPORTANT:
#
# This is NOT our machine-learning model.
#
# We are creating a synthetic world where certain combinations
# of customer behaviors are more associated with abuse.
#
# The ML model will later try to learn these patterns WITHOUT
# being given this risk formula.

risk_score = np.zeros(NUM_SAMPLES)


risk_score += (
    2.5 * return_ratio
)


risk_score += (
    2.0 * refund_ratio
)


risk_score += (
    0.45 *
    np.maximum(account_count - 1, 0)
)


risk_score += (
    0.20 *
    address_reuse_count
)


risk_score += (
    0.20 *
    device_reuse_count
)


risk_score += (
    0.15 *
    payment_failures
)


risk_score += (
    0.000015 *
    np.maximum(order_value - 5000, 0)
)


#
# These are important because suspicious behavior is often
# stronger when multiple signals occur together.
#
# Example:
#
# High return rate alone:
#       → moderate concern
#
# High return rate + high refund rate:
#       → stronger concern
#
# High returns + refunds + device/account reuse:
#       → much stronger concern


# Return + refund interaction
risk_score += (
    2.5 *
    return_ratio *
    refund_ratio
)


# Return behavior + device reuse
risk_score += (
    0.8 *
    return_ratio *
    device_reuse_count
)


# Multiple accounts + address reuse
risk_score += (
    0.6 *
    np.maximum(account_count - 1, 0) *
    address_reuse_count
)


# Multiple accounts + device reuse
risk_score += (
    0.5 *
    np.maximum(account_count - 1, 0) *
    device_reuse_count
)


claim_risk = {
    "damaged": 0.10,
    "wrong_item": 0.05,
    "not_as_described": 0.15,
    "changed_mind": -0.05,
    "missing_item": 0.20
}

risk_score += np.array([
    claim_risk[claim]
    for claim in claim_type
])


category_risk = {
    "electronics": 0.20,
    "fashion": 0.05,
    "home": 0.10,
    "beauty": 0.00,
    "grocery": -0.05
}

risk_score += np.array([
    category_risk[category]
    for category in product_category
])


#
# Real-world behavior is not perfectly predictable.
#
# This prevents the dataset from becoming a simple deterministic
# rule-based problem.

risk_score += np.random.normal(
    loc=0,
    scale=0.20,
    size=NUM_SAMPLES
)


#
# Sigmoid converts the score into a value between 0 and 1.
#
# 0.0 → very low probability
# 0.5 → medium probability
# 1.0 → very high probability
#
# The 2.8 offset controls the overall prevalence of abuse.

abuse_probability = 1 / (
    1 +
    np.exp(
        -(risk_score - 2.8)
    )
)


print("\n========== RISK PROBABILITY ==========")

print(
    f"Mean:   {abuse_probability.mean():.4f}"
)

print(
    f"Median: {np.median(abuse_probability):.4f}"
)

print(
    f"Min:    {abuse_probability.min():.4f}"
)

print(
    f"Max:    {abuse_probability.max():.4f}"
)


#
# We don't simply say:
#
#     probability > 0.5 → abuse
#
# Instead, probability controls the chance that a sample
# receives the abuse label.
#
# This introduces realistic uncertainty.

is_abuse = np.random.binomial(
    n=1,
    p=abuse_probability
)


df = pd.DataFrame({

    "customer_age_days":
        customer_age_days,

    "previous_orders":
        previous_orders,

    "previous_returns":
        previous_returns,

    "previous_refunds":
        previous_refunds,

    "return_ratio":
        return_ratio,

    "refund_ratio":
        refund_ratio,

    "order_value":
        order_value,

    "days_since_purchase":
        days_since_purchase,

    "account_count":
        account_count,

    "address_reuse_count":
        address_reuse_count,

    "device_reuse_count":
        device_reuse_count,

    "payment_failures":
        payment_failures,

    "claim_type":
        claim_type,

    "product_category":
        product_category,

    "is_abuse":
        is_abuse
})


output_path = (
    "data/raw/return_abuse_dataset.csv"
)

df.to_csv(
    output_path,
    index=False
)


print("\n========== DATASET GENERATED ==========")

print(
    f"Rows: {len(df)}"
)

print(
    f"Columns: {len(df.columns)}"
)


print("\n========== CLASS DISTRIBUTION ==========")

print(
    df["is_abuse"].value_counts()
)


print("\n========== CLASS PERCENTAGE ==========")

print(
    df["is_abuse"]
    .value_counts(normalize=True)
    .mul(100)
    .round(2)
)


print("\n========== FIRST 5 ROWS ==========")

print(
    df.head()
)


print(
    f"\nDataset saved to: {output_path}"
)
