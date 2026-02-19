"""
Quick script to test MySQL connection
Run this to verify your MySQL credentials work before running the main app
"""
import pymysql
from dotenv import load_dotenv
import os

load_dotenv()

# Get database URL from .env
db_url = os.environ.get('DATABASE_URL', '')
print(f"Testing connection with: {db_url.split('@')[0]}@...")  # Hide password in output

try:
    # Parse connection string (simple parsing for mysql+pymysql://user:pass@host/db)
    if 'mysql+pymysql://' in db_url:
        # Extract parts
        url_part = db_url.replace('mysql+pymysql://', '')
        auth_part, rest = url_part.split('@', 1)
        username, password = auth_part.split(':', 1)
        host_db = rest.split('?')[0]
        if '/' in host_db:
            host, database = host_db.split('/', 1)
        else:
            host = host_db
            database = None
        
        # Decode URL-encoded password
        import urllib.parse
        password = urllib.parse.unquote(password)
        
        print(f"\nConnecting to MySQL...")
        print(f"Host: {host}")
        print(f"Username: {username}")
        print(f"Database: {database or '(will create)'}")
        
        # Test connection
        connection = pymysql.connect(
            host=host,
            user=username,
            password=password,
            charset='utf8mb4'
        )
        
        print("[OK] Connection successful!")
        
        # Check if database exists
        cursor = connection.cursor()
        cursor.execute("SHOW DATABASES LIKE 'employee_evaluation'")
        result = cursor.fetchone()
        
        if result:
            print("[OK] Database 'employee_evaluation' exists")
        else:
            print("[WARNING] Database 'employee_evaluation' does not exist")
            print("  Creating database...")
            cursor.execute("CREATE DATABASE employee_evaluation CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci")
            print("[OK] Database created successfully!")
        
        connection.close()
        print("\n[SUCCESS] All checks passed! You can now run the Flask app.")
        
except pymysql.err.OperationalError as e:
    if e.args[0] == 1045:
        print("\n[ERROR] Access denied - Wrong username or password")
        print("  Please check your .env file credentials")
    elif e.args[0] == 1049:
        print("\n[ERROR] Database does not exist")
        print("  The database will be created automatically when you run the app")
    else:
        print(f"\n[ERROR] MySQL Error: {e}")
except Exception as e:
    print(f"\n[ERROR] Error: {e}")
    print("\nTroubleshooting:")
    print("1. Make sure MySQL service is running")
    print("2. Check your .env file has correct credentials")
    print("3. Verify MySQL username and password are correct")
