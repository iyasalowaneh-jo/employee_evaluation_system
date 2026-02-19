"""
Comprehensive data seeding script
Creates all users, KPIs, 360 questions, and evaluation cycle
Run this once to populate the database with demo data
"""
from app import app
from models import db, User, Employee, KPI, EvaluationCycle, FeedbackQuestion, RandomizationLog, FeedbackEvaluation, Evaluation, EvaluationRelationship, KPICreationRule
from kpi_creation import KPI_CREATION_HIERARCHY
from datetime import date, datetime, timedelta
import random


def seed_kpi_creation_rules():
    """Populate KPICreationRule from KPI_CREATION_HIERARCHY"""
    for manager_role, config in KPI_CREATION_HIERARCHY.items():
        for target_role in config.get('can_create_for', []):
            existing = KPICreationRule.query.filter_by(manager_role=manager_role, target_role=target_role).first()
            if not existing:
                db.session.add(KPICreationRule(manager_role=manager_role, target_role=target_role))

def seed_all_data():
    """Seed all data for the performance management system"""
    with app.app_context():
        print("Starting data seeding...")
        
        # Drop and recreate all tables to ensure schema is up to date
        print("Updating database schema...")
        db.drop_all()
        db.create_all()
        print("[OK] Database schema updated")
        
        # Clear existing data (if any remains) - in correct order to avoid foreign key issues
        print("Clearing existing data...")
        # Delete in order to respect foreign keys
        db.session.query(FeedbackEvaluation).delete()
        db.session.query(Evaluation).delete()
        db.session.query(RandomizationLog).delete()
        db.session.query(FeedbackQuestion).delete()
        db.session.query(KPI).delete()
        db.session.query(EvaluationCycle).delete()
        # Set manager_id to NULL before deleting employees
        db.session.execute(db.text("UPDATE employees SET manager_id = NULL"))
        db.session.query(User).delete()
        db.session.query(Employee).delete()
        db.session.commit()
        print("[OK] All existing data cleared")
        
        # Load evaluation relationship matrix (required for 360 assignment)
        try:
            from load_evaluation_dataset_to_mysql import load_dataset as load_evaluation_dataset
            load_evaluation_dataset()
        except Exception as ex:
            print(f"[WARNING] Could not load evaluation_relationships: {ex}")
            print("  Run: python load_evaluation_dataset_to_mysql.py")
        
        # Create employees with organizational structure (matches evaluation matrix labels)
        print("\n1. Creating employees...")
        employees = {}

        # Executive Level
        employees['ceo'] = create_employee('CEO (Rana)', 'ceo@company.com', 'Executive', 'CEO', None)
        employees['tech_manager'] = create_employee('Technical Manager (Anas)', 'tech.manager@company.com', 'Executive', 'Technical Manager', employees['ceo'].employee_id)

        # Unit Level
        employees['unit_manager'] = create_employee('Unit Manager (Majd H)', 'unit.manager@company.com', 'Unit Level', 'Unit Manager', employees['ceo'].employee_id)

        # Business Development (Rana creates KPIs for BD, CFO, Majd H, PM Manager)
        employees['bd'] = create_employee('BD (Ban)', 'bd@company.com', 'Business Development', 'BD', employees['ceo'].employee_id)

        # Finance (Rana creates KPIs for CFO)
        employees['cfo'] = create_employee('CFO (Haytham)', 'cfo@company.com', 'Finance', 'CFO', employees['ceo'].employee_id)

        # Project Management (Rana creates KPIs for PM Manager)
        employees['pm_manager'] = create_employee('PM Manager (Majd M)', 'pm.manager@company.com', 'Project Management', 'PM Manager', employees['ceo'].employee_id)
        employees['pm1'] = create_employee('PM 1 (Bana)', 'pm1@company.com', 'Project Management', 'PM 1', employees['pm_manager'].employee_id)
        employees['pm2'] = create_employee('PM 2 (Feryal)', 'pm2@company.com', 'Project Management', 'PM 2', employees['pm_manager'].employee_id)
        employees['pm3'] = create_employee('PM 3 (Leen)', 'pm3@company.com', 'Project Management', 'PM 3', employees['pm_manager'].employee_id)

        # Operations (Majd H creates for Ops Manager, Field Manager; Ayat creates for Ops 1-4, Lebanon, Egypt; Anas creates for Ops Ahmad/Abd/Weklat)
        employees['ops_manager'] = create_employee('Ops Manager (Ayat)', 'ops.manager@company.com', 'Operations', 'Ops Manager', employees['unit_manager'].employee_id)
        employees['field_manager'] = create_employee('Field Manager (Ala\'a H)', 'field.manager@company.com', 'Operations', 'Field Manager', employees['unit_manager'].employee_id)
        employees['ops1'] = create_employee('Ops 1 (Hala)', 'ops1@company.com', 'Operations', 'Ops 1', employees['ops_manager'].employee_id)
        employees['ops2'] = create_employee('Ops 2 (Rahaf)', 'ops2@company.com', 'Operations', 'Ops 2', employees['ops_manager'].employee_id)
        employees['ops3'] = create_employee('Ops 3 (Aya)', 'ops3@company.com', 'Operations', 'Ops 3', employees['ops_manager'].employee_id)
        employees['ops4'] = create_employee('Ops 4 (Hamzeh)', 'ops4@company.com', 'Operations', 'Ops 4', employees['ops_manager'].employee_id)
        employees['ops_lebanon'] = create_employee('Ops Lebanon (Ala\'a Q)', 'ops.lebanon@company.com', 'Operations', 'Ops Lebanon', employees['ops_manager'].employee_id)
        employees['ops_egypt'] = create_employee('Ops Egypt (Marwa)', 'ops.egypt@company.com', 'Operations', 'Ops Egypt', employees['ops_manager'].employee_id)
        employees['ops_ahmad'] = create_employee('Ops (Ahmad Salam)', 'ops.ahmad@company.com', 'Operations', 'Ops', employees['tech_manager'].employee_id)
        employees['ops_abd'] = create_employee('Ops (Abd al baqe)', 'ops.abd@company.com', 'Operations', 'Ops', employees['tech_manager'].employee_id)
        employees['ops_weklat'] = create_employee('Ops (Weklat)', 'ops.weklat@company.com', 'Operations', 'Ops', employees['tech_manager'].employee_id)

        # Data Processing
        employees['dp_supervisor'] = create_employee('DP Supervisor (Tareq)', 'dp.supervisor@company.com', 'Data Processing', 'DP Supervisor', employees['unit_manager'].employee_id)
        employees['qa_officer'] = create_employee('QA Officer (Manal)', 'qa.officer@company.com', 'Data Processing', 'QA Officer', employees['dp_supervisor'].employee_id)
        employees['dp1'] = create_employee('DP 1 (Odeh)', 'dp1@company.com', 'Data Processing', 'DP 1', employees['dp_supervisor'].employee_id)
        employees['dp2'] = create_employee('DP 2 (Abdullah)', 'dp2@company.com', 'Data Processing', 'DP 2', employees['dp_supervisor'].employee_id)
        employees['dp3'] = create_employee('DP 3 (Iyas)', 'dp3@company.com', 'Data Processing', 'DP 3', employees['dp_supervisor'].employee_id)
        employees['qa_senior'] = create_employee('QA Senior Hamdan', 'qa.senior@company.com', 'Compliance', 'QA Senior compliance', employees['unit_manager'].employee_id)

        # Finance (accountants)
        employees['accountant1'] = create_employee('Accountant 1 (Dania)', 'accountant1@company.com', 'Finance', 'Accountant 1', employees['cfo'].employee_id)
        employees['accountant2'] = create_employee('Accountant 2 (Balqees)', 'accountant2@company.com', 'Finance', 'Accountant 2', employees['cfo'].employee_id)

        # Admin (Ace) - CFO creates KPIs for Ace 1, 2
        employees['ace1'] = create_employee('Ace 1 (Ala\'a Z)', 'ace1@company.com', 'Admin', 'Ace 1', employees['cfo'].employee_id)
        employees['ace2'] = create_employee('Ace 2 (Qassas)', 'ace2@company.com', 'Admin', 'Ace 2', employees['cfo'].employee_id)

        # PM Nigeria - Technical Manager (Anas) creates KPIs
        employees['pm_nigeria'] = create_employee('Pm Nigeria (Funmi)', 'pm.nigeria@company.com', 'Project Management', 'Pm Nigeria', employees['tech_manager'].employee_id)

        # Analysis - Valeria creates for Analysis 1, 2; Anas creates for Valeria
        employees['analysis'] = create_employee('Analysis (Valeria)', 'analysis@company.com', 'Analysis', 'Analysis', employees['tech_manager'].employee_id)
        employees['analysis1'] = create_employee('Analysis 1 (Marco)', 'analysis1@company.com', 'Analysis', 'Analysis 1', employees['analysis'].employee_id)
        employees['analysis2'] = create_employee('Analysis 2 (Manuel)', 'analysis2@company.com', 'Analysis', 'Analysis 2', employees['analysis'].employee_id)

        db.session.commit()
        print(f"[OK] Created {len(employees)} employees")

        # Create user accounts for all employees
        print("\n2. Creating user accounts...")
        user_roles = {
            'ceo': 'admin',
            'tech_manager': 'department_manager',
            'unit_manager': 'department_manager',
            'bd': 'employee',
            'cfo': 'department_manager',
            'pm_manager': 'department_manager',
            'pm1': 'employee', 'pm2': 'employee', 'pm3': 'employee', 'pm_nigeria': 'employee',
            'ops_manager': 'department_manager',
            'field_manager': 'department_manager',
            'ops1': 'employee', 'ops2': 'employee', 'ops3': 'employee', 'ops4': 'employee',
            'ops_lebanon': 'employee', 'ops_egypt': 'employee', 'ops_ahmad': 'employee', 'ops_abd': 'employee', 'ops_weklat': 'employee',
            'dp_supervisor': 'department_manager',
            'qa_officer': 'employee', 'qa_senior': 'employee',
            'dp1': 'employee', 'dp2': 'employee', 'dp3': 'employee',
            'accountant1': 'employee', 'accountant2': 'employee',
            'ace1': 'employee', 'ace2': 'employee',
            'analysis': 'department_manager', 'analysis1': 'employee', 'analysis2': 'employee',
        }
        
        for emp_key, emp in employees.items():
            # Check if user already exists
            existing_user = User.query.filter_by(employee_id=emp.employee_id).first()
            if existing_user:
                continue
            
            # CEO gets admin role, others get their assigned roles
            if emp_key == 'ceo':
                role = 'admin'  # CEO is also admin
            else:
                role = user_roles.get(emp_key, 'employee')
            
            user = User(
                employee_id=emp.employee_id,
                email=emp.email,
                role=role
            )
            # Default password for all users: password123
            # CEO/admin gets both passwords set (can login with either email)
            user.set_password('password123')
            db.session.add(user)
        
        # Also create admin@company.com login that points to CEO
        # But since employee_id is unique, we'll just note that CEO can login as admin
        # Actually, we can't have two users with same employee_id, so CEO email is the admin login
        # Let's create a note: CEO can login with ceo@company.com (password123) and has admin role
        
        db.session.commit()
        print("[OK] Created user accounts")
        
        # Seed KPI creation rules (who can create KPIs for whom)
        print("\n3. Seeding KPI creation rules...")
        seed_kpi_creation_rules()
        db.session.commit()
        print("[OK] KPI creation rules seeded")
        
        # Create KPIs
        print("\n4. Creating KPIs...")
        kpis = create_kpis(employees)
        db.session.flush()
        create_employee_unique_kpis(employees)
        db.session.commit()
        print(f"[OK] Created {len(kpis)} KPIs + unique employee KPIs")
        
        # Create 360 Feedback Questions
        print("\n5. Creating 360 feedback questions...")
        questions = create_feedback_questions()
        db.session.commit()
        print(f"[OK] Created {len(questions)} feedback questions")
        
        # Create active evaluation cycle
        print("\n6. Creating evaluation cycle...")
        cycle = EvaluationCycle(
            name='Q1 2026 Performance Evaluation',
            start_date=date.today(),
            end_date=date.today() + timedelta(days=90),
            description='Quarterly performance evaluation cycle',
            status='active'
        )
        db.session.add(cycle)
        db.session.commit()
        print("[OK] Created evaluation cycle")
        
        # Assign 360 evaluations
        print("\n7. Assigning 360 evaluations...")
        from cycle_assignment import assign_360_evaluations, assign_kpi_evaluations
        assign_360_evaluations(employees, cycle.cycle_id)
        db.session.commit()
        print("[OK] Assigned 360 evaluations")
        
        # Assign KPI evaluations (manager-to-subordinate)
        print("\n8. Assigning KPI evaluations...")
        assign_kpi_evaluations(employees, cycle.cycle_id)
        db.session.commit()
        print("[OK] Assigned KPI evaluations")
        
        print("\n" + "="*60)
        print("[SUCCESS] DATA SEEDING COMPLETE!")
        print("="*60)
        print("\nDefault Login Credentials:")
        print("  Admin/CEO: ceo@company.com / password123 (CEO has admin role)")
        print("  All Users: [email] / password123")
        print("\nExample user emails:")
        for key, emp in list(employees.items())[:5]:
            print(f"  {emp.full_name}: {emp.email}")
        print("  ... and more")
        print("\n[READY] System is ready to use!")

def create_employee(name, email, department, role, manager_id):
    """Helper to create an employee"""
    employee = Employee(
        full_name=name,
        email=email,
        department=department,
        role=role,
        join_date=date.today() - timedelta(days=random.randint(30, 1000)),
        manager_id=manager_id,
        status='active'
    )
    db.session.add(employee)
    db.session.flush()
    return employee

def create_kpis(employees):
    """Create KPIs for all roles and all employees"""
    kpis = []
    
    # Generic KPI templates (role='Template' prevents migration from setting applies_to_all=True)
    kpis.append(KPI(kpi_name='Quality of Work', description='Overall quality and accuracy of work output', role='Template', department=None, weight=33.0, is_default=True, applies_to_all=False))
    kpis.append(KPI(kpi_name='Timeliness', description='Meeting deadlines and delivering on time', role='Template', department=None, weight=33.0, is_default=True, applies_to_all=False))
    kpis.append(KPI(kpi_name='Collaboration & Communication', description='Effectiveness in working with others and communicating clearly', role='Template', department=None, weight=34.0, is_default=True, applies_to_all=False))
    
    # Data Processing Officers KPIs
    kpis.append(KPI(kpi_name='Data Accuracy Rate', description='Percentage of data entries without errors', role='Data Processing Officer', department='Data Processing', weight=25.0, is_default=True))
    kpis.append(KPI(kpi_name='Timeliness of Submissions', description='On-time completion of data processing tasks', role='Data Processing Officer', department='Data Processing', weight=20.0, is_default=True))
    kpis.append(KPI(kpi_name='Compliance with Protocols', description='Adherence to data processing standards', role='Data Processing Officer', department='Data Processing', weight=20.0, is_default=True))
    kpis.append(KPI(kpi_name='Rework/Error Rate', description='Percentage of work requiring correction', role='Data Processing Officer', department='Data Processing', weight=20.0, is_default=True))
    kpis.append(KPI(kpi_name='Responsiveness to Feedback', description='Speed and quality of response to feedback', role='Data Processing Officer', department='Data Processing', weight=15.0, is_default=True))
    
    # QA Officer KPIs
    kpis.append(KPI(kpi_name='Quality Checks Completed', description='Number of quality checks performed', role='QA Officer', department='Data Processing', weight=25.0, is_default=True))
    kpis.append(KPI(kpi_name='Error Detection Rate', description='Percentage of errors identified before delivery', role='QA Officer', department='Data Processing', weight=25.0, is_default=True))
    kpis.append(KPI(kpi_name='Documentation Accuracy', description='Completeness and accuracy of QA documentation', role='QA Officer', department='Data Processing', weight=20.0, is_default=True))
    kpis.append(KPI(kpi_name='Coordination with DP Team', description='Effectiveness of collaboration with data processing team', role='QA Officer', department='Data Processing', weight=30.0, is_default=True))
    
    # DP Supervisor KPIs
    kpis.append(KPI(kpi_name='Team Productivity', description='Overall team output and efficiency', role='DP Supervisor', department='Data Processing', weight=25.0, is_default=True))
    kpis.append(KPI(kpi_name='Error Reduction %', description='Percentage reduction in team errors', role='DP Supervisor', department='Data Processing', weight=25.0, is_default=True))
    kpis.append(KPI(kpi_name='Training & Coaching Effectiveness', description='Success of team development initiatives', role='DP Supervisor', department='Data Processing', weight=25.0, is_default=True))
    kpis.append(KPI(kpi_name='Workflow Optimization', description='Improvements in process efficiency', role='DP Supervisor', department='Data Processing', weight=25.0, is_default=True))
    
    # Operations Officers KPIs
    kpis.append(KPI(kpi_name='Task Completion Rate', description='Percentage of assigned tasks completed on time', role='Operations Officer', department='Operations', weight=30.0, is_default=True))
    kpis.append(KPI(kpi_name='Field Reporting Accuracy', description='Accuracy of field reports and documentation', role='Operations Officer', department='Operations', weight=25.0, is_default=True))
    kpis.append(KPI(kpi_name='Coordination with Teams', description='Effectiveness of cross-team collaboration', role='Operations Officer', department='Operations', weight=25.0, is_default=True))
    kpis.append(KPI(kpi_name='Safety Compliance', description='Adherence to safety protocols and procedures', role='Operations Officer', department='Operations', weight=20.0, is_default=True))
    
    # Operations Manager / Field Manager KPIs
    kpis.append(KPI(kpi_name='Project Delivery on Time', description='Percentage of projects delivered within deadline', role='Operations Manager', department='Operations', weight=30.0, is_default=True))
    kpis.append(KPI(kpi_name='Resource Allocation Efficiency', description='Optimal use of resources and budget', role='Operations Manager', department='Operations', weight=25.0, is_default=True))
    kpis.append(KPI(kpi_name='Risk Mitigation', description='Effectiveness in identifying and managing risks', role='Operations Manager', department='Operations', weight=25.0, is_default=True))
    kpis.append(KPI(kpi_name='Team Coordination', description='Quality of team management and coordination', role='Operations Manager', department='Operations', weight=20.0, is_default=True))
    
    kpis.append(KPI(kpi_name='Project Delivery on Time', description='Percentage of projects delivered within deadline', role='Field Manager', department='Operations', weight=30.0, is_default=True))
    kpis.append(KPI(kpi_name='Resource Allocation Efficiency', description='Optimal use of resources and budget', role='Field Manager', department='Operations', weight=25.0, is_default=True))
    kpis.append(KPI(kpi_name='Risk Mitigation', description='Effectiveness in identifying and managing risks', role='Field Manager', department='Operations', weight=25.0, is_default=True))
    kpis.append(KPI(kpi_name='Team Coordination', description='Quality of team management and coordination', role='Field Manager', department='Operations', weight=20.0, is_default=True))
    
    # Project Managers KPIs
    kpis.append(KPI(kpi_name='Project Delivery on Time', description='Percentage of projects completed on schedule', role='Project Manager', department='Project Management', weight=30.0, is_default=True))
    kpis.append(KPI(kpi_name='Stakeholder Communication', description='Quality and frequency of stakeholder updates', role='Project Manager', department='Project Management', weight=25.0, is_default=True))
    kpis.append(KPI(kpi_name='Budget Adherence', description='Projects completed within allocated budget', role='Project Manager', department='Project Management', weight=25.0, is_default=True))
    kpis.append(KPI(kpi_name='Risk Management', description='Proactive identification and mitigation of project risks', role='Project Manager', department='Project Management', weight=20.0, is_default=True))
    
    # PM Manager KPIs
    kpis.append(KPI(kpi_name='Portfolio Delivery Rate', description='Percentage of projects in portfolio delivered successfully', role='PM Manager', department='Project Management', weight=30.0, is_default=True))
    kpis.append(KPI(kpi_name='Cross-Project Coordination', description='Effectiveness of coordination across multiple projects', role='PM Manager', department='Project Management', weight=25.0, is_default=True))
    kpis.append(KPI(kpi_name='Team Performance', description='Overall performance of project management team', role='PM Manager', department='Project Management', weight=25.0, is_default=True))
    kpis.append(KPI(kpi_name='Strategic Alignment', description='Projects aligned with organizational goals', role='PM Manager', department='Project Management', weight=20.0, is_default=True))
    
    # Finance Roles KPIs
    kpis.append(KPI(kpi_name='Accuracy of Financial Reports', description='Error-free financial reporting', role='Senior Accountant', department='Finance', weight=35.0, is_default=True))
    kpis.append(KPI(kpi_name='Timeliness of Submissions', description='On-time submission of financial reports', role='Senior Accountant', department='Finance', weight=30.0, is_default=True))
    kpis.append(KPI(kpi_name='Compliance with Policies', description='Adherence to financial policies and regulations', role='Senior Accountant', department='Finance', weight=35.0, is_default=True))
    
    kpis.append(KPI(kpi_name='Accuracy of Financial Reports', description='Error-free financial reporting', role='Accountant Officer', department='Finance', weight=35.0, is_default=True))
    kpis.append(KPI(kpi_name='Timeliness of Submissions', description='On-time submission of financial reports', role='Accountant Officer', department='Finance', weight=30.0, is_default=True))
    kpis.append(KPI(kpi_name='Compliance with Policies', description='Adherence to financial policies and regulations', role='Accountant Officer', department='Finance', weight=35.0, is_default=True))
    
    kpis.append(KPI(kpi_name='Financial Strategy Execution', description='Implementation of financial strategies', role='CFO', department='Finance', weight=30.0, is_default=True))
    kpis.append(KPI(kpi_name='Budget Management', description='Effective budget planning and control', role='CFO', department='Finance', weight=30.0, is_default=True))
    kpis.append(KPI(kpi_name='Team Leadership', description='Leadership effectiveness of finance team', role='CFO', department='Finance', weight=40.0, is_default=True))
    
    # Business Development KPIs
    kpis.append(KPI(kpi_name='Leads Generated', description='Number of qualified leads generated', role='Business Development Officer', department=None, weight=30.0, is_default=True))
    kpis.append(KPI(kpi_name='Proposal Quality', description='Quality and success rate of proposals', role='Business Development Officer', department=None, weight=30.0, is_default=True))
    kpis.append(KPI(kpi_name='Conversion Support', description='Effectiveness in supporting sales conversions', role='Business Development Officer', department=None, weight=40.0, is_default=True))
    
    # Admin Officers KPIs
    kpis.append(KPI(kpi_name='Process Efficiency', description='Efficiency of administrative processes', role='Admin Officer', department='Administration', weight=35.0, is_default=True))
    kpis.append(KPI(kpi_name='Documentation Accuracy', description='Accuracy and completeness of documentation', role='Admin Officer', department='Administration', weight=30.0, is_default=True))
    kpis.append(KPI(kpi_name='Internal Support Quality', description='Quality of support provided to internal teams', role='Admin Officer', department='Administration', weight=35.0, is_default=True))
    
    # Executive and Manager KPIs (these can be global/None)
    kpis.append(KPI(kpi_name='Strategic Planning', description='Quality of strategic planning and execution', role='CEO', department=None, weight=40.0, is_default=True))
    kpis.append(KPI(kpi_name='Organizational Leadership', description='Effectiveness in leading the organization', role='CEO', department=None, weight=60.0, is_default=True))
    
    kpis.append(KPI(kpi_name='Technical Strategy', description='Development and execution of technical strategy', role='Technical Manager', department=None, weight=40.0, is_default=True))
    kpis.append(KPI(kpi_name='Team Leadership', description='Leadership effectiveness of technical teams', role='Technical Manager', department=None, weight=60.0, is_default=True))
    
    kpis.append(KPI(kpi_name='Department Performance', description='Overall performance of all departments', role='Unit Manager', department=None, weight=50.0, is_default=True))
    kpis.append(KPI(kpi_name='Cross-Department Coordination', description='Effectiveness of coordination across departments', role='Unit Manager', department=None, weight=50.0, is_default=True))
    
    for kpi in kpis:
        db.session.add(kpi)
    db.session.flush()
    
    # Do NOT auto-assign KPIs to employees - managers create and assign KPIs per employee.
    # Default KPIs serve as templates/suggestions on the Create KPI page.
    
    return kpis


def create_employee_unique_kpis(employees):
    """Create unique, personalized example KPIs for each employee (manager-created, approved).
    Each employee gets 1-4 KPIs totaling exactly 100% weight. Varies by employee for realism."""
    from datetime import datetime, timezone
    
    def add_kpis_for_employee(manager, emp, kpi_specs):
        """Add KPIs for one employee. kpi_specs: list of (name, desc, weight) - weights must sum to 100."""
        if not manager or not emp:
            return
        total = sum(w for _, _, w in kpi_specs)
        if abs(total - 100.0) > 0.01:
            raise ValueError(f"KPI weights must sum to 100, got {total} for {emp.full_name}")
        for name, desc, weight in kpi_specs:
            k = KPI(
                kpi_name=name,
                description=desc,
                weight=weight,
                is_active=True,
                is_default=False,
                applies_to_all=False,
                created_by=manager.employee_id,
                status='approved',
                approved_by=employees['ceo'].employee_id,
                approved_at=datetime.now(timezone.utc)
            )
            db.session.add(k)
            db.session.flush()
            k.assigned_employees.append(emp)
    
    dp_sup = employees.get('dp_supervisor')
    pm_mgr = employees.get('pm_manager')
    ops_mgr = employees.get('ops_manager')
    cfo = employees.get('cfo')
    tech_mgr = employees.get('tech_manager')
    unit_mgr = employees.get('unit_manager')
    ceo = employees.get('ceo')
    analysis_mgr = employees.get('analysis')
    
    # --- DP Supervisor's team (1-4 KPIs each, total 100%) ---
    add_kpis_for_employee(dp_sup, employees.get('dp3'), [
        ('Evaluation system development', 'Design and implement the employee evaluation system', 55.0),
        ('System integration & testing', 'Complete end-to-end integration and testing', 45.0),
    ])  # 2 KPIs
    add_kpis_for_employee(dp_sup, employees.get('dp2'), [
        ('Script translation code', 'Develop tools to translate scripts across systems', 40.0),
        ('Data pipeline automation', 'Automate data processing pipelines', 35.0),
        ('Documentation & handover', 'Document workflow and complete knowledge transfer', 25.0),
    ])  # 3 KPIs
    add_kpis_for_employee(dp_sup, employees.get('dp1'), [
        ('Data quality audits', 'Conduct quarterly data quality audits and report findings', 50.0),
        ('Process documentation', 'Document and update data processing procedures', 50.0),
    ])  # 2 KPIs
    add_kpis_for_employee(dp_sup, employees.get('qa_officer'), [
        ('QA automation scripts', 'Build automated QA test scripts for new workflows', 35.0),
        ('Error tracking dashboard', 'Maintain error tracking dashboard and weekly reports', 30.0),
        ('Quality metrics reporting', 'Produce monthly quality metrics and trends', 35.0),
    ])  # 3 KPIs
    
    # --- QA Senior (1 KPI) ---
    add_kpis_for_employee(unit_mgr, employees.get('qa_senior'), [
        ('Compliance review & QA standards', 'Complete compliance review cycles and maintain QA documentation', 100.0),
    ])
    
    # --- PM Manager's team (2-4 KPIs each) ---
    add_kpis_for_employee(pm_mgr, employees.get('pm1'), [
        ('Project Alpha delivery', 'Deliver Project Alpha milestones on schedule', 40.0),
        ('Stakeholder reporting', 'Weekly stakeholder status reports', 25.0),
        ('Risk management', 'Identify and mitigate project risks', 35.0),
    ])  # 3 KPIs
    add_kpis_for_employee(pm_mgr, employees.get('pm2'), [
        ('Project Beta launch', 'Complete Project Beta launch and handover', 50.0),
        ('Risk register maintenance', 'Maintain and update project risk register', 50.0),
    ])  # 2 KPIs
    add_kpis_for_employee(pm_mgr, employees.get('pm3'), [
        ('Project Gamma scope', 'Finalize scope and baseline', 30.0),
        ('Resource allocation plan', 'Develop Q2 resource allocation plan', 25.0),
        ('Budget tracking', 'Track project budget vs plan', 25.0),
        ('Stakeholder alignment', 'Ensure stakeholder alignment on deliverables', 20.0),
    ])  # 4 KPIs
    
    # --- Pm Nigeria (2 KPIs) ---
    add_kpis_for_employee(tech_mgr, employees.get('pm_nigeria'), [
        ('Nigeria regional delivery', 'Deliver regional project milestones', 60.0),
        ('Regional stakeholder engagement', 'Maintain stakeholder engagement plan', 40.0),
    ])
    
    # --- Ops Manager's team (1-4 KPIs each) ---
    add_kpis_for_employee(ops_mgr, employees.get('ops1'), [
        ('Field operations optimization', 'Optimize field operations in assigned region', 55.0),
        ('Field report accuracy', 'Maintain 95%+ accuracy on field reports', 45.0),
    ])  # 2 KPIs
    add_kpis_for_employee(ops_mgr, employees.get('ops2'), [
        ('Supply chain coordination', 'Coordinate supply chain activities', 35.0),
        ('Inventory tracking', 'Implement and maintain inventory tracking', 35.0),
        ('Vendor performance', 'Monitor vendor performance and SLA compliance', 30.0),
    ])  # 3 KPIs
    add_kpis_for_employee(ops_mgr, employees.get('ops3'), [
        ('Site safety audits', 'Complete quarterly site safety audits', 50.0),
        ('Safety training coordination', 'Coordinate safety training for field staff', 50.0),
    ])  # 2 KPIs
    add_kpis_for_employee(ops_mgr, employees.get('ops4'), [
        ('Logistics coordination', 'Manage logistics for field operations', 40.0),
        ('Vendor management', 'Maintain vendor relationships and tracking', 35.0),
        ('Cost efficiency', 'Achieve logistics cost targets', 25.0),
    ])  # 3 KPIs
    add_kpis_for_employee(ops_mgr, employees.get('ops_lebanon'), [
        ('Lebanon operations delivery', 'Deliver Lebanon operations targets', 50.0),
        ('Regional reporting', 'Submit timely regional operations reports', 50.0),
    ])  # 2 KPIs
    add_kpis_for_employee(ops_mgr, employees.get('ops_egypt'), [
        ('Egypt operations delivery', 'Deliver Egypt operations targets', 60.0),
        ('Cross-region coordination', 'Coordinate with other regional operations', 40.0),
    ])  # 2 KPIs
    
    # --- Ops Ahmad, Abd, Weklat - same 2 KPIs each (100% total per person) ---
    for emp in [employees.get('ops_ahmad'), employees.get('ops_abd'), employees.get('ops_weklat')]:
        if emp:
            add_kpis_for_employee(tech_mgr, emp, [
                ('Field data collection', 'Complete field data collection per schedule', 50.0),
                ('Data quality for submissions', 'Ensure data quality on field submissions', 50.0),
            ])
    
    # --- Field Manager (4 KPIs) ---
    add_kpis_for_employee(unit_mgr, employees.get('field_manager'), [
        ('Field team performance', 'Achieve field team performance targets', 30.0),
        ('Field resource allocation', 'Optimize field resource allocation', 25.0),
        ('Safety compliance', 'Ensure team safety compliance', 25.0),
        ('Stakeholder communication', 'Maintain field-stakeholder communication', 20.0),
    ])
    
    # --- CFO's team (2-4 KPIs each) ---
    add_kpis_for_employee(cfo, employees.get('accountant1'), [
        ('Monthly financial close', 'Complete monthly close within 5 business days', 55.0),
        ('Reconciliation accuracy', 'Maintain 100% reconciliation accuracy', 45.0),
    ])  # 2 KPIs
    add_kpis_for_employee(cfo, employees.get('accountant2'), [
        ('Budget variance reporting', 'Produce monthly budget variance reports', 35.0),
        ('AP/AR processing', 'Process AP/AR within SLA', 35.0),
        ('Audit support', 'Support internal and external audit requirements', 30.0),
    ])  # 3 KPIs
    add_kpis_for_employee(cfo, employees.get('ace1'), [
        ('Office administration efficiency', 'Improve administration efficiency metrics', 50.0),
        ('Document management system', 'Maintain document management system', 50.0),
    ])  # 2 KPIs
    add_kpis_for_employee(cfo, employees.get('ace2'), [
        ('Procurement support', 'Support procurement and vendor onboarding', 35.0),
        ('Internal communications', 'Coordinate internal communications', 35.0),
        ('Administrative compliance', 'Ensure administrative compliance', 30.0),
    ])  # 3 KPIs
    
    # --- BD (1 KPI) ---
    add_kpis_for_employee(ceo, employees.get('bd'), [
        ('Lead generation & proposals', 'Achieve quarterly lead generation target and proposal submission rate', 100.0),
    ])
    
    # --- Analysis (2 KPIs) ---
    add_kpis_for_employee(tech_mgr, employees.get('analysis'), [
        ('Analysis framework development', 'Develop and document analysis framework', 50.0),
        ('Data insights delivery', 'Deliver monthly data insights report', 50.0),
    ])
    
    # --- Analysis 1, Analysis 2 (3-4 KPIs each) ---
    add_kpis_for_employee(analysis_mgr, employees.get('analysis1'), [
        ('Predictive model implementation', 'Implement predictive analysis model', 40.0),
        ('Model accuracy tracking', 'Maintain model accuracy metrics', 30.0),
        ('Data validation', 'Ensure data quality for analysis', 30.0),
    ])  # 3 KPIs
    add_kpis_for_employee(analysis_mgr, employees.get('analysis2'), [
        ('Reporting automation', 'Automate key reporting dashboards', 30.0),
        ('Dashboard maintenance', 'Maintain and update analysis dashboards', 25.0),
        ('Ad-hoc analysis', 'Deliver ad-hoc analysis requests on time', 25.0),
        ('Documentation', 'Document analysis methodologies', 20.0),
    ])  # 4 KPIs
    
    # --- DP Supervisor (3 KPIs) ---
    add_kpis_for_employee(unit_mgr, employees.get('dp_supervisor'), [
        ('DP team productivity target', 'Achieve DP team productivity target', 40.0),
        ('Quality improvement initiatives', 'Implement quality improvement initiatives', 35.0),
        ('Team development', 'Complete team training and development plan', 25.0),
    ])
    
    # --- PM Manager (4 KPIs) ---
    add_kpis_for_employee(ceo, employees.get('pm_manager'), [
        ('PM portfolio delivery', 'Deliver PM portfolio targets', 30.0),
        ('Cross-project coordination', 'Lead cross-project coordination', 25.0),
        ('Resource optimization', 'Optimize resource allocation across projects', 25.0),
        ('Stakeholder satisfaction', 'Achieve stakeholder satisfaction targets', 20.0),
    ])
    
    # --- Ops Manager (3 KPIs) ---
    add_kpis_for_employee(unit_mgr, employees.get('ops_manager'), [
        ('Operations delivery target', 'Achieve operations delivery targets', 40.0),
        ('Operations efficiency improvements', 'Implement efficiency improvements', 35.0),
        ('Team performance', 'Achieve team performance metrics', 25.0),
    ])
    
    # --- CFO (2 KPIs) ---
    add_kpis_for_employee(ceo, employees.get('cfo'), [
        ('Finance team targets', 'Achieve finance team targets', 55.0),
        ('Financial planning cycle', 'Complete annual financial planning cycle', 45.0),
    ])
    
    # --- Unit Manager (4 KPIs) ---
    add_kpis_for_employee(ceo, employees.get('unit_manager'), [
        ('Unit performance targets', 'Achieve unit performance targets', 30.0),
        ('Cross-unit initiatives', 'Lead cross-unit initiatives', 25.0),
        ('Strategic alignment', 'Align unit goals with organizational strategy', 25.0),
        ('People development', 'Develop high-potential talent in unit', 20.0),
    ])
    
    # --- Technical Manager (2 KPIs) ---
    add_kpis_for_employee(ceo, employees.get('tech_manager'), [
        ('Technical strategy execution', 'Execute technical strategy initiatives', 55.0),
        ('Technical team development', 'Lead technical team development', 45.0),
    ])


def create_feedback_questions():
    """Create 360-degree feedback questions in two scopes: global (1 or 0) and direct (1 only)."""
    questions = []

    # ---- GLOBAL: observable by anyone in the environment (direct or indirect relationship) ----
    # Kept broad: respect, communication, integrity, positive presence, openness to feedback.
    # Excluded: deadlines, ownership, mistakes, cross-team work, shared goals, resolving disagreements
    #   (those need direct collaboration and are in DIRECT below).
    global_questions = [
        ('Professional Conduct', 'Treats others with respect and maintains a professional demeanor'),
        ('Professional Conduct', 'Communicates clearly and in a timely manner'),
        ('Professional Conduct', 'Can be relied upon to follow through on commitments'),
        ('Professional Conduct', 'Behaves with integrity and honesty'),
        ('Professional Conduct', 'Contributes positively to the work environment'),
        ('Professional Conduct', 'Stays open to feedback and different perspectives'),
        ('Open-Ended', 'What are this person\'s main strengths?'),
        ('Open-Ended', 'What areas would you suggest for this person\'s development?'),
    ]
    for category, question_text in global_questions:
        is_open = question_text.startswith('What ')
        q = FeedbackQuestion(
            category=category,
            question_text=question_text,
            is_for_managers=False,
            is_open_ended=is_open,
            question_scope='global',
            is_active=True
        )
        questions.append(q)
        db.session.add(q)

    # ---- DIRECT: only when evaluator has direct working relationship (1); need collaboration to answer ----
    direct_questions = [
        # Reliability (moved from global: need direct work to assess)
        ('Reliability', 'Meets agreed deadlines and commitments'),
        ('Reliability', 'Takes ownership of responsibilities when needed'),
        ('Reliability', 'Acknowledges mistakes and learns from them'),
        # Collaboration (moved from global: need direct/cross-team experience)
        ('Collaboration', 'Works effectively with people from different roles or teams'),
        ('Collaboration', 'Supports shared goals and objectives'),
        ('Collaboration', 'Resolves disagreements constructively when they arise'),
        # Day-to-day
        ('Day-to-Day Collaboration', 'Works effectively with you on shared tasks or projects'),
        ('Day-to-Day Collaboration', 'Delivers work that meets or exceeds quality expectations'),
        ('Day-to-Day Collaboration', 'Shares relevant information and updates in a timely way'),
        ('Day-to-Day Collaboration', 'Collaborates constructively when solving problems together'),
        ('Day-to-Day Collaboration', 'Gives and receives feedback in a constructive way'),
        ('Day-to-Day Collaboration', 'Supports team priorities and goals in day-to-day work'),
        ('Working Relationship', 'Communicates clearly in the context of your direct collaboration'),
        ('Working Relationship', 'Is responsive and dependable in your working relationship'),
        ('Working Relationship', 'Aligns on expectations and delivers on agreed outcomes'),
        ('Working Relationship', 'Brings a constructive and solution-oriented approach to shared work'),
    ]
    for category, question_text in direct_questions:
        is_open = question_text.startswith('How ') or question_text.startswith('What ')
        q = FeedbackQuestion(
            category=category,
            question_text=question_text,
            is_for_managers=False,
            is_open_ended=is_open,
            question_scope='direct',
            is_active=True
        )
        questions.append(q)
        db.session.add(q)

    return questions

if __name__ == '__main__':
    seed_all_data()
