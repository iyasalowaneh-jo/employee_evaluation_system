from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
import json

db = SQLAlchemy()

class User(UserMixin, db.Model):
    """User model for authentication"""
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    employee_id = db.Column(db.Integer, db.ForeignKey('employees.employee_id'), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), nullable=False, default='employee')  # admin, manager, employee
    
    # Relationship
    employee = db.relationship('Employee', backref='user', uselist=False)
    
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

class Employee(db.Model):
    """Employee model"""
    __tablename__ = 'employees'
    
    employee_id = db.Column(db.Integer, primary_key=True)
    full_name = db.Column(db.String(200), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    department = db.Column(db.String(100), nullable=False)
    role = db.Column(db.String(100), nullable=False)
    join_date = db.Column(db.Date, nullable=False)
    manager_id = db.Column(db.Integer, db.ForeignKey('employees.employee_id'), nullable=True)
    status = db.Column(db.String(20), default='active')  # active, inactive
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    manager = db.relationship('Employee', remote_side=[employee_id], backref='subordinates')

# KPI Creation Permissions: who (manager role) can create KPIs for whom (target role)
# Admin-editable; overrides default hierarchy when present
class KPICreationRule(db.Model):
    __tablename__ = 'kpi_creation_rules'
    id = db.Column(db.Integer, primary_key=True)
    manager_role = db.Column(db.String(100), nullable=False)
    target_role = db.Column(db.String(100), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    __table_args__ = (db.UniqueConstraint('manager_role', 'target_role', name='uq_manager_target'),)


# Association table for KPI <-> Employee (many-to-many, when applies_to_all=False)
employee_kpis = db.Table(
    'employee_kpis',
    db.Column('kpi_id', db.Integer, db.ForeignKey('kpis.kpi_id', ondelete='CASCADE'), primary_key=True),
    db.Column('employee_id', db.Integer, db.ForeignKey('employees.employee_id', ondelete='CASCADE'), primary_key=True)
)


class KPI(db.Model):
    """KPI model"""
    __tablename__ = 'kpis'
    
    kpi_id = db.Column(db.Integer, primary_key=True)
    kpi_name = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=True)
    department = db.Column(db.String(100), nullable=True)  # None means global
    role = db.Column(db.String(100), nullable=True)  # None means all roles
    weight = db.Column(db.Float, default=1.0, nullable=False)  # Weight factor (0-100)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    is_default = db.Column(db.Boolean, default=False)  # True for system/default KPIs that can be edited/deleted
    
    # Approval workflow fields
    created_by = db.Column(db.Integer, db.ForeignKey('employees.employee_id'), nullable=True)
    status = db.Column(db.String(20), default='draft')  # draft, pending_review, approved, declined
    approved_by = db.Column(db.Integer, db.ForeignKey('employees.employee_id'), nullable=True)
    approved_at = db.Column(db.DateTime, nullable=True)
    decline_reason = db.Column(db.Text, nullable=True)  # Reason if declined
    
    # Employee-based assignment: applies_to_all=True means all employees; else use employee_kpis
    applies_to_all = db.Column(db.Boolean, default=False, nullable=False)
    
    # Relationships
    creator = db.relationship('Employee', foreign_keys=[created_by], backref='kpis_created')
    approver = db.relationship('Employee', foreign_keys=[approved_by])
    assigned_employees = db.relationship(
        'Employee',
        secondary=employee_kpis,
        backref=db.backref('assigned_kpis', lazy='dynamic'),
        lazy='dynamic'
    )


class EvaluationCycle(db.Model):
    """Evaluation cycle model"""
    __tablename__ = 'evaluation_cycles'
    
    cycle_id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    start_date = db.Column(db.Date, nullable=False)
    end_date = db.Column(db.Date, nullable=False)
    description = db.Column(db.Text, nullable=True)
    status = db.Column(db.String(20), default='draft')  # draft, active, completed
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    include_kpi = db.Column(db.Boolean, default=True, nullable=False)   # This round includes KPI evaluations
    include_360 = db.Column(db.Boolean, default=True, nullable=False)   # This round includes 360 feedback
    
    # Relationship
    evaluations = db.relationship('Evaluation', backref='cycle', lazy=True)
    assignments = db.relationship('RandomizationLog', backref='cycle', lazy=True)

class Evaluation(db.Model):
    """Evaluation submission model (KPI evaluations)"""
    __tablename__ = 'evaluations'
    
    evaluation_id = db.Column(db.Integer, primary_key=True)
    evaluator_id = db.Column(db.Integer, db.ForeignKey('employees.employee_id'), nullable=False)
    evaluatee_id = db.Column(db.Integer, db.ForeignKey('employees.employee_id'), nullable=False)
    cycle_id = db.Column(db.Integer, db.ForeignKey('evaluation_cycles.cycle_id'), nullable=False)
    scores = db.Column(db.Text, nullable=False)  # JSON string: {kpi_id: score, ...}
    comments = db.Column(db.Text, nullable=True)
    status = db.Column(db.String(20), default='draft')  # draft, pending_review, approved, final
    submitted_at = db.Column(db.DateTime, default=datetime.utcnow)
    approved_at = db.Column(db.DateTime, nullable=True)
    approved_by = db.Column(db.Integer, db.ForeignKey('employees.employee_id'), nullable=True)
    
    # Relationships
    evaluator = db.relationship('Employee', foreign_keys=[evaluator_id], backref='evaluations_given')
    evaluatee = db.relationship('Employee', foreign_keys=[evaluatee_id], backref='evaluations_received')
    approver = db.relationship('Employee', foreign_keys=[approved_by])

class FeedbackQuestion(db.Model):
    """360-degree feedback questions"""
    __tablename__ = 'feedback_questions'
    
    question_id = db.Column(db.Integer, primary_key=True)
    category = db.Column(db.String(100), nullable=False)  # Communication, Collaboration, etc.
    question_text = db.Column(db.Text, nullable=False)
    is_for_managers = db.Column(db.Boolean, default=False)  # Leadership questions for managers only
    is_open_ended = db.Column(db.Boolean, default=False)  # True for open-ended text questions
    # question_scope: 'global' = asked to everyone (direct or indirect relationship); 'direct' = only for direct (1) relationship
    question_scope = db.Column(db.String(20), default='global', nullable=False)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class DeletedFeedbackCategory(db.Model):
    """Category names that have been 'deleted' (hidden from dropdown for new questions)."""
    __tablename__ = 'deleted_feedback_categories'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False, unique=True)
    deleted_at = db.Column(db.DateTime, default=datetime.utcnow)


class RandomizationLog(db.Model):
    """Randomization assignment log"""
    __tablename__ = 'randomization_log'
    
    log_id = db.Column(db.Integer, primary_key=True)
    cycle_id = db.Column(db.Integer, db.ForeignKey('evaluation_cycles.cycle_id'), nullable=False)
    evaluator_id = db.Column(db.Integer, db.ForeignKey('employees.employee_id'), nullable=True)  # For KPI evaluations (not anonymous)
    evaluator_hash = db.Column(db.String(64), nullable=True, index=True)  # For 360 evaluations (anonymous)
    evaluatee_id = db.Column(db.Integer, db.ForeignKey('employees.employee_id'), nullable=False)
    evaluation_type = db.Column(db.String(20), default='360')  # '360' or 'kpi'
    assigned_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    evaluator = db.relationship('Employee', foreign_keys=[evaluator_id])  # Only for KPI evaluations
    evaluatee = db.relationship('Employee', foreign_keys=[evaluatee_id])
    
    # Unique constraint to prevent duplicate assignments in same cycle
    # For 360: uses evaluator_hash, for KPI: uses evaluator_id
    __table_args__ = (
        db.UniqueConstraint('cycle_id', 'evaluator_hash', 'evaluatee_id', 'evaluation_type', name='unique_360_assignment'),
        db.UniqueConstraint('cycle_id', 'evaluator_id', 'evaluatee_id', 'evaluation_type', name='unique_kpi_assignment'),
    )

class FeedbackEvaluation(db.Model):
    """360-degree feedback evaluation submissions"""
    __tablename__ = 'feedback_evaluations'
    
    feedback_id = db.Column(db.Integer, primary_key=True)
    evaluator_hash = db.Column(db.String(64), nullable=False, index=True)  # Hashed evaluator identifier (SHA-256)
    evaluatee_id = db.Column(db.Integer, db.ForeignKey('employees.employee_id'), nullable=False)
    cycle_id = db.Column(db.Integer, db.ForeignKey('evaluation_cycles.cycle_id'), nullable=False)
    question_id = db.Column(db.Integer, db.ForeignKey('feedback_questions.question_id'), nullable=False)
    score = db.Column(db.Float, nullable=True)  # 1-5 scale (NULL for open-ended questions)
    comment = db.Column(db.Text, nullable=True)  # Used for open-ended responses or optional comments
    status = db.Column(db.String(20), default='draft')  # draft, submitted
    submitted_at = db.Column(db.DateTime, nullable=True)  # Only set when submitted
    
    # Anonymized metadata for diversity calculations (hashed)
    evaluator_department_hash = db.Column(db.String(64), nullable=True)  # Hashed department for diversity
    evaluator_role_hash = db.Column(db.String(64), nullable=True)  # Hashed role for diversity
    is_manager_hash = db.Column(db.String(64), nullable=True)  # Hashed manager relationship
    
    # Relationships (evaluator relationship removed for anonymity)
    evaluatee = db.relationship('Employee', foreign_keys=[evaluatee_id])
    question = db.relationship('FeedbackQuestion')

class EvaluatorScore(db.Model):
    """Store final calculated score for each evaluator_hash-evaluatee pair"""
    __tablename__ = 'evaluator_scores'
    
    id = db.Column(db.Integer, primary_key=True)
    evaluator_hash = db.Column(db.String(64), nullable=False, index=True)  # Hashed evaluator identifier
    evaluatee_id = db.Column(db.Integer, db.ForeignKey('employees.employee_id'), nullable=False)
    cycle_id = db.Column(db.Integer, db.ForeignKey('evaluation_cycles.cycle_id'), nullable=False)
    final_score = db.Column(db.Float, nullable=False)  # Average of all scored questions for this evaluator-evaluatee pair
    question_count = db.Column(db.Integer, nullable=False)  # Number of scored questions used in calculation
    calculated_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    evaluatee = db.relationship('Employee', foreign_keys=[evaluatee_id])
    cycle = db.relationship('EvaluationCycle')
    
    # Unique constraint: one score per evaluator-evaluatee-cycle combination
    __table_args__ = (
        db.UniqueConstraint('evaluator_hash', 'evaluatee_id', 'cycle_id', name='unique_evaluator_score'),
    )


class EvaluationRelationship(db.Model):
    """
    Evaluation relationship matrix: who can evaluate whom and with which scope.
    Loaded from data/evaluation_relationships.csv (see load_evaluation_dataset_to_mysql.py).
    relationship: 1 = direct (all questions), 0 = global only, x = none, z = self/N/A.
    """
    __tablename__ = 'evaluation_relationships'

    id = db.Column(db.Integer, primary_key=True)
    evaluator_role = db.Column(db.String(120), nullable=False, index=True)   # e.g. "CEO (Rana)"
    evaluatee_role = db.Column(db.String(120), nullable=False, index=True)   # e.g. "DP 1 (Odeh)"
    relationship = db.Column(db.String(1), nullable=False)  # '1', '0', 'x', 'z'

    __table_args__ = (
        db.UniqueConstraint('evaluator_role', 'evaluatee_role', name='unique_eval_relationship'),
    )