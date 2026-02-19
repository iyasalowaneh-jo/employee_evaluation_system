"""
Create and populate evaluator_scores table with final scores for each evaluator_hash-evaluatee pair
"""
from app import app
from models import db, Employee, EvaluationCycle, FeedbackEvaluation, EvaluatorScore
from collections import defaultdict
from datetime import datetime

def create_evaluator_scores_table():
    """Create the evaluator_scores table if it doesn't exist"""
    with app.app_context():
        # Create table
        db.create_all()
        print("Table 'evaluator_scores' created (if it didn't exist)")
        print("=" * 80)

def populate_evaluator_scores():
    """Populate evaluator_scores table from existing FeedbackEvaluation data"""
    with app.app_context():
        print("\nPopulating evaluator_scores table from existing evaluations...")
        print("=" * 80)
        
        # Get all active cycles
        cycles = EvaluationCycle.query.filter_by(status='active').all()
        
        if not cycles:
            print("No active cycles found!")
            return
        
        total_scores_created = 0
        
        for cycle in cycles:
            print(f"\nProcessing cycle: {cycle.name} (ID: {cycle.cycle_id})")
            
            # Get all submitted feedback evaluations for this cycle
            feedback_evaluations = FeedbackEvaluation.query.filter_by(
                cycle_id=cycle.cycle_id,
                status='submitted'
            ).all()
            
            print(f"Found {len(feedback_evaluations)} submitted feedback evaluations")
            
            # Group by evaluator_hash and evaluatee_id
            evaluator_scores_dict = defaultdict(lambda: defaultdict(list))
            
            for feedback in feedback_evaluations:
                # Only include scored questions (exclude open-ended and inactive/missing questions)
                if (feedback.score is not None and feedback.question
                        and not getattr(feedback.question, 'is_open_ended', True)
                        and getattr(feedback.question, 'is_active', True)):
                    evaluator_scores_dict[feedback.evaluator_hash][feedback.evaluatee_id].append(feedback.score)
            
            print(f"Found {len(evaluator_scores_dict)} unique evaluators")
            
            # Calculate and store final scores
            for evaluator_hash, evaluatee_scores in evaluator_scores_dict.items():
                for evaluatee_id, scores in evaluatee_scores.items():
                    if scores:
                        # Calculate average score for this evaluator-evaluatee pair
                        final_score = sum(scores) / len(scores)
                        
                        # Check if score already exists
                        existing = EvaluatorScore.query.filter_by(
                            evaluator_hash=evaluator_hash,
                            evaluatee_id=evaluatee_id,
                            cycle_id=cycle.cycle_id
                        ).first()
                        
                        if existing:
                            # Update existing score
                            existing.final_score = final_score
                            existing.question_count = len(scores)
                            existing.calculated_at = datetime.utcnow()
                            print(f"  Updated: evaluator_hash {evaluator_hash[:16]}... -> employee {evaluatee_id}: {final_score:.2f} ({len(scores)} questions)")
                        else:
                            # Create new score
                            evaluator_score = EvaluatorScore(
                                evaluator_hash=evaluator_hash,
                                evaluatee_id=evaluatee_id,
                                cycle_id=cycle.cycle_id,
                                final_score=final_score,
                                question_count=len(scores),
                                calculated_at=datetime.utcnow()
                            )
                            db.session.add(evaluator_score)
                            print(f"  Created: evaluator_hash {evaluator_hash[:16]}... -> employee {evaluatee_id}: {final_score:.2f} ({len(scores)} questions)")
                            total_scores_created += 1
            
            # Commit for this cycle
            try:
                db.session.commit()
                print(f"\n[SUCCESS] Committed scores for cycle {cycle.name}")
            except Exception as e:
                db.session.rollback()
                print(f"\n[ERROR] Error committing scores for cycle {cycle.name}: {e}")
                raise
        
        print(f"\n" + "=" * 80)
        print(f"[SUCCESS] Created/updated {total_scores_created} evaluator scores")
        print("=" * 80)

def show_evaluator_scores_sample(employee_id=None):
    """Show sample of evaluator scores"""
    with app.app_context():
        print("\n" + "=" * 80)
        print("Sample Evaluator Scores:")
        print("=" * 80)
        
        query = EvaluatorScore.query
        if employee_id:
            query = query.filter_by(evaluatee_id=employee_id)
        
        scores = query.order_by(EvaluatorScore.evaluatee_id, EvaluatorScore.final_score.desc()).limit(20).all()
        
        if not scores:
            print("No evaluator scores found!")
            return
        
        print(f"\n{'Evaluator Hash':<20} {'Employee ID':<15} {'Final Score':<15} {'Questions':<10} {'Cycle':<30}")
        print("-" * 90)
        
        for score in scores:
            employee = Employee.query.get(score.evaluatee_id)
            cycle = EvaluationCycle.query.get(score.cycle_id)
            employee_name = employee.full_name if employee else f"ID {score.evaluatee_id}"
            cycle_name = cycle.name if cycle else f"ID {score.cycle_id}"
            
            print(f"{score.evaluator_hash[:16]:<20} {employee_name:<15} {score.final_score:<15.2f} {score.question_count:<10} {cycle_name:<30}")

def main():
    """Main function"""
    print("=" * 80)
    print("Creating and Populating Evaluator Scores Table")
    print("=" * 80)
    
    # Create table
    create_evaluator_scores_table()
    
    # Populate from existing data
    populate_evaluator_scores()
    
    # Show sample
    show_evaluator_scores_sample()

if __name__ == '__main__':
    main()
