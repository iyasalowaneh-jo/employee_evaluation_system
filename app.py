from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, send_file
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from flask_wtf.csrf import CSRFProtect
from werkzeug.utils import secure_filename
import os
import pandas as pd
from datetime import datetime, date
import json
from functools import wraps

from config import Config
from models import db, User, Employee, KPI, EvaluationCycle, Evaluation, RandomizationLog, FeedbackQuestion, FeedbackEvaluation, KPICreationRule, EvaluatorScore
from forms import LoginForm, EmployeeForm, KPIForm, CycleForm, EvaluationForm
from anonymization import hash_evaluator_id
from utils import (
    allowed_file, calculate_kpi_averages, get_dashboard_data,
    send_notification_email
)

app = Flask(__name__)
app.config.from_object(Config)

# Initialize extensions
csrf = CSRFProtect(app)
db.init_app(app)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'
login_manager.login_message = 'Please log in to access this page.'

# Create upload folder
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

@app.context_processor
def inject_pending_kpi_count():
    """Make pending KPI and KPI evaluation counts available to all templates"""
    out = {'pending_kpi_count': 0, 'pending_kpi_evaluation_count': 0}
    if not current_user.is_authenticated or not current_user.employee:
        return out
    try:
        if current_user.role == 'admin' or current_user.employee.role == 'CEO':
            out['pending_kpi_count'] = KPI.query.filter_by(status='pending_review').count()
        if current_user.employee.role in ['CEO', 'Technical Manager']:
            out['pending_kpi_evaluation_count'] = Evaluation.query.filter_by(status='pending_review').count()
    except Exception:
        pass
    return out

def role_required(role):
    """Decorator to require specific role"""
    def decorator(f):
        @wraps(f)
        @login_required
        def decorated_function(*args, **kwargs):
            if current_user.role != role and current_user.role != 'admin':
                flash('You do not have permission to access this page.', 'danger')
                return redirect(url_for('dashboard'))
            return f(*args, **kwargs)
        return decorated_function
    return decorator

# Routes
@app.route('/')
def index():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data).first()
        if user and user.check_password(form.password.data):
            login_user(user, remember=form.remember_me.data)
            next_page = request.args.get('next')
            return redirect(next_page) if next_page else redirect(url_for('dashboard'))
        flash('Invalid email or password', 'danger')
    
    return render_template('login.html', form=form)

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('You have been logged out.', 'info')
    return redirect(url_for('login'))

@app.route('/dashboard')
@login_required
def dashboard():
    role = current_user.role
    dashboard_data = get_dashboard_data(current_user.employee.employee_id, role)
    
    # Map roles to template names
    template_map = {
        'admin': 'dashboard_admin',
        'ceo': 'dashboard_admin',  # CEO uses admin dashboard
        'technical_manager': 'dashboard_admin',  # Technical Manager uses admin dashboard
        'unit_manager': 'dashboard_manager',
        'department_manager': 'dashboard_manager',
        'manager': 'dashboard_manager',
        'employee': 'dashboard_employee'
    }
    
    template_name = template_map.get(role, 'dashboard_employee')
    return render_template(f'{template_name}.html', data=dashboard_data)

# Employee Management Routes (Admin only)
@app.route('/admin/employees')
@role_required('admin')
def list_employees():
    employees = Employee.query.all()
    return render_template('admin/employees.html', employees=employees)

@app.route('/admin/employees/add', methods=['GET', 'POST'])
@role_required('admin')
def add_employee():
    form = EmployeeForm()
    form.manager_id.choices = [(0, 'None')] + [(e.employee_id, e.full_name) 
                                                 for e in Employee.query.all()]
    
    if form.validate_on_submit():
        employee = Employee(
            full_name=form.full_name.data,
            email=form.email.data,
            department=form.department.data,
            role=form.role.data,
            join_date=form.join_date.data,
            manager_id=form.manager_id.data if form.manager_id.data else None,
            status=form.status.data
        )
        db.session.add(employee)
        db.session.flush()
        
        # Create user account
        user = User(
            employee_id=employee.employee_id,
            email=employee.email,
            role='employee'
        )
        user.set_password('password123')  # Default password, should be changed
        db.session.add(user)
        db.session.commit()
        
        flash('Employee added successfully!', 'success')
        return redirect(url_for('list_employees'))
    
    return render_template('admin/employee_form.html', form=form, title='Add Employee')

@app.route('/admin/employees/upload', methods=['GET', 'POST'])
@role_required('admin')
def upload_employees():
    if request.method == 'POST':
        if 'file' not in request.files:
            flash('No file selected', 'danger')
            return redirect(request.url)
        
        file = request.files['file']
        if file.filename == '':
            flash('No file selected', 'danger')
            return redirect(request.url)
        
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(filepath)
            
            try:
                # Read file
                if filename.endswith('.csv'):
                    df = pd.read_csv(filepath)
                else:
                    df = pd.read_excel(filepath)
                
                # Validate and process
                required_columns = ['full_name', 'email', 'department', 'role', 'join_date']
                missing = [col for col in required_columns if col not in df.columns]
                if missing:
                    flash(f'Missing required columns: {", ".join(missing)}', 'danger')
                    os.remove(filepath)
                    return redirect(request.url)
                
                # Process each row
                success_count = 0
                error_count = 0
                
                for _, row in df.iterrows():
                    try:
                        # Check if employee exists
                        if Employee.query.filter_by(email=row['email']).first():
                            error_count += 1
                            continue
                        
                        # Parse join_date
                        if isinstance(row['join_date'], str):
                            join_date = datetime.strptime(row['join_date'], '%Y-%m-%d').date()
                        else:
                            join_date = row['join_date']
                        
                        employee = Employee(
                            full_name=row['full_name'],
                            email=row['email'],
                            department=row['department'],
                            role=row['role'],
                            join_date=join_date,
                            status=row.get('status', 'active')
                        )
                        db.session.add(employee)
                        db.session.flush()
                        
                        # Create user account
                        user = User(
                            employee_id=employee.employee_id,
                            email=employee.email,
                            role='employee'
                        )
                        user.set_password('password123')
                        db.session.add(user)
                        success_count += 1
                        
                    except Exception as e:
                        error_count += 1
                        db.session.rollback()
                        continue
                
                db.session.commit()
                flash(f'Successfully imported {success_count} employees. {error_count} errors.', 'success')
                os.remove(filepath)
                
            except Exception as e:
                flash(f'Error processing file: {str(e)}', 'danger')
                os.remove(filepath)
            
            return redirect(url_for('list_employees'))
    
    return render_template('admin/upload_employees.html')

# KPI Management Routes
@app.route('/admin/kpis')
@role_required('admin')
def list_kpis():
    # Show all KPIs for admin (including pending/declined for management)
    kpis = KPI.query.order_by(KPI.created_at.desc()).all()
    default_kpis_count = KPI.query.filter_by(is_default=True).count()
    return render_template('admin/kpis.html', kpis=kpis, default_kpis_count=default_kpis_count)

@app.route('/admin/kpis/add', methods=['GET', 'POST'])
@role_required('admin')
def add_kpi():
    form = KPIForm()
    employees = Employee.query.filter_by(status='active').order_by(Employee.full_name).all()
    form.employee_ids.choices = [(e.employee_id, e.full_name) for e in employees]
    if form.validate_on_submit():
        applies = form.applies_to_all.data
        emp_ids = list(form.employee_ids.data or [])
        if not applies and not emp_ids:
            form.employee_ids.errors.append('Select at least one employee, or check "Apply to all employees".')
            return render_template('admin/kpi_form.html', form=form, title='Add KPI', employees=employees)
        # Each employee can receive KPIs only from one manager (admin KPIs have created_by=None)
        if not applies:
            from kpi_creation import get_kpi_creator_for_employee
            for eid in emp_ids:
                creator = get_kpi_creator_for_employee(eid)
                if creator is not None:
                    emp = Employee.query.get(eid)
                    other = Employee.query.get(creator)
                    other_name = other.full_name if other else 'another manager'
                    flash(f'{emp.full_name} already receives KPIs from {other_name}. Each employee can receive KPIs only from one manager.', 'danger')
                    return render_template('admin/kpi_form.html', form=form, title='Add KPI', employees=employees)
        kpi = KPI(
            kpi_name=form.kpi_name.data,
            description=form.description.data,
            weight=form.weight.data,
            is_active=True,
            status='approved',
            is_default=False,
            applies_to_all=applies
        )
        db.session.add(kpi)
        db.session.flush()
        if not applies and emp_ids:
            for eid in emp_ids:
                emp = Employee.query.get(eid)
                if emp:
                    kpi.assigned_employees.append(emp)
        db.session.commit()
        flash('KPI added successfully!', 'success')
        return redirect(url_for('list_kpis'))
    return render_template('admin/kpi_form.html', form=form, title='Add KPI', employees=employees)

@app.route('/admin/kpis/<int:kpi_id>/edit', methods=['GET', 'POST'])
@role_required('admin')
def admin_edit_kpi(kpi_id):
    """Edit KPI - allows editing both default and custom KPIs"""
    from flask import g
    g.editing_kpi_id = kpi_id
    kpi = KPI.query.get_or_404(kpi_id)
    form = KPIForm(obj=kpi)
    employees = Employee.query.filter_by(status='active').order_by(Employee.full_name).all()
    form.employee_ids.choices = [(e.employee_id, e.full_name) for e in employees]
    if request.method == 'GET':
        form.applies_to_all.data = getattr(kpi, 'applies_to_all', False)
        form.employee_ids.data = [e.employee_id for e in kpi.assigned_employees.all()]
    if form.validate_on_submit():
        applies = form.applies_to_all.data
        emp_ids = list(form.employee_ids.data or [])
        if not applies and not emp_ids:
            form.employee_ids.errors.append('Select at least one employee, or check "Apply to all employees".')
            return render_template('admin/kpi_form.html', form=form, title='Edit KPI', kpi=kpi, employees=employees)
        # Each employee can receive KPIs only from one manager
        if not applies:
            from kpi_creation import get_kpi_creator_for_employee
            kpi_creator = kpi.created_by  # employee_id or None
            for eid in emp_ids:
                creator = get_kpi_creator_for_employee(eid, exclude_kpi_id=kpi_id)
                if creator is not None and creator != kpi_creator:
                    emp = Employee.query.get(eid)
                    other = Employee.query.get(creator)
                    other_name = other.full_name if other else 'another manager'
                    flash(f'{emp.full_name} already receives KPIs from {other_name}. Each employee can receive KPIs only from one manager.', 'danger')
                    return render_template('admin/kpi_form.html', form=form, title='Edit KPI', kpi=kpi, employees=employees)
        kpi.kpi_name = form.kpi_name.data
        kpi.description = form.description.data
        kpi.weight = form.weight.data
        kpi.applies_to_all = applies
        # Update employee assignments
        kpi.assigned_employees = []
        if not applies and emp_ids:
            for eid in emp_ids:
                emp = Employee.query.get(eid)
                if emp:
                    kpi.assigned_employees.append(emp)
        if kpi.is_default and kpi.status == 'declined':
            kpi.status = 'approved'
            kpi.decline_reason = None
        db.session.commit()
        flash('KPI updated successfully!', 'success')
        return redirect(url_for('list_kpis'))
    return render_template('admin/kpi_form.html', form=form, title='Edit KPI', kpi=kpi, employees=employees)

@app.route('/admin/kpis/<int:kpi_id>/delete', methods=['POST'])
@role_required('admin')
def admin_delete_kpi(kpi_id):
    """Delete KPI - allows deleting both default and custom KPIs"""
    kpi = KPI.query.get_or_404(kpi_id)
    
    # Check if KPI is being used in evaluations (scores stored as JSON: {kpi_id: score})
    from models import Evaluation
    import json
    all_evals = Evaluation.query.all()
    kpi_in_use = False
    for e in all_evals:
        try:
            scores = json.loads(e.scores) if e.scores else {}
            if str(kpi_id) in scores or kpi_id in scores:
                kpi_in_use = True
                break
        except (json.JSONDecodeError, ValueError):
            continue
    
    if kpi_in_use:
        flash('Cannot delete KPI: It is being used in evaluations. Deactivate it instead.', 'danger')
        return redirect(url_for('list_kpis'))
    
    kpi_name = kpi.kpi_name
    kpi_type = 'default' if kpi.is_default else 'custom'
    
    # Delete the KPI
    db.session.delete(kpi)
    db.session.commit()
    
    flash(f'{kpi_type.capitalize()} KPI "{kpi_name}" deleted successfully!', 'success')
    return redirect(url_for('list_kpis'))

@app.route('/admin/kpis/<int:kpi_id>/toggle-status', methods=['POST'])
@role_required('admin')
def toggle_kpi_status(kpi_id):
    """Toggle KPI active/inactive status"""
    kpi = KPI.query.get_or_404(kpi_id)
    kpi.is_active = not kpi.is_active
    db.session.commit()
    
    status = 'activated' if kpi.is_active else 'deactivated'
    flash(f'KPI "{kpi.kpi_name}" {status} successfully!', 'success')
    return redirect(request.referrer or url_for('list_kpis'))

@app.route('/admin/kpis/default', methods=['GET'])
@role_required('admin')
def default_kpis():
    """View and manage default KPIs grouped by role"""
    default_kpis = KPI.query.filter_by(is_default=True).order_by(KPI.kpi_name).all()
    
    # Group by role
    kpis_by_role = {}
    for kpi in default_kpis:
        role = kpi.role or 'All Roles'
        if role not in kpis_by_role:
            kpis_by_role[role] = []
        kpis_by_role[role].append(kpi)
    
    return render_template('admin/default_kpis.html', kpis_by_role=kpis_by_role)

# KPI Creation Permissions (who can create KPIs for whom)
@app.route('/admin/kpi-permissions')
@role_required('admin')
def kpi_permissions():
    """View and manage KPI creation rules (who can create KPIs for whom)"""
    rules = KPICreationRule.query.order_by(KPICreationRule.manager_role, KPICreationRule.target_role).all()
    roles = sorted({r for (r,) in db.session.query(Employee.role).distinct().all() if r})
    return render_template('admin/kpi_permissions.html', rules=rules, roles=roles)

@app.route('/admin/kpi-permissions/add', methods=['POST'])
@role_required('admin')
def add_kpi_permission():
    manager_role = request.form.get('manager_role', '').strip()
    target_role = request.form.get('target_role', '').strip()
    if not manager_role or not target_role:
        flash('Manager role and target role are required.', 'danger')
        return redirect(url_for('kpi_permissions'))
    existing = KPICreationRule.query.filter_by(manager_role=manager_role, target_role=target_role).first()
    if existing:
        flash(f'Rule already exists: {manager_role} → {target_role}', 'warning')
        return redirect(url_for('kpi_permissions'))
    db.session.add(KPICreationRule(manager_role=manager_role, target_role=target_role))
    db.session.commit()
    flash(f'Added rule: {manager_role} can create KPIs for {target_role}', 'success')
    return redirect(url_for('kpi_permissions'))

@app.route('/admin/kpi-permissions/<int:rule_id>/delete', methods=['POST'])
@role_required('admin')
def delete_kpi_permission(rule_id):
    rule = KPICreationRule.query.get_or_404(rule_id)
    db.session.delete(rule)
    db.session.commit()
    flash('Rule removed.', 'success')
    return redirect(url_for('kpi_permissions'))

@app.route('/admin/kpi-permissions/reset', methods=['POST'])
@role_required('admin')
def reset_kpi_permissions():
    """Reset rules from default hierarchy (KPI_CREATION_HIERARCHY)"""
    from kpi_creation import KPI_CREATION_HIERARCHY
    KPICreationRule.query.delete()
    for manager_role, config in KPI_CREATION_HIERARCHY.items():
        for target_role in config.get('can_create_for', []):
            db.session.add(KPICreationRule(manager_role=manager_role, target_role=target_role))
    db.session.commit()
    flash('KPI creation rules reset to default hierarchy.', 'success')
    return redirect(url_for('kpi_permissions'))

# Evaluation Cycle Routes
@app.route('/admin/cycles')
@role_required('admin')
def list_cycles():
    cycles = EvaluationCycle.query.order_by(EvaluationCycle.created_at.desc()).all()
    has_active_cycle = EvaluationCycle.query.filter_by(status='active').first() is not None
    return render_template('admin/cycles.html', cycles=cycles, has_active_cycle=has_active_cycle)

@app.route('/admin/cycles/add', methods=['GET', 'POST'])
@role_required('admin')
def add_cycle():
    active_cycle = EvaluationCycle.query.filter_by(status='active').first()
    if active_cycle:
        flash(f'Cannot create a new evaluation round while "{active_cycle.name}" is still active. Please close the current round first.', 'danger')
        return redirect(url_for('list_cycles'))
    
    form = CycleForm()
    if form.validate_on_submit():
        cycle = EvaluationCycle(
            name=form.name.data,
            start_date=form.start_date.data,
            end_date=form.end_date.data,
            description=form.description.data,
            status='draft',
            include_kpi=form.include_kpi.data,
            include_360=form.include_360.data
        )
        db.session.add(cycle)
        db.session.commit()
        flash('Evaluation cycle created successfully!', 'success')
        return redirect(url_for('list_cycles'))
    
    return render_template('admin/cycle_form.html', form=form, title='Create Evaluation Cycle')

@app.route('/admin/cycles/<int:cycle_id>/assign', methods=['POST'])
@role_required('admin')
def assign_evaluators_route(cycle_id):
    """Assign 360 and KPI evaluators for this cycle. Uses relationship matrix and KPI hierarchy."""
    cycle = EvaluationCycle.query.get_or_404(cycle_id)
    
    employees_list = Employee.query.filter_by(status='active').all()
    if len(employees_list) < 2:
        flash('Need at least 2 active employees for evaluation.', 'danger')
        return redirect(url_for('list_cycles'))
    
    # Build employees dict (id -> employee) for cycle_assignment
    employees = {e.employee_id: e for e in employees_list}
    
    # Clear existing cycle data for the types this cycle includes
    if cycle.include_360:
        RandomizationLog.query.filter_by(cycle_id=cycle_id, evaluation_type='360').delete()
        FeedbackEvaluation.query.filter_by(cycle_id=cycle_id).delete()
        EvaluatorScore.query.filter_by(cycle_id=cycle_id).delete()
    if cycle.include_kpi:
        RandomizationLog.query.filter_by(cycle_id=cycle_id, evaluation_type='kpi').delete()
        Evaluation.query.filter_by(cycle_id=cycle_id).delete()
    
    # Assign based on cycle type
    try:
        from cycle_assignment import assign_360_evaluations, assign_kpi_evaluations
        if cycle.include_360:
            assign_360_evaluations(employees, cycle_id)
        if cycle.include_kpi:
            assign_kpi_evaluations(employees, cycle_id)
    except Exception as e:
        db.session.rollback()
        flash(f'Assignment failed: {e}. Ensure evaluation_relationships data is loaded (run load_evaluation_dataset_to_mysql.py).', 'danger')
        return redirect(url_for('list_cycles'))
    
    cycle.status = 'active'
    db.session.commit()
    
    parts = []
    if cycle.include_360:
        parts.append('360')
    if cycle.include_kpi:
        parts.append('KPI')
    flash(f'{ " and ".join(parts) } evaluators assigned. ' + ('Managers should assign KPIs to employees for this cycle.' if cycle.include_kpi else ''), 'success')
    return redirect(url_for('list_cycles'))

@app.route('/admin/cycles/<int:cycle_id>/close', methods=['POST'])
@role_required('admin')
def close_cycle(cycle_id):
    """Close an active evaluation round (set status to completed)."""
    cycle = EvaluationCycle.query.get_or_404(cycle_id)
    if cycle.status != 'active':
        flash(f'Only active cycles can be closed. This cycle is "{cycle.status}".', 'warning')
        return redirect(url_for('list_cycles'))
    cycle.status = 'completed'
    db.session.commit()
    flash(f'Evaluation round "{cycle.name}" has been closed.', 'success')
    return redirect(url_for('list_cycles'))

# Evaluation Routes
@app.route('/evaluations')
@login_required
def my_evaluations():
    employee_id = current_user.employee.employee_id
    # Use hashed evaluator ID for anonymity
    # Need to check all active cycles
    active_cycles = EvaluationCycle.query.filter_by(status='active').all()
    assignments = []
    for cycle in active_cycles:
        evaluator_hash = hash_evaluator_id(employee_id, cycle.cycle_id)
        cycle_assignments = RandomizationLog.query.filter_by(
            evaluator_hash=evaluator_hash,
            cycle_id=cycle.cycle_id
        ).all()
        assignments.extend(cycle_assignments)
    
    # Get cycle info and check if already submitted
    evaluations_data = []
    for assignment in assignments:
        cycle = assignment.cycle
        existing = Evaluation.query.filter_by(
            evaluator_id=employee_id,
            evaluatee_id=assignment.evaluatee_id,
            cycle_id=assignment.cycle_id
        ).first()
        
        evaluations_data.append({
            'assignment': assignment,
            'cycle': cycle,
            'evaluatee': assignment.evaluatee,
            'submitted': existing is not None,
            'evaluation': existing
        })
    
    return render_template('evaluations/list.html', evaluations=evaluations_data)

@app.route('/evaluations/<int:cycle_id>/<int:evaluatee_id>', methods=['GET', 'POST'])
@login_required
def submit_evaluation(cycle_id, evaluatee_id):
    # Verify assignment
    assignment = RandomizationLog.query.filter_by(
        cycle_id=cycle_id,
        evaluator_id=current_user.employee.employee_id,
        evaluatee_id=evaluatee_id
    ).first_or_404()
    
    # Get KPIs for this evaluation (employee-based assignment)
    evaluatee = Employee.query.get(evaluatee_id)
    from kpi_creation import get_kpis_for_employee
    kpis = get_kpis_for_employee(evaluatee)
    
    # Check if already submitted
    existing_evaluation = Evaluation.query.filter_by(
        evaluator_id=current_user.employee.employee_id,
        evaluatee_id=evaluatee_id,
        cycle_id=cycle_id
    ).first()
    
    form = EvaluationForm()
    
    if request.method == 'POST':
        scores = {}
        for kpi_id, score in request.form.items():
            if kpi_id.startswith('kpi_'):
                kpi_id_int = int(kpi_id.replace('kpi_', ''))
                try:
                    scores[kpi_id_int] = float(score)
                except ValueError:
                    pass
        
        # Submit as pending_review so CEO can approve; otherwise stays draft and never appears in Pending Approvals
        status = 'pending_review'
        if existing_evaluation:
            existing_evaluation.scores = json.dumps(scores)
            existing_evaluation.comments = request.form.get('comments', '')
            existing_evaluation.status = status
            existing_evaluation.submitted_at = datetime.utcnow()
        else:
            evaluation = Evaluation(
                evaluator_id=current_user.employee.employee_id,
                evaluatee_id=evaluatee_id,
                cycle_id=cycle_id,
                scores=json.dumps(scores),
                comments=request.form.get('comments', ''),
                status=status
            )
            db.session.add(evaluation)
        
        db.session.commit()
        flash('Evaluation submitted successfully!', 'success')
        return redirect(url_for('my_evaluations'))
    
    # Pre-populate form if editing
    if existing_evaluation:
        form.comments.data = existing_evaluation.comments
        existing_scores = json.loads(existing_evaluation.scores)
    else:
        existing_scores = {}
    
    return render_template('evaluations/form.html', 
                         form=form, 
                         kpis=kpis, 
                         evaluatee=evaluatee,
                         cycle=assignment.cycle,
                         existing_scores=existing_scores)

# Reports and Analytics
@app.route('/reports/department')
@role_required('manager')
def department_report():
    employee_id = current_user.employee.employee_id
    manager = Employee.query.get(employee_id)
    subordinates = Employee.query.filter_by(manager_id=employee_id).all()
    
    # Get latest cycle
    latest_cycle = EvaluationCycle.query.filter_by(status='active').first()
    if not latest_cycle:
        flash('No active evaluation cycle found', 'info')
        return redirect(url_for('dashboard'))
    
    report_data = calculate_kpi_averages(subordinates, latest_cycle.cycle_id)
    return render_template('reports/department.html', report_data=report_data, cycle=latest_cycle)

# Import 360 routes (must be after app creation)
try:
    from app_360 import register_360_routes, calculate_employee_kpi_score, calculate_employee_360_score, get_feedback_details
    # Register 360 routes
    register_360_routes(app)
except ImportError:
    print("Warning: Could not import 360 routes. Some features may not be available.")
    def calculate_employee_kpi_score(employee_id, cycle_id):
        return 0.0
    def calculate_employee_360_score(employee_id, cycle_id):
        return 0.0
    def get_feedback_details(employee_id, cycle_id):
        return {}

# Import and register KPI evaluation routes
try:
    from kpi_routes import register_kpi_routes
    register_kpi_routes(app)
except ImportError as e:
    print(f"Warning: Could not import KPI routes: {e}")

# Import and register KPI creation routes
try:
    from kpi_creation_routes import register_kpi_creation_routes
    register_kpi_creation_routes(app)
except ImportError as e:
    print(f"Warning: Could not import KPI creation routes: {e}")

# Import and register results visibility routes
try:
    from results_routes import register_results_routes
    register_results_routes(app)
except ImportError as e:
    print(f"Warning: Could not import results routes: {e}")

# Add route for my performance
@app.route('/results/my-performance')
@login_required
def my_performance():
    """View own performance results (KPI + 360 combined)"""
    employee_id = current_user.employee.employee_id
    employee = Employee.query.get(employee_id)
    
    # Get active cycle
    latest_cycle = EvaluationCycle.query.filter_by(status='active').first()
    if not latest_cycle:
        flash('No active evaluation cycle found', 'info')
        return redirect(url_for('dashboard'))
    
    # Calculate KPI and 360 scores; combine only if this round includes them and score > 0
    kpi_score = calculate_employee_kpi_score(employee_id, latest_cycle.cycle_id)
    feedback_score = calculate_employee_360_score(employee_id, latest_cycle.cycle_id)
    include_kpi = getattr(latest_cycle, 'include_kpi', True)
    include_360 = getattr(latest_cycle, 'include_360', True)
    use_kpi = include_kpi and kpi_score > 0
    use_360 = include_360 and feedback_score > 0
    if use_kpi and use_360:
        combined_score = (kpi_score * 0.6) + (feedback_score * 0.4)
    elif use_kpi:
        combined_score = kpi_score
    elif use_360:
        combined_score = feedback_score
    else:
        combined_score = 0.0
    
    # Get detailed feedback
    feedback_details = get_feedback_details(employee_id, latest_cycle.cycle_id)
    
    return render_template('results/my_performance.html',
                         employee=employee,
                         cycle=latest_cycle,
                         kpi_score=kpi_score,
                         feedback_score=feedback_score,
                         combined_score=combined_score,
                         feedback_details=feedback_details)

if __name__ == '__main__':
    # Run migration for open-ended questions if needed
    try:
        from migrate_open_ended import migrate_open_ended
        with app.app_context():
            migrate_open_ended()
    except Exception as e:
        print(f"Migration check: {e}")
    
    with app.app_context():
        # Create all tables (this will add missing columns if models changed)
        db.create_all()
        
        # Run migration to add any missing columns
        try:
            from migrate_evaluations import migrate_evaluations_table
            migrate_evaluations_table()
        except Exception as e:
            print(f"Migration note: {e}")
        
        # Run migration for feedback status
        try:
            from migrate_feedback_status import migrate_feedback_status
            migrate_feedback_status()
        except Exception as e:
            print(f"Feedback status migration note: {e}")
        # Run migration for KPI employee assignment
        try:
            from migrate_kpi_employee_assignment import migrate
            migrate()
        except Exception as e:
            print(f"KPI employee migration note: {e}")
        # Ensure only 2 open-ended questions (global) are active
        try:
            from migrate_trim_open_ended import migrate_trim_open_ended
            migrate_trim_open_ended()
        except Exception as e:
            print(f"Trim open-ended note: {e}")
        # Check if data needs to be seeded
        employee_count = Employee.query.count()
        if employee_count == 0:
            print("="*60)
            print("No data found. Running seed script...")
            print("="*60)
            try:
                from seed_data import seed_all_data
                seed_all_data()
                print("\n✅ Seeding complete! System is ready to use.")
            except Exception as e:
                print(f"\n❌ Error during seeding: {e}")
                print("You can run 'python seed_data.py' manually to seed data.")
        
        # Check if CEO has admin role (backup check)
        if employee_count > 0:
            ceo = Employee.query.filter_by(role='CEO').first()
            if ceo:
                ceo_user = User.query.filter_by(employee_id=ceo.employee_id).first()
                if ceo_user and ceo_user.role != 'admin':
                    # Update CEO to have admin role
                    ceo_user.role = 'admin'
                    db.session.commit()
                    print("CEO user updated with admin role")
                elif not ceo_user:
                    # Create CEO user with admin role
                    ceo_user = User(
                        employee_id=ceo.employee_id,
                        email=ceo.email,
                        role='admin'
                    )
                    ceo_user.set_password('password123')
                    db.session.add(ceo_user)
                    db.session.commit()
                    print(f"CEO/Admin user created: {ceo.email} / password123")
    
    print("\n🚀 Starting Flask application...")
    print("📊 Access the system at: http://localhost:5000")
    print("👤 Admin/CEO login: ceo@company.com / password123")
    print("👥 All users password: password123\n")
    app.run(debug=True, host='0.0.0.0', port=5000)
