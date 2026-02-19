"""
Verify 360 evaluation assignments in database
"""
from app import app
from models import db, Employee, RandomizationLog, EvaluationCycle

with app.app_context():
    # Get active cycle
    cycle = EvaluationCycle.query.filter_by(status='active').first()
    if not cycle:
        print("No active evaluation cycle found")
        exit(1)
    
    # Get all employees
    employees = Employee.query.filter_by(status='active').all()
    print(f"Total employees: {len(employees)}")
    print(f"Expected total evaluations: {len(employees) * 10} = {len(employees) * 10}\n")
    
    # Check assignments
    all_assignments = RandomizationLog.query.filter_by(
        cycle_id=cycle.cycle_id,
        evaluation_type='360'
    ).all()
    
    print(f"Total assignments in database: {len(all_assignments)}")
    
    # Check for duplicates
    assignment_pairs = set()
    duplicates = []
    for assignment in all_assignments:
        pair = (assignment.evaluator_id, assignment.evaluatee_id)
        if pair in assignment_pairs:
            duplicates.append(pair)
        assignment_pairs.add(pair)
    
    if duplicates:
        print(f"\n[ERROR] Found {len(duplicates)} duplicate assignments:")
        for dup in duplicates[:5]:
            print(f"  - {dup}")
    else:
        print("[OK] No duplicate assignments found")
    
    # Count received and submitted for each employee
    print("\nEmployee Evaluation Counts:")
    print("-" * 80)
    print(f"{'Employee':<30} {'Received':<12} {'Submitted':<12} {'Status':<20}")
    print("-" * 80)
    
    errors = []
    for emp in employees:
        received = RandomizationLog.query.filter_by(
            cycle_id=cycle.cycle_id,
            evaluatee_id=emp.employee_id,
            evaluation_type='360'
        ).count()
        
        submitted = RandomizationLog.query.filter_by(
            cycle_id=cycle.cycle_id,
            evaluator_id=emp.employee_id,
            evaluation_type='360'
        ).count()
        
        status = "OK" if received == 10 and submitted == 10 else "ERROR"
        if status == "ERROR":
            errors.append(f"{emp.full_name}: received={received}, submitted={submitted}")
        
        print(f"{emp.full_name:<30} {received:<12} {submitted:<12} {status:<20}")
    
    print("-" * 80)
    
    if errors:
        print(f"\n[ERROR] Found {len(errors)} employees with incorrect counts:")
        for error in errors:
            print(f"  - {error}")
    else:
        print("\n[SUCCESS] All employees have exactly 10 received and 10 submitted evaluations!")
