"""
Complete all 360-degree feedback and KPI evaluations for employee_id = 6 with HIGH INCONSISTENCY
This will create scores with high variance - some evaluators give very high scores, others very low.
"""
from app import app
from models import (
    db, Employee, EvaluationCycle, FeedbackQuestion, FeedbackEvaluation, 
    RandomizationLog, KPI, Evaluation
)
from anonymization import hash_evaluator_id, hash_evaluator_metadata
from datetime import datetime, timedelta
import json
import random

def get_inconsistent_360_scores(evaluator_index, total_evaluators):
    """
    Generate inconsistent scores - some evaluators give high scores, others give low scores
    This creates high variance/inconsistency in the evaluation
    """
    # Distribute evaluators: some give high scores (4-5), some give low scores (1-2.5), some give medium (2.5-3.5)
    # This creates high standard deviation
    
    # Split evaluators into groups for maximum inconsistency
    if evaluator_index < total_evaluators * 0.3:  # First 30% give very high scores
        base_score = random.uniform(4.2, 5.0)
    elif evaluator_index < total_evaluators * 0.6:  # Next 30% give very low scores
        base_score = random.uniform(1.0, 2.3)
    else:  # Remaining 40% give mixed scores (some high, some low)
        if random.random() < 0.5:
            base_score = random.uniform(3.8, 4.5)  # High
        else:
            base_score = random.uniform(2.0, 3.0)  # Low-medium
    
    variation = random.uniform(-0.3, 0.3)
    score = max(1.0, min(5.0, base_score + variation))
    return round(score, 1)

def get_inconsistent_kpi_scores():
    """Generate inconsistent KPI scores with high variance"""
    # Mix of high and low scores for inconsistency
    if random.random() < 0.4:  # 40% chance of high score
        base_score = random.uniform(4.0, 5.0)
    elif random.random() < 0.7:  # 30% chance of low score
        base_score = random.uniform(1.0, 2.5)
    else:  # 30% chance of medium score
        base_score = random.uniform(2.5, 3.5)
    
    variation = random.uniform(-0.3, 0.3)
    score = max(1.0, min(5.0, base_score + variation))
    return round(score, 1)

def get_strengths_comment_inconsistent():
    """Generate mixed strengths comments - some positive, some critical"""
    strengths = [
        "Strong attention to detail and thorough in completing tasks. Very reliable and consistent in work quality.",
        "Excellent communication skills and always willing to help colleagues. Great team player with positive attitude.",
        "Shows potential but needs more experience. Sometimes struggles with complex tasks but willing to learn.",
        "Inconsistent performance - excellent on some days but needs improvement on others. Has good technical skills.",
        "Good understanding of processes but execution can be variable. Shows promise when focused."
    ]
    return random.choice(strengths)

def get_improvements_comment_inconsistent():
    """Generate improvement comments reflecting inconsistency"""
    improvements = [
        "Needs to improve consistency in work quality. Performance varies significantly between tasks.",
        "Would benefit from better time management and prioritization. Sometimes misses deadlines.",
        "Could improve communication - sometimes unclear about project status and challenges.",
        "Needs to take more ownership of responsibilities. Relies too much on others for guidance.",
        "Should work on maintaining consistent quality standards across all assignments."
    ]
    return random.choice(improvements)

def complete_360_evaluations_inconsistent(employee_id):
    """Complete all 360-degree feedback evaluations with high inconsistency"""
    print(f"\n=== Completing 360-degree feedback evaluations for employee_id = {employee_id} (HIGH INCONSISTENCY) ===")
    
    # Get employee info
    employee = Employee.query.get(employee_id)
    if not employee:
        print(f"Error: Employee with ID {employee_id} not found!")
        return
    
    print(f"Employee: {employee.full_name} ({employee.role}, {employee.department})")
    
    # Check if employee is a manager
    manager_roles = ['CEO', 'Technical Manager', 'Unit Manager', 'DP Supervisor', 
                     'Operations Manager', 'PM Manager', 'CFO', 'Field Manager', 'Project Manager']
    is_manager = employee.role in manager_roles
    
    # Get all active cycles
    cycles = EvaluationCycle.query.filter_by(status='active').all()
    if not cycles:
        print("No active evaluation cycles found!")
        return
    
    total_completed = 0
    
    for cycle in cycles:
        print(f"\nProcessing cycle: {cycle.name} (ID: {cycle.cycle_id})")
        
        # Calculate recent date (within last 30 days of cycle end)
        cycle_end = cycle.end_date
        recent_date = cycle_end - timedelta(days=random.randint(5, 20))
        
        # Get all 360 assignments for this employee in this cycle
        assignments = RandomizationLog.query.filter_by(
            evaluatee_id=employee_id,
            cycle_id=cycle.cycle_id,
            evaluation_type='360'
        ).all()
        
        print(f"Found {len(assignments)} 360-degree feedback assignments")
        
        # Get all active feedback questions
        all_questions = FeedbackQuestion.query.filter_by(is_active=True).all()
        questions = [q for q in all_questions if not q.is_for_managers or is_manager]
        
        print(f"Total questions to answer: {len(questions)}")
        
        # Track evaluator index for inconsistency distribution
        evaluator_index = 0
        
        for assignment in assignments:
            evaluator_hash = assignment.evaluator_hash
            
            if not evaluator_hash:
                print(f"  Warning: Assignment {assignment.log_id} has no evaluator_hash, skipping...")
                continue
            
            # Find the actual evaluator
            evaluator = None
            for emp in Employee.query.filter_by(status='active').all():
                test_hash = hash_evaluator_id(emp.employee_id, cycle.cycle_id)
                if test_hash == evaluator_hash:
                    evaluator = emp
                    break
            
            if not evaluator:
                print(f"  Warning: Could not find evaluator for hash {evaluator_hash[:16]}..., skipping...")
                continue
            
            print(f"  Processing evaluation from evaluator: {evaluator.full_name} ({evaluator.role})")
            
            # Determine if evaluator is manager of evaluatee
            is_evaluator_manager = (evaluator.employee_id == employee.manager_id)
            
            # Check existing evaluations
            existing_evaluations = FeedbackEvaluation.query.filter_by(
                evaluator_hash=evaluator_hash,
                evaluatee_id=employee_id,
                cycle_id=cycle.cycle_id
            ).all()
            
            existing_question_ids = {e.question_id for e in existing_evaluations}
            
            # Create/update evaluations for each question with INCONSISTENT scores
            for question in questions:
                if question.question_id in existing_question_ids:
                    # Update existing evaluation
                    existing = next(e for e in existing_evaluations if e.question_id == question.question_id)
                    if existing.status != 'submitted':
                        if question.is_open_ended:
                            if question.question_text.startswith("What are this employee's main strengths"):
                                existing.comment = get_strengths_comment_inconsistent()
                            else:
                                existing.comment = get_improvements_comment_inconsistent()
                            existing.score = None
                        else:
                            # Use inconsistent scoring based on evaluator position
                            existing.score = get_inconsistent_360_scores(evaluator_index, len(assignments))
                            if random.random() < 0.4:
                                existing.comment = f"Variable performance in this area."
                        
                        existing.status = 'submitted'
                        existing.submitted_at = recent_date
                else:
                    # Create new evaluation with INCONSISTENT scores
                    if question.is_open_ended:
                        if question.question_text.startswith("What are this employee's main strengths"):
                            comment = get_strengths_comment_inconsistent()
                        else:
                            comment = get_improvements_comment_inconsistent()
                        
                        feedback = FeedbackEvaluation(
                            evaluator_hash=evaluator_hash,
                            evaluatee_id=employee_id,
                            cycle_id=cycle.cycle_id,
                            question_id=question.question_id,
                            score=None,
                            comment=comment,
                            status='submitted',
                            submitted_at=recent_date,
                            evaluator_department_hash=hash_evaluator_metadata(
                                evaluator.employee_id, cycle.cycle_id, 'department', evaluator.department
                            ),
                            evaluator_role_hash=hash_evaluator_metadata(
                                evaluator.employee_id, cycle.cycle_id, 'role', evaluator.role
                            ),
                            is_manager_hash=hash_evaluator_metadata(
                                evaluator.employee_id, cycle.cycle_id, 'is_manager', str(is_evaluator_manager)
                            )
                        )
                    else:
                        # Generate INCONSISTENT score based on evaluator position
                        score = get_inconsistent_360_scores(evaluator_index, len(assignments))
                        comment = None
                        if random.random() < 0.4:
                            comment = f"Performance varies in this area."
                        
                        feedback = FeedbackEvaluation(
                            evaluator_hash=evaluator_hash,
                            evaluatee_id=employee_id,
                            cycle_id=cycle.cycle_id,
                            question_id=question.question_id,
                            score=score,
                            comment=comment,
                            status='submitted',
                            submitted_at=recent_date,
                            evaluator_department_hash=hash_evaluator_metadata(
                                evaluator.employee_id, cycle.cycle_id, 'department', evaluator.department
                            ),
                            evaluator_role_hash=hash_evaluator_metadata(
                                evaluator.employee_id, cycle.cycle_id, 'role', evaluator.role
                            ),
                            is_manager_hash=hash_evaluator_metadata(
                                evaluator.employee_id, cycle.cycle_id, 'is_manager', str(is_evaluator_manager)
                            )
                        )
                    
                    db.session.add(feedback)
            
            evaluator_index += 1
            total_completed += 1
    
    print(f"\nCompleted {total_completed} 360-degree feedback evaluations with HIGH INCONSISTENCY")
    return total_completed

def complete_kpi_evaluations_inconsistent(employee_id):
    """Complete all KPI evaluations with high inconsistency"""
    print(f"\n=== Completing KPI evaluations for employee_id = {employee_id} (HIGH INCONSISTENCY) ===")
    
    # Get employee info
    employee = Employee.query.get(employee_id)
    if not employee:
        print(f"Error: Employee with ID {employee_id} not found!")
        return
    
    print(f"Employee: {employee.full_name} ({employee.role}, {employee.department})")
    
    # Get all active cycles
    cycles = EvaluationCycle.query.filter_by(status='active').all()
    if not cycles:
        print("No active evaluation cycles found!")
        return
    
    total_completed = 0
    
    for cycle in cycles:
        print(f"\nProcessing cycle: {cycle.name} (ID: {cycle.cycle_id})")
        
        # Get all KPI assignments for this employee in this cycle
        assignments = RandomizationLog.query.filter_by(
            evaluatee_id=employee_id,
            cycle_id=cycle.cycle_id,
            evaluation_type='kpi'
        ).all()
        
        print(f"Found {len(assignments)} KPI evaluation assignments")
        
        # Get relevant KPIs for this employee
        kpis = KPI.query.filter_by(is_active=True).filter(
            db.or_(
                KPI.department == None,
                KPI.department == employee.department,
                KPI.role == None,
                KPI.role == employee.role
            )
        ).all()
        
        print(f"Total KPIs to evaluate: {len(kpis)}")
        
        for assignment in assignments:
            evaluator_id = assignment.evaluator_id
            
            if not evaluator_id:
                print(f"  Warning: Assignment {assignment.log_id} has no evaluator_id, skipping...")
                continue
            
            evaluator = Employee.query.get(evaluator_id)
            if not evaluator:
                print(f"  Warning: Evaluator with ID {evaluator_id} not found, skipping...")
                continue
            
            print(f"  Processing evaluation from evaluator: {evaluator.full_name} ({evaluator.role})")
            
            # Check if evaluation already exists
            existing_evaluation = Evaluation.query.filter_by(
                evaluator_id=evaluator_id,
                evaluatee_id=employee_id,
                cycle_id=cycle.cycle_id
            ).first()
            
            # Generate INCONSISTENT scores for all KPIs (mix of high and low)
            scores = {}
            for kpi in kpis:
                scores[kpi.kpi_id] = get_inconsistent_kpi_scores()
            
            # Generate comments reflecting inconsistency
            comments = f"Performance shows significant variation across KPIs. Some areas demonstrate strong performance while others need substantial improvement. Consistency in work quality and execution is the main area requiring attention."
            
            if existing_evaluation:
                # Update existing evaluation
                existing_evaluation.scores = json.dumps(scores)
                existing_evaluation.comments = comments
                existing_evaluation.status = 'pending_review'
                existing_evaluation.submitted_at = datetime.utcnow()
                print(f"    Updated KPI evaluation with {len(scores)} KPIs (INCONSISTENT scores)")
            else:
                # Create new evaluation
                evaluation = Evaluation(
                    evaluator_id=evaluator_id,
                    evaluatee_id=employee_id,
                    cycle_id=cycle.cycle_id,
                    scores=json.dumps(scores),
                    comments=comments,
                    status='pending_review',
                    submitted_at=datetime.utcnow()
                )
                db.session.add(evaluation)
                print(f"    Created KPI evaluation with {len(scores)} KPIs (INCONSISTENT scores)")
            
            total_completed += 1
    
    print(f"\nCompleted {total_completed} KPI evaluations with HIGH INCONSISTENCY")
    return total_completed

def main():
    """Main function to complete all evaluations for employee_id = 6 with high inconsistency"""
    employee_id = 6
    
    with app.app_context():
        print("=" * 80)
        print(f"Completing all evaluations for employee_id = {employee_id} with HIGH INCONSISTENCY")
        print("=" * 80)
        
        # Complete 360-degree feedback evaluations
        count_360 = complete_360_evaluations_inconsistent(employee_id)
        
        # Complete KPI evaluations
        count_kpi = complete_kpi_evaluations_inconsistent(employee_id)
        
        # Commit all changes
        try:
            db.session.commit()
            print("\n" + "=" * 80)
            print("[SUCCESS] All evaluations completed with HIGH INCONSISTENCY and saved to database!")
            print(f"  - 360-degree feedback evaluations: {count_360}")
            print(f"  - KPI evaluations: {count_kpi}")
            print("  - Scores have HIGH VARIANCE (some very high, some very low)")
            print("=" * 80)
        except Exception as e:
            db.session.rollback()
            print(f"\n[ERROR] Failed to save evaluations: {e}")
            raise

if __name__ == '__main__':
    main()
