import pandas as pd

# -----------------------------------------
# Load dataset
# -----------------------------------------

DATA_PATH = "data/raw/return_abuse_dataset.csv"

df = pd.read_csv(DATA_PATH)


# -----------------------------------------
# Basic information
# -----------------------------------------

print("\n========== DATASET INFO ==========")

print(f"Rows: {df.shape[0]}")
print(f"Columns: {df.shape[1]}")


# -----------------------------------------
# Column names
# -----------------------------------------

print("\n========== COLUMNS ==========")

for column in df.columns:
    print(column)


# -----------------------------------------
# Missing values
# -----------------------------------------

print("\n========== MISSING VALUES ==========")

print(df.isnull().sum())


# -----------------------------------------
# Target distribution
# -----------------------------------------

print("\n========== TARGET DISTRIBUTION ==========")

print(df["is_abuse"].value_counts())

print("\nPercentage:")
print(
    df["is_abuse"]
    .value_counts(normalize=True)
    .mul(100)
    .round(2)
)


# -----------------------------------------
# Numerical statistics
# -----------------------------------------

print("\n========== NUMERICAL STATISTICS ==========")

print(df.describe())


# -----------------------------------------
# Categorical values
# -----------------------------------------

print("\n========== CATEGORICAL FEATURES ==========")

print("\nClaim Types:")
print(df["claim_type"].value_counts())

print("\nProduct Categories:")
print(df["product_category"].value_counts())


# -----------------------------------------
# Compare behavior by class
# -----------------------------------------

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