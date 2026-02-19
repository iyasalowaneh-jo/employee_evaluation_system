"""
Load the evaluation relationship dataset into MySQL from data/evaluation_relationships.csv.
Creates the evaluation_relationships table (if needed) and fills it from the CSV.

Run from project root:
  python load_evaluation_dataset_to_mysql.py

Then open MySQL Workbench (or any client), connect to your database,
and query: SELECT * FROM evaluation_relationships;
"""
import csv
import os
import sys

_project_root = os.path.dirname(os.path.abspath(__file__))
_data_dir = os.path.join(_project_root, 'data')
_csv_path = os.path.join(_data_dir, 'evaluation_relationships.csv')

sys.path.insert(0, _project_root)

from app import app
from models import db, EvaluationRelationship


def load_dataset():
    if not os.path.isfile(_csv_path):
        print("Error: evaluation_relationships.csv not found at", _csv_path)
        print("Create it from matrix.xlsx (e.g. with pandas) or place the CSV in the data folder.")
        return

    with app.app_context():
        db.create_all()
        print("Table evaluation_relationships ready.")

        deleted = db.session.query(EvaluationRelationship).delete()
        if deleted:
            print(f"Cleared {deleted} existing rows.")

        inserted = 0
        with open(_csv_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                evaluator = (row.get('evaluator') or '').strip()
                evaluatee = (row.get('evaluatee') or '').strip()
                rel = (row.get('relationship') or 'x').strip().lower()
                if rel not in ('1', '0', 'x'):
                    rel = 'x'
                if not evaluator or not evaluatee:
                    continue
                rec = EvaluationRelationship(
                    evaluator_role=evaluator,
                    evaluatee_role=evaluatee,
                    relationship=rel,
                )
                db.session.add(rec)
                inserted += 1

        db.session.commit()
        print(f"Inserted {inserted} rows into evaluation_relationships.")
        print("\nYou can open it in MySQL:")
        print("  1. Open MySQL Workbench and connect to your database.")
        print("  2. In the left panel, expand your schema -> Tables.")
        print("  3. Right-click evaluation_relationships -> Select Rows - Limit 1000")
        print("  Or run: SELECT * FROM evaluation_relationships;")


if __name__ == '__main__':
    load_dataset()
