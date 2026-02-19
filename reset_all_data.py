"""
Reset all datasets and re-seed with fresh data
This will clear all existing data and recreate everything
"""
from app import app
from models import db, User, Employee, KPI, EvaluationCycle, FeedbackQuestion, RandomizationLog, FeedbackEvaluation, Evaluation
from seed_data import seed_all_data
from load_evaluation_dataset_to_mysql import load_dataset as load_evaluation_dataset

def reset_all_data():
    """Reset all data and re-seed"""
    with app.app_context():
        print("="*60)
        print("RESETTING ALL DATA")
        print("="*60)
        
        # Drop all tables and recreate
        print("\n1. Dropping all tables...")
        db.drop_all()
        print("   [OK] All tables dropped")
        
        print("\n2. Creating all tables...")
        db.create_all()
        print("   [OK] All tables created")
        
        print("\n3. Loading evaluation relationship matrix (required for 360 assignment)...")
        load_evaluation_dataset()
        print("   [OK] Evaluation relationships loaded")
        
        print("\n4. Seeding fresh data...")
        print("-"*60)
        try:
            seed_all_data()
            print("-"*60)
            print("\n[SUCCESS] Data reset complete! All datasets have been reset and re-seeded.")
            print("\nSystem is ready to use with:")
            print("   - Fresh employee data")
            print("   - Fresh KPI definitions")
            print("   - Fresh 360 feedback questions")
            print("   - New evaluation cycle")
            print("   - 360 evaluations (relationship-based: direct/indirect only, ~70/30 split)")
            print("   - KPI evaluation assignments")
            print("   - Evaluation relationships (who evaluates whom)")
            print("\nLogin credentials:")
            print("   - CEO/Admin: ceo@company.com / password123")
            print("   - All users: [email] / password123")
        except Exception as e:
            print(f"\n[ERROR] Error during seeding: {e}")
            import traceback
            traceback.print_exc()
            raise

if __name__ == '__main__':
    reset_all_data()
