"""
Script to complete all 360-degree feedback and KPI evaluations for employee_id = 5 (DP Officer 1)
This script populates existing datasets with realistic evaluation data without changing any code structures.
"""
from app import app
from models import (
    db, Employee, EvaluationCycle, FeedbackQuestion, FeedbackEvaluation, 
    RandomizationLog, KPI, Evaluation
)
from anonymization import hash_evaluator_id, hash_evaluator_metadata
from datetime import datetime
import json
import random

def get_realistic_360_scores():
    """Generate realistic 360 feedback scores (1-5 scale)"""
    # Slightly above average scores with some variation
    base_score = random.uniform(3.5, 4.5)
    variation = random.uniform(-0.5, 0.5)
    score = max(1.0, min(5.0, base_score + variation))
    return round(score, 1)

def get_realistic_kpi_scores():
    """Generate realistic KPI scores (1-5 scale)"""
    # Similar to 360 scores
    base_score = random.uniform(3.5, 4.5)
    variation = random.uniform(-0.5, 0.5)
    score = max(1.0, min(5.0, base_score + variation))
    return round(score, 1)

def get_strengths_comment():
    """Generate realistic strengths comment"""
    strengths = [
        "Strong attention to detail and thorough in completing tasks. Very reliable and consistent in work quality.",
        "Excellent communication skills and always willing to help colleagues. Great team player with positive attitude.",
        "Proactive approach to problem-solving and takes initiative. Shows good understanding of department processes.",
        "Dedicated and committed to meeting deadlines. Maintains high standards in all work assignments.",
        "Good technical skills and adapts well to new systems. Collaborative and supportive team member."
    ]
    return random.choice(strengths)

def get_improvements_comment():
    """Generate realistic improvement areas comment"""
    improvements = [
        "Could benefit from taking on more leadership opportunities and mentoring junior colleagues.",
        "Would benefit from more proactive communication about project status and potential challenges.",
        "Could improve time management skills when handling multiple priorities simultaneously.",
        "Would benefit from more cross-departmental collaboration to broaden perspective.",
        "Could enhance presentation skills and confidence when presenting to larger groups."
    ]
    return random.choice(improvements)

def complete_360_evaluations(employee_id):
    """Complete all 360-degree feedback evaluations for employee_id"""
    print(f"\n=== Completing 360-degree feedback evaluations for employee_id = {employee_id} ===")
    
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
        
        # Get all 360 assignments for this employee in this cycle
        assignments = RandomizationLog.query.filter_by(
            evaluatee_id=employee_id,
            cycle_id=cycle.cycle_id,
            evaluation_type='360'
        ).all()
        
        print(f"Found {len(assignments)} 360-degree feedback assignments")
        
        # Get all active feedback questions
        all_questions = FeedbackQuestion.query.filter_by(is_active=True).all()
        
        # Filter questions based on whether employee is a manager
        questions = [q for q in all_questions if not q.is_for_managers or is_manager]
        
        print(f"Total questions to answer: {len(questions)} (including {sum(1 for q in questions if q.is_open_ended)} open-ended)")
        
        for assignment in assignments:
            # Get evaluator hash from assignment
            evaluator_hash = assignment.evaluator_hash
            
            if not evaluator_hash:
                print(f"  Warning: Assignment {assignment.log_id} has no evaluator_hash, skipping...")
                continue
            
            # We need to find the actual evaluator to get their metadata for hashing
            # Since we can't reverse the hash, we'll need to find evaluators who might have this hash
            # Actually, for 360 evaluations, we don't need the actual evaluator - we just need to use the hash
            # But we do need evaluator metadata. Let's try to find potential evaluators
            
            # For now, let's use a placeholder approach - we'll need to find which evaluator this hash belongs to
            # Actually, looking at the code, the evaluator_hash is stored in RandomizationLog
            # We can't easily reverse it, but we can check if evaluations already exist
            
            # Check existing evaluations for this assignment
            existing_evaluations = FeedbackEvaluation.query.filter_by(
                evaluator_hash=evaluator_hash,
                evaluatee_id=employee_id,
                cycle_id=cycle.cycle_id
            ).all()
            
            existing_question_ids = {e.question_id for e in existing_evaluations}
            
            # Find which evaluator this hash belongs to by checking all employees
            # This is a bit inefficient but necessary since we can't reverse the hash
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
            
            # Create/update evaluations for each question
            for question in questions:
                if question.question_id in existing_question_ids:
                    # Update existing evaluation
                    existing = next(e for e in existing_evaluations if e.question_id == question.question_id)
                    if existing.status != 'submitted':
                        # Update with realistic data
                        if question.is_open_ended:
                            if question.question_text.startswith("What are this employee's main strengths"):
                                existing.comment = get_strengths_comment()
                            else:
                                existing.comment = get_improvements_comment()
                            existing.score = None
                        else:
                            existing.score = get_realistic_360_scores()
                            # Add occasional comment
                            if random.random() < 0.3:  # 30% chance of comment
                                existing.comment = f"Good performance in this area."
                        
                        existing.status = 'submitted'
                        existing.submitted_at = datetime.utcnow()
                        print(f"    Updated question {question.question_id}: {question.question_text[:50]}...")
                else:
                    # Create new evaluation
                    if question.is_open_ended:
                        if question.question_text.startswith("What are this employee's main strengths"):
                            comment = get_strengths_comment()
                        else:
                            comment = get_improvements_comment()
                        
                        feedback = FeedbackEvaluation(
                            evaluator_hash=evaluator_hash,
                            evaluatee_id=employee_id,
                            cycle_id=cycle.cycle_id,
                            question_id=question.question_id,
                            score=None,
                            comment=comment,
                            status='submitted',
                            submitted_at=datetime.utcnow(),
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
                        score = get_realistic_360_scores()
                        comment = None
                        if random.random() < 0.3:  # 30% chance of comment
                            comment = f"Consistent performance in this area."
                        
                        feedback = FeedbackEvaluation(
                            evaluator_hash=evaluator_hash,
                            evaluatee_id=employee_id,
                            cycle_id=cycle.cycle_id,
                            question_id=question.question_id,
                            score=score,
                            comment=comment,
                            status='submitted',
                            submitted_at=datetime.utcnow(),
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
                    print(f"    Created question {question.question_id}: {question.question_text[:50]}...")
            
            total_completed += 1
    
    print(f"\nCompleted {total_completed} 360-degree feedback evaluations")
    return total_completed

def complete_kpi_evaluations(employee_id):
    """Complete all KPI evaluations for employee_id"""
    print(f"\n=== Completing KPI evaluations for employee_id = {employee_id} ===")
    
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
        # KPIs can be department-specific, role-specific, or global
        kpis = KPI.query.filter_by(is_active=True).filter(
            db.or_(
                KPI.department == None,  # Global KPIs
                KPI.department == employee.department,  # Department-specific
                KPI.role == None,  # All roles
                KPI.role == employee.role  # Role-specific
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
            
            # Generate realistic scores for all KPIs
            scores = {}
            for kpi in kpis:
                scores[kpi.kpi_id] = get_realistic_kpi_scores()
            
            # Generate realistic comments
            comments = f"Overall good performance across all KPIs. {employee.full_name} demonstrates consistent effort and meets most expectations. Some areas show strong performance, while others have room for improvement."
            
            if existing_evaluation:
                # Update existing evaluation
                existing_evaluation.scores = json.dumps(scores)
                existing_evaluation.comments = comments
                existing_evaluation.status = 'pending_review'
                existing_evaluation.submitted_at = datetime.utcnow()
                print(f"    Updated KPI evaluation with {len(scores)} KPIs")
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
                print(f"    Created KPI evaluation with {len(scores)} KPIs")
            
            total_completed += 1
    
    print(f"\nCompleted {total_completed} KPI evaluations")
    return total_completed

def main():
    """Main function to complete all evaluations for employee_id = 5"""
    employee_id = 5
    
    with app.app_context():
        print("=" * 80)
        print(f"Completing all evaluations for employee_id = {employee_id}")
        print("=" * 80)
        
        # Complete 360-degree feedback evaluations
        count_360 = complete_360_evaluations(employee_id)
        
        # Complete KPI evaluations
        count_kpi = complete_kpi_evaluations(employee_id)
        
        # Commit all changes
        try:
            db.session.commit()
            print("\n" + "=" * 80)
            print("SUCCESS: All evaluations completed and saved to database!")
            print(f"  - 360-degree feedback evaluations: {count_360}")
            print(f"  - KPI evaluations: {count_kpi}")
            print("=" * 80)
        except Exception as e:
            db.session.rollback()
            print(f"\nERROR: Failed to save evaluations: {e}")
            raise

if __name__ == '__main__':
    main()
