from flask_wtf import FlaskForm
from wtforms import StringField, TextAreaField, DateField, FloatField, SelectField, SelectMultipleField, PasswordField, BooleanField
from wtforms.validators import DataRequired, Email, Optional, NumberRange, Length, ValidationError
from flask import current_app

class LoginForm(FlaskForm):
    email = StringField('Email', validators=[DataRequired(), Email()])
    password = PasswordField('Password', validators=[DataRequired()])
    remember_me = BooleanField('Remember Me')

class EmployeeForm(FlaskForm):
    full_name = StringField('Full Name', validators=[DataRequired(), Length(max=200)])
    email = StringField('Email', validators=[DataRequired(), Email(), Length(max=120)])
    department = StringField('Department', validators=[DataRequired(), Length(max=100)])
    role = StringField('Role', validators=[DataRequired(), Length(max=100)])
    join_date = DateField('Join Date', validators=[DataRequired()])
    manager_id = SelectField('Manager', coerce=int, validators=[Optional()])
    status = SelectField('Status', choices=[('active', 'Active'), ('inactive', 'Inactive')], 
                        validators=[DataRequired()])

class KPIForm(FlaskForm):
    kpi_name = StringField('KPI Name', validators=[DataRequired(), Length(max=200)])
    description = TextAreaField('Description', validators=[Optional()])
    applies_to_all = BooleanField('Apply to all employees', default=False)
    employee_ids = SelectMultipleField('Assign to specific employees', coerce=int, validators=[Optional()])
    weight = FloatField('Weight', validators=[DataRequired(), NumberRange(min=0.1, max=100)], 
                       default=1.0)
    
    def validate_employee_ids(self, field):
        """Require at least one employee when not applies_to_all."""
        applies = self.applies_to_all.data if hasattr(self, 'applies_to_all') and self.applies_to_all else False
        ids = list(field.data or [])
        if not applies and not ids:
            raise ValidationError('Select at least one employee, or check "Apply to all employees".')
    
    def validate_weight(self, field):
        """Check total weight does not exceed 100% for any assigned employee."""
        from flask import g, has_request_context
        from kpi_creation import calculate_total_weight_for_employee, get_remaining_weight_for_employee
        from models import Employee
        
        if not has_request_context():
            return
        weight = field.data
        exclude_kpi_id = getattr(g, 'editing_kpi_id', None)
        applies_to_all = self.applies_to_all.data if hasattr(self, 'applies_to_all') and self.applies_to_all else False
        employee_ids = list(self.employee_ids.data or []) if hasattr(self, 'employee_ids') else []
        
        if applies_to_all:
            employee_ids = [e.employee_id for e in Employee.query.filter_by(status='active').all()]
        
        for eid in employee_ids:
            total = calculate_total_weight_for_employee(eid, exclude_kpi_id)
            if total + weight > 100:
                emp = Employee.query.get(eid)
                name = emp.full_name if emp else f'ID {eid}'
                remaining = get_remaining_weight_for_employee(eid, exclude_kpi_id)
                raise ValidationError(
                    f'Total weight would exceed 100% for {name}. '
                    f'Current: {total:.1f}%, This KPI: {weight:.1f}%, Remaining: {remaining:.1f}%'
                )

class CycleForm(FlaskForm):
    name = StringField('Cycle Name', validators=[DataRequired(), Length(max=200)])
    start_date = DateField('Start Date', validators=[DataRequired()])
    end_date = DateField('End Date', validators=[DataRequired()])
    description = TextAreaField('Description', validators=[Optional()])
    include_kpi = BooleanField('Include KPI evaluations', default=True)
    include_360 = BooleanField('Include 360-degree feedback', default=True)

    def validate_include_360(self, field):
        if not field.data and not self.include_kpi.data:
            raise ValidationError('Select at least one: KPI evaluations or 360 feedback.')

class EvaluationForm(FlaskForm):
    kpi_scores = SelectField('KPI Scores', choices=[], validators=[Optional()])
    comments = TextAreaField('Comments', validators=[Optional()])

# Standard categories for 360 feedback questions (used in dropdown)
FEEDBACK_QUESTION_CATEGORIES = [
    ('Communication', 'Communication'),
    ('Collaboration', 'Collaboration'),
    ('Accountability', 'Accountability'),
    ('Problem-solving', 'Problem-solving'),
    ('Professionalism & Respect', 'Professionalism & Respect'),
    ('Leadership', 'Leadership'),
    ('Open-Ended Feedback', 'Open-Ended Feedback'),
]
NEW_CATEGORY_VALUE = '__new__'  # value when user chooses "Add new category"

QUESTION_SCOPE_CHOICES = [
    ('global', 'Global (asked to everyone with any relationship)'),
    ('direct', 'Direct (asked only when evaluator has direct working relationship)'),
]

class FeedbackQuestionForm(FlaskForm):
    category = SelectField('Category', choices=FEEDBACK_QUESTION_CATEGORIES, validators=[DataRequired()])
    new_category = StringField('New category name', validators=[Optional(), Length(max=100)],
                               description='Only used when "Add new category" is selected above.')
    question_text = TextAreaField('Question Text', validators=[DataRequired()])
    question_scope = SelectField('Scope', choices=QUESTION_SCOPE_CHOICES, default='global',
                                 validators=[DataRequired()])
    is_for_managers = BooleanField('For managers only', default=False)
    is_open_ended = BooleanField('Open-ended (no numeric score)', default=False)
    is_active = BooleanField('Active', default=True)

    def validate_new_category(self, field):
        if self.category.data == NEW_CATEGORY_VALUE and (not field.data or not field.data.strip()):
            raise ValidationError('Please enter the new category name.')
