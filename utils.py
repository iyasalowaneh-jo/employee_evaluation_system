import pandas as pd
import random
from datetime import datetime
import json

def allowed_file(filename):
    """Check if file extension is allowed"""
    ALLOWED_EXTENSIONS = {'xlsx', 'xls', 'csv'}
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def assign_evaluators(employees_df, min_peer=3, cross_department=True, exclude_past_assignments=True):
    """
    Assign evaluators to employees based on randomization rules.
    
    Args:
        employees_df: DataFrame with columns ['employee_id', 'department']
        min_peer: Minimum number of evaluators per employee
        cross_department: Whether to require cross-department evaluators
        exclude_past_assignments: Whether to avoid repeat assignments from past cycles
    
    Returns:
        DataFrame with columns ['evaluator_id', 'evaluatee_id']
    """
    from models import RandomizationLog
    
    assignments = []
    employees_list = employees_df.to_dict('records')
    
    # Get past assignments if needed
    past_assignments = set()
    if exclude_past_assignments:
        past_logs = RandomizationLog.query.all()
        # Use anonymized evaluator hashes
        past_assignments = {(log.evaluator_hash, log.evaluatee_id) for log in past_logs}
    
    for employee in employees_list:
        employee_id = employee['employee_id']
        department = employee['department']
        
        # Exclude self
        potential_evaluators = [e for e in employees_list if e['employee_id'] != employee_id]
        
        # Filter by department if cross_department is True
        if cross_department:
            # Require at least 1 from different department
            same_dept = [e for e in potential_evaluators if e['department'] == department]
            different_dept = [e for e in potential_evaluators if e['department'] != department]
            
            selected = []
            
            # Ensure at least one cross-department evaluator
            if different_dept:
                available = [e for e in different_dept 
                           if (e['employee_id'], employee_id) not in past_assignments]
                if available:
                    selected.append(random.choice(available))
            
            # Fill remaining slots
            all_available = [e for e in potential_evaluators 
                           if e['employee_id'] not in [s['employee_id'] for s in selected]
                           and (e['employee_id'], employee_id) not in past_assignments]
            
            needed = min_peer - len(selected)
            if len(all_available) >= needed:
                selected.extend(random.sample(all_available, needed))
            else:
                selected.extend(all_available)
            
            # If still need more (edge case), allow repeats
            while len(selected) < min_peer and len(potential_evaluators) > 0:
                selected.append(random.choice(potential_evaluators))
                if len(selected) >= min_peer:
                    break
        else:
            # Same department only
            same_dept = [e for e in potential_evaluators if e['department'] == department]
            available = [e for e in same_dept 
                       if (e['employee_id'], employee_id) not in past_assignments]
            
            if len(available) >= min_peer:
                selected = random.sample(available, min_peer)
            else:
                selected = available
        
        # Add assignments
        for evaluator in selected[:min_peer]:
            assignments.append({
                'evaluator_id': evaluator['employee_id'],
                'evaluatee_id': employee_id
            })
    
    return pd.DataFrame(assignments)

def calculate_kpi_averages(employees, cycle_id):
    """Calculate KPI scores for employees (approved/final; uses authoritative evaluator only e.g. DP Supervisor for DPs)"""
    from models import Evaluation, KPI
    
    results = {}
    
    for employee in employees:
        evaluations = Evaluation.query.filter(
            Evaluation.evaluatee_id == employee.employee_id,
            Evaluation.cycle_id == cycle_id,
            Evaluation.status.in_(['approved', 'final'])
        ).all()
        try:
            from kpi_evaluation import filter_to_authoritative_evaluations
            evaluations = filter_to_authoritative_evaluations(evaluations, employee)
        except ImportError:
            pass
        
        if not evaluations:
            results[employee.employee_id] = {
                'employee': employee,
                'kpi_scores': {},
                'average': 0,
                'total_evaluations': 0
            }
            continue
        
        kpi_totals = {}
        kpi_counts = {}
        
        for evaluation in evaluations:
            scores = json.loads(evaluation.scores)
            for kpi_id, score in scores.items():
                kpi_id = int(kpi_id)
                kpi_totals[kpi_id] = kpi_totals.get(kpi_id, 0) + score
                kpi_counts[kpi_id] = kpi_counts.get(kpi_id, 0) + 1
        
        # Calculate per-KPI averages and overall weighted average
        kpi_averages = {}
        for kpi_id in kpi_totals:
            avg = kpi_totals[kpi_id] / kpi_counts[kpi_id]
            kpi_averages[kpi_id] = avg
        
        # Weighted average by KPI weight: sum(score_i * weight_i) / sum(weight_i)
        total_weight = 0.0
        weighted_sum = 0.0
        for kpi_id, avg in kpi_averages.items():
            kpi = KPI.query.get(kpi_id)
            w = float(kpi.weight) if kpi and kpi.weight else (100.0 / len(kpi_averages))
            total_weight += w
            weighted_sum += avg * w
        overall_avg = (weighted_sum / total_weight) if total_weight > 0 else 0
        
        # Count unique evaluators (each evaluator = 1 evaluation submission)
        unique_evaluators = set(e.evaluator_id for e in evaluations)
        evaluation_count = len(unique_evaluators)
        
        results[employee.employee_id] = {
            'employee': employee,
            'kpi_scores': kpi_averages,
            'average': overall_avg,
            'total_evaluations': evaluation_count  # Count of evaluation submissions, not individual KPIs
        }
    
    return results

def get_dashboard_data(employee_id, role):
    """Get dashboard data based on user role"""
    from models import db, Employee, EvaluationCycle, Evaluation, RandomizationLog, KPI, EvaluatorScore, FeedbackEvaluation
    from sqlalchemy import distinct
    
    data = {}
    
    if role in ['admin', 'ceo', 'technical_manager']:
        # Admin/CEO/Technical Manager dashboard stats
        total_employees = Employee.query.filter_by(status='active').count()
        total_kpis = KPI.query.filter_by(is_active=True).count()
        active_cycles = EvaluationCycle.query.filter_by(status='active').count()
        
        # Get latest cycle
        latest_cycle = EvaluationCycle.query.filter_by(status='active').first()
        if latest_cycle:
            total_assignments = RandomizationLog.query.filter_by(cycle_id=latest_cycle.cycle_id).count()
            # Count both KPI (Evaluation) and 360 (EvaluatorScore) completions
            completed_kpi = Evaluation.query.filter_by(cycle_id=latest_cycle.cycle_id).count()
            completed_360 = EvaluatorScore.query.filter_by(cycle_id=latest_cycle.cycle_id).count()
            completed_evaluations = completed_kpi + completed_360
            completion_rate = (completed_evaluations / total_assignments * 100) if total_assignments > 0 else 0
        else:
            completion_rate = 0
        
        data = {
            'total_employees': total_employees,
            'total_kpis': total_kpis,
            'active_cycles': active_cycles,
            'completion_rate': completion_rate,
            'latest_cycle': latest_cycle
        }
    
    elif role in ['manager', 'unit_manager', 'department_manager']:
        # Manager dashboard
        manager = Employee.query.get(employee_id)
        subordinates = Employee.query.filter_by(manager_id=employee_id).all()
        
        latest_cycle = EvaluationCycle.query.filter_by(status='active').first()
        if latest_cycle:
            report_data = calculate_kpi_averages(subordinates, latest_cycle.cycle_id)
        else:
            report_data = {}
        
        data = {
            'subordinates': subordinates,
            'report_data': report_data,
            'latest_cycle': latest_cycle
        }
    
    else:  # employee
        # Employee dashboard
        employee = Employee.query.get(employee_id)
        latest_cycle = EvaluationCycle.query.filter_by(status='active').first()
        # Count all evaluation assignments: 360 (by hash) + KPI (by evaluator_id)
        assignments = 0
        if latest_cycle:
            try:
                from anonymization import hash_evaluator_id
                evaluator_hash = hash_evaluator_id(employee_id, latest_cycle.cycle_id)
                assignments += RandomizationLog.query.filter_by(
                    cycle_id=latest_cycle.cycle_id,
                    evaluator_hash=evaluator_hash,
                    evaluation_type='360'
                ).count()
            except ImportError:
                pass
            assignments += RandomizationLog.query.filter_by(
                cycle_id=latest_cycle.cycle_id,
                evaluator_id=employee_id,
                evaluation_type='kpi'
            ).count()
        
        # Get KPIs assigned to this employee
        from kpi_creation import get_kpis_for_employee
        assigned_kpis = get_kpis_for_employee(employee, include_pending=True) if employee else []
        assigned_kpis_total_weight = sum(k.weight for k in assigned_kpis)
        
        if latest_cycle:
            # Completed = KPI evaluations submitted + 360 feedback submissions (distinct evaluatees)
            completed_kpi = Evaluation.query.filter_by(
                evaluator_id=employee_id,
                cycle_id=latest_cycle.cycle_id
            ).count()
            completed_360 = 0
            try:
                from anonymization import hash_evaluator_id
                eh = hash_evaluator_id(employee_id, latest_cycle.cycle_id)
                completed_360 = db.session.query(distinct(FeedbackEvaluation.evaluatee_id)).filter(
                    FeedbackEvaluation.evaluator_hash == eh,
                    FeedbackEvaluation.cycle_id == latest_cycle.cycle_id,
                    FeedbackEvaluation.status == 'submitted'
                ).count()
            except ImportError:
                pass
            completed = completed_kpi + completed_360
            
            # Get evaluations received: approved/final for scores; use only authoritative evaluator (e.g. DP Supervisor for DPs)
            evaluations_received = Evaluation.query.filter(
                Evaluation.evaluatee_id == employee_id,
                Evaluation.cycle_id == latest_cycle.cycle_id,
                Evaluation.status.in_(['approved', 'final'])
            ).all()
            if employee and evaluations_received:
                try:
                    from kpi_evaluation import filter_to_authoritative_evaluations
                    evaluations_received = filter_to_authoritative_evaluations(evaluations_received, employee)
                except ImportError:
                    pass
            pending_review_count = Evaluation.query.filter(
                Evaluation.evaluatee_id == employee_id,
                Evaluation.cycle_id == latest_cycle.cycle_id,
                Evaluation.status == 'pending_review'
            ).count()
            
            # Calculate own KPI averages
            kpi_averages = {}
            if evaluations_received:
                kpi_totals = {}
                kpi_counts = {}
                for eval in evaluations_received:
                    scores = json.loads(eval.scores)
                    for kpi_id, score in scores.items():
                        kpi_id = int(kpi_id)
                        kpi_totals[kpi_id] = kpi_totals.get(kpi_id, 0) + score
                        kpi_counts[kpi_id] = kpi_counts.get(kpi_id, 0) + 1
                
                for kpi_id in kpi_totals:
                    kpi_averages[kpi_id] = kpi_totals[kpi_id] / kpi_counts[kpi_id]
            # Resolve KPI names for display
            kpi_names = {}
            for kpi_id in kpi_averages:
                kpi = KPI.query.get(kpi_id)
                kpi_names[kpi_id] = kpi.kpi_name if kpi else f'KPI #{kpi_id}'
        else:
            completed = 0
            evaluations_received = []
            kpi_averages = {}
            kpi_names = {}
        
        # How many will evaluate me (as evaluatee) and how many have completed
        # Use 360 assignments only: seed caps at 10 per person; KPI evaluator is typically in that pool
        evaluators_assigned_to_me = 0
        evaluators_completed_for_me = 0
        if latest_cycle:
            evaluators_assigned_to_me = RandomizationLog.query.filter_by(
                cycle_id=latest_cycle.cycle_id,
                evaluatee_id=employee_id,
                evaluation_type='360'
            ).count()
            # Completed: 360 uses EvaluatorScore; KPI uses Evaluation (manager evaluates KPIs)
            # For "completed from my evaluators" we count 360 completions (EvaluatorScore)
            evaluators_completed_for_me = EvaluatorScore.query.filter_by(
                cycle_id=latest_cycle.cycle_id,
                evaluatee_id=employee_id
            ).count()
        
        data = {
            'employee': employee,
            'assignments': assignments,
            'completed': completed,
            'latest_cycle': latest_cycle,
            'kpi_averages': kpi_averages,
            'kpi_names': kpi_names,
            'assigned_kpis': assigned_kpis,
            'assigned_kpis_total_weight': assigned_kpis_total_weight,
            'evaluators_assigned_to_me': evaluators_assigned_to_me,
            'evaluators_completed_for_me': evaluators_completed_for_me,
            'kpi_pending_approval': pending_review_count > 0 if latest_cycle else False
        }
    
    return data

def send_notification_email(recipient_email, subject, body):
    """Send notification email (placeholder - implement with Flask-Mail)"""
    # TODO: Implement email sending with Flask-Mail
    print(f"Email notification to {recipient_email}: {subject}")
    print(f"Body: {body}")
    pass
