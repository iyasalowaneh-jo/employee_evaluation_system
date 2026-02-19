# Employee Evaluation System

A comprehensive, full-featured Employee Evaluation System built with Flask, MySQL, and Bootstrap 5. This system supports 360-degree feedback, KPI tracking, automated evaluator randomization, and comprehensive dashboards for administrators, managers, and employees.

## Features

### User Roles

- **Admin**: Manage employees, KPIs, evaluation cycles, assign evaluators, view all reports
- **Manager**: View team performance, KPI averages, generate department reports
- **Employee/Evaluator**: Complete assigned evaluations, view own performance scores

### Core Functionality

1. **Employee Data Management**
   - Add employees manually or bulk upload via Excel/CSV
   - Automatic validation (duplicate emails, missing fields)
   - Department and role management

2. **KPI Management**
   - Define global or department-specific KPIs
   - Customize KPI weights
   - Role-based KPI assignment

3. **Evaluation Cycles**
   - Create and manage evaluation periods
   - Automated evaluator assignment with randomization
   - Cross-department evaluation support

4. **360-Degree Feedback**
   - Automated peer assignment (minimum 3 evaluators per employee)
   - Cross-department evaluator requirement
   - Self-assessment capability
   - Prevents repeat assignments across cycles

5. **Dynamic Evaluation Forms**
   - Auto-generated based on KPIs
   - 1-5 rating scale
   - Optional comment sections
   - Form validation

6. **Dashboards & Analytics**
   - **Admin Dashboard**: System-wide statistics, completion rates, employee metrics
   - **Manager Dashboard**: Team performance, KPI comparisons, department reports
   - **Employee Dashboard**: Personal KPI scores, evaluation assignments, progress tracking

7. **Security**
   - Password hashing with bcrypt
   - Role-based access control (RBAC)
   - Session management with Flask-Login
   - CSRF protection

## Technology Stack

- **Backend**: Flask 3.0.0
- **Database**: MySQL (SQLAlchemy ORM)
- **Frontend**: Bootstrap 5, Plotly.js
- **Data Processing**: Pandas, openpyxl
- **Authentication**: Flask-Login, bcrypt
- **Forms**: Flask-WTF, WTForms

## Installation

### Prerequisites

- Python 3.8+
- MySQL 5.7+ or MySQL 8.0+
- pip (Python package manager)

### Step 1: Clone/Download the Project

```bash
cd employee_evaluation_system
```

### Step 2: Create Virtual Environment

```bash
# Windows
python -m venv venv
venv\Scripts\activate

# Linux/Mac
python3 -m venv venv
source venv/bin/activate
```

### Step 3: Install Dependencies

```bash
pip install -r requirements.txt
```

**Note for MySQL**: The project uses `pymysql` as the MySQL connector. If you encounter issues on Windows, you may need to install MySQL C client libraries or use `mysqlclient` instead (requires Visual C++ build tools on Windows).

### Step 4: Database Setup

**Install MySQL** (if not already installed):
- Windows: Download MySQL Installer from [mysql.com](https://dev.mysql.com/downloads/installer/)
- Linux: `sudo apt-get install mysql-server` (Ubuntu/Debian) or `sudo yum install mysql-server` (CentOS/RHEL)
- Mac: `brew install mysql` or download from mysql.com

1. Start MySQL service and create a database:

1. Create a MySQL database:

```sql
CREATE DATABASE employee_evaluation CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
```

2. Create a MySQL user (if needed) and grant permissions:

```sql
CREATE USER 'eval_user'@'localhost' IDENTIFIED BY 'your_password';
GRANT ALL PRIVILEGES ON employee_evaluation.* TO 'eval_user'@'localhost';
FLUSH PRIVILEGES;
```

3. Update database configuration in `.env` file (copy from `.env.example`):

```env
DATABASE_URL=mysql+pymysql://username:password@localhost/employee_evaluation?charset=utf8mb4
SECRET_KEY=your-secret-key-here
```

**Note**: 
- Replace `username` and `password` with your MySQL credentials
- The `?charset=utf8mb4` parameter ensures proper UTF-8 support for international characters

### Step 5: Initialize Database

The database tables will be created automatically when you first run the application. The app will also create a default admin user:

- **Email**: `admin@company.com`
- **Password**: `admin123`

**⚠️ IMPORTANT**: Change the default admin password after first login!

### Step 6: Run the Application

```bash
python app.py
```

The application will start at `http://localhost:5000`

## Usage Guide

### Admin Workflow

1. **Login** with admin credentials
2. **Add Employees**:
   - Go to Admin > Employees
   - Click "Add Employee" or "Upload CSV/Excel"
   - For bulk upload, ensure CSV/Excel has columns: `full_name`, `email`, `department`, `role`, `join_date`

3. **Define KPIs**:
   - Go to Admin > KPIs
   - Click "Add KPI"
   - Set department/role (optional for global KPIs)
   - Set weight (0-100)

4. **Create Evaluation Cycle**:
   - Go to Admin > Evaluation Cycles
   - Click "Create Cycle"
   - Enter cycle name, start/end dates
   - Click "Assign Evaluators" to auto-assign evaluators

### Manager Workflow

1. **Login** as manager
2. **View Team Dashboard**: See team performance metrics
3. **Generate Reports**: Access detailed department reports

### Employee Workflow

1. **Login** with employee credentials
2. **View Assigned Evaluations**: Go to "My Evaluations"
3. **Complete Evaluations**: Fill out evaluation forms with KPI ratings (1-5) and comments
4. **Track Progress**: View completion status on dashboard

## File Structure

```
employee_evaluation_system/
├── app.py                 # Main Flask application
├── models.py              # Database models (SQLAlchemy)
├── forms.py               # WTForms form definitions
├── utils.py               # Utility functions (randomization, calculations)
├── config.py              # Configuration settings
├── requirements.txt       # Python dependencies
├── .env.example           # Environment variables template
├── README.md              # This file
├── templates/             # Jinja2 templates
│   ├── base.html
│   ├── login.html
│   ├── dashboard_admin.html
│   ├── dashboard_manager.html
│   ├── dashboard_employee.html
│   ├── admin/
│   │   ├── employees.html
│   │   ├── employee_form.html
│   │   ├── upload_employees.html
│   │   ├── kpis.html
│   │   ├── kpi_form.html
│   │   ├── cycles.html
│   │   └── cycle_form.html
│   ├── evaluations/
│   │   ├── list.html
│   │   └── form.html
│   └── reports/
│       └── department.html
├── static/                # Static files (CSS, JS, images)
│   ├── css/
│   └── js/
└── uploads/               # Uploaded files (CSV/Excel)
```

## Database Schema

### Tables

- **users**: Authentication (email, password_hash, role)
- **employees**: Employee information (name, email, department, role, manager)
- **kpis**: KPI definitions (name, description, weight, department, role)
- **evaluation_cycles**: Evaluation periods (name, start_date, end_date)
- **evaluations**: Submitted evaluations (scores JSON, comments)
- **randomization_log**: Evaluator assignments (audit trail)

## Evaluation Randomization Logic

The system automatically assigns evaluators based on:

- **Minimum evaluators**: 3 per employee (configurable)
- **Cross-department**: At least 1 evaluator from different department
- **No self-evaluation**: Excludes employee from evaluating themselves
- **Avoid repeats**: Prevents same evaluator-evaluatee pairs across cycles (configurable)

## CSV/Excel Upload Format

Required columns:
- `full_name`: Employee full name
- `email`: Unique email address
- `department`: Department name
- `role`: Job role/title
- `join_date`: Date in YYYY-MM-DD format

Optional columns:
- `status`: 'active' or 'inactive' (default: 'active')
- `manager_id`: ID of manager employee

Example CSV:
```csv
full_name,email,department,role,join_date
John Doe,john.doe@company.com,Engineering,Developer,2024-01-15
Jane Smith,jane.smith@company.com,Marketing,Manager,2023-06-20
```

## Security Considerations

1. **Change Default Passwords**: Always change default admin password
2. **Environment Variables**: Store sensitive data (SECRET_KEY, DATABASE_URL) in `.env` file (not in version control)
3. **HTTPS**: Use HTTPS in production
4. **Database Security**: Use strong database passwords and restrict access
5. **CSRF Protection**: Already enabled via Flask-WTF

## Deployment

### Production Checklist

- [ ] Set `FLASK_ENV=production`
- [ ] Use strong `SECRET_KEY`
- [ ] Configure production database
- [ ] Set up HTTPS/SSL
- [ ] Configure email server for notifications
- [ ] Use production WSGI server (Gunicorn, uWSGI)
- [ ] Set up reverse proxy (Nginx, Apache)
- [ ] Enable logging
- [ ] Set up database backups

### Using Gunicorn (Linux/Mac)

```bash
pip install gunicorn
gunicorn -w 4 -b 0.0.0.0:5000 app:app
```

## Troubleshooting

### Database Connection Error

- Verify MySQL is running
- Check `DATABASE_URL` in `.env` file (format: `mysql+pymysql://user:password@localhost/employee_evaluation`)
- Ensure database exists: `CREATE DATABASE employee_evaluation CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;`
- Verify MySQL user has proper permissions
- On Windows, if you get connection errors, try installing `mysqlclient` instead of `pymysql` (requires MySQL C client libraries)

### Import Errors

- Ensure virtual environment is activated
- Install all dependencies: `pip install -r requirements.txt`

### File Upload Issues

- Check `uploads/` directory exists and is writable
- Verify file format (CSV, XLSX, XLS)
- Check file size (max 16MB)

## Support & Documentation

For issues or questions:
1. Check this README
2. Review code comments
3. Check Flask and SQLAlchemy documentation

## License

This project is provided as-is for use in employee evaluation systems.

## Credits

Built with Flask, SQLAlchemy, Bootstrap 5, and Plotly.js.
