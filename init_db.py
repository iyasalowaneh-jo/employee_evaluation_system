"""
Database initialization script.
Run this script to create all tables in the database.
"""

from app import app
from models import db, User, Employee, KPI, EvaluationCycle, Evaluation, RandomizationLog
from datetime import date

def init_database():
    """Initialize database with tables and default admin user"""
    with app.app_context():
        # Create all tables
        print("Creating database tables...")
        db.create_all()
        print("✓ Tables created successfully!")
        
        # Check if admin user exists
        admin_user = User.query.filter_by(email='admin@company.com').first()
        if not admin_user:
            print("\nCreating default admin user...")
            
            # Create admin employee
            admin_employee = Employee(
                full_name='Admin User',
                email='admin@company.com',
                department='IT',
                role='Administrator',
                join_date=date.today(),
                status='active'
            )
            db.session.add(admin_employee)
            db.session.flush()
            
            # Create admin user account
            admin_user = User(
                employee_id=admin_employee.employee_id,
                email='admin@company.com',
                role='admin'
            )
            admin_user.set_password('admin123')
            db.session.add(admin_user)
            db.session.commit()
            
            print("✓ Default admin user created!")
            print("  Email: admin@company.com")
            print("  Password: admin123")
            print("  ⚠️  IMPORTANT: Change this password after first login!")
        else:
            print("\nAdmin user already exists. Skipping admin creation.")
        
        print("\n✅ Database initialization complete!")
        print("\nYou can now run the application with: python app.py")

if __name__ == '__main__':
    init_database()
