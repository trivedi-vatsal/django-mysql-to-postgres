#!/usr/bin/env python
"""
Reset PostgreSQL database by dropping all tables
"""

import os
import sys
import django
from pathlib import Path
from dotenv import load_dotenv

# Add the project root to Python path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

# Change to project root directory
os.chdir(project_root)

# Load environment variables
env_path = project_root / ".env"
if env_path.exists():
    load_dotenv(env_path)

# Set up Django environment
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "admin_portal_server.settings")
django.setup()

from django.db import connection

print("🔄 Resetting PostgreSQL database...")
print("⚠️  This will drop all tables and recreate the schema!")

response = input("Are you sure you want to continue? (yes/no): ")
if response.lower() != "yes":
    print("❌ Operation cancelled")
    sys.exit(0)

try:
    with connection.cursor() as cursor:
        print("\n🗑️  Dropping all tables...")
        cursor.execute("DROP SCHEMA public CASCADE;")
        print("✅ All tables dropped")

        print("🔨 Creating fresh schema...")
        cursor.execute("CREATE SCHEMA public;")
        print("✅ Fresh schema created")

        print("🔐 Granting permissions...")
        cursor.execute("GRANT ALL ON SCHEMA public TO postgres;")
        cursor.execute("GRANT ALL ON SCHEMA public TO public;")
        print("✅ Permissions granted")

    print("\n🎉 Database reset complete!")
    print("📝 Next steps:")
    print("   1. Delete old migration files (except __init__.py)")
    print("   2. Run: python manage.py makemigrations")
    print("   3. Run: python manage.py migrate")

except Exception as e:
    print(f"\n❌ Error resetting database: {e}")
    sys.exit(1)
