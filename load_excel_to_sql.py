import pandas as pd
from sqlalchemy import create_engine

# =========================
# DATABASE CONFIG
# =========================

DB_USER = "root"
DB_PASSWORD = "Pihu%40123"
DB_HOST = "localhost"
DB_NAME = "ticket_system"

# =========================
# CREATE CONNECTION
# =========================

engine = create_engine(
    f"mysql+pymysql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}/{DB_NAME}"
)

# =========================
# LOAD EXCEL FILE
# =========================

df = pd.read_excel("insurance_ticket_resolution_data.xlsx")

# =========================
# RENAME COLUMNS
# =========================

df = df.rename(columns={
    "Ticket_ID": "ticket_id",
    "Issue_Title": "issue_title",
    "Issue_Description": "issue_description",
    "Resolution_Steps": "resolution_steps",
    "Status": "status"
})

# =========================
# SELECT REQUIRED COLUMNS
# =========================

df = df[
    [
        "ticket_id",
        "issue_title",
        "issue_description",
        "resolution_steps",
        "status"
    ]
]

# =========================
# ADD INGESTED COLUMN
# =========================

df["ingested"] = False

# =========================
# INSERT INTO SQL
# =========================

df.to_sql(
    name="tickets",
    con=engine,
    if_exists="append",
    index=False
)

print("Data inserted successfully!")