import pandas as pd

from sklearn.model_selection import train_test_split

# ==========================================
# LOAD DATA
# ==========================================

df = pd.read_excel(
    "insurance_ticket_resolution_data.xlsx"
)

# ==========================================
# KEEP ONLY RESOLVED TICKETS
# ==========================================

df = df[
    df["Status"] == "Resolved"
]

print(
    f"Resolved Tickets: {len(df)}"
)

# ==========================================
# STRATIFIED SPLIT
# ==========================================

vector_db_df = []
test_df = []

for category in df["Issue_Category"].unique():

    category_df = df[
        df["Issue_Category"] == category
    ]

    train_split, test_split = train_test_split(
        category_df,
        test_size=0.20,
        random_state=42,
        shuffle=True
    )

    vector_db_df.append(
        train_split
    )

    test_df.append(
        test_split
    )

# ==========================================
# MERGE SPLITS
# ==========================================

vector_db_df = pd.concat(
    vector_db_df
).reset_index(drop=True)

test_df = pd.concat(
    test_df
).reset_index(drop=True)

# ==========================================
# SAVE FILES
# ==========================================

vector_db_df.to_excel(
    "vector_db_dataset.xlsx",
    index=False
)

test_df.to_excel(
    "evaluation_test_dataset.xlsx",
    index=False
)

# ==========================================
# SUMMARY
# ==========================================

print("\nVECTOR DB DATASET")

print(
    vector_db_df["Issue_Category"]
    .value_counts()
)

print(
    f"\nTotal: {len(vector_db_df)}"
)

print("\nTEST DATASET")

print(
    test_df["Issue_Category"]
    .value_counts()
)

print(
    f"\nTotal: {len(test_df)}"
)

print(
    "\nFiles generated successfully."
)