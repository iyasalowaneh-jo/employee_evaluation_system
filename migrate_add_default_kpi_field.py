"""
Migration script to add is_default field to KPIs table
Marks all existing KPIs created by seed_data.py as default KPIs
"""
from app import app, db
from sqlalchemy import text

def migrate():
    with app.app_context():
        try:
            # Check if column already exists
            result = db.session.execute(text("SHOW COLUMNS FROM kpis LIKE 'is_default'"))
            column_exists = result.fetchone() is not None
            
            if not column_exists:
                print("Adding is_default column to kpis table...")
                db.session.execute(text("ALTER TABLE kpis ADD COLUMN is_default BOOLEAN DEFAULT FALSE"))
                db.session.commit()
                print("[OK] Added is_default column")
            else:
                print("[SKIP] is_default column already exists")
            
            # Mark all existing KPIs (created by seed_data) as default
            # These are KPIs that don't have a created_by (system-created)
            print("\nMarking system KPIs as default...")
            result = db.session.execute(
                text("UPDATE kpis SET is_default = TRUE WHERE created_by IS NULL AND status = 'approved'")
            )
            rows_updated = result.rowcount
            db.session.commit()
            print(f"[OK] Marked {rows_updated} KPIs as default")
            
            # Also mark any KPIs that match the default KPI names/roles from seed_data
            # This ensures we catch all default KPIs even if they were modified
            default_kpi_roles = [
                'Data Processing Officer', 'QA Officer', 'DP Supervisor',
                'Operations Officer', 'Operations Manager', 'Field Manager',
                'Project Manager', 'PM Manager',
                'Senior Accountant', 'Accountant Officer', 'CFO',
                'Business Development Officer', 'Admin Officer',
                'CEO', 'Technical Manager', 'Unit Manager'
            ]
            
            for role in default_kpi_roles:
                result = db.session.execute(
                    text("UPDATE kpis SET is_default = TRUE WHERE role = :role AND created_by IS NULL"),
                    {'role': role}
                )
            
            db.session.commit()
            print("[OK] Migration completed successfully!")
            
        except Exception as e:
            db.session.rollback()
            print(f"[ERROR] Migration failed: {str(e)}")
            raise

if __name__ == '__main__':
    migrate()
