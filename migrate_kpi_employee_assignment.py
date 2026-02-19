"""
Migration: Add applies_to_all and employee_kpis table for employee-based KPI assignment.
Backfills existing KPIs: applies_to_all=True when department and role were both None;
otherwise assigns to employees matching department/role.
"""
from app import app
from models import db, KPI, Employee
from sqlalchemy import text

def migrate():
    with app.app_context():
        # Create employee_kpis table if not exists
        db.create_all()
        
        # Add applies_to_all column if missing
        try:
            db.session.execute(text("ALTER TABLE kpis ADD COLUMN applies_to_all BOOLEAN DEFAULT FALSE NOT NULL"))
            db.session.commit()
            print("[OK] Added applies_to_all column to kpis")
        except Exception as e:
            if 'Duplicate column' in str(e) or 'already exists' in str(e).lower():
                print("[OK] applies_to_all column already exists")
            else:
                print(f"[WARN] applies_to_all: {e}")
            db.session.rollback()
        
        # Backfill: for each KPI, set applies_to_all or create employee_kpis links
        employees = list(Employee.query.all())
        for kpi in KPI.query.all():
            if getattr(kpi, 'applies_to_all', False):
                continue
            # Skip default KPIs - they are templates only, not auto-assigned to employees
            if getattr(kpi, 'is_default', False):
                continue
            # Skip if already has assignments (idempotent)
            if kpi.assigned_employees.count() > 0:
                continue
            kpi_dept = getattr(kpi, 'department', None)
            kpi_role = getattr(kpi, 'role', None)
            if kpi_dept is None and kpi_role is None:
                kpi.applies_to_all = True
                continue
            for emp in employees:
                dept_match = kpi_dept is None or emp.department == kpi_dept
                role_match = (kpi_role is None or
                             kpi_role.lower() in emp.role.lower() or
                             emp.role.lower() in kpi_role.lower())
                if dept_match and role_match:
                    if not kpi.assigned_employees.filter_by(employee_id=emp.employee_id).first():
                        kpi.assigned_employees.append(emp)
        db.session.commit()
        print("[OK] Backfilled KPI employee assignments")


if __name__ == '__main__':
    migrate()
