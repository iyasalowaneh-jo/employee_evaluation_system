"""
Migration script to add is_open_ended column to feedback_questions table
and make score nullable in feedback_evaluations table
"""
from app import app
from models import db
from sqlalchemy import text

def migrate_open_ended():
    """Add is_open_ended column and update score to nullable"""
    with app.app_context():
        try:
            # Add is_open_ended column to feedback_questions if it doesn't exist
            db.session.execute(text("""
                ALTER TABLE feedback_questions 
                ADD COLUMN is_open_ended BOOLEAN DEFAULT FALSE
            """))
            print("[OK] Added is_open_ended column to feedback_questions")
        except Exception as e:
            error_str = str(e)
            if "Duplicate column name" in error_str or "already exists" in error_str or "1050" in error_str:
                print("[OK] is_open_ended column already exists")
            else:
                print(f"Error adding is_open_ended: {error_str}")
        
        try:
            # Make score nullable in feedback_evaluations
            db.session.execute(text("""
                ALTER TABLE feedback_evaluations 
                MODIFY COLUMN score FLOAT NULL
            """))
            print("[OK] Made score column nullable in feedback_evaluations")
        except Exception as e:
            error_str = str(e)
            if "Duplicate column name" in error_str or "1054" in error_str:
                print("[OK] score column is already nullable")
            else:
                print(f"Error modifying score column: {error_str}")
        
        db.session.commit()
        print("Migration completed successfully!")

if __name__ == '__main__':
    migrate_open_ended()
