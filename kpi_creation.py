"""
KPI Creation System - Manager-Based KPI Creation with Approval Workflow
Each manager can create KPIs for their subordinates, which must be approved by CEO before use.
Uses KPICreationRule from DB when available; falls back to KPI_CREATION_HIERARCHY.
"""
from models import Employee, KPI, KPICreationRule
from flask_login import current_user

# Define who can create KPIs for which roles (matches org hierarchy)
KPI_CREATION_HIERARCHY = {
    'CEO': {
        'can_create_for': ['CFO', 'Unit Manager', 'PM Manager', 'BD'],
        'department': None
    },
    'Unit Manager': {
        'can_create_for': ['DP Supervisor', 'Ops Manager', 'Field Manager', 'QA Senior compliance'],
        'department': None
    },
    'Analysis': {
        'can_create_for': ['Analysis 1', 'Analysis 2'],
        'department': 'Analysis'
    },
    'DP Supervisor': {
        'can_create_for': ['QA Officer', 'DP 1', 'DP 2', 'DP 3'],
        'department': 'Data Processing'
    },
    'Ops Manager': {
        'can_create_for': ['Ops 1', 'Ops 2', 'Ops 3', 'Ops 4', 'Ops Lebanon', 'Ops Egypt'],
        'department': 'Operations'
    },
    'PM Manager': {
        'can_create_for': ['PM 1', 'PM 2', 'PM 3'],
        'department': 'Project Management'
    },
    'CFO': {
        'can_create_for': ['Accountant 1', 'Accountant 2', 'Ace 1', 'Ace 2'],
        'department': None
    },
    'Technical Manager': {
        'can_create_for': ['Ops', 'Pm Nigeria', 'Analysis'],  # Ops (Ahmad/Abd/Weklat), Pm Nigeria, Analysis (Valeria)
        'department': None
    }
}

def _get_creatable_roles_from_db(manager_role):
    """Get creatable roles from KPICreationRule table. Returns empty list if no rules exist."""
    rules = KPICreationRule.query.filter_by(manager_role=manager_role).all()
    return [r.target_role for r in rules]

def _uses_db_rules():
    """True if KPICreationRule has any rows (use DB instead of hierarchy)."""
    return KPICreationRule.query.count() > 0

def can_create_kpi_for_role(manager_role, target_role):
    """
    Check if a manager can create KPIs for a specific role
    Uses KPICreationRule from DB when available; else KPI_CREATION_HIERARCHY.
    
    Args:
        manager_role: Role of the manager trying to create KPIs
        target_role: Role for which KPIs are being created
        
    Returns:
        bool: True if manager can create KPIs for this role
    """
    if _uses_db_rules():
        allowed = _get_creatable_roles_from_db(manager_role)
        for r in allowed:
            if r.lower() in target_role.lower() or target_role.lower() in r.lower():
                return True
        return False
    
    if manager_role not in KPI_CREATION_HIERARCHY:
        return False
    allowed_roles = KPI_CREATION_HIERARCHY[manager_role]['can_create_for']
    for allowed_role in allowed_roles:
        if allowed_role.lower() in target_role.lower() or target_role.lower() in allowed_role.lower():
            return True
    return False

def get_creatable_roles(manager_role):
    """
    Get list of roles that a manager can create KPIs for
    Uses KPICreationRule from DB when available; else KPI_CREATION_HIERARCHY.
    
    Args:
        manager_role: Role of the manager
        
    Returns:
        list: List of role names
    """
    if _uses_db_rules():
        return _get_creatable_roles_from_db(manager_role)
    if manager_role not in KPI_CREATION_HIERARCHY:
        return []
    return KPI_CREATION_HIERARCHY[manager_role]['can_create_for']

def get_manager_department(manager_role):
    """
    Get the department associated with a manager for KPI creation
    
    Args:
        manager_role: Role of the manager
        
    Returns:
        str or None: Department name or None
    """
    if manager_role not in KPI_CREATION_HIERARCHY:
        return None
    
    return KPI_CREATION_HIERARCHY[manager_role].get('department')

def calculate_total_weight(department, role, exclude_kpi_id=None):
    """
    Calculate total weight of ALL KPIs for a department/role combination
    Counts ALL KPIs regardless of status (approved, pending, draft, default)
    Default KPIs are NOT approved but they DO count toward total weight
    
    Args:
        department: Department name (or None)
        role: Role name (or None)
        exclude_kpi_id: KPI ID to exclude from calculation (for updates)
        
    Returns:
        float: Total weight (0-100+)
    """
    from sqlalchemy import or_
    
    # Count ALL KPIs regardless of status (approved, pending, draft, default)
    # This includes default KPIs even though they're not approved
    all_kpis_query = KPI.query.filter(
        KPI.role == role,
        KPI.is_active == True
    )
    
    # Match department (None means global/matches any)
    if department:
        all_kpis_query = all_kpis_query.filter(
            or_(KPI.department == department, KPI.department.is_(None))
        )
    else:
        all_kpis_query = all_kpis_query.filter(KPI.department.is_(None))
    
    if exclude_kpi_id:
        all_kpis_query = all_kpis_query.filter(KPI.kpi_id != exclude_kpi_id)
    
    all_kpis = all_kpis_query.all()
    total = sum(kpi.weight for kpi in all_kpis)
    
    # Safety check: ensure we don't return negative or invalid values
    return max(0.0, total)

def get_remaining_weight(department, role, exclude_kpi_id=None):
    """Get remaining weight for department/role (legacy)."""
    total = calculate_total_weight(department, role, exclude_kpi_id)
    return max(0, 100.0 - total)


def get_kpis_for_employee(employee, include_pending=False):
    """
    Get KPIs that apply to this employee (employee-based assignment).
    - applies_to_all=True: KPI applies to all employees
    - applies_to_all=False: KPI applies only if employee in assigned_employees
    """
    from sqlalchemy import or_
    if employee is None:
        return []
    base = KPI.query.filter_by(is_active=True)
    if include_pending:
        base = base.filter(KPI.status.in_(['approved', 'pending_review', 'draft']))
    else:
        base = base.filter(KPI.status == 'approved')
    all_kpis = base.all()
    result = []
    for kpi in all_kpis:
        if getattr(kpi, 'applies_to_all', False):
            result.append(kpi)
        else:
            if kpi.assigned_employees.filter_by(employee_id=employee.employee_id).first():
                result.append(kpi)
    return result


def calculate_total_weight_for_employee(employee_id, exclude_kpi_id=None):
    """Total weight of KPIs assigned to this employee."""
    from models import Employee
    emp = Employee.query.get(employee_id)
    if not emp:
        return 0.0
    kpis = get_kpis_for_employee(emp, include_pending=True)
    total = sum(k.weight for k in kpis if (exclude_kpi_id is None or k.kpi_id != exclude_kpi_id))
    return max(0.0, total)


def get_remaining_weight_for_employee(employee_id, exclude_kpi_id=None):
    """Remaining weight for this employee."""
    total = calculate_total_weight_for_employee(employee_id, exclude_kpi_id)
    return max(0, 100.0 - total)


def get_kpi_creator_for_employee(employee_id, exclude_kpi_id=None):
    """
    Get the creator (created_by) of KPIs assigned to this employee.
    Each employee can receive KPIs only from one manager.
    Returns created_by of the first assigned KPI, or None if none.
    Excludes applies_to_all KPIs and the optional exclude_kpi_id.
    """
    emp = Employee.query.get(employee_id)
    if not emp:
        return None
    # Get KPIs assigned to this employee (not applies_to_all)
    kpis = KPI.query.join(KPI.assigned_employees).filter(
        Employee.employee_id == employee_id,
        KPI.applies_to_all == False,
        KPI.is_active == True,
        KPI.status.in_(['draft', 'pending_review', 'approved'])
    ).all()
    for kpi in kpis:
        if exclude_kpi_id and kpi.kpi_id == exclude_kpi_id:
            continue
        return kpi.created_by  # First creator found
    return None
