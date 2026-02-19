"""
Migration script to add status column to feedback_evaluations table
"""
from app import app
from models import db
from sqlalchemy import text

def migrate_feedback_status():
    """Add status column to feedback_evaluations"""
    with app.app_context():
        try:
            # Check if column exists
            db.session.execute(text("SELECT status FROM feedback_evaluations LIMIT 1"))
            print("[OK] Column 'status' already exists")
        except Exception:
            try:
                # Add status column
                print("Adding column 'status'...")
                db.session.execute(text("""
                    ALTER TABLE feedback_evaluations 
                    ADD COLUMN status VARCHAR(20) DEFAULT 'draft'
                """))
                print("[OK] Added column 'status'")
            except Exception as e:
                print(f"Error adding status column: {e}")
        
        try:
            # Make submitted_at nullable
            db.session.execute(text("""
                ALTER TABLE feedback_evaluations 
                MODIFY COLUMN submitted_at DATETIME NULL
            """))
            print("[OK] Made submitted_at nullable")
        except Exception as e:
            error_str = str(e)
            if "Duplicate column name" in error_str or "1054" in error_str:
                print("[OK] submitted_at is already nullable")
            else:
                print(f"Error modifying submitted_at: {error_str}")
        
        db.session.commit()
        print("Migration completed successfully!")

if __name__ == '__main__':
    migrate_feedback_status()
