import pandas as pd


DATA_PATH = "data/raw/return_abuse_dataset.csv"

df = pd.read_csv(DATA_PATH)


print("\n========== DATASET INFO ==========")

print(f"Rows: {df.shape[0]}")
print(f"Columns: {df.shape[1]}")


print("\n========== COLUMNS ==========")

for column in df.columns:
    print(column)


print("\n========== MISSING VALUES ==========")

print(df.isnull().sum())


print("\n========== TARGET DISTRIBUTION ==========")

print(df["is_abuse"].value_counts())

print("\nPercentage:")
print(
    df["is_abuse"]
    .value_counts(normalize=True)
    .mul(100)
    .round(2)
)


print("\n========== NUMERICAL STATISTICS ==========")

print(df.describe())


print("\n========== CATEGORICAL FEATURES ==========")

print("\nClaim Types:")
print(df["claim_type"].value_counts())

print("\nProduct Categories:")
print(df["product_category"].value_counts())


print("\n========== BEHAVIOR BY CLASS ==========")

comparison = df.groupby("is_abuse")[
    [
        "order_value",
        "previous_orders",
        "previous_returns",
        "previous_refunds",
        "return_ratio",
        "refund_ratio",
        "account_count",
        "address_reuse_count",
        "device_reuse_count",
        "payment_failures"
    ]
].mean()

print(comparison)