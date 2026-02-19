"""
Display evaluator scores in the format requested:
hash 1 employee 5 score = 4.2
hash 2 employee 5 score = 3.9 etc .....
"""
from app import app
from models import db, Employee, EvaluationCycle, EvaluatorScore

def show_evaluator_scores(employee_id=None, cycle_id=None):
    """Show evaluator scores for specific employee or all employees"""
    with app.app_context():
        print("=" * 80)
        if employee_id:
            employee = Employee.query.get(employee_id)
            print(f"Evaluator Scores for: {employee.full_name if employee else f'Employee ID {employee_id}'}")
        else:
            print("All Evaluator Scores")
        print("=" * 80)
        
        query = EvaluatorScore.query
        
        if employee_id:
            query = query.filter_by(evaluatee_id=employee_id)
        
        if cycle_id:
            query = query.filter_by(cycle_id=cycle_id)
        else:
            # Get active cycle by default
            cycle = EvaluationCycle.query.filter_by(status='active').first()
            if cycle:
                query = query.filter_by(cycle_id=cycle.cycle_id)
                print(f"Cycle: {cycle.name} (ID: {cycle.cycle_id})")
        
        scores = query.order_by(EvaluatorScore.evaluatee_id, EvaluatorScore.final_score.desc()).all()
        
        if not scores:
            print("\nNo evaluator scores found!")
            return
        
        print(f"\nTotal records: {len(scores)}")
        print("\nFormat: hash <hash> employee <id> score = <score>")
        print("-" * 80)
        
        # Group by employee for better readability
        current_employee_id = None
        hash_index = 1
        
        for score in scores:
            if score.evaluatee_id != current_employee_id:
                if current_employee_id is not None:
                    print()  # Blank line between employees
                employee = Employee.query.get(score.evaluatee_id)
                employee_name = employee.full_name if employee else f"Employee ID {score.evaluatee_id}"
                print(f"\n{employee_name} (ID: {score.evaluatee_id}):")
                current_employee_id = score.evaluatee_id
                hash_index = 1
            
            print(f"  hash {hash_index} employee {score.evaluatee_id} score = {score.final_score:.2f} (hash: {score.evaluator_hash[:16]}...)")
            hash_index += 1
        
        print("\n" + "=" * 80)
        
        # Summary statistics
        if employee_id:
            employee_scores = [s.final_score for s in scores]
            if employee_scores:
                avg_score = sum(employee_scores) / len(employee_scores)
                min_score = min(employee_scores)
                max_score = max(employee_scores)
                print(f"\nSummary for Employee {employee_id}:")
                print(f"  Number of evaluators: {len(employee_scores)}")
                print(f"  Average score: {avg_score:.2f}")
                print(f"  Min score: {min_score:.2f}")
                print(f"  Max score: {max_score:.2f}")
                print(f"  Score range: {max_score - min_score:.2f}")

if __name__ == '__main__':
    import sys
    
    employee_id = None
    cycle_id = None
    
    if len(sys.argv) > 1:
        try:
            employee_id = int(sys.argv[1])
        except ValueError:
            print(f"Invalid employee_id: {sys.argv[1]}")
            sys.exit(1)
    
    if len(sys.argv) > 2:
        try:
            cycle_id = int(sys.argv[2])
        except ValueError:
            print(f"Invalid cycle_id: {sys.argv[2]}")
            sys.exit(1)
    
    show_evaluator_scores(employee_id, cycle_id)
