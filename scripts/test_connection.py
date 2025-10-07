"""
Test PostgreSQL Connection Script

This script tests if Django can connect to PostgreSQL successfully.
Run this BEFORE starting the migration process.

Usage:
    python scripts/postgres_migration/test_connection.py
"""

import os
import sys
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

# Load environment variables
from dotenv import load_dotenv

load_dotenv()

print("=" * 60)
print("PostgreSQL Connection Test")
print("=" * 60)

# Check if DATABASE_URL is set
database_url = os.getenv("DATABASE_URL", "")
print(
    f"\n📋 DATABASE_URL: {database_url[:50]}..."
    if len(database_url) > 50
    else f"\n📋 DATABASE_URL: {database_url}"
)

if not database_url:
    print("❌ DATABASE_URL environment variable is not set!")
    print("\nPlease add to .env file:")
    print("DATABASE_URL=postgresql://postgres:postgres@localhost:5432/postgres")
    sys.exit(1)

if not database_url.startswith("postgresql://"):
    print(f"⚠️  WARNING: DATABASE_URL does not start with 'postgresql://'")
    print(f"   Current value: {database_url}")
    sys.exit(1)

print("✅ DATABASE_URL is configured for PostgreSQL")

# Setup Django
print("\n🔧 Setting up Django...")
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "admin_portal_server.settings")

try:
    import django

    django.setup()
    print("✅ Django setup successful")
except Exception as e:
    print(f"❌ Django setup failed: {e}")
    sys.exit(1)

# Check psycopg installation
print("\n📦 Checking psycopg installation...")
try:
    import psycopg

    print(f"✅ psycopg installed (version: {psycopg.__version__})")
except ImportError:
    print("❌ psycopg not installed!")
    print("\nPlease install:")
    print("pip install psycopg[binary]==3.2.3")
    sys.exit(1)

# Test database connection
print("\n🔌 Testing database connection...")
from django.db import connection

try:
    with connection.cursor() as cursor:
        # Test basic query
        cursor.execute("SELECT version();")
        version = cursor.fetchone()[0]
        print(f"✅ Connected to PostgreSQL!")
        print(f"   Version: {version.split(',')[0]}")

        # Get database name
        cursor.execute("SELECT current_database();")
        db_name = cursor.fetchone()[0]
        print(f"   Database: {db_name}")

        # Get username
        cursor.execute("SELECT current_user;")
        username = cursor.fetchone()[0]
        print(f"   User: {username}")

        # Test table creation permission
        cursor.execute(
            """
            SELECT has_schema_privilege(current_user, 'public', 'CREATE');
        """
        )
        can_create = cursor.fetchone()[0]
        if can_create:
            print(f"   Permissions: ✅ Can create tables")
        else:
            print(f"   Permissions: ❌ Cannot create tables")
            print("   Please grant CREATE privileges to the user")

except Exception as e:
    print(f"❌ Connection failed: {e}")
    print("\nTroubleshooting:")
    print("1. Check if PostgreSQL is running:")
    print("   Get-Process -Name postgres")
    print("2. Check if PostgreSQL is listening on the correct port:")
    print("   netstat -ano | findstr :5432")
    print("3. Verify credentials in .env file")
    print("4. Check pg_hba.conf for authentication settings")
    sys.exit(1)

# Test Django database settings
print("\n⚙️  Checking Django database settings...")
from django.conf import settings

db_config = settings.DATABASES["default"]
print(f"   Engine: {db_config['ENGINE']}")
print(f"   Host: {db_config.get('HOST', 'localhost')}")
print(f"   Port: {db_config.get('PORT', '5432')}")
print(f"   Name: {db_config.get('NAME', 'N/A')}")

if "postgresql" not in db_config["ENGINE"]:
    print("⚠️  WARNING: Django is not configured for PostgreSQL!")
    sys.exit(1)

print("✅ Django is configured for PostgreSQL")

# Check for existing tables
print("\n📊 Checking database state...")
try:
    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT COUNT(*)
            FROM information_schema.tables
            WHERE table_schema = 'public';
        """
        )
        table_count = cursor.fetchone()[0]

        if table_count == 0:
            print(f"   Tables: {table_count} (Fresh database - ready for migration)")
        else:
            print(f"   Tables: {table_count} (Database has existing tables)")
            print("   ⚠️  Consider running reset_database.py for a clean start")

except Exception as e:
    print(f"   Could not check tables: {e}")

# Success summary
print("\n" + "=" * 60)
print("✅ All Connection Tests Passed!")
print("=" * 60)
print("\nYou can now proceed with migration:")
print("1. python scripts/postgres_migration/reset_database.py (if needed)")
print("2. Remove old migration files")
print("3. python manage.py makemigrations")
print("4. python manage.py migrate")

sys.exit(0)
