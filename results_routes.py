"""
Results Visibility Routes
Implements role-based results viewing with strict permission checks
"""
from flask import render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from models import db, Employee, EvaluationCycle, FeedbackEvaluation, Evaluation, KPI
from results_visibility import (
    can_view_employee_results, get_viewable_employees, 
    calculate_employee_performance, log_results_access
)
from kpi_evaluation import filter_to_authoritative_evaluations
import json

def register_results_routes(app):
    """Register results visibility routes"""
    
    @app.route('/results/my-results')
    @login_required
    def my_results():
        """View own performance results (all users)"""
        employee_id = current_user.employee.employee_id
        employee = Employee.query.get(employee_id)
        
        latest_cycle = EvaluationCycle.query.filter_by(status='active').first()
        if not latest_cycle:
            flash('No active evaluation cycle found', 'info')
            return redirect(url_for('dashboard'))
        
        performance = calculate_employee_performance(employee_id, latest_cycle.cycle_id)
        
        # Get KPI breakdown (approved/final only; use authoritative evaluator e.g. DP Supervisor for DPs)
        kpi_evaluations = Evaluation.query.filter(
            Evaluation.evaluatee_id == employee_id,
            Evaluation.cycle_id == latest_cycle.cycle_id,
            Evaluation.status.in_(['approved', 'final'])
        ).all()
        kpi_evaluations = filter_to_authoritative_evaluations(kpi_evaluations, employee)
        
        kpi_breakdown = []
        if kpi_evaluations:
            kpi_totals = {}
            kpi_counts = {}
            for eval in kpi_evaluations:
                scores = json.loads(eval.scores)
                for kpi_id, score in scores.items():
                    kpi_id = int(kpi_id)
                    kpi_totals[kpi_id] = kpi_totals.get(kpi_id, 0) + float(score)
                    kpi_counts[kpi_id] = kpi_counts.get(kpi_id, 0) + 1
            for kpi_id in kpi_totals:
                kpi = KPI.query.get(kpi_id)
                if kpi:
                    avg = kpi_totals[kpi_id] / kpi_counts[kpi_id]
                    kpi_breakdown.append({
                        'kpi': kpi,
                        'score': round(avg, 2)
                    })
        
        # Get 360 feedback by category (exclude open-ended questions from scoring)
        feedbacks = FeedbackEvaluation.query.filter_by(
            evaluatee_id=employee_id,
            cycle_id=latest_cycle.cycle_id
        ).all()
        
        feedback_by_category = {}
        # Group by category and evaluator to count submissions (not individual questions)
        category_evaluators = {}  # Track unique evaluators per category
        
        # Separate open-ended responses
        open_ended_responses = []
        
        for feedback in feedbacks:
            if not feedback.question or not getattr(feedback.question, 'is_active', True):
                continue
            # Skip open-ended questions in category averages (they don't have scores)
            if feedback.question.is_open_ended:
                open_ended_responses.append({
                    'question': feedback.question,
                    'response': feedback.comment,
                    # Evaluator is anonymized - no direct reference
                    'evaluator': None,  # Anonymized
                    'submitted_at': feedback.submitted_at
                })
                continue
            
            category = feedback.question.category
            evaluator_hash = feedback.evaluator_hash  # Use anonymized hash
            
            if category not in feedback_by_category:
                feedback_by_category[category] = {'scores': [], 'count': 0}
                category_evaluators[category] = set()
            
            # Only add score if it exists (skip open-ended)
            if feedback.score is not None:
                feedback_by_category[category]['scores'].append(feedback.score)
            
            # Track unique evaluators per category (each evaluator = 1 submission/response)
            if evaluator_hash not in category_evaluators[category]:
                category_evaluators[category].add(evaluator_hash)
                feedback_by_category[category]['count'] += 1
        
        # Calculate category averages (only for scored questions)
        for category in feedback_by_category:
            scores = feedback_by_category[category]['scores']
            feedback_by_category[category]['average'] = sum(scores) / len(scores) if scores else 0
            # Count is already set correctly above (unique evaluators per category)
        
        # Group open-ended responses by question
        open_ended_by_question = {}
        for response in open_ended_responses:
            question_text = response['question'].question_text
            if question_text not in open_ended_by_question:
                open_ended_by_question[question_text] = []
            open_ended_by_question[question_text].append({
                'response': response['response'],
                'evaluator': response['evaluator'],
                'submitted_at': response['submitted_at']
            })
        
        log_results_access(employee_id, employee_id, 'my_results')
        
        return render_template('results/my_results.html',
                             employee=employee,
                             cycle=latest_cycle,
                             performance=performance,
                             kpi_breakdown=kpi_breakdown,
                             feedback_by_category=feedback_by_category,
                             open_ended_by_question=open_ended_by_question)
    
    @app.route('/results/team')
    @login_required
    def team_results():
        """View team performance results (managers only)"""
        viewer = current_user.employee
        viewer_role = viewer.role  # Use actual employee role from database
        
        # Check if user has permission to view team results
        allowed_roles = ['CEO', 'Technical Manager', 'Unit Manager', 'DP Supervisor', 
                        'Operations Manager', 'PM Manager', 'CFO']
        
        if viewer_role not in allowed_roles:
            flash('You do not have permission to view team results.', 'danger')
            return redirect(url_for('my_results'))
        
        latest_cycle = EvaluationCycle.query.filter_by(status='active').first()
        if not latest_cycle:
            flash('No active evaluation cycle found', 'info')
            return redirect(url_for('dashboard'))
        
        # Get viewable employees
        viewable = get_viewable_employees(viewer.employee_id)
        
        # Calculate performance for each
        team_results = []
        for employee in viewable:
            # Skip self for managers (they can see own in "My Results")
            if employee.employee_id == viewer.employee_id:
                continue
            
            performance = calculate_employee_performance(employee.employee_id, latest_cycle.cycle_id)
            
            # Get KPI breakdown for this employee (approved/final; authoritative evaluator only)
            kpi_evaluations = Evaluation.query.filter(
                Evaluation.evaluatee_id == employee.employee_id,
                Evaluation.cycle_id == latest_cycle.cycle_id,
                Evaluation.status.in_(['approved', 'final'])
            ).all()
            kpi_evaluations = filter_to_authoritative_evaluations(kpi_evaluations, employee)
            
            kpi_breakdown = {}
            kpi_totals = {}
            kpi_counts = {}
            
            for eval in kpi_evaluations:
                scores = json.loads(eval.scores)
                for kpi_id, score in scores.items():
                    kpi_id = int(kpi_id)
                    if kpi_id not in kpi_totals:
                        kpi_totals[kpi_id] = 0
                        kpi_counts[kpi_id] = 0
                    kpi_totals[kpi_id] += float(score)
                    kpi_counts[kpi_id] += 1
            
            # Calculate averages for each KPI
            for kpi_id in kpi_totals:
                kpi = KPI.query.get(kpi_id)
                if kpi:
                    avg_score = kpi_totals[kpi_id] / kpi_counts[kpi_id] if kpi_counts[kpi_id] > 0 else 0
                    kpi_breakdown[kpi.kpi_name] = {
                        'average': round(avg_score, 2),
                        'count': kpi_counts[kpi_id],
                        'weight': kpi.weight
                    }
            
            team_results.append({
                'employee': employee,
                'performance': performance,
                'kpi_breakdown': kpi_breakdown
            })
        
        # Sort by final score (descending)
        team_results.sort(key=lambda x: x['performance']['final_score'], reverse=True)
        
        log_results_access(viewer.employee_id, None, 'team_results')
        
        return render_template('results/team_results.html',
                             team_results=team_results,
                             cycle=latest_cycle,
                             viewer_role=viewer_role)
    
    @app.route('/results/organization')
    @login_required
    def organization_results():
        """View organization-wide results (CEO and Technical Manager only)"""
        viewer = current_user.employee
        viewer_role = viewer.role  # Use actual employee role from database
        
        # Only CEO and Technical Manager can access
        if viewer_role not in ['CEO', 'Technical Manager']:
            flash('You do not have permission to view organization-wide results.', 'danger')
            return redirect(url_for('team_results'))
        
        latest_cycle = EvaluationCycle.query.filter_by(status='active').first()
        if not latest_cycle:
            flash('No active evaluation cycle found', 'info')
            return redirect(url_for('dashboard'))
        
        # Get all employees
        all_employees = Employee.query.filter_by(status='active').all()
        
        # Calculate performance for each
        org_results = []
        departments = set()
        
        for employee in all_employees:
            performance = calculate_employee_performance(employee.employee_id, latest_cycle.cycle_id)
            
            # Get KPI breakdown for this employee (approved/final only, to match unified KPI score logic)
            kpi_evaluations = Evaluation.query.filter(
                Evaluation.evaluatee_id == employee.employee_id,
                Evaluation.cycle_id == latest_cycle.cycle_id,
                Evaluation.status.in_(['approved', 'final'])
            ).all()
            
            kpi_breakdown = {}
            kpi_totals = {}
            kpi_counts = {}
            
            for eval in kpi_evaluations:
                scores = json.loads(eval.scores)
                for kpi_id, score in scores.items():
                    kpi_id = int(kpi_id)
                    if kpi_id not in kpi_totals:
                        kpi_totals[kpi_id] = 0
                        kpi_counts[kpi_id] = 0
                    kpi_totals[kpi_id] += float(score)
                    kpi_counts[kpi_id] += 1
            
            # Calculate averages for each KPI
            for kpi_id in kpi_totals:
                kpi = KPI.query.get(kpi_id)
                if kpi:
                    avg_score = kpi_totals[kpi_id] / kpi_counts[kpi_id] if kpi_counts[kpi_id] > 0 else 0
                    kpi_breakdown[kpi.kpi_name] = {
                        'average': round(avg_score, 2),
                        'count': kpi_counts[kpi_id],
                        'weight': kpi.weight
                    }
            
            org_results.append({
                'employee': employee,
                'performance': performance,
                'kpi_breakdown': kpi_breakdown
            })
            departments.add(employee.department)
        
        # Sort by final score (descending)
        org_results.sort(key=lambda x: x['performance']['final_score'], reverse=True)
        
        # Get filter parameter
        filter_dept = request.args.get('department', 'all')
        if filter_dept != 'all':
            org_results = [r for r in org_results if r['employee'].department == filter_dept]
        
        # Get sort parameter
        sort_by = request.args.get('sort', 'final_score')
        if sort_by == 'name':
            org_results.sort(key=lambda x: x['employee'].full_name)
        elif sort_by == 'department':
            org_results.sort(key=lambda x: x['employee'].department)
        elif sort_by == 'kpi_score':
            org_results.sort(key=lambda x: x['performance']['kpi_score'], reverse=True)
        elif sort_by == 'feedback_score':
            org_results.sort(key=lambda x: x['performance']['feedback_score'], reverse=True)
        else:  # final_score
            org_results.sort(key=lambda x: x['performance']['final_score'], reverse=True)
        
        log_results_access(viewer.employee_id, None, 'organization_results')
        
        return render_template('results/organization_results.html',
                             org_results=org_results,
                             cycle=latest_cycle,
                             departments=sorted(departments),
                             current_filter=filter_dept,
                             current_sort=sort_by)
    
    @app.route('/results/employee/<int:employee_id>')
    @login_required
    def view_employee_results(employee_id):
        """View specific employee's results (with permission check)"""
        viewer_id = current_user.employee.employee_id
        
        # Check permission
        if not can_view_employee_results(viewer_id, employee_id):
            flash('You do not have permission to view this employee\'s results.', 'danger')
            return redirect(url_for('my_results'))
        
        employee = Employee.query.get_or_404(employee_id)
        latest_cycle = EvaluationCycle.query.filter_by(status='active').first()
        
        if not latest_cycle:
            flash('No active evaluation cycle found', 'info')
            return redirect(url_for('dashboard'))
        
        performance = calculate_employee_performance(employee_id, latest_cycle.cycle_id)
        
        # Get KPI breakdown (approved/final; authoritative evaluator only e.g. DP Supervisor for DPs)
        kpi_evaluations = Evaluation.query.filter(
            Evaluation.evaluatee_id == employee_id,
            Evaluation.cycle_id == latest_cycle.cycle_id,
            Evaluation.status.in_(['approved', 'final'])
        ).all()
        kpi_evaluations = filter_to_authoritative_evaluations(kpi_evaluations, employee)
        
        kpi_breakdown = {}
        kpi_totals = {}
        kpi_counts = {}
        kpi_comments = []
        
        for eval in kpi_evaluations:
            scores = json.loads(eval.scores)
            for kpi_id, score in scores.items():
                kpi_id = int(kpi_id)
                if kpi_id not in kpi_totals:
                    kpi_totals[kpi_id] = 0
                    kpi_counts[kpi_id] = 0
                kpi_totals[kpi_id] += float(score)
                kpi_counts[kpi_id] += 1
            
            # Collect comments/justifications from evaluations
            if eval.comments:
                kpi_comments.append({
                    'evaluator': eval.evaluator,
                    'comments': eval.comments,
                    'status': eval.status,
                    'submitted_at': eval.submitted_at
                })
        
        # Calculate averages for each KPI
        for kpi_id in kpi_totals:
            kpi = KPI.query.get(kpi_id)
            if kpi:
                avg_score = kpi_totals[kpi_id] / kpi_counts[kpi_id] if kpi_counts[kpi_id] > 0 else 0
                kpi_breakdown[kpi.kpi_name] = {
                    'average': round(avg_score, 2),
                    'count': kpi_counts[kpi_id],
                    'weight': kpi.weight
                }
        
        # Get 360 feedback by category (exclude open-ended questions from scoring)
        feedbacks = FeedbackEvaluation.query.filter_by(
            evaluatee_id=employee_id,
            cycle_id=latest_cycle.cycle_id
        ).all()
        
        feedback_by_category = {}
        # Group by category and evaluator to count submissions (not individual questions)
        category_evaluators = {}  # Track unique evaluators per category
        
        # Separate open-ended responses
        open_ended_responses = []
        
        for feedback in feedbacks:
            if not feedback.question or not getattr(feedback.question, 'is_active', True):
                continue
            # Skip open-ended questions in category averages (they don't have scores)
            if feedback.question.is_open_ended:
                open_ended_responses.append({
                    'question': feedback.question,
                    'response': feedback.comment,
                    # Evaluator is anonymized - no direct reference
                    'evaluator': None,  # Anonymized
                    'submitted_at': feedback.submitted_at
                })
                continue
            
            category = feedback.question.category
            evaluator_hash = feedback.evaluator_hash  # Use anonymized hash
            
            if category not in feedback_by_category:
                feedback_by_category[category] = {'scores': [], 'count': 0}
                category_evaluators[category] = set()
            
            # Only add score if it exists (skip open-ended)
            if feedback.score is not None:
                feedback_by_category[category]['scores'].append(feedback.score)
            
            # Track unique evaluators per category (each evaluator = 1 submission/response)
            if evaluator_hash not in category_evaluators[category]:
                category_evaluators[category].add(evaluator_hash)
                feedback_by_category[category]['count'] += 1
        
        # Calculate category averages (only for scored questions)
        for category in feedback_by_category:
            scores = feedback_by_category[category]['scores']
            feedback_by_category[category]['average'] = sum(scores) / len(scores) if scores else 0
            # Count is already set correctly above (unique evaluators per category)
        
        # Group open-ended responses by question
        open_ended_by_question = {}
        for response in open_ended_responses:
            question_text = response['question'].question_text
            if question_text not in open_ended_by_question:
                open_ended_by_question[question_text] = []
            open_ended_by_question[question_text].append({
                'response': response['response'],
                'evaluator': response['evaluator'],
                'submitted_at': response['submitted_at']
            })
        
        log_results_access(viewer_id, employee_id, 'employee_detail')
        
        return render_template('results/employee_detail.html',
                             employee=employee,
                             cycle=latest_cycle,
                             performance=performance,
                             kpi_breakdown=kpi_breakdown,
                             kpi_comments=kpi_comments,
                             feedback_by_category=feedback_by_category,
                             open_ended_by_question=open_ended_by_question)
    
    return app
