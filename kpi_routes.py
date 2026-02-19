"""
KPI Evaluation Routes
Handles all KPI evaluation functionality with hierarchical access control
"""
from flask import render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from models import db, Employee, KPI, Evaluation, EvaluationCycle, RandomizationLog
from datetime import datetime
import json
from kpi_evaluation import (
    can_evaluate_kpi, get_evaluatable_employees, can_view_kpi_results,
    get_kpi_evaluation_status, create_kpi_evaluation_assignment,
    KPI_EVALUATION_HIERARCHY, normalize_evaluator_role
)

def register_kpi_routes(app):
    """Register KPI evaluation routes"""
    
    @app.route('/kpi-evaluations')
    @login_required
    def my_kpi_evaluations():
        """List employees that current user can evaluate"""
        evaluator = current_user.employee
        evaluatable = get_evaluatable_employees(evaluator.employee_id)
        
        if not evaluatable:
            flash('You do not have permission to evaluate KPIs.', 'info')
            return redirect(url_for('dashboard'))
        
        # Get active cycle
        latest_cycle = EvaluationCycle.query.filter_by(status='active').first()
        if not latest_cycle:
            flash('No active evaluation cycle found', 'info')
            return redirect(url_for('dashboard'))
        
        # Get evaluation status for each employee
        evaluations_data = []
        for employee in evaluatable:
            # Check if assignment exists
            assignment = RandomizationLog.query.filter_by(
                cycle_id=latest_cycle.cycle_id,
                evaluator_id=evaluator.employee_id,
                evaluatee_id=employee.employee_id,
                evaluation_type='kpi'
            ).first()
            
            # Create assignment if it doesn't exist
            if not assignment:
                assignment = create_kpi_evaluation_assignment(
                    latest_cycle.cycle_id,
                    evaluator.employee_id,
                    employee.employee_id
                )
                db.session.add(assignment)
                db.session.commit()
            
            # Get existing evaluation
            existing = Evaluation.query.filter_by(
                evaluator_id=evaluator.employee_id,
                evaluatee_id=employee.employee_id,
                cycle_id=latest_cycle.cycle_id
            ).first()
            
            evaluations_data.append({
                'employee': employee,
                'cycle': latest_cycle,
                'evaluation': existing,
                'status': existing.status if existing else 'not_started'
            })
        
        return render_template('kpi_evaluations/list.html', 
                             evaluations=evaluations_data, 
                             cycle=latest_cycle)
    
    @app.route('/kpi-evaluations/<int:cycle_id>/<int:evaluatee_id>', methods=['GET', 'POST'])
    @login_required
    def submit_kpi_evaluation(cycle_id, evaluatee_id):
        """Submit KPI evaluation for an employee"""
        evaluator = current_user.employee
        evaluatee = Employee.query.get_or_404(evaluatee_id)
        
        # Verify evaluator can evaluate this employee
        if not can_evaluate_kpi(evaluator.role, evaluatee.role):
            flash('You do not have permission to evaluate this employee\'s KPIs.', 'danger')
            return redirect(url_for('my_kpi_evaluations'))
        
        # Verify assignment exists
        assignment = RandomizationLog.query.filter_by(
            cycle_id=cycle_id,
            evaluator_id=evaluator.employee_id,
            evaluatee_id=evaluatee_id,
            evaluation_type='kpi'
        ).first()
        
        if not assignment:
            # Create assignment
            assignment = create_kpi_evaluation_assignment(
                cycle_id, evaluator.employee_id, evaluatee_id
            )
            db.session.add(assignment)
            db.session.commit()
        
        # Get KPIs for this employee (employee-based assignment)
        from kpi_creation import get_kpis_for_employee
        kpis = get_kpis_for_employee(evaluatee)
        
        if not kpis:
            flash('No KPIs defined for this role.', 'warning')
            return redirect(url_for('my_kpi_evaluations'))
        
        # Get existing evaluation
        existing_evaluation = Evaluation.query.filter_by(
            evaluator_id=evaluator.employee_id,
            evaluatee_id=evaluatee_id,
            cycle_id=cycle_id
        ).first()
        
        if request.method == 'POST':
            scores = {}
            for kpi in kpis:
                score = request.form.get(f'kpi_{kpi.kpi_id}')
                if score:
                    try:
                        score_float = float(score)
                        if 1 <= score_float <= 5:
                            scores[kpi.kpi_id] = score_float
                    except ValueError:
                        pass
            
            if not scores:
                flash('Please provide at least one KPI score.', 'danger')
                return redirect(request.url)
            
            comments = request.form.get('comments', '')
            status = request.form.get('status', 'draft')  # draft or pending_review
            
            if existing_evaluation:
                existing_evaluation.scores = json.dumps(scores)
                existing_evaluation.comments = comments
                existing_evaluation.status = status
                existing_evaluation.submitted_at = datetime.utcnow()
            else:
                evaluation = Evaluation(
                    evaluator_id=evaluator.employee_id,
                    evaluatee_id=evaluatee_id,
                    cycle_id=cycle_id,
                    scores=json.dumps(scores),
                    comments=comments,
                    status=status
                )
                db.session.add(evaluation)
            
            db.session.commit()
            flash('KPI evaluation saved successfully!', 'success')
            return redirect(url_for('my_kpi_evaluations'))
        
        # Pre-populate form if editing
        existing_scores = {}
        existing_comments = ''
        existing_status = 'draft'
        if existing_evaluation:
            existing_scores = json.loads(existing_evaluation.scores)
            existing_comments = existing_evaluation.comments or ''
            existing_status = existing_evaluation.status
        
        return render_template('kpi_evaluations/form.html',
                             kpis=kpis,
                             evaluatee=evaluatee,
                             cycle=assignment.cycle,
                             existing_scores=existing_scores,
                             existing_comments=existing_comments,
                             existing_status=existing_status)
    
    @app.route('/kpi-results')
    @login_required
    def kpi_results():
        """View KPI results based on role permissions"""
        viewer = current_user.employee
        latest_cycle = EvaluationCycle.query.filter_by(status='active').first()
        
        if not latest_cycle:
            flash('No active evaluation cycle found', 'info')
            return redirect(url_for('dashboard'))
        
        # Determine which employees' results can be viewed
        viewable_employees = []
        
        viewer_role_key = normalize_evaluator_role(viewer.role)
        if can_view_kpi_results(viewer.role):
            if KPI_EVALUATION_HIERARCHY.get(viewer_role_key, {}).get('can_view') == 'all':
                # CEO, Technical Manager, Analysis - view all
                viewable_employees = Employee.query.filter_by(status='active').all()
            elif KPI_EVALUATION_HIERARCHY.get(viewer_role_key, {}).get('can_view') == 'all_departments':
                # Unit Manager - view all departments
                viewable_employees = Employee.query.filter_by(status='active').all()
            else:
                # Department managers - view their department only
                if viewer_role_key in KPI_EVALUATION_HIERARCHY:
                    department = KPI_EVALUATION_HIERARCHY[viewer_role_key]['can_view']
                    viewable_employees = Employee.query.filter_by(
                        status='active',
                        department=department
                    ).all()
                else:
                    viewable_employees = []
        else:
            # Regular employees - view only their own
            viewable_employees = [viewer]
        
        # Get evaluation status for each
        results_data = []
        for employee in viewable_employees:
            status_info = get_kpi_evaluation_status(latest_cycle.cycle_id, employee.employee_id)
            
            # Get detailed evaluation information for review (CEO only)
            evaluation_details = []
            if viewer.role == 'CEO' and status_info.get('evaluations'):
                for eval_obj in status_info['evaluations']:
                    if eval_obj.status == 'pending_review':
                        scores_dict = json.loads(eval_obj.scores) if eval_obj.scores else {}
                        kpi_details = []
                        for kpi_id, score in scores_dict.items():
                            kpi = KPI.query.get(int(kpi_id))
                            if kpi:
                                kpi_details.append({
                                    'kpi': kpi,
                                    'score': float(score)
                                })
                        
                        evaluation_details.append({
                            'evaluation': eval_obj,
                            'evaluator': eval_obj.evaluator,
                            'kpi_details': kpi_details,
                            'comments': eval_obj.comments or '',
                            'submitted_at': eval_obj.submitted_at
                        })
            
            results_data.append({
                'employee': employee,
                'status_info': status_info,
                'evaluation_details': evaluation_details  # For CEO review
            })
        
        return render_template('kpi_evaluations/results.html',
                             results=results_data,
                             cycle=latest_cycle,
                             viewer_role=viewer.role)
    
    @app.route('/kpi-evaluations/pending-approval')
    @login_required
    def pending_kpi_evaluation_approvals():
        """List KPI evaluations pending CEO/Technical Manager approval"""
        viewer = current_user.employee
        if viewer.role not in ['CEO', 'Technical Manager']:
            flash('Only CEO and Technical Manager can approve KPI evaluations.', 'danger')
            return redirect(url_for('dashboard'))
        latest_cycle = EvaluationCycle.query.filter_by(status='active').first()
        if not latest_cycle:
            flash('No active evaluation cycle.', 'info')
            return redirect(url_for('dashboard'))
        pending = Evaluation.query.filter_by(
            cycle_id=latest_cycle.cycle_id,
            status='pending_review'
        ).order_by(Evaluation.submitted_at.desc()).all()
        # Parse scores and compute weighted average for each (by KPI weight)
        pending_data = []
        for eval in pending:
            scores_dict = json.loads(eval.scores) if eval.scores else {}
            total_weight = 0.0
            weighted_sum = 0.0
            for kpi_id, score in (scores_dict or {}).items():
                kpi = KPI.query.get(int(kpi_id))
                w = float(kpi.weight) if kpi and kpi.weight else (100.0 / len(scores_dict) if scores_dict else 1)
                total_weight += w
                weighted_sum += float(score) * w
            avg = round((weighted_sum / total_weight), 2) if total_weight > 0 else 0
            kpi_details = []
            for kpi_id, score in (scores_dict or {}).items():
                kpi = KPI.query.get(int(kpi_id))
                kpi_details.append({'kpi': kpi, 'score': float(score)})
            pending_data.append({
                'evaluation': eval,
                'average_score': avg,
                'scores_dict': scores_dict,
                'kpi_details': kpi_details
            })
        return render_template('kpi_evaluations/pending_evaluation_approvals.html',
                             pending=pending_data,
                             cycle=latest_cycle)
    
    @app.route('/kpi-results/approve/<int:evaluation_id>', methods=['POST'])
    @login_required
    def approve_kpi_evaluation(evaluation_id):
        """Approve a KPI evaluation (CEO/Technical Manager only)"""
        evaluation = Evaluation.query.get_or_404(evaluation_id)
        approver = current_user.employee
        
        # Only CEO and Technical Manager can approve
        if approver.role not in ['CEO', 'Technical Manager']:
            flash('You do not have permission to approve evaluations.', 'danger')
            return redirect(url_for('kpi_results'))
        
        evaluation.status = 'approved'
        evaluation.approved_at = datetime.utcnow()
        evaluation.approved_by = approver.employee_id
        db.session.commit()
        
        flash('KPI evaluation approved successfully! The employee will now see their scores in their portal.', 'success')
        # Redirect to KPI Results so approver can verify the employee shows "Approved"
        referrer = request.referrer or ''
        if 'kpi-results' in referrer:
            return redirect(url_for('kpi_results'))
        return redirect(url_for('pending_kpi_evaluation_approvals'))
    
    return app
