"""
Additional routes for 360-degree feedback system
This file contains routes that need to be added to app.py
"""
from flask import render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from models import db, Employee, EvaluationCycle, FeedbackQuestion, FeedbackEvaluation, RandomizationLog, KPI, Evaluation, EvaluatorScore, DeletedFeedbackCategory, EvaluationRelationship
from forms import FeedbackQuestionForm, FEEDBACK_QUESTION_CATEGORIES, NEW_CATEGORY_VALUE
from datetime import datetime
from anonymization import hash_evaluator_id, hash_evaluator_metadata
import json

def _ceo_or_admin():
    """Return True if current user is CEO or admin."""
    if not current_user.is_authenticated or not current_user.employee:
        return False
    return (current_user.employee.role == 'CEO') or (current_user.role == 'admin')


def _get_360_relationship(evaluator_employee, evaluatee_employee):
    """
    Look up evaluation matrix: 1 = direct, 0 = indirect, x/z = none/self.
    Matrix uses Employee.full_name as role labels. Returns '1', '0', or None (treat as global-only).
    """
    if not evaluator_employee or not evaluatee_employee:
        return None
    rec = EvaluationRelationship.query.filter_by(
        evaluator_role=evaluator_employee.full_name,
        evaluatee_role=evaluatee_employee.full_name
    ).first()
    if not rec or rec.relationship in ('x', 'z'):
        return None
    return rec.relationship


def get_questions_for_360(evaluator_employee, evaluatee_employee):
    """
    Return active 360 questions for this evaluator–evaluatee pair.
    - relationship '1' (direct): global + direct questions.
    - relationship '0' or missing: global questions only.
    """
    rel = _get_360_relationship(evaluator_employee, evaluatee_employee)
    is_direct = (rel == '1')
    base = FeedbackQuestion.query.filter_by(is_active=True).all()
    out = []
    for q in base:
        if not getattr(q, 'question_scope', 'global') or q.question_scope == 'global':
            out.append(q)
        elif q.question_scope == 'direct' and is_direct:
            out.append(q)
    # Open-ended questions always last (last two in My 360-Degree Feedback Evaluations)
    out.sort(key=lambda q: (1 if getattr(q, 'is_open_ended', False) else 0))
    return out


def _get_category_choices(current_category=None):
    """
    Build category dropdown choices: standard + distinct from DB, excluding deleted categories, plus "Add new category".
    """
    deleted_names = {row[0] for row in db.session.query(DeletedFeedbackCategory.name).all()}
    standard_values = {c[0] for c in FEEDBACK_QUESTION_CATEGORIES}
    # Exclude deleted from standard and from DB
    standard_choices = [(v, l) for v, l in FEEDBACK_QUESTION_CATEGORIES if v not in deleted_names]
    distinct_cats = [row[0] for row in db.session.query(FeedbackQuestion.category).distinct().all() if row[0]]
    extra = [c for c in distinct_cats if c not in standard_values and c not in deleted_names]
    choices = standard_choices + [(c, c) for c in extra] + [(NEW_CATEGORY_VALUE, '— Add new category —')]
    return choices

def calculate_and_store_evaluator_score(evaluator_hash, evaluatee_id, cycle_id):
    """
    Calculate and store the final score for an evaluator-evaluatee pair.
    This is the average of all scored questions (excluding open-ended).
    """
    # Get all submitted feedback evaluations for this evaluator-evaluatee pair
    feedback_evaluations = FeedbackEvaluation.query.filter_by(
        evaluator_hash=evaluator_hash,
        evaluatee_id=evaluatee_id,
        cycle_id=cycle_id,
        status='submitted'
    ).all()
    
    # Get only scored questions (exclude open-ended and inactive/missing questions)
    scores = [f.score for f in feedback_evaluations 
              if f.score is not None 
              and f.question 
              and not getattr(f.question, 'is_open_ended', True) 
              and getattr(f.question, 'is_active', True)]
    
    if not scores:
        # No scores available, don't create a record
        return
    
    # Calculate average score
    final_score = sum(scores) / len(scores)
    
    # Check if score already exists
    existing = EvaluatorScore.query.filter_by(
        evaluator_hash=evaluator_hash,
        evaluatee_id=evaluatee_id,
        cycle_id=cycle_id
    ).first()
    
    if existing:
        # Update existing score
        existing.final_score = final_score
        existing.question_count = len(scores)
        existing.calculated_at = datetime.utcnow()
    else:
        # Create new score
        evaluator_score = EvaluatorScore(
            evaluator_hash=evaluator_hash,
            evaluatee_id=evaluatee_id,
            cycle_id=cycle_id,
            final_score=final_score,
            question_count=len(scores),
            calculated_at=datetime.utcnow()
        )
        db.session.add(evaluator_score)
    
    db.session.commit()

def register_360_routes(app):
    """Register 360-degree feedback routes"""
    
    @app.route('/evaluations/360')
    @login_required
    def my_360_evaluations():
        """List all 360 evaluations assigned to current user (original behavior without scope filtering)."""
        employee_id = current_user.employee.employee_id
        
        # Get all active cycles and find assignments using hashed evaluator ID
        active_cycles = EvaluationCycle.query.filter_by(status='active').all()
        assignments = []
        for cycle in active_cycles:
            evaluator_hash = hash_evaluator_id(employee_id, cycle.cycle_id)
            cycle_assignments = RandomizationLog.query.filter_by(
                evaluator_hash=evaluator_hash,
                evaluation_type='360',
                cycle_id=cycle.cycle_id
            ).all()
            assignments.extend(cycle_assignments)
        
        evaluations_data = []
        for assignment in assignments:
            cycle = assignment.cycle
            evaluator_hash = hash_evaluator_id(employee_id, assignment.cycle_id)
            evaluatee = assignment.evaluatee
            evaluator_emp = current_user.employee
            questions = get_questions_for_360(evaluator_emp, evaluatee)
            total_questions = len(questions)
            
            # Count submitted questions (not draft)
            submitted_count = FeedbackEvaluation.query.filter_by(
                evaluator_hash=evaluator_hash,
                evaluatee_id=assignment.evaluatee_id,
                cycle_id=assignment.cycle_id,
                status='submitted'
            ).count()
            
            # Count draft questions
            draft_count = FeedbackEvaluation.query.filter_by(
                evaluator_hash=evaluator_hash,
                evaluatee_id=assignment.evaluatee_id,
                cycle_id=assignment.cycle_id,
                status='draft'
            ).count()
            
            # Determine overall status
            if submitted_count == total_questions and total_questions > 0:
                status = 'submitted'
            elif draft_count > 0 or submitted_count > 0:
                status = 'draft'
            else:
                status = 'not_started'
            
            evaluations_data.append({
                'assignment': assignment,
                'cycle': cycle,
                'evaluatee': assignment.evaluatee,
                'completed': submitted_count == total_questions and total_questions > 0,
                'submitted_count': submitted_count,
                'draft_count': draft_count,
                'total_questions': total_questions,
                'status': status
            })
        
        latest_cycle = EvaluationCycle.query.filter_by(status='active').first()
        return render_template('evaluations/360_list.html', evaluations=evaluations_data, latest_cycle=latest_cycle)
    
    @app.route('/evaluations/360/<int:cycle_id>/<int:evaluatee_id>', methods=['GET', 'POST'])
    @login_required
    def submit_360_evaluation(cycle_id, evaluatee_id):
        """Submit 360-degree feedback evaluation"""
        # Verify assignment using hashed evaluator ID
        evaluator_hash = hash_evaluator_id(current_user.employee.employee_id, cycle_id)
        assignment = RandomizationLog.query.filter_by(
            cycle_id=cycle_id,
            evaluator_hash=evaluator_hash,
            evaluatee_id=evaluatee_id,
            evaluation_type='360'
        ).first_or_404()
        
        evaluatee = Employee.query.get(evaluatee_id)
        evaluator_emp = current_user.employee
        questions = get_questions_for_360(evaluator_emp, evaluatee)
        
        if request.method == 'POST':
            # Get action (draft or submit)
            action = request.form.get('action', 'draft')  # 'draft' or 'submit'
            
            # Use hashed evaluator ID for anonymity
            evaluator_hash = hash_evaluator_id(current_user.employee.employee_id, cycle_id)
            evaluator = current_user.employee
            is_manager = evaluator.employee_id == evaluatee.manager_id if evaluatee else False
            
            # Get existing evaluations for this assignment
            existing = FeedbackEvaluation.query.filter_by(
                evaluator_hash=evaluator_hash,
                evaluatee_id=evaluatee_id,
                cycle_id=cycle_id
            ).all()
            existing_dict = {e.question_id: e for e in existing}
            
            # Determine status and submitted_at
            if action == 'submit':
                status = 'submitted'
                submitted_at = datetime.utcnow()
            else:
                status = 'draft'
                submitted_at = None
            
            # Process submitted scores and open-ended responses
            for question in questions:
                if question.is_open_ended:
                    # Open-ended question: use comment field, no score
                    response_text = request.form.get(f'open_ended_{question.question_id}', '').strip()
                    if response_text:
                        if question.question_id in existing_dict:
                            # Update existing
                            existing_dict[question.question_id].comment = response_text
                            existing_dict[question.question_id].score = None
                            existing_dict[question.question_id].status = status
                            if action == 'submit':
                                existing_dict[question.question_id].submitted_at = submitted_at
                        else:
                            # Create new with anonymized evaluator ID
                            feedback = FeedbackEvaluation(
                                evaluator_hash=evaluator_hash,
                                evaluatee_id=evaluatee_id,
                                cycle_id=cycle_id,
                                question_id=question.question_id,
                                score=None,  # No score for open-ended questions
                                comment=response_text,
                                status=status,
                                submitted_at=submitted_at,
                                evaluator_department_hash=hash_evaluator_metadata(evaluator.employee_id, cycle_id, 'department', evaluator.department),
                                evaluator_role_hash=hash_evaluator_metadata(evaluator.employee_id, cycle_id, 'role', evaluator.role),
                                is_manager_hash=hash_evaluator_metadata(evaluator.employee_id, cycle_id, 'is_manager', str(is_manager))
                            )
                            db.session.add(feedback)
                else:
                    # Regular question: score required, optional comment
                    score = request.form.get(f'question_{question.question_id}')
                    comment = request.form.get(f'comment_{question.question_id}', '')
                    
                    if score:
                        try:
                            score_float = float(score)
                            if 1 <= score_float <= 5:
                                if question.question_id in existing_dict:
                                    # Update existing
                                    existing_dict[question.question_id].score = score_float
                                    existing_dict[question.question_id].comment = comment
                                    existing_dict[question.question_id].status = status
                                    if action == 'submit':
                                        existing_dict[question.question_id].submitted_at = submitted_at
                                else:
                                    # Create new with anonymized evaluator ID
                                    feedback = FeedbackEvaluation(
                                        evaluator_hash=evaluator_hash,
                                        evaluatee_id=evaluatee_id,
                                        cycle_id=cycle_id,
                                        question_id=question.question_id,
                                        score=score_float,
                                        comment=comment,
                                        status=status,
                                        submitted_at=submitted_at,
                                        evaluator_department_hash=hash_evaluator_metadata(evaluator.employee_id, cycle_id, 'department', evaluator.department),
                                        evaluator_role_hash=hash_evaluator_metadata(evaluator.employee_id, cycle_id, 'role', evaluator.role),
                                        is_manager_hash=hash_evaluator_metadata(evaluator.employee_id, cycle_id, 'is_manager', str(is_manager))
                                    )
                                    db.session.add(feedback)
                        except ValueError:
                            pass
            
            db.session.commit()
            
            # Calculate and store evaluator score if submitted
            if action == 'submit':
                calculate_and_store_evaluator_score(evaluator_hash, evaluatee_id, cycle_id)
                flash('360 feedback submitted successfully!', 'success')
            else:
                flash('360 feedback saved as draft. You can continue editing later.', 'info')
            return redirect(url_for('my_360_evaluations'))
        
        # Get existing scores for pre-population (using hashed evaluator ID)
        evaluator_hash = hash_evaluator_id(current_user.employee.employee_id, cycle_id)
        existing_scores = {}
        existing = FeedbackEvaluation.query.filter_by(
            evaluator_hash=evaluator_hash,
            evaluatee_id=evaluatee_id,
            cycle_id=cycle_id
        ).all()
        
        # Original "fully submitted" logic: all records for this assignment are submitted
        is_fully_submitted = all(e.status == 'submitted' for e in existing) and len(existing) > 0
        
        for e in existing:
            if not e.question:
                continue
            existing_scores[e.question_id] = {
                'score': e.score,
                'comment': e.comment,
                'response': e.comment if e.question.is_open_ended else e.comment
            }
        
        return render_template('evaluations/360_form.html',
                             questions=questions,
                             evaluatee=evaluatee,
                             cycle=assignment.cycle,
                             existing_scores=existing_scores,
                             is_fully_submitted=is_fully_submitted)

    # ---------- CEO-only: Manage 360 feedback questions ----------
    @app.route('/360-questions')
    @login_required
    def list_360_questions():
        """List all 360 feedback questions (CEO only)."""
        if not _ceo_or_admin():
            flash('You do not have permission to manage 360 questions.', 'danger')
            return redirect(url_for('dashboard'))
        questions = FeedbackQuestion.query.order_by(FeedbackQuestion.category, FeedbackQuestion.question_id).all()
        return render_template('360_questions/list.html', questions=questions)

    @app.route('/360-questions/add', methods=['GET', 'POST'])
    @login_required
    def add_360_question():
        """Add a new 360 feedback question (CEO only)."""
        if not _ceo_or_admin():
            flash('You do not have permission to manage 360 questions.', 'danger')
            return redirect(url_for('dashboard'))
        form = FeedbackQuestionForm()
        form.category.choices = _get_category_choices()
        if form.validate_on_submit():
            category_to_save = (form.new_category.data.strip() if form.category.data == NEW_CATEGORY_VALUE
                                else form.category.data)
            q = FeedbackQuestion(
                category=category_to_save,
                question_text=form.question_text.data.strip(),
                question_scope=(form.question_scope.data or 'global'),
                is_for_managers=form.is_for_managers.data,
                is_open_ended=form.is_open_ended.data,
                is_active=form.is_active.data,
            )
            db.session.add(q)
            db.session.commit()
            flash('360 feedback question added.', 'success')
            return redirect(url_for('list_360_questions'))
        return render_template('360_questions/add.html', form=form, new_category_value=NEW_CATEGORY_VALUE)

    @app.route('/360-questions/<int:question_id>/edit', methods=['GET', 'POST'])
    @login_required
    def edit_360_question(question_id):
        """Edit a 360 feedback question (CEO only)."""
        if not _ceo_or_admin():
            flash('You do not have permission to manage 360 questions.', 'danger')
            return redirect(url_for('dashboard'))
        question = FeedbackQuestion.query.get_or_404(question_id)
        form = FeedbackQuestionForm(obj=question)
        form.category.choices = _get_category_choices(current_category=question.category)
        if form.validate_on_submit():
            category_to_save = (form.new_category.data.strip() if form.category.data == NEW_CATEGORY_VALUE
                                else form.category.data)
            question.category = category_to_save
            question.question_text = form.question_text.data.strip()
            question.question_scope = form.question_scope.data or 'global'
            question.is_for_managers = form.is_for_managers.data
            question.is_open_ended = form.is_open_ended.data
            question.is_active = form.is_active.data
            db.session.commit()
            flash('360 feedback question updated.', 'success')
            return redirect(url_for('list_360_questions'))
        return render_template('360_questions/edit.html', form=form, question=question, new_category_value=NEW_CATEGORY_VALUE)

    @app.route('/360-questions/<int:question_id>/delete', methods=['POST'])
    @login_required
    def delete_360_question(question_id):
        """Permanently delete a 360 feedback question and all its evaluations (CEO only)."""
        if not _ceo_or_admin():
            flash('You do not have permission to manage 360 questions.', 'danger')
            return redirect(url_for('dashboard'))
        question = FeedbackQuestion.query.get_or_404(question_id)
        # Delete all feedback evaluations that reference this question
        FeedbackEvaluation.query.filter_by(question_id=question_id).delete(synchronize_session=False)
        db.session.delete(question)
        db.session.commit()
        flash('360 feedback question and all its evaluations have been permanently deleted.', 'success')
        return redirect(url_for('list_360_questions'))

    @app.route('/360-questions/categories')
    @login_required
    def list_360_categories():
        """List all 360 feedback categories; CEO can delete a category and all its questions."""
        if not _ceo_or_admin():
            flash('You do not have permission to manage categories.', 'danger')
            return redirect(url_for('dashboard'))
        # Only show categories that actually have questions in the DB (so deleted categories disappear)
        distinct_from_db = [row[0] for row in db.session.query(FeedbackQuestion.category).distinct().all() if row[0]]
        all_names = sorted(set(distinct_from_db))
        categories = []
        for name in all_names:
            count = FeedbackQuestion.query.filter_by(category=name).count()
            categories.append({
                'name': name,
                'question_count': count,
            })
        return render_template('360_questions/categories.html', categories=categories)

    @app.route('/360-questions/categories/delete', methods=['POST'])
    @login_required
    def delete_360_category():
        """Permanently delete a category and all questions (and their evaluations) in it (CEO only)."""
        if not _ceo_or_admin():
            flash('You do not have permission to manage categories.', 'danger')
            return redirect(url_for('dashboard'))
        name = (request.form.get('category_name') or '').strip()
        if not name:
            flash('Category name is required.', 'danger')
            return redirect(url_for('list_360_categories'))
        questions = FeedbackQuestion.query.filter_by(category=name).all()
        question_ids = [q.question_id for q in questions]
        if question_ids:
            # Delete all feedback evaluations that reference these questions
            FeedbackEvaluation.query.filter(FeedbackEvaluation.question_id.in_(question_ids)).delete(synchronize_session=False)
            # Delete all questions in this category
            FeedbackQuestion.query.filter_by(category=name).delete()
            # Record category as deleted so it is removed from the dropdown
            if not DeletedFeedbackCategory.query.filter_by(name=name).first():
                db.session.add(DeletedFeedbackCategory(name=name))
            db.session.commit()
            flash(f'Category "{name}" and all its questions and evaluations have been permanently deleted. It is also removed from the dropdown.', 'success')
        else:
            # No questions; still record as deleted so it disappears from dropdown if it was there (e.g. standard)
            if not DeletedFeedbackCategory.query.filter_by(name=name).first():
                db.session.add(DeletedFeedbackCategory(name=name))
                db.session.commit()
            flash(f'Category "{name}" has been removed from the dropdown.', 'info')
        return redirect(url_for('list_360_categories'))
    
    return app

def calculate_employee_kpi_score(employee_id, cycle_id):
    """Calculate KPI score using unified logic (approved evals, weighted by KPI weight)."""
    from results_visibility import calculate_kpi_score
    score, _ = calculate_kpi_score(employee_id, cycle_id, approved_only=True)
    return score

def calculate_employee_360_score(employee_id, cycle_id):
    """
    Calculate trimmed mean 360 feedback score for an employee.
    Uses trimmed mean to reduce impact of extreme or malicious evaluations.
    """
    from results_visibility import calculate_trimmed_mean_360_score
    
    feedbacks = FeedbackEvaluation.query.filter_by(
        evaluatee_id=employee_id,
        cycle_id=cycle_id
    ).all()
    
    # Calculate trimmed mean (reduces impact of extreme scores)
    trimmed_mean, raw_mean, evaluator_count, trimmed_count = calculate_trimmed_mean_360_score(feedbacks)
    return trimmed_mean

def get_feedback_details(employee_id, cycle_id):
    """Get detailed 360 feedback by category"""
    feedbacks = FeedbackEvaluation.query.filter_by(
        evaluatee_id=employee_id,
        cycle_id=cycle_id
    ).all()
    
    categories = {}
    for feedback in feedbacks:
        if not feedback.question or not getattr(feedback.question, 'is_active', True):
            continue
        category = feedback.question.category
        if category not in categories:
            categories[category] = {'scores': [], 'comments': []}
        if feedback.score is not None and not getattr(feedback.question, 'is_open_ended', True):
            categories[category]['scores'].append(feedback.score)
        if feedback.comment:
            categories[category]['comments'].append(feedback.comment)
    
    # Calculate averages
    for category in categories:
        scores = categories[category]['scores']
        categories[category]['average'] = sum(scores) / len(scores) if scores else 0
        categories[category]['count'] = len(scores)
    
    return categories
