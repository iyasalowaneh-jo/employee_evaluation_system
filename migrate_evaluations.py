"""
Migration script to add missing columns to evaluations table
Run this once to update the database schema
"""
from app import app
from models import db
from sqlalchemy import text

def migrate_evaluations_table():
    """Add missing columns to evaluations table"""
    with app.app_context():
        try:
            # Check if columns exist and add them if they don't
            print("Migrating evaluations table...")
            
            # Check and add status column
            try:
                db.session.execute(text("SELECT status FROM evaluations LIMIT 1"))
                print("✓ Column 'status' already exists")
            except Exception:
                print("Adding column 'status'...")
                db.session.execute(text("ALTER TABLE evaluations ADD COLUMN status VARCHAR(20) DEFAULT 'draft'"))
                print("✓ Added column 'status'")
            
            # Check and add approved_at column
            try:
                db.session.execute(text("SELECT approved_at FROM evaluations LIMIT 1"))
                print("✓ Column 'approved_at' already exists")
            except Exception:
                print("Adding column 'approved_at'...")
                db.session.execute(text("ALTER TABLE evaluations ADD COLUMN approved_at DATETIME NULL"))
                print("✓ Added column 'approved_at'")
            
            # Check and add approved_by column
            try:
                db.session.execute(text("SELECT approved_by FROM evaluations LIMIT 1"))
                print("✓ Column 'approved_by' already exists")
            except Exception:
                print("Adding column 'approved_by'...")
                db.session.execute(text("ALTER TABLE evaluations ADD COLUMN approved_by INT NULL"))
                # Add foreign key constraint
                try:
                    db.session.execute(text("""
                        ALTER TABLE evaluations 
                        ADD CONSTRAINT fk_evaluations_approved_by 
                        FOREIGN KEY (approved_by) REFERENCES employees(employee_id)
                    """))
                except Exception as e:
                    print(f"Note: Foreign key constraint may already exist: {e}")
                print("✓ Added column 'approved_by'")
            
            db.session.commit()
            print("\n✅ Migration complete! Database schema updated.")
            
        except Exception as e:
            db.session.rollback()
            print(f"\n❌ Migration error: {e}")
            print("You may need to drop and recreate the tables.")
            raise

if __name__ == '__main__':
    migrate_evaluations_table()
