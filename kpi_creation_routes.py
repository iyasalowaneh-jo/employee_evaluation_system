"""
Routes for manager-based KPI creation and CEO approval
"""
from flask import render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from models import db, Employee, KPI, EvaluationCycle
from forms import KPIForm
from kpi_creation import (
    can_create_kpi_for_role, get_creatable_roles, get_manager_department,
    calculate_total_weight, get_remaining_weight,
    calculate_total_weight_for_employee, get_remaining_weight_for_employee,
    get_kpi_creator_for_employee
)
from datetime import datetime

def register_kpi_creation_routes(app):
    """Register KPI creation routes"""
    
    @app.route('/kpis/create', methods=['GET', 'POST'])
    @login_required
    def create_kpi():
        """Create KPI - available to managers for their subordinates"""
        manager = current_user.employee
        if not manager:
            flash('Employee record not found', 'danger')
            return redirect(url_for('dashboard'))
        
        manager_role = manager.role
        
        # Check if user can create KPIs
        creatable_roles = get_creatable_roles(manager_role)
        if not creatable_roles:
            flash('You do not have permission to create KPIs. Only managers can create KPIs for their subordinates.', 'danger')
            return redirect(url_for('dashboard'))
        
        form = KPIForm()
        # Get employees manager can assign KPIs to: direct reports whose role is in creatable_roles
        direct_reports = Employee.query.filter_by(manager_id=manager.employee_id, status='active').order_by(Employee.full_name).all()
        assignable_employees = [e for e in direct_reports if can_create_kpi_for_role(manager_role, e.role or '')]
        form.employee_ids.choices = [(e.employee_id, f"{e.full_name} ({e.role})") for e in assignable_employees]
        form.applies_to_all.data = False  # Managers assign to specific subordinates only
        # Pre-select employee if ?for_employee=X (from Add KPI button - single employee only)
        for_emp_id = request.args.get('for_employee', type=int)
        for_employee_obj = None
        if for_emp_id:
            for e in assignable_employees:
                if e.employee_id == for_emp_id:
                    for_employee_obj = e
                    form.employee_ids.data = [for_emp_id]
                    break
        
        manager_dept = get_manager_department(manager_role)
        
        # Compute remaining_weights per employee (for validation display)
        remaining_weights = {e.employee_id: get_remaining_weight_for_employee(e.employee_id) for e in assignable_employees}
        # Also key by full_name for template
        remaining_weights_by_name = {e.full_name: get_remaining_weight_for_employee(e.employee_id) for e in assignable_employees}
        
        # Get default KPIs for display
        default_kpis_by_role = {}
        if creatable_roles:
            from sqlalchemy import or_
            default_kpis_query = KPI.query.filter(
                KPI.is_default == True,
                KPI.is_active == True
            ).filter(
                or_(KPI.role.in_(creatable_roles), KPI.role == 'Template')
            )
            if manager_dept and manager_role != 'CFO':
                default_kpis_query = default_kpis_query.filter(
                    or_(KPI.department == manager_dept, KPI.department.is_(None))
                )
            default_kpis_list = default_kpis_query.order_by(KPI.role, KPI.kpi_name).all()
            for kpi in default_kpis_list:
                role_kpi = kpi.role or 'All Roles'
                if role_kpi not in default_kpis_by_role:
                    default_kpis_by_role[role_kpi] = []
                default_kpis_by_role[role_kpi].append(kpi)
        
        if request.method == 'POST':
            if form.validate_on_submit():
                applies = form.applies_to_all.data
                emp_ids = list(form.employee_ids.data or [])
                weight = form.weight.data
                
                if not applies and not emp_ids:
                    form.employee_ids.errors.append('Select at least one employee.')
                    return render_template('kpi_creation/create.html', form=form, manager=manager,
                                         creatable_roles=creatable_roles, assignable_employees=assignable_employees,
                                         remaining_weights=remaining_weights, default_kpis_by_role=default_kpis_by_role,
                                         for_employee=for_employee_obj)
                
                # Validate each selected employee is a direct subordinate
                assignable_ids = {e.employee_id for e in assignable_employees}
                for eid in emp_ids:
                    emp = Employee.query.get(eid)
                    if not emp or eid not in assignable_ids:
                        flash('Invalid employee selection. Please select from your direct reports.', 'danger')
                        return render_template('kpi_creation/create.html', form=form, manager=manager,
                                             creatable_roles=creatable_roles, assignable_employees=assignable_employees,
                                             remaining_weights=remaining_weights, default_kpis_by_role=default_kpis_by_role,
                                             for_employee=for_employee_obj)
                
                # Each employee can receive KPIs only from one manager
                for eid in emp_ids:
                    creator = get_kpi_creator_for_employee(eid)
                    if creator is not None and creator != manager.employee_id:
                        emp = Employee.query.get(eid)
                        other = Employee.query.get(creator)
                        other_name = other.full_name if other else 'another manager'
                        flash(f'{emp.full_name} already receives KPIs from {other_name}. Each employee can receive KPIs only from one manager.', 'danger')
                        return render_template('kpi_creation/create.html', form=form, manager=manager,
                                             creatable_roles=creatable_roles, assignable_employees=assignable_employees,
                                             remaining_weights=remaining_weights, default_kpis_by_role=default_kpis_by_role,
                                             for_employee=for_employee_obj)
                
                # Check total weight per employee (employee-based constraint)
                weight_error = None
                for eid in emp_ids:
                    emp = Employee.query.get(eid)
                    total_weight = calculate_total_weight_for_employee(eid)
                    remaining = get_remaining_weight_for_employee(eid)
                    if total_weight >= 100 or total_weight + weight > 100 or weight > remaining:
                        weight_error = (emp.full_name if emp else f'ID {eid}', total_weight, remaining)
                        break
                
                if weight_error:
                    name, tw, rem = weight_error
                    flash(
                        f'Cannot create KPI: Weight would exceed 100% for {name}. '
                        f'Current: {tw:.1f}%, Remaining: {rem:.1f}%, Your input: {weight:.1f}%.',
                        'warning'
                    )
                    return render_template('kpi_creation/create.html', form=form, manager=manager,
                                         creatable_roles=creatable_roles, assignable_employees=assignable_employees,
                                         remaining_weights=remaining_weights, default_kpis_by_role=default_kpis_by_role,
                                         for_employee=for_employee_obj)
                
                if weight <= 0:
                    form.weight.errors.append('Weight must be greater than 0.')
                    return render_template('kpi_creation/create.html', form=form, manager=manager,
                                         creatable_roles=creatable_roles, assignable_employees=assignable_employees,
                                         remaining_weights=remaining_weights, default_kpis_by_role=default_kpis_by_role)
                
                # Create KPI with draft status (employee-based assignment)
                kpi = KPI(
                    kpi_name=form.kpi_name.data,
                    description=form.description.data,
                    weight=weight,
                    is_active=True,
                    created_by=manager.employee_id,
                    status='draft',
                    applies_to_all=False
                )
                db.session.add(kpi)
                db.session.flush()
                for eid in emp_ids:
                    emp = Employee.query.get(eid)
                    if emp:
                        kpi.assigned_employees.append(emp)
                db.session.commit()
                
                flash('KPI created successfully! It will be submitted for CEO approval.', 'success')
                return redirect(url_for('my_kpis'))
        
        return render_template('kpi_creation/create.html',
                             form=form,
                             manager=manager,
                             creatable_roles=creatable_roles,
                             assignable_employees=assignable_employees,
                             remaining_weights=remaining_weights,
                             default_kpis_by_role=default_kpis_by_role,
                             for_employee=for_employee_obj)
    
    @app.route('/kpis/my-kpis')
    @login_required
    def my_kpis():
        """List KPIs created by current manager and assigned to their reports (excludes default templates)"""
        manager = current_user.employee
        if not manager:
            flash('Employee record not found', 'danger')
            return redirect(url_for('dashboard'))
        
        # Get roles this manager can create KPIs for
        creatable_roles = get_creatable_roles(manager.role)
        
        # Get all KPIs created by this manager (assigned to their reports)
        # Only show KPIs that are actually assigned to employees - not default templates
        my_kpis = KPI.query.filter_by(created_by=manager.employee_id).order_by(KPI.created_at.desc()).all()
        
        # Exclude unassigned default KPIs - they are templates for Create KPI page only
        all_kpis = [k for k in my_kpis if not (k.is_default and k.assigned_employees.count() == 0)]
        
        # Group KPIs by employee - direct reports whose role is in creatable_roles
        direct_reports = Employee.query.filter_by(manager_id=manager.employee_id, status='active').order_by(Employee.full_name).all()
        assignable_employees = [e for e in direct_reports if can_create_kpi_for_role(manager.role, e.role or '')]
        
        kpis_by_employee = {}
        for emp in assignable_employees:
            emp_kpis = []
            for kpi in all_kpis:
                if getattr(kpi, 'applies_to_all', False):
                    emp_kpis.append(kpi)
                elif any(e.employee_id == emp.employee_id for e in kpi.assigned_employees.all()):
                    emp_kpis.append(kpi)
            total_weight = calculate_total_weight_for_employee(emp.employee_id)
            remaining = get_remaining_weight_for_employee(emp.employee_id)
            kpis_by_employee[emp] = {
                'employee': emp,
                'kpis': emp_kpis,
                'total_weight': total_weight,
                'remaining_weight': remaining,
            }
        
        return render_template('kpi_creation/my_kpis.html', 
                             manager=manager,
                             kpis_by_employee=kpis_by_employee,
                             assignable_employees=assignable_employees,
                             creatable_roles=creatable_roles)
    
    @app.route('/kpis/<int:kpi_id>/submit', methods=['POST'])
    @login_required
    def submit_kpi_for_approval(kpi_id):
        """Submit KPI for CEO approval - converts default KPIs to regular KPIs first"""
        kpi = KPI.query.get_or_404(kpi_id)
        manager = current_user.employee
        
        # If it's a default KPI, convert it to regular KPI first, then submit
        if kpi.is_default and (kpi.created_by is None or kpi.created_by != manager.employee_id):
            # Convert default KPI to regular KPI owned by manager
            kpi.is_default = False
            kpi.created_by = manager.employee_id
            kpi.status = 'draft'  # Set to draft first
            db.session.commit()
            flash('Default KPI converted to your KPI.', 'info')
        
        # Now treat it as a regular KPI - verify ownership
        if kpi.created_by != manager.employee_id:
            flash('You do not have permission to submit this KPI.', 'danger')
            return redirect(url_for('my_kpis'))
        
        # Allow resubmission of declined KPIs
        if kpi.status != 'draft' and kpi.status != 'declined':
            flash('This KPI has already been submitted or processed.', 'warning')
            return redirect(url_for('my_kpis'))
        
        # STRICT weight validation per assigned employee
        applies_all = getattr(kpi, 'applies_to_all', False)
        assigned = list(kpi.assigned_employees.all()) if not applies_all else list(Employee.query.filter_by(status='active').all())
        if not assigned and not applies_all:
            flash('This KPI has no assigned employees. Please edit and assign employees before submitting.', 'warning')
            return redirect(url_for('my_kpis'))
        for emp in assigned:
            total_weight = calculate_total_weight_for_employee(emp.employee_id, exclude_kpi_id=kpi_id)
            new_total = total_weight + kpi.weight
            if new_total > 100:
                remaining = get_remaining_weight_for_employee(emp.employee_id, exclude_kpi_id=kpi_id)
                flash(
                    f'Cannot submit: Total weight would exceed 100% for {emp.full_name}. '
                    f'Current: {total_weight:.1f}%, This KPI: {kpi.weight:.1f}%, '
                    f'Total would be: {new_total:.1f}%. Reduce to {remaining:.1f}% or less.',
                    'danger'
                )
                return redirect(url_for('my_kpis'))
        
        # Clear decline reason if it was declined
        if kpi.decline_reason:
            kpi.decline_reason = None
        
        # CEO's own KPIs are auto-approved; others go to pending_review
        if manager.role == 'CEO':
            kpi.status = 'approved'
            kpi.approved_by = manager.employee_id
            kpi.approved_at = datetime.utcnow()
            db.session.commit()
            flash('KPI submitted and approved automatically (CEO).', 'success')
        else:
            kpi.status = 'pending_review'
            db.session.commit()
            flash('KPI submitted for CEO approval.', 'success')
        
        return redirect(url_for('my_kpis'))
    
    @app.route('/kpis/<int:kpi_id>/edit', methods=['GET', 'POST'])
    @login_required
    def edit_kpi(kpi_id):
        """Edit KPI - allows editing default KPIs (converts to regular) or own draft KPIs"""
        kpi = KPI.query.get_or_404(kpi_id)
        manager = current_user.employee
        
        # Check if this is a default KPI that manager wants to edit
        # If it's a default KPI, convert it to a regular KPI on first edit
        is_default_kpi = kpi.is_default and (kpi.created_by is None or kpi.created_by != manager.employee_id)
        
        if is_default_kpi:
            # Convert default KPI to regular KPI owned by manager
            kpi.is_default = False
            kpi.created_by = manager.employee_id
            kpi.status = 'draft'  # Set to draft so it can be edited
            db.session.commit()
            flash('Default KPI converted to your KPI. You can now edit it.', 'info')
        
        # Now treat it as a regular KPI - verify ownership and status
        if kpi.created_by != manager.employee_id:
            flash('You do not have permission to edit this KPI.', 'danger')
            return redirect(url_for('my_kpis'))
        
        if kpi.status not in ('draft', 'declined', 'approved'):
            flash('This KPI cannot be edited.', 'warning')
            return redirect(url_for('my_kpis'))
        
        form = KPIForm(obj=kpi) if request.method == 'GET' else KPIForm(request.form)
        creatable_roles = get_creatable_roles(manager.role)
        direct_reports = Employee.query.filter_by(manager_id=manager.employee_id, status='active').order_by(Employee.full_name).all()
        assignable_employees = [e for e in direct_reports if can_create_kpi_for_role(manager.role, e.role or '')]
        form.employee_ids.choices = [(e.employee_id, f"{e.full_name} ({e.role})") for e in assignable_employees]
        if request.method == 'GET':
            form.applies_to_all.data = getattr(kpi, 'applies_to_all', False)
            form.employee_ids.data = [e.employee_id for e in kpi.assigned_employees.all()]
        
        # Pass KPI ID to form validator via Flask g
        from flask import g
        g.editing_kpi_id = kpi_id
        
        if request.method == 'POST':
            if form.validate_on_submit():
                emp_ids = list(form.employee_ids.data or [])
                applies = False  # Managers always assign to specific employees
                if not applies and not emp_ids:
                    form.employee_ids.errors.append('Select at least one employee.')
                    return render_template('kpi_creation/edit.html', form=form, kpi=kpi, manager=manager)
                
                # Each employee can receive KPIs only from one manager
                for eid in emp_ids:
                    creator = get_kpi_creator_for_employee(eid, exclude_kpi_id=kpi_id)
                    if creator is not None and creator != manager.employee_id:
                        emp = Employee.query.get(eid)
                        other = Employee.query.get(creator)
                        other_name = other.full_name if other else 'another manager'
                        flash(f'{emp.full_name} already receives KPIs from {other_name}. Each employee can receive KPIs only from one manager.', 'danger')
                        return render_template('kpi_creation/edit.html', form=form, kpi=kpi, manager=manager)
                
                # Weight constraint per assigned employee
                target_emp_ids = [e.employee_id for e in Employee.query.filter_by(status='active').all()] if applies else emp_ids
                for eid in target_emp_ids:
                    total = calculate_total_weight_for_employee(eid, exclude_kpi_id=kpi_id)
                    if total + form.weight.data > 100:
                        form.weight.errors.append(
                            f'Total weight would exceed 100% for one or more assigned employees.'
                        )
                        return render_template('kpi_creation/edit.html', form=form, kpi=kpi, manager=manager)
                
                kpi.kpi_name = form.kpi_name.data
                kpi.description = form.description.data
                kpi.weight = form.weight.data
                kpi.applies_to_all = applies
                kpi.assigned_employees = []
                if not applies and emp_ids:
                    for eid in emp_ids:
                        emp = Employee.query.get(eid)
                        if emp:
                            kpi.assigned_employees.append(emp)
                
                # If KPI was declined, change status back to draft so it can be resubmitted
                if kpi.status == 'declined':
                    kpi.status = 'draft'
                    kpi.decline_reason = None  # Clear decline reason
                
                db.session.commit()
                flash('KPI updated successfully!', 'success')
                return redirect(url_for('my_kpis'))
        
        return render_template('kpi_creation/edit.html', form=form, kpi=kpi, manager=manager)
    
    @app.route('/kpis/<int:kpi_id>/delete', methods=['POST'])
    @login_required
    def delete_kpi(kpi_id):
        """Delete KPI - allows deleting default KPIs or own draft KPIs"""
        kpi = KPI.query.get_or_404(kpi_id)
        manager = current_user.employee
        
        # Check if KPI is being used in evaluations
        # KPIs are stored in JSON scores field: {"kpi_id": score, ...}
        from models import Evaluation
        import json
        
        all_evaluations = Evaluation.query.all()
        kpi_in_use = False
        
        for evaluation in all_evaluations:
            try:
                scores = json.loads(evaluation.scores)
                if str(kpi_id) in scores or int(kpi_id) in scores:
                    kpi_in_use = True
                    break
            except (json.JSONDecodeError, ValueError):
                continue
        
        if kpi_in_use:
            flash('Cannot delete KPI: It is being used in evaluations. Please remove it from evaluations first.', 'danger')
            return redirect(url_for('my_kpis'))
        
        # If it's a default KPI, deactivate it (don't delete from system, just hide from this manager)
        if kpi.is_default and (kpi.created_by is None or kpi.created_by != manager.employee_id):
            # For default KPIs, we'll deactivate them so they don't show in the manager's view
            # But we need a way to track this per-manager. For now, we'll just delete it.
            # Actually, let's allow deletion of default KPIs - they can be recreated if needed
            kpi.is_active = False
            db.session.commit()
            flash('KPI removed successfully!', 'success')
            return redirect(url_for('my_kpis'))
        
        # For non-default KPIs, verify ownership and status
        if kpi.created_by != manager.employee_id:
            flash('You do not have permission to delete this KPI.', 'danger')
            return redirect(url_for('my_kpis'))
        
        if kpi.status not in ('draft', 'declined', 'approved'):
            flash('This KPI cannot be deleted.', 'warning')
            return redirect(url_for('my_kpis'))
        
        db.session.delete(kpi)
        db.session.commit()
        flash('KPI deleted successfully!', 'success')
        return redirect(url_for('my_kpis'))
    
    # CEO Approval Routes
    @app.route('/kpis/pending-approval')
    @login_required
    def pending_kpi_approvals():
        """List KPIs pending CEO approval"""
        if current_user.role != 'admin' and current_user.employee.role != 'CEO':
            flash('Only CEO can review KPI approvals.', 'danger')
            return redirect(url_for('dashboard'))
        
        pending_kpis = KPI.query.filter_by(status='pending_review').order_by(KPI.created_at.desc()).all()
        pending_count = len(pending_kpis)
        
        # Group by creator and calculate weight info
        kpis_by_creator = {}
        for kpi in pending_kpis:
            creator = kpi.creator
            if creator:
                key = f"{creator.full_name} ({creator.role})"
                if key not in kpis_by_creator:
                    kpis_by_creator[key] = []
                kpis_by_creator[key].append(kpi)
        
        return render_template('kpi_creation/pending_approvals.html', 
                             pending_kpis=pending_kpis,
                             kpis_by_creator=kpis_by_creator)
    
    @app.route('/kpis/<int:kpi_id>/approve', methods=['POST'])
    @login_required
    def approve_kpi(kpi_id):
        """Approve KPI - CEO only"""
        if current_user.role != 'admin' and current_user.employee.role != 'CEO':
            flash('Only CEO can approve KPIs.', 'danger')
            return redirect(url_for('dashboard'))
        
        kpi = KPI.query.get_or_404(kpi_id)
        
        if kpi.status != 'pending_review':
            flash('This KPI is not pending approval.', 'warning')
            return redirect(url_for('pending_kpi_approvals'))
        
        # STRICT weight validation per assigned employee
        assigned = kpi.assigned_employees.all() if not getattr(kpi, 'applies_to_all', False) else Employee.query.filter_by(status='active').all()
        for emp in assigned:
            total_weight = calculate_total_weight_for_employee(emp.employee_id, exclude_kpi_id=kpi_id)
            new_total = total_weight + kpi.weight
            if new_total > 100:
                remaining = get_remaining_weight_for_employee(emp.employee_id, exclude_kpi_id=kpi_id)
                flash(
                    f'Cannot approve: Total weight would exceed 100% for {emp.full_name}. '
                    f'Current: {total_weight:.1f}%, This KPI: {kpi.weight:.1f}%. '
                    f'Ask manager to reduce weight to {remaining:.1f}% or less.',
                    'danger'
                )
                return redirect(url_for('pending_kpi_approvals'))
        
        kpi.status = 'approved'
        kpi.approved_by = current_user.employee.employee_id
        kpi.approved_at = datetime.utcnow()
        
        db.session.commit()
        flash('KPI approved successfully!', 'success')
        return redirect(url_for('pending_kpi_approvals'))
    
    @app.route('/kpis/<int:kpi_id>/decline', methods=['POST'])
    @login_required
    def decline_kpi(kpi_id):
        """Decline KPI - CEO only"""
        if current_user.role != 'admin' and current_user.employee.role != 'CEO':
            flash('Only CEO can decline KPIs.', 'danger')
            return redirect(url_for('dashboard'))
        
        kpi = KPI.query.get_or_404(kpi_id)
        
        if kpi.status != 'pending_review':
            flash('This KPI is not pending approval.', 'warning')
            return redirect(url_for('pending_kpi_approvals'))
        
        decline_reason = request.form.get('decline_reason', '').strip()
        
        if not decline_reason:
            flash('Please provide a reason for declining the KPI.', 'warning')
            return redirect(url_for('pending_kpi_approvals'))
        
        kpi.status = 'declined'
        kpi.approved_by = current_user.employee.employee_id
        kpi.approved_at = datetime.utcnow()
        kpi.decline_reason = decline_reason
        
        db.session.commit()
        flash(f'KPI "{kpi.kpi_name}" has been declined.', 'info')
        return redirect(url_for('pending_kpi_approvals'))
    
    return app
