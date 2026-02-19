# MySQL Setup Guide

## Quick Fix for "Access Denied" Error

The error you're seeing means the application can't connect to MySQL because the credentials are incorrect. Follow these steps:

## Step 1: Update Your .env File

1. Open the `.env` file in the project root
2. Update the `DATABASE_URL` line with your actual MySQL credentials:

```env
DATABASE_URL=mysql+pymysql://YOUR_MYSQL_USERNAME:YOUR_MYSQL_PASSWORD@localhost/employee_evaluation?charset=utf8mb4
```

**Common MySQL usernames:**
- `root` (default admin user)
- Or a custom user you created

**Replace:**
- `YOUR_MYSQL_USERNAME` with your MySQL username (often `root`)
- `YOUR_MYSQL_PASSWORD` with your MySQL password

## Step 2: Create the Database (if not exists)

Connect to MySQL using MySQL Command Line Client or MySQL Workbench and run:

```sql
CREATE DATABASE IF NOT EXISTS employee_evaluation CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
```

## Step 3: Verify MySQL is Running

Make sure MySQL service is running:
- **Windows**: Check Services (services.msc) for "MySQL" service
- Or use MySQL Workbench to connect

## Step 4: Test Connection

You can test your MySQL connection with this Python script:

```python
import pymysql

try:
    connection = pymysql.connect(
        host='localhost',
        user='root',  # Replace with your username
        password='your_password',  # Replace with your password
        database='employee_evaluation'
    )
    print("✓ Connection successful!")
    connection.close()
except Exception as e:
    print(f"✗ Connection failed: {e}")
```

## Common Issues

### Issue 1: Forgot MySQL Root Password

**Windows (MySQL 8.0+):**
1. Stop MySQL service
2. Create a text file `C:\mysql-init.txt` with:
   ```
   ALTER USER 'root'@'localhost' IDENTIFIED BY 'newpassword';
   ```
3. Start MySQL with: `mysqld --init-file=C:\mysql-init.txt`
4. After it starts, delete the init file

**Or use MySQL Installer to reset password**

### Issue 2: MySQL User Doesn't Have Permissions

If using a non-root user, grant permissions:

```sql
GRANT ALL PRIVILEGES ON employee_evaluation.* TO 'your_username'@'localhost';
FLUSH PRIVILEGES;
```

### Issue 3: MySQL Not Running

- **Windows**: Open Services (Win+R, type `services.msc`), find MySQL service, start it
- Or use MySQL Workbench to start the server

## Example .env Configuration

If your MySQL:
- Username: `root`
- Password: `mypassword123`
- Database: `employee_evaluation`

Your `.env` file should have:

```env
DATABASE_URL=mysql+pymysql://root:mypassword123@localhost/employee_evaluation?charset=utf8mb4
```

**Note:** If your password contains special characters, you may need to URL-encode them:
- `@` becomes `%40`
- `#` becomes `%23`
- `$` becomes `%24`
- etc.

## After Updating .env

1. Save the `.env` file
2. Restart your Flask application
3. The database tables will be created automatically on first run
