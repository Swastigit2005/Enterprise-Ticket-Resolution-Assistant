import pandas as pd

from db import get_connection

# ==========================================
# LOAD EXCEL
# ==========================================

EXCEL_FILE = (
    "insurance_ticket_resolution_data.xlsx"
)

df = pd.read_excel(
    EXCEL_FILE
)

# ==========================================
# DB CONNECTION
# ==========================================

conn = get_connection()

cursor = conn.cursor()

# ==========================================
# UPDATE TICKETS
# ==========================================

updated_count = 0

for _, row in df.iterrows():

    cursor.execute(
        """
        UPDATE tickets
        SET
            ticket_date=%s,
            priority=%s,
            customer_name=%s,
            customer_email=%s,
            assigned_to=%s,
            issue_category=%s
        WHERE ticket_id=%s
        """,
        (
            row["Date"],
            row["Priority"],
            row["Customer_Name"],
            row["Customer_Email"],
            row["Assigned_To"],
            row["Issue_Category"],
            row["Ticket_ID"]
        )
    )

    updated_count += 1

# ==========================================
# COMMIT
# ==========================================

conn.commit()

cursor.close()
conn.close()

print(
    f"{updated_count} tickets updated successfully."
)