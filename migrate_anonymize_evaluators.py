"""
Migration script to anonymize evaluator IDs in existing data
This converts existing evaluator_id fields to evaluator_hash
"""
from app import app
from models import db, FeedbackEvaluation, RandomizationLog
from anonymization import hash_evaluator_id, hash_evaluator_metadata
from sqlalchemy import text

def migrate_anonymize_evaluators():
    """Anonymize evaluator IDs in existing data"""
    with app.app_context():
        try:
            # Check if migration already done
            result = db.session.execute(text("SHOW COLUMNS FROM feedback_evaluations LIKE 'evaluator_hash'"))
            if result.fetchone():
                print("[OK] Migration already completed - evaluator_hash column exists")
                return
            
            print("Starting anonymization migration...")
            
            # Step 1: Add new columns to feedback_evaluations
            print("1. Adding anonymized columns to feedback_evaluations...")
            try:
                db.session.execute(text("""
                    ALTER TABLE feedback_evaluations 
                    ADD COLUMN evaluator_hash VARCHAR(64) NULL,
                    ADD COLUMN evaluator_department_hash VARCHAR(64) NULL,
                    ADD COLUMN evaluator_role_hash VARCHAR(64) NULL,
                    ADD COLUMN is_manager_hash VARCHAR(64) NULL
                """))
                print("   [OK] Columns added")
            except Exception as e:
                print(f"   [WARNING] {e}")
            
            # Step 2: Migrate existing data in feedback_evaluations
            print("2. Migrating feedback_evaluations data...")
            feedbacks = FeedbackEvaluation.query.all()
            for feedback in feedbacks:
                # Get evaluator info (if relationship still exists)
                try:
                    # Hash the evaluator_id
                    evaluator_hash = hash_evaluator_id(feedback.evaluator_id, feedback.cycle_id)
                    feedback.evaluator_hash = evaluator_hash
                    
                    # Hash metadata if evaluator relationship exists
                    if hasattr(feedback, 'evaluator') and feedback.evaluator:
                        evaluator = feedback.evaluator
                        evaluatee = feedback.evaluatee
                        is_manager = evaluator.employee_id == evaluatee.manager_id if evaluatee else False
                        
                        feedback.evaluator_department_hash = hash_evaluator_metadata(
                            evaluator.employee_id, feedback.cycle_id, 'department', evaluator.department
                        )
                        feedback.evaluator_role_hash = hash_evaluator_metadata(
                            evaluator.employee_id, feedback.cycle_id, 'role', evaluator.role
                        )
                        feedback.is_manager_hash = hash_evaluator_metadata(
                            evaluator.employee_id, feedback.cycle_id, 'is_manager', str(is_manager)
                        )
                except Exception as e:
                    print(f"   [WARNING] Error migrating feedback {feedback.feedback_id}: {e}")
            
            db.session.commit()
            print("   [OK] Feedback evaluations migrated")
            
            # Step 3: Add evaluator_hash to randomization_log
            print("3. Adding evaluator_hash to randomization_log...")
            try:
                db.session.execute(text("""
                    ALTER TABLE randomization_log 
                    ADD COLUMN evaluator_hash VARCHAR(64) NULL
                """))
                print("   [OK] Column added")
            except Exception as e:
                print(f"   [WARNING] {e}")
            
            # Step 4: Migrate randomization_log data
            print("4. Migrating randomization_log data...")
            assignments = RandomizationLog.query.all()
            for assignment in assignments:
                try:
                    evaluator_hash = hash_evaluator_id(assignment.evaluator_id, assignment.cycle_id)
                    assignment.evaluator_hash = evaluator_hash
                except Exception as e:
                    print(f"   [WARNING] Error migrating assignment {assignment.log_id}: {e}")
            
            db.session.commit()
            print("   [OK] Randomization log migrated")
            
            # Step 5: Make evaluator_hash NOT NULL and add indexes
            print("5. Making evaluator_hash NOT NULL and adding indexes...")
            try:
                # Update any NULL values (shouldn't happen, but safety check)
                db.session.execute(text("""
                    UPDATE feedback_evaluations 
                    SET evaluator_hash = 'MIGRATION_ERROR' 
                    WHERE evaluator_hash IS NULL
                """))
                db.session.execute(text("""
                    UPDATE randomization_log 
                    SET evaluator_hash = 'MIGRATION_ERROR' 
                    WHERE evaluator_hash IS NULL
                """))
                
                # Make NOT NULL
                db.session.execute(text("""
                    ALTER TABLE feedback_evaluations 
                    MODIFY COLUMN evaluator_hash VARCHAR(64) NOT NULL
                """))
                db.session.execute(text("""
                    ALTER TABLE randomization_log 
                    MODIFY COLUMN evaluator_hash VARCHAR(64) NOT NULL
                """))
                
                # Add indexes
                db.session.execute(text("""
                    CREATE INDEX idx_feedback_evaluator_hash ON feedback_evaluations(evaluator_hash)
                """))
                db.session.execute(text("""
                    CREATE INDEX idx_randomization_evaluator_hash ON randomization_log(evaluator_hash)
                """))
                
                print("   [OK] Constraints and indexes added")
            except Exception as e:
                print(f"   [WARNING] {e}")
            
            # Step 6: Remove old evaluator_id columns (optional - comment out if you want to keep for reference)
            print("6. Removing old evaluator_id columns...")
            try:
                # Remove foreign key constraint first
                db.session.execute(text("""
                    ALTER TABLE feedback_evaluations 
                    DROP FOREIGN KEY feedback_evaluations_ibfk_1
                """))
                db.session.execute(text("""
                    ALTER TABLE randomization_log 
                    DROP FOREIGN KEY randomization_log_ibfk_1
                """))
                
                # Remove columns
                db.session.execute(text("""
                    ALTER TABLE feedback_evaluations 
                    DROP COLUMN evaluator_id
                """))
                db.session.execute(text("""
                    ALTER TABLE randomization_log 
                    DROP COLUMN evaluator_id
                """))
                
                print("   [OK] Old columns removed")
            except Exception as e:
                print(f"   [WARNING] Could not remove old columns: {e}")
                print("   [INFO] You may need to remove them manually")
            
            db.session.commit()
            print("\n[SUCCESS] Anonymization migration completed!")
            print("[IMPORTANT] Evaluator IDs are now anonymized. Original IDs cannot be recovered.")
            
        except Exception as e:
            db.session.rollback()
            print(f"\n[ERROR] Migration failed: {e}")
            raise

if __name__ == '__main__':
    migrate_anonymize_evaluators()
