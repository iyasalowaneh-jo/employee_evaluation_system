"""
Add include_kpi and include_360 columns to evaluation_cycles if missing.
Run once: python migrate_cycle_include_flags.py
"""
from app import app
from models import db
from sqlalchemy import text

def migrate():
    with app.app_context():
        for col, default in [('include_kpi', 1), ('include_360', 1)]:
            try:
                db.session.execute(text(f"SELECT {col} FROM evaluation_cycles LIMIT 1"))
                db.session.rollback()
                print(f"Column '{col}' already exists.")
            except Exception:
                db.session.rollback()
                print(f"Adding column '{col}'...")
                db.session.execute(text(f"ALTER TABLE evaluation_cycles ADD COLUMN {col} TINYINT(1) NOT NULL DEFAULT {default}"))
                db.session.commit()
                print(f"Added '{col}'.")
        print("Done.")

if __name__ == '__main__':
    migrate()
