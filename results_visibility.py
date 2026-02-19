"""
Results Visibility System - Role-Based Access Control
Implements strict permission checks for viewing performance results
"""
from models import Employee, Evaluation, FeedbackEvaluation, EvaluationCycle, RandomizationLog, KPI
from flask_login import current_user
from datetime import datetime, timedelta
from anonymization import get_metadata_hash_groups
import json
import math
from collections import defaultdict

def can_view_employee_results(viewer_employee_id, target_employee_id):
    """
    Check if viewer can see target employee's results
    
    Args:
        viewer_employee_id: ID of the person viewing
        target_employee_id: ID of the person whose results are being viewed
    
    Returns:
        bool: True if viewer can see target's results
    """
    if viewer_employee_id == target_employee_id:
        return True  # Everyone can see their own results
    
    viewer = Employee.query.get(viewer_employee_id)
    target = Employee.query.get(target_employee_id)
    
    if not viewer or not target:
        return False
    
    viewer_role = viewer.role
    
    # CEO and Technical Manager can see all
    if viewer_role in ['CEO', 'Technical Manager']:
        return True
    
    # Unit Manager can see DP and Operations departments
    if viewer_role == 'Unit Manager':
        return target.department in ['Data Processing', 'Operations']
    
    # DP Supervisor can see Data Processing team only
    if viewer_role == 'DP Supervisor':
        return target.department == 'Data Processing' and target.role != 'DP Supervisor'
    
    # Operations Manager can see Operations team only
    if viewer_role == 'Operations Manager':
        return target.department == 'Operations' and target.role not in ['Operations Manager', 'Unit Manager']
    
    # PM Manager can see Project Management team only
    if viewer_role == 'PM Manager':
        return target.department == 'Project Management' and target.role != 'PM Manager'
    
    # CFO can see Finance team only
    if viewer_role == 'CFO':
        return target.department == 'Finance' and target.role != 'CFO'
    
    # All other roles can only see their own
    return False

def get_viewable_employees(viewer_employee_id):
    """
    Get list of employees whose results the viewer can see
    
    Args:
        viewer_employee_id: ID of the person viewing
    
    Returns:
        list: List of Employee objects
    """
    viewer = Employee.query.get(viewer_employee_id)
    if not viewer:
        return []
    
    viewer_role = viewer.role
    
    # CEO and Technical Manager can see all
    if viewer_role in ['CEO', 'Technical Manager']:
        return Employee.query.filter_by(status='active').all()
    
    # Unit Manager can see DP and Operations departments
    if viewer_role == 'Unit Manager':
        return Employee.query.filter(
            Employee.status == 'active',
            Employee.department.in_(['Data Processing', 'Operations'])
        ).all()
    
    # DP Supervisor can see Data Processing team (excluding self)
    if viewer_role == 'DP Supervisor':
        return Employee.query.filter(
            Employee.status == 'active',
            Employee.department == 'Data Processing',
            Employee.employee_id != viewer_employee_id
        ).all()
    
    # Operations Manager can see Operations team (excluding self and Unit Manager)
    if viewer_role == 'Operations Manager':
        return Employee.query.filter(
            Employee.status == 'active',
            Employee.department == 'Operations',
            Employee.role.notin_(['Operations Manager', 'Unit Manager'])
        ).all()
    
    # PM Manager can see Project Management team (excluding self)
    if viewer_role == 'PM Manager':
        return Employee.query.filter(
            Employee.status == 'active',
            Employee.department == 'Project Management',
            Employee.employee_id != viewer_employee_id
        ).all()
    
    # CFO can see Finance team (excluding self)
    if viewer_role == 'CFO':
        return Employee.query.filter(
            Employee.status == 'active',
            Employee.department == 'Finance',
            Employee.employee_id != viewer_employee_id
        ).all()
    
    # All other roles can only see themselves
    return [viewer]

def calculate_trimmed_mean_360_score(feedback_evaluations):
    """
    Calculate trimmed mean for 360 feedback scores.
    
    Rules:
    - Only include evaluations where status = 'submitted'
    - Each evaluator contributes one score (average of all their question scores)
    - Draft or incomplete evaluations are excluded
    
    Trimmed Mean logic:
    - If evaluators >= 10: Trim floor(total * 0.10) scores from bottom and top
    - If evaluators are 5-9: Remove 1 lowest and 1 highest score
    - If evaluators < 5: Do not trim, use simple average
    
    Returns:
        tuple: (trimmed_mean, raw_mean, evaluator_count, trimmed_count)
    """
    # Filter to only submitted evaluations with numeric scores (exclude open-ended and inactive/missing questions)
    submitted_feedbacks = [
        f for f in feedback_evaluations 
        if f.status == 'submitted' 
        and f.score is not None 
        and f.question
        and not getattr(f.question, 'is_open_ended', True)
        and getattr(f.question, 'is_active', True)
    ]
    
    if not submitted_feedbacks:
        return (0.0, 0.0, 0, 0)
    
    # Group by evaluator_hash to get one score per evaluator
    evaluator_scores = defaultdict(list)
    for feedback in submitted_feedbacks:
        evaluator_scores[feedback.evaluator_hash].append(feedback.score)
    
    # Calculate average score per evaluator
    evaluator_averages = []
    for evaluator_hash, scores in evaluator_scores.items():
        avg_score = sum(scores) / len(scores)
        evaluator_averages.append(avg_score)
    
    evaluator_count = len(evaluator_averages)
    
    if evaluator_count == 0:
        return (0.0, 0.0, 0, 0)
    
    # Calculate raw mean (for debugging/audit)
    raw_mean = sum(evaluator_averages) / evaluator_count
    
    # Apply trimmed mean logic
    if evaluator_count < 5:
        # Fewer than 5 evaluators: no trimming
        trimmed_mean = raw_mean
        trimmed_count = 0
    elif evaluator_count < 10:
        # 5-9 evaluators: remove 1 lowest and 1 highest
        sorted_scores = sorted(evaluator_averages)
        trimmed_scores = sorted_scores[1:-1]  # Remove first and last
        trimmed_mean = sum(trimmed_scores) / len(trimmed_scores) if trimmed_scores else raw_mean
        trimmed_count = 2
    else:
        # 10+ evaluators: trim floor(total * 0.10) from bottom and top
        trim_count = int(math.floor(evaluator_count * 0.10))
        sorted_scores = sorted(evaluator_averages)
        trimmed_scores = sorted_scores[trim_count:-trim_count] if trim_count > 0 else sorted_scores
        trimmed_mean = sum(trimmed_scores) / len(trimmed_scores) if trimmed_scores else raw_mean
        trimmed_count = trim_count * 2
    
    return (trimmed_mean, raw_mean, evaluator_count, trimmed_count)


def calculate_kpi_score(employee_id, cycle_id, approved_only=True):
    """
    Unified KPI score calculation. Used across all results pages.
    
    - Only includes approved evaluations (or pending_review if approved_only=False).
    - For employees with a single designated evaluator (e.g. DP -> DP Supervisor), uses only that evaluator's scores.
    - Weighted average by KPI weight: sum(score_i * weight_i) / sum(weight_i).
    """
    evaluations = Evaluation.query.filter_by(
        evaluatee_id=employee_id,
        cycle_id=cycle_id
    )
    if approved_only:
        evaluations = evaluations.filter(Evaluation.status.in_(['approved', 'final']))
    evaluations = evaluations.all()
    
    # Use only authoritative evaluator's scores (e.g. DP Supervisor for DPs, CEO for Unit Manager)
    employee = Employee.query.get(employee_id)
    if employee:
        from kpi_evaluation import filter_to_authoritative_evaluations
        evaluations = filter_to_authoritative_evaluations(evaluations, employee)
    
    if not evaluations:
        return 0.0, 0
    
    # Per KPI: average across all evaluators
    kpi_totals = {}
    kpi_counts = {}
    for ev in evaluations:
        scores = json.loads(ev.scores) if ev.scores else {}
        for kpi_id, score in scores.items():
            kid = int(kpi_id)
            kpi_totals[kid] = kpi_totals.get(kid, 0) + float(score)
            kpi_counts[kid] = kpi_counts.get(kid, 0) + 1
    
    kpi_avgs = {k: kpi_totals[k] / kpi_counts[k] for k in kpi_totals}
    if not kpi_avgs:
        return 0.0, len(evaluations)
    
    # Weighted average by KPI weight: sum(score_i * weight_i) / sum(weight_i)
    total_weight = 0.0
    weighted_sum = 0.0
    for kpi_id, avg in kpi_avgs.items():
        kpi = KPI.query.get(kpi_id)
        w = float(kpi.weight) if kpi and kpi.weight else (100.0 / len(kpi_avgs))
        total_weight += w
        weighted_sum += avg * w
    score = round((weighted_sum / total_weight), 2) if total_weight > 0 else 0.0
    return score, len(evaluations)


def calculate_employee_performance(employee_id, cycle_id):
    """
    Calculate complete performance metrics for an employee
    
    Confidence Level:
    - Represents the statistical reliability of 360-degree feedback only
    - Calculated solely based on the number of submitted, unique 360 evaluators
    - KPI evaluations are excluded from confidence calculation by design
    - KPIs are assumed valid by authority, not by volume
    - 360 feedback reliability increases with sample size (probabilistic)
    
    Returns:
        dict: {
            'kpi_score': float,
            'feedback_score': float,
            'final_score': float,
            'confidence': float,  # 0.0 to 1.0, based ONLY on 360 feedback count
            'confidence_label': str,  # Very High / High / Medium / Low / Very Low / Critical / No Confidence
            'confidence_percentage': float,  # 0 to 100
            'kpi_count': int,
            'kpi_expected': int,  # Expected number of KPI evaluations
            'feedback_count': int,  # Number of unique 360 evaluators (submitted only)
            'feedback_expected': int,  # Expected number of 360 feedback evaluations (target: 10)
        }
    """
    employee = Employee.query.get(employee_id)
    
    # Calculate expected KPI evaluations
    # Most employees: 1 evaluation (from their manager)
    # Unit Manager, PM Manager, CFO: 1 evaluation (from CEO)
    kpi_expected = 1
    
    # Calculate expected 360 feedback evaluations (always 10 for reliable results)
    feedback_expected = 10
    
    # Calculate KPI score (unified: weighted avg across all approved evaluations)
    kpi_score, kpi_submission_count = calculate_kpi_score(employee_id, cycle_id, approved_only=True)
    
    # Calculate 360 feedback score using Trimmed Mean
    # This reduces the impact of extreme or malicious evaluations
    feedback_evaluations = FeedbackEvaluation.query.filter_by(
        evaluatee_id=employee_id,
        cycle_id=cycle_id
    ).all()
    
    feedback_score = 0.0
    feedback_raw_mean = 0.0  # For debugging/audit purposes
    feedback_submission_count = 0  # Count of complete 360 feedback submissions
    feedback_trimmed_count = 0  # Number of scores trimmed
    
    if feedback_evaluations:
        # Get unique evaluators (each evaluator who submitted = 1 evaluation)
        # Only count submitted evaluations, not drafts
        # Use evaluator_hash instead of evaluator_id for anonymity
        unique_evaluators = set(f.evaluator_hash for f in feedback_evaluations if f.status == 'submitted')
        feedback_submission_count = len(unique_evaluators)
        
        # Calculate trimmed mean (reduces impact of extreme scores)
        trimmed_mean, raw_mean, evaluator_count, trimmed_count = calculate_trimmed_mean_360_score(feedback_evaluations)
        feedback_score = trimmed_mean
        feedback_raw_mean = raw_mean
        feedback_trimmed_count = trimmed_count
    
    # Final score: include only components that exist this round and have a non-zero score
    cycle = EvaluationCycle.query.get(cycle_id)
    include_kpi = getattr(cycle, 'include_kpi', True) if cycle else True
    include_360 = getattr(cycle, 'include_360', True) if cycle else True
    use_kpi = include_kpi and kpi_score > 0
    use_360 = include_360 and feedback_score > 0
    if use_kpi and use_360:
        final_score = (kpi_score * 0.6) + (feedback_score * 0.4)
    elif use_kpi:
        final_score = kpi_score
    elif use_360:
        final_score = feedback_score
    else:
        final_score = 0.0
    
    # Confidence reflects reliability of 360 feedback using a 4-pillar quality model.
    # KPI evaluations are excluded from confidence calculation by design.
    # 
    # The 4-pillar model assesses:
    # 1. Number of evaluations (40%) - Sample size
    # 2. Source diversity (25%) - Cross-department and role diversity
    # 3. Score consistency (25%) - Agreement among evaluators
    # 4. Recency & relevance (10%) - Timeliness of feedback
    
    # Get all submitted 360 feedback evaluations
    submitted_feedbacks = [f for f in feedback_evaluations if f.status == 'submitted']
    
    # Pillar 1: Number of Evaluations (40%)
    valid_360_count = feedback_submission_count  # Already filtered to submitted, distinct evaluators
    count_score = min(valid_360_count / 10.0, 1.0)  # Cap at 1.0 (10+ evaluators = 100%)
    pillar_1 = count_score * 40
    
    # Pillar 2: Source Diversity (25%) - Interaction-scope based (NOT department-based)
    # Diversity is measured by how many distinct interaction scopes contributed feedback.
    employee = Employee.query.get(employee_id)
    scope_groups = set()
    evaluator_map = {}
    
    if employee and submitted_feedbacks:
        unique_evaluator_hashes = set(f.evaluator_hash for f in submitted_feedbacks)
        from anonymization import hash_evaluator_id
        
        for emp in Employee.query.filter_by(status='active').all():
            test_hash = hash_evaluator_id(emp.employee_id, cycle_id)
            if test_hash in unique_evaluator_hashes:
                evaluator_map[test_hash] = emp
        
        # Determine interaction scope for each evaluator→evaluatee
        try:
            from app_360 import get_interaction_scope, SCOPE_INDIRECT
        except Exception:
            get_interaction_scope = None
            SCOPE_INDIRECT = 'Indirect'
        
        for evaluator_hash in unique_evaluator_hashes:
            evaluator = evaluator_map.get(evaluator_hash)
            if evaluator and get_interaction_scope:
                scope_groups.add(get_interaction_scope(evaluator.role, employee.role))
            elif evaluator:
                scope_groups.add(SCOPE_INDIRECT)
        
        diversity_score = min(len(scope_groups) / 4.0, 1.0)  # Max 4 scopes
    else:
        diversity_score = 0.0
    
    pillar_2 = diversity_score * 25
    
    # Pillar 3: Score Consistency (25%)
    # Calculate standard deviation of 360 scores (exclude open-ended and inactive/missing questions)
    scored_feedbacks_list = [
        f for f in submitted_feedbacks 
        if f.score is not None 
        and f.question 
        and not getattr(f.question, 'is_open_ended', True) 
        and getattr(f.question, 'is_active', True)
    ]
    
    if len(scored_feedbacks_list) > 1:
        scores = [f.score for f in scored_feedbacks_list]
        mean_score = sum(scores) / len(scores)
        variance = sum((x - mean_score) ** 2 for x in scores) / len(scores)
        std_dev = math.sqrt(variance)
        
        # Map standard deviation to consistency score
        if std_dev <= 0.5:
            consistency_score = 1.0
        elif std_dev <= 0.8:
            consistency_score = 0.8
        elif std_dev <= 1.1:
            consistency_score = 0.6
        elif std_dev <= 1.5:
            consistency_score = 0.4
        else:
            consistency_score = 0.2
    elif len(scored_feedbacks_list) == 1:
        # Single score - moderate consistency
        consistency_score = 0.6
    else:
        # No scores available
        consistency_score = 0.0
    
    pillar_3 = consistency_score * 25
    
    # Pillar 4: Relevance (10%) - Interaction-scope based (NOT department-based)
    # Higher weight to feedback from people with direct interaction (Operational/Managerial/Strategic).
    if employee and submitted_feedbacks:
        unique_evaluator_hashes = set(f.evaluator_hash for f in submitted_feedbacks)
        total_evaluators = len(unique_evaluator_hashes)
        direct_count = 0
        
        try:
            from app_360 import get_interaction_scope, SCOPE_INDIRECT
        except Exception:
            get_interaction_scope = None
            SCOPE_INDIRECT = 'Indirect'
        
        for evaluator_hash in unique_evaluator_hashes:
            evaluator = evaluator_map.get(evaluator_hash) if 'evaluator_map' in locals() else None
            if evaluator and get_interaction_scope:
                scope = get_interaction_scope(evaluator.role, employee.role)
                if scope != SCOPE_INDIRECT:
                    direct_count += 1
        
        relevance_score = (direct_count / total_evaluators) if total_evaluators > 0 else 0.0
    else:
        relevance_score = 0.0
    
    pillar_4 = relevance_score * 10
    
    # Final Confidence Percentage
    confidence_percentage = pillar_1 + pillar_2 + pillar_3 + pillar_4
    confidence = confidence_percentage / 100.0  # Convert to 0.0-1.0 scale
    
    # Determine confidence label based on percentage
    if confidence_percentage >= 90:
        confidence_label = 'Very High'
    elif confidence_percentage >= 75:
        confidence_label = 'High'
    elif confidence_percentage >= 60:
        confidence_label = 'Medium'
    elif confidence_percentage >= 40:
        confidence_label = 'Low'
    elif confidence_percentage >= 20:
        confidence_label = 'Very Low'
    elif confidence_percentage > 0:
        confidence_label = 'Critical'
    else:
        confidence_label = 'No Confidence'
    
    return {
        'kpi_score': round(kpi_score, 2),
        'feedback_score': round(feedback_score, 2),  # Trimmed mean
        'feedback_raw_mean': round(feedback_raw_mean, 2),  # Raw mean for debugging/audit
        'feedback_trimmed_count': feedback_trimmed_count,  # Number of scores trimmed
        'final_score': round(final_score, 2),
        'confidence': confidence,  # 0.0 to 1.0 (0% to 100%) - Based ONLY on 360 feedback (4-pillar model)
        'confidence_label': confidence_label,  # Very High / High / Medium / Low / Very Low / Critical / No Confidence
        'confidence_percentage': round(confidence_percentage, 1),  # 0 to 100 (from 4-pillar calculation)
        'confidence_pillars': {
            'pillar_1_count': round(pillar_1, 1),  # Number of evaluations (40%)
            'pillar_2_diversity': round(pillar_2, 1),  # Source diversity (25%)
            'pillar_3_consistency': round(pillar_3, 1),  # Score consistency (25%)
            'pillar_4_recency': round(pillar_4, 1),  # Recency & relevance (10%)
        },
        'kpi_count': kpi_submission_count,  # Number of KPI evaluation submissions
        'kpi_expected': kpi_expected,  # Expected number of KPI evaluations
        'feedback_count': feedback_submission_count,  # Number of unique 360 evaluators (submitted only)
        'feedback_expected': feedback_expected,  # Expected number of 360 feedback evaluations (target: 10)
        # IMPORTANT: Confidence is calculated SOLELY based on 360 feedback count
        # KPI evaluations are excluded because they are not probabilistic and do not gain reliability by repetition
    }

def log_results_access(viewer_employee_id, target_employee_id, page_type):
    """
    Log access to results for audit purposes
    In production, this would write to an audit log table
    """
    # TODO: Implement audit logging
    print(f"Audit: Employee {viewer_employee_id} accessed {page_type} for employee {target_employee_id}")
