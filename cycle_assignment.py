"""
Cycle assignment: 360 and KPI evaluation assignments per cycle.
Used when activating a new evaluation cycle (relationship-based 360 + hierarchical KPI).
"""
import random
from models import RandomizationLog, EvaluationRelationship

try:
    from anonymization import hash_evaluator_id
except ImportError:
    import hashlib
    import hmac
    EVALUATOR_SALT = b'evaluator_anonymization_salt_2024'
    def hash_evaluator_id(evaluator_id, cycle_id):
        message = f"{evaluator_id}_{cycle_id}".encode('utf-8')
        hash_obj = hmac.new(EVALUATOR_SALT, message, hashlib.sha256)
        return hash_obj.hexdigest()


def assign_360_evaluations(employees, cycle_id):
    """
    360 evaluation assignment using the evaluation relationship matrix.
    
    Rules:
    1. Only assign where relationship is '1' (direct) or '0' (indirect) - NEVER 'x' (no relationship).
    2. Per evaluatee: target up to 10 evaluations, with ~70% from direct, ~30% from indirect.
    3. If fewer than 10 valid relationships: use what's available (no forcing).
    4. Per evaluator: cap at 10 evaluations submitted.
    5. No self-evaluation.
    
    Args:
        employees: dict-like {id: Employee} or iterable of Employee
        cycle_id: evaluation cycle ID
    """
    employee_list = list(employees.values()) if hasattr(employees, 'values') else list(employees)
    employee_by_id = {e.employee_id: e for e in employee_list}
    max_per_person = 10
    assignment_set = set()  # (evaluator_id, evaluatee_id)
    
    # Build valid pairs from EvaluationRelationship (only 1 or 0, not x or z)
    valid_pairs = {}
    for evaluator in employee_list:
        for evaluatee in employee_list:
            if evaluator.employee_id == evaluatee.employee_id:
                continue
            rec = EvaluationRelationship.query.filter_by(
                evaluator_role=evaluator.full_name,
                evaluatee_role=evaluatee.full_name
            ).first()
            if rec and rec.relationship in ('1', '0'):
                valid_pairs[(evaluator.employee_id, evaluatee.employee_id)] = rec.relationship
    
    # Per-evaluatee: targets
    direct_candidates = {eid: [] for eid in employee_by_id}
    indirect_candidates = {eid: [] for eid in employee_by_id}
    for (eval_id, eval_ee_id), rel in valid_pairs.items():
        if rel == '1':
            direct_candidates[eval_ee_id].append(eval_id)
        else:
            indirect_candidates[eval_ee_id].append(eval_id)
    
    target_received = {}
    target_direct = {}
    for eid in employee_by_id:
        n_direct = len(direct_candidates[eid])
        n_indirect = len(indirect_candidates[eid])
        total_available = n_direct + n_indirect
        target_received[eid] = min(max_per_person, total_available)
        target_direct[eid] = min(round(0.7 * target_received[eid]), n_direct)
        target_direct[eid] = min(target_direct[eid], target_received[eid])
    
    received_count = {eid: 0 for eid in employee_by_id}
    direct_received = {eid: 0 for eid in employee_by_id}
    submitted_count = {eid: 0 for eid in employee_by_id}
    assignments = []
    
    def can_assign(eval_id, eval_ee_id):
        if (eval_id, eval_ee_id) in assignment_set:
            return False
        if submitted_count[eval_id] >= max_per_person:
            return False
        if received_count[eval_ee_id] >= target_received[eval_ee_id]:
            return False
        return (eval_id, eval_ee_id) in valid_pairs
    
    def score_candidate(eval_id, eval_ee_id):
        rel = valid_pairs.get((eval_id, eval_ee_id))
        if not rel:
            return -1
        eval_ee_need = target_received[eval_ee_id] - received_count[eval_ee_id]
        eval_need = max_per_person - submitted_count[eval_id]
        score = eval_ee_need + eval_need
        if rel == '1' and direct_received[eval_ee_id] < target_direct[eval_ee_id]:
            score += 100
        elif rel == '0' and direct_received[eval_ee_id] >= target_direct[eval_ee_id]:
            score += 50
        return score
    
    max_iter = len(valid_pairs) * 2
    for _ in range(max_iter):
        candidates = [
            (eval_id, eval_ee_id)
            for (eval_id, eval_ee_id) in valid_pairs
            if can_assign(eval_id, eval_ee_id)
        ]
        if not candidates:
            break
        scored = [(score_candidate(eid, eeid), eid, eeid) for (eid, eeid) in candidates]
        scored.sort(reverse=True, key=lambda x: x[0])
        top_n = min(25, len(scored))
        top_tier = [(eid, eeid) for _, eid, eeid in scored[:top_n]]
        eval_id, eval_ee_id = random.choice(top_tier)
        rel = valid_pairs[(eval_id, eval_ee_id)]
        assignment_set.add((eval_id, eval_ee_id))
        assignments.append((eval_id, eval_ee_id))
        received_count[eval_ee_id] += 1
        submitted_count[eval_id] += 1
        if rel == '1':
            direct_received[eval_ee_id] += 1
    
    for evaluator_id, evaluatee_id in assignments:
        log = RandomizationLog(
            cycle_id=cycle_id,
            evaluator_hash=hash_evaluator_id(evaluator_id, cycle_id),
            evaluatee_id=evaluatee_id,
            evaluation_type='360'
        )
        from models import db
        db.session.add(log)


def assign_kpi_evaluations(employees, cycle_id):
    """Assign KPI evaluations based on hierarchical structure (manager-to-subordinate)."""
    from kpi_evaluation import can_evaluate_kpi, create_kpi_evaluation_assignment
    
    employee_list = list(employees.values()) if hasattr(employees, 'values') else list(employees)
    for evaluator in employee_list:
        evaluatable = []
        for evaluatee in employee_list:
            if evaluator.employee_id == evaluatee.employee_id:
                continue
            if can_evaluate_kpi(evaluator.role, evaluatee.role):
                evaluatable.append(evaluatee)
        for evaluatee in evaluatable:
            assignment = create_kpi_evaluation_assignment(
                cycle_id,
                evaluator.employee_id,
                evaluatee.employee_id
            )
            from models import db
            db.session.add(assignment)
