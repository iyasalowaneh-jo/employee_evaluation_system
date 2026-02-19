"""
Build evaluation_relationships.csv from matrix.xlsx in the data folder.
"""
import pandas as pd
import os

# ====== CONFIG ======
DATA_DIR = os.path.dirname(os.path.abspath(__file__))
input_excel = os.path.join(DATA_DIR, "matrix.xlsx")
output_csv = os.path.join(DATA_DIR, "evaluation_relationships.csv")
# ====================

# Read matrix
df = pd.read_excel(input_excel)

# First column = employee names
df.rename(columns={df.columns[0]: "employee"}, inplace=True)
df.set_index("employee", inplace=True)

employees = df.index.tolist()

long_rows = []

# -------- BUILD RELATIONSHIPS --------
for emp_a in employees:
    for emp_b in employees:

        if emp_a == emp_b:
            continue

        val_ab = df.loc[emp_a, emp_b]
        val_ba = df.loc[emp_b, emp_a]

        # Resolve z / NaN by mirroring
        if pd.isna(val_ab) or val_ab == "z":
            final_value = val_ba
        else:
            final_value = val_ab

        # If still z or NaN, skip
        if pd.isna(final_value) or final_value == "z":
            continue

        long_rows.append({
            "evaluator": emp_a,
            "evaluatee": emp_b,
            "relationship": final_value
        })

relationships_df = pd.DataFrame(long_rows)

# -------- EXPORT evaluation_relationships.csv --------
relationships_df.to_csv(output_csv, index=False, encoding="utf-8")
print("evaluation_relationships.csv created:", output_csv)
