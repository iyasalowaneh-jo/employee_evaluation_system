"""
KPI Evaluation System - Hierarchical Manager-Based Evaluations
Implements strict role-based KPI evaluation according to organizational hierarchy
"""
from models import Employee, KPI, Evaluation, EvaluationCycle
from flask_login import current_user
import json

# Role aliases: map alternate role names to hierarchy key (evaluator side only)
EVALUATOR_ROLE_ALIASES = {
    'Operations Manager': 'Ops Manager',
}

# Define KPI evaluation hierarchy (evaluator role -> list of evaluatee roles they can evaluate)
KPI_EVALUATION_HIERARCHY = {
    'CEO': {
        'can_evaluate': ['Unit Manager', 'PM Manager', 'CFO', 'BD'],
        'can_view': 'all'
    },
    'Technical Manager': {
        'can_evaluate': ['Analysis', 'Pm Nigeria', 'Ops'],  # Ops = Ops (Ahmad Salam), Ops (Abd al baqe), Ops (Weklat) only
        'can_view': 'all'
    },
    'Analysis': {
        'can_evaluate': ['Analysis 1', 'Analysis 2'],
        'can_view': 'all'
    },
    'Unit Manager': {
        'can_evaluate': ['DP Supervisor', 'Ops Manager', 'Field Manager', 'QA Senior compliance'],
        'can_view': 'all_departments'
    },
    'DP Supervisor': {
        'can_evaluate': ['DP 1', 'DP 2', 'DP 3', 'QA Officer'],
        'can_view': 'Data Processing'
    },
    'Ops Manager': {
        'can_evaluate': ['Ops 1', 'Ops 2', 'Ops 3', 'Ops 4', 'Ops Lebanon', 'Ops Egypt'],
        'can_view': 'Operations'
    },
    'PM Manager': {
        'can_evaluate': ['PM 1', 'PM 2', 'PM 3'],
        'can_view': 'Project Management'
    },
    'CFO': {
        'can_evaluate': ['Ace 1', 'Ace 2', 'Accountant 1', 'Accountant 2'],
        'can_view': 'Finance'
    }
}

def normalize_evaluator_role(role):
    """Resolve evaluator role to hierarchy key (handles aliases)."""
    return EVALUATOR_ROLE_ALIASES.get(role, role)


def _normalize_evaluator_role(role):
    """Internal alias for normalize_evaluator_role."""
    return normalize_evaluator_role(role)


def can_evaluate_kpi(evaluator_role, evaluatee_role):
    """
    Check if evaluator can evaluate evaluatee's KPIs
    
    Args:
        evaluator_role: Role of the person doing the evaluation
        evaluatee_role: Role of the person being evaluated
    
    Returns:
        bool: True if evaluator can evaluate evaluatee
    """
    evaluator_role = _normalize_evaluator_role(evaluator_role)
    if evaluator_role not in KPI_EVALUATION_HIERARCHY:
        return False

    allowed_roles = KPI_EVALUATION_HIERARCHY[evaluator_role]['can_evaluate']
    
    # Check if evaluatee_role matches any allowed role (supports partial matches)
    evaluatee_lower = (evaluatee_role or '').strip().lower()
    for allowed_role in allowed_roles:
        allowed_lower = allowed_role.lower()
        # Exact match
        if allowed_lower == evaluatee_lower:
            return True
        # Evaluatee "Ops" (the three: Ahmad Salam, Abd al baqe, Weklat) only matches allowed "Ops" - not "Ops Manager"
        # so Unit Manager cannot evaluate them; only Technical Manager can (has "Ops" in list)
        if evaluatee_lower == 'ops':
            continue
        # "Ops" as allowed matches only exactly "Ops" - not Ops 1, Ops 2, etc. (those are under Ops Manager)
        if allowed_lower == 'ops':
            continue
        # Contains match (e.g., "Data Processing Officer" matches "DP Officer 1")
        if allowed_lower in evaluatee_lower or evaluatee_lower in allowed_lower:
            return True
        # Handle specific cases with numbers / short role names
        if 'officer' in allowed_lower and ('officer' in evaluatee_lower or 'dp ' in evaluatee_lower or evaluatee_lower.startswith('ops ') or 'accountant' in evaluatee_lower):
            if 'data processing' in allowed_lower and ('dp' in evaluatee_lower or 'data processing' in evaluatee_lower):
                return True
            if 'operations' in allowed_lower and ('operations' in evaluatee_lower or evaluatee_lower.startswith('ops') or 'ops ' in evaluatee_lower):
                return True
            if 'accountant' in allowed_lower and 'accountant' in evaluatee_lower:
                return True
        if 'manager' in allowed_lower and 'manager' in evaluatee_lower:
            if 'project' in allowed_lower and ('project' in evaluatee_lower or evaluatee_lower.startswith('pm ')):
                return True
            if 'field' in allowed_lower and 'field' in evaluatee_lower:
                return True
        # Ops / DP / PM numbered roles
        if allowed_lower.startswith('ops ') and evaluatee_lower.startswith('ops'):
            return True
        if allowed_lower.startswith('dp ') and evaluatee_lower.startswith('dp'):
            return True
        if allowed_lower.startswith('pm ') and evaluatee_lower.startswith('pm'):
            return True

    return False

def get_evaluatable_employees(evaluator_employee_id):
    """
    Get list of employees that the evaluator can evaluate
    
    Args:
        evaluator_employee_id: ID of the evaluator employee
    
    Returns:
        list: List of Employee objects that can be evaluated
    """
    evaluator = Employee.query.get(evaluator_employee_id)
    if not evaluator:
        return []

    evaluator_role = _normalize_evaluator_role(evaluator.role)

    if evaluator_role not in KPI_EVALUATION_HIERARCHY:
        return []

    allowed_roles = KPI_EVALUATION_HIERARCHY[evaluator_role]['can_evaluate']
    
    # Get all active employees
    all_employees = Employee.query.filter_by(status='active').all()
    
    # Filter employees by allowed roles
    evaluatable = []
    for employee in all_employees:
        # Exclude self
        if employee.employee_id == evaluator_employee_id:
            continue

        emp_role_lower = (employee.role or '').strip().lower()
        # Check if employee's role matches any allowed role
        for allowed_role in allowed_roles:
            allowed_lower = allowed_role.lower()
            # "Ops" (no number) matches only role exactly "Ops" - not Ops 1, Ops 2, etc.
            if allowed_lower == 'ops':
                if emp_role_lower == 'ops':
                    evaluatable.append(employee)
                    break
                continue
            # Employee role "Ops" (Ahmad Salam, Abd al baqe, Weklat) must not match "Ops Manager" -
            # only Technical Manager (allowed "Ops") can evaluate them; Unit Manager must not get them
            if emp_role_lower == 'ops':
                continue
            if allowed_lower in emp_role_lower or emp_role_lower in allowed_lower:
                evaluatable.append(employee)
                break

    return evaluatable

def can_view_kpi_results(evaluator_role, evaluatee_department=None):
    """
    Check if evaluator can view KPI results
    
    Args:
        evaluator_role: Role of the person viewing
        evaluatee_department: Department of the person whose results are being viewed (optional)
    
    Returns:
        bool: True if evaluator can view results
    """
    evaluator_role = _normalize_evaluator_role(evaluator_role)
    if evaluator_role not in KPI_EVALUATION_HIERARCHY:
        return False

    view_permission = KPI_EVALUATION_HIERARCHY[evaluator_role]['can_view']
    
    if view_permission == 'all':
        return True
    elif view_permission == 'all_departments':
        return True  # Unit Manager can view all
    elif evaluatee_department and view_permission == evaluatee_department:
        return True
    
    return False

def get_authoritative_evaluator_role(evaluatee_role):
    """
    Return the evaluator role that should be the single source of KPI scores for this evaluatee.
    Each employee has one designated evaluator per hierarchy; use only that evaluator's scores.
    Returns None if multiple evaluators could apply (fallback to averaging).
    """
    if not evaluatee_role:
        return None
    role = (evaluatee_role or '').strip()
    # Map evaluatee roles to their authoritative evaluator
    EVALUATEE_TO_EVALUATOR = {
        'Unit Manager': 'CEO', 'PM Manager': 'CEO', 'CFO': 'CEO', 'BD': 'CEO',
        'DP 1': 'DP Supervisor', 'DP 2': 'DP Supervisor', 'DP 3': 'DP Supervisor',
        'QA Officer': 'DP Supervisor',
        'Analysis 1': 'Analysis', 'Analysis 2': 'Analysis',
        'Ops': 'Technical Manager',  # Ops (Ahmad Salam, etc.) - exact match only
        'Ops 1': 'Ops Manager', 'Ops 2': 'Ops Manager', 'Ops 3': 'Ops Manager',
        'Ops 4': 'Ops Manager', 'Ops Lebanon': 'Ops Manager', 'Ops Egypt': 'Ops Manager',
        'PM 1': 'PM Manager', 'PM 2': 'PM Manager', 'PM 3': 'PM Manager',
        'Ace 1': 'CFO', 'Ace 2': 'CFO', 'Accountant 1': 'CFO', 'Accountant 2': 'CFO',
        'DP Supervisor': 'Unit Manager', 'Ops Manager': 'Unit Manager',
        'Field Manager': 'Unit Manager', 'QA Senior compliance': 'Unit Manager',
        'Analysis': 'Technical Manager', 'Pm Nigeria': 'Technical Manager',
    }
    if role in EVALUATEE_TO_EVALUATOR:
        return EVALUATEE_TO_EVALUATOR[role]
    # Partial matches for DP/PM/Ops numbered roles
    role_lower = role.lower()
    if role_lower.startswith('dp') and 'supervisor' not in role_lower:
        return 'DP Supervisor'
    if role_lower.startswith('pm '):
        return 'PM Manager'
    if role_lower.startswith('ops ') or role_lower in ('ops',):
        return 'Technical Manager' if role_lower == 'ops' else 'Ops Manager'
    return None


def filter_to_authoritative_evaluations(evaluations, evaluatee_employee):
    """
    For employees with a single designated evaluator (e.g. DP 1/2/3 -> DP Supervisor),
    return only that evaluator's evaluation. Otherwise return all evaluations (for averaging).
    """
    if not evaluations or not evaluatee_employee:
        return evaluations
    auth_role = get_authoritative_evaluator_role(evaluatee_employee.role)
    if not auth_role:
        return evaluations
    filtered = [e for e in evaluations if e.evaluator and e.evaluator.role == auth_role]
    return filtered if filtered else evaluations  # fallback if no match


def get_kpi_evaluation_status(cycle_id, evaluatee_id):
    """
    Get KPI evaluation status for an employee in a cycle.
    Uses authoritative evaluator only and weighted average by KPI weight (same as employee portal).
    """
    evaluations = Evaluation.query.filter_by(
        evaluatee_id=evaluatee_id,
        cycle_id=cycle_id
    ).all()
    
    if not evaluations:
        return {
            'status': 'not_started',
            'evaluations': [],
            'average_score': 0,
            'needs_approval': False
        }
    
    evaluatee = Employee.query.get(evaluatee_id)
    evaluations = filter_to_authoritative_evaluations(evaluations, evaluatee)
    
    if not evaluations:
        return {
            'status': 'not_started',
            'evaluations': [],
            'average_score': 0,
            'needs_approval': False
        }
    
    # Prefer approved/final for displayed score (matches employee portal)
    approved_evals = [e for e in evaluations if e.status in ('approved', 'final')]
    display_evals = approved_evals if approved_evals else [e for e in evaluations if e.status == 'pending_review']
    display_evals = display_evals or evaluations  # fallback to any
    
    # Weighted average by KPI weight (same as results_visibility.calculate_kpi_score)
    kpi_totals = {}
    kpi_counts = {}
    for ev in display_evals:
        scores = json.loads(ev.scores) if ev.scores else {}
        for kpi_id, score in scores.items():
            kid = int(kpi_id)
            kpi_totals[kid] = kpi_totals.get(kid, 0) + float(score)
            kpi_counts[kid] = kpi_counts.get(kid, 0) + 1
    kpi_avgs = {k: kpi_totals[k] / kpi_counts[k] for k in kpi_totals} if kpi_totals else {}
    total_weight = 0.0
    weighted_sum = 0.0
    for kpi_id, avg in kpi_avgs.items():
        kpi = KPI.query.get(kpi_id)
        w = float(kpi.weight) if kpi and kpi.weight else (100.0 / len(kpi_avgs))
        total_weight += w
        weighted_sum += avg * w
    avg_score = round((weighted_sum / total_weight), 2) if total_weight > 0 else 0
    
    # Primary eval for status: prefer approved, then pending_review, else first
    primary = None
    for ev in evaluations:
        if ev.status in ('approved', 'final'):
            primary = ev
            break
    if not primary:
        primary = next((e for e in evaluations if e.status == 'pending_review'), evaluations[0])
    
    status_map = {'approved': 'approved', 'final': 'approved', 'pending_review': 'pending_review', 'draft': 'draft'}
    status_str = status_map.get(primary.status, primary.status)
    if status_str == 'approved':
        status_str = 'completed' if evaluatee and evaluatee.role in ['Unit Manager', 'PM Manager', 'CFO'] else 'approved'
    
    return {
        'status': status_str,
        'evaluations': evaluations,
        'average_score': avg_score,
        'needs_approval': any(e.status == 'pending_review' for e in evaluations)
    }

def create_kpi_evaluation_assignment(cycle_id, evaluator_id, evaluatee_id):
    """
    Create a KPI evaluation assignment in RandomizationLog
    
    This is different from 360 evaluations - these are manager-to-subordinate assignments
    """
    from models import RandomizationLog
    
    # Check if assignment already exists
    existing = RandomizationLog.query.filter_by(
        cycle_id=cycle_id,
        evaluator_id=evaluator_id,
        evaluatee_id=evaluatee_id,
        evaluation_type='kpi'
    ).first()
    
    if existing:
        return existing
    
    assignment = RandomizationLog(
        cycle_id=cycle_id,
        evaluator_id=evaluator_id,
        evaluatee_id=evaluatee_id,
        evaluation_type='kpi'
    )
    
    return assignment
