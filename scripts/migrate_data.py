"""
MySQL to PostgreSQL Data Migration Script

This script migrates data from MySQL to PostgreSQL.
It handles the data transfer while Django migrations handle the schema.

Prerequisites:
1. PostgreSQL database must be set up with migrations applied
2. MySQL database must be accessible
3. Both mysqlclient and psycopg must be installed

Usage:
    python scripts/postgres_migration/migrate_data.py [options]

Options:
    --mysql-url     MySQL connection URL (default: from DATABASE_MYSQL_URL env var)
    --postgres-url  PostgreSQL connection URL (default: from DATABASE_POSTGRES_URL env var)
    --batch-size    Number of records per batch (default: 1000)
    --tables        Comma-separated list of tables to migrate (default: all)
    --dry-run       Preview migration without making changes
    --skip-tables   Comma-separated list of tables to skip

Environment Variables:
    DATABASE_MYSQL_URL     - Source MySQL database URL
    DATABASE_POSTGRES_URL  - Destination PostgreSQL database URL

Example .env.mysql file:
    DATABASE_MYSQL_URL=mysql://root:root@127.0.0.1:3306/ariya_dev
    DATABASE_POSTGRES_URL=postgresql://postgres:postgres@localhost:5432/postgres

Example:
    python scripts/postgres_migration/migrate_data.py --dry-run
    python scripts/postgres_migration/migrate_data.py --batch-size=500
    python scripts/postgres_migration/migrate_data.py --tables=auth_user,adminportal_company
"""

import os
import sys
import time
import argparse
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any, Optional

# Add project root to Python path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

# Load environment variables
from dotenv import load_dotenv

load_dotenv()

print("=" * 80)
print("MySQL to PostgreSQL Data Migration")
print("=" * 80)


class DatabaseConnection:
    """Wrapper for database connections"""

    def __init__(self, db_type: str, connection_string: str):
        self.db_type = db_type
        self.connection_string = connection_string
        self.connection = None
        self.cursor = None

    def connect(self):
        """Establish database connection"""
        if self.db_type == "mysql":
            import MySQLdb
            from urllib.parse import urlparse

            parsed = urlparse(self.connection_string)
            self.connection = MySQLdb.connect(
                host=parsed.hostname or "localhost",
                port=parsed.port or 3306,
                user=parsed.username or "root",
                passwd=parsed.password or "",
                db=parsed.path.lstrip("/") if parsed.path else "",
                charset="utf8mb4",
            )
        elif self.db_type == "postgresql":
            import psycopg

            self.connection = psycopg.connect(self.connection_string)

        self.cursor = self.connection.cursor()
        print(f"✅ Connected to {self.db_type.upper()}")

    def close(self):
        """Close database connection"""
        if self.cursor:
            self.cursor.close()
        if self.connection:
            self.connection.close()
        print(f"🔌 Disconnected from {self.db_type.upper()}")

    def execute(self, query: str, params: Optional[tuple] = None):
        """Execute a query"""
        if params:
            self.cursor.execute(query, params)
        else:
            self.cursor.execute(query)
        return self.cursor

    def fetchall(self):
        """Fetch all results"""
        return self.cursor.fetchall()

    def fetchone(self):
        """Fetch one result"""
        return self.cursor.fetchone()

    def commit(self):
        """Commit transaction"""
        self.connection.commit()

    def rollback(self):
        """Rollback transaction"""
        self.connection.rollback()


class DataMigrator:
    """Main data migration class"""

    def __init__(
        self,
        mysql_url: str,
        postgres_url: str,
        batch_size: int = 1000,
        dry_run: bool = False,
    ):
        self.mysql_url = mysql_url
        self.postgres_url = postgres_url
        self.batch_size = batch_size
        self.dry_run = dry_run
        self.mysql_conn = None
        self.postgres_conn = None
        self.stats = {
            "tables_migrated": 0,
            "tables_skipped": 0,
            "total_rows": 0,
            "failed_tables": [],
        }

    def connect_databases(self):
        """Connect to both databases"""
        print("\n📡 Connecting to databases...")

        self.mysql_conn = DatabaseConnection("mysql", self.mysql_url)
        self.mysql_conn.connect()

        self.postgres_conn = DatabaseConnection("postgresql", self.postgres_url)
        self.postgres_conn.connect()

    def disconnect_databases(self):
        """Disconnect from both databases"""
        print("\n🔌 Closing connections...")
        if self.mysql_conn:
            self.mysql_conn.close()
        if self.postgres_conn:
            self.postgres_conn.close()

    def get_tables(
        self,
        include_tables: Optional[List[str]] = None,
        exclude_tables: Optional[List[str]] = None,
    ) -> List[str]:
        """Get list of tables to migrate"""
        print("\n📋 Fetching table list...")

        # Get all tables from MySQL
        self.mysql_conn.execute(
            """
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = DATABASE()
            AND table_type = 'BASE TABLE'
            ORDER BY table_name
        """
        )

        all_tables = [row[0] for row in self.mysql_conn.fetchall()]

        # Filter tables
        if include_tables:
            tables = [t for t in all_tables if t in include_tables]
        else:
            tables = all_tables

        # Exclude tables
        if exclude_tables:
            tables = [t for t in tables if t not in exclude_tables]

        # Always exclude Django system tables that shouldn't be migrated
        system_tables = [
            "django_migrations",  # Migrations are regenerated
            "django_session",  # Sessions are temporary
            "django_admin_log",  # Can be regenerated
        ]
        tables = [t for t in tables if t not in system_tables]

        print(f"✅ Found {len(tables)} tables to migrate")
        return tables

    def get_table_info(self, table_name: str) -> Dict[str, Any]:
        """Get table structure information"""
        # Get column information
        self.mysql_conn.execute(
            f"""
            SELECT COLUMN_NAME, DATA_TYPE, IS_NULLABLE, COLUMN_KEY
            FROM information_schema.COLUMNS
            WHERE TABLE_SCHEMA = DATABASE()
            AND TABLE_NAME = %s
            ORDER BY ORDINAL_POSITION
        """,
            (table_name,),
        )

        columns = []
        primary_keys = []

        for row in self.mysql_conn.fetchall():
            col_name, data_type, is_nullable, column_key = row
            columns.append(col_name)
            if column_key == "PRI":
                primary_keys.append(col_name)

        # Get row count
        self.mysql_conn.execute(f"SELECT COUNT(*) FROM `{table_name}`")
        row_count = self.mysql_conn.fetchone()[0]

        return {
            "columns": columns,
            "primary_keys": primary_keys,
            "row_count": row_count,
        }

    def migrate_table(self, table_name: str) -> bool:
        """Migrate a single table"""
        try:
            print(f"\n📦 Migrating table: {table_name}")

            # Get table info
            table_info = self.get_table_info(table_name)
            columns = table_info["columns"]
            row_count = table_info["row_count"]

            print(f"   Columns: {len(columns)}")
            print(f"   Rows: {row_count:,}")

            if row_count == 0:
                print(f"   ⏭️  Skipping empty table")
                self.stats["tables_skipped"] += 1
                return True

            if self.dry_run:
                print(f"   🔍 [DRY RUN] Would migrate {row_count:,} rows")
                self.stats["tables_migrated"] += 1
                self.stats["total_rows"] += row_count
                return True

            # Check if table exists in PostgreSQL
            self.postgres_conn.execute(
                """
                SELECT EXISTS (
                    SELECT FROM information_schema.tables
                    WHERE table_schema = 'public'
                    AND table_name = %s
                )
            """,
                (table_name,),
            )

            table_exists = self.postgres_conn.fetchone()[0]

            if not table_exists:
                print(f"   ⚠️  Table does not exist in PostgreSQL - skipping")
                self.stats["tables_skipped"] += 1
                return False

            # Disable triggers for faster insertion
            self.postgres_conn.execute(
                f'ALTER TABLE "{table_name}" DISABLE TRIGGER ALL'
            )

            # Migrate data in batches
            offset = 0
            migrated_rows = 0

            while offset < row_count:
                # Fetch batch from MySQL
                column_list = ", ".join([f"`{col}`" for col in columns])
                self.mysql_conn.execute(
                    f"SELECT {column_list} FROM `{table_name}` LIMIT %s OFFSET %s",
                    (self.batch_size, offset),
                )

                rows = self.mysql_conn.fetchall()

                if not rows:
                    break

                # Insert into PostgreSQL
                placeholders = ", ".join(["%s"] * len(columns))
                column_names = ", ".join([f'"{col}"' for col in columns])

                insert_query = f"""
                    INSERT INTO "{table_name}" ({column_names})
                    VALUES ({placeholders})
                    ON CONFLICT DO NOTHING
                """

                for row in rows:
                    try:
                        # Convert data types if needed
                        converted_row = self.convert_row_data(row)
                        self.postgres_conn.execute(insert_query, converted_row)
                    except Exception as e:
                        print(f"   ⚠️  Error inserting row: {e}")
                        continue

                self.postgres_conn.commit()

                migrated_rows += len(rows)
                offset += self.batch_size

                # Progress indicator
                progress = (migrated_rows / row_count) * 100
                print(
                    f"   Progress: {migrated_rows:,}/{row_count:,} ({progress:.1f}%)",
                    end="\r",
                )

            # Re-enable triggers
            self.postgres_conn.execute(f'ALTER TABLE "{table_name}" ENABLE TRIGGER ALL')

            # Update sequences for auto-increment fields
            self.update_sequences(table_name, table_info["primary_keys"])

            print(f"\n   ✅ Migrated {migrated_rows:,} rows")
            self.stats["tables_migrated"] += 1
            self.stats["total_rows"] += migrated_rows

            return True

        except Exception as e:
            print(f"\n   ❌ Error migrating table {table_name}: {e}")
            self.stats["failed_tables"].append(table_name)
            if not self.dry_run:
                self.postgres_conn.rollback()
            return False

    def convert_row_data(self, row: tuple) -> tuple:
        """Convert MySQL data types to PostgreSQL compatible formats"""
        converted = []
        for value in row:
            if value is None:
                converted.append(None)
            elif isinstance(value, bytes):
                # Convert binary data to string if possible
                try:
                    converted.append(value.decode("utf-8"))
                except:
                    converted.append(value)
            elif isinstance(value, datetime):
                # Ensure datetime has timezone info for PostgreSQL
                converted.append(value)
            else:
                converted.append(value)
        return tuple(converted)

    def update_sequences(self, table_name: str, primary_keys: List[str]):
        """Update PostgreSQL sequences after data migration"""
        if not primary_keys or self.dry_run:
            return

        for pk in primary_keys:
            try:
                # Check if sequence exists
                sequence_name = f"{table_name}_{pk}_seq"

                self.postgres_conn.execute(
                    f"""
                    SELECT setval(
                        pg_get_serial_sequence('"{table_name}"', '{pk}'),
                        COALESCE((SELECT MAX("{pk}") FROM "{table_name}"), 1),
                        true
                    )
                """
                )

                print(f"   🔄 Updated sequence for {pk}")
            except Exception as e:
                # Sequence might not exist (UUID fields, etc.)
                pass

    def run(
        self,
        include_tables: Optional[List[str]] = None,
        exclude_tables: Optional[List[str]] = None,
    ):
        """Run the complete migration"""
        start_time = time.time()

        try:
            # Connect to databases
            self.connect_databases()

            # Get tables to migrate
            tables = self.get_tables(include_tables, exclude_tables)

            if not tables:
                print("\n⚠️  No tables to migrate")
                return

            # Confirm migration
            if not self.dry_run:
                print(
                    f"\n⚠️  About to migrate {len(tables)} tables from MySQL to PostgreSQL"
                )
                print(f"   This will INSERT data into existing PostgreSQL tables")
                confirm = input("\nType 'yes' to continue: ")
                if confirm.lower() != "yes":
                    print("❌ Migration cancelled")
                    return

            # Migrate each table
            print(f"\n🚀 Starting migration...")
            for i, table in enumerate(tables, 1):
                print(f"\n[{i}/{len(tables)}]", end=" ")
                self.migrate_table(table)

            # Summary
            elapsed_time = time.time() - start_time
            print("\n" + "=" * 80)
            print("📊 Migration Summary")
            print("=" * 80)
            print(f"✅ Tables migrated: {self.stats['tables_migrated']}")
            print(f"⏭️  Tables skipped: {self.stats['tables_skipped']}")
            print(f"📝 Total rows migrated: {self.stats['total_rows']:,}")

            if self.stats["failed_tables"]:
                print(f"❌ Failed tables: {len(self.stats['failed_tables'])}")
                for table in self.stats["failed_tables"]:
                    print(f"   - {table}")

            print(f"⏱️  Time elapsed: {elapsed_time:.2f} seconds")

            if self.dry_run:
                print("\n🔍 This was a DRY RUN - no data was actually migrated")
            else:
                print("\n✅ Migration complete!")

        except Exception as e:
            print(f"\n❌ Migration failed: {e}")
            raise
        finally:
            self.disconnect_databases()


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description="Migrate data from MySQL to PostgreSQL",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )

    parser.add_argument(
        "--mysql-url",
        default=None,
        help="MySQL connection URL (default: from DATABASE_MYSQL_URL env var)",
    )

    parser.add_argument(
        "--postgres-url",
        default=None,
        help="PostgreSQL connection URL (default: from DATABASE_POSTGRES_URL env var)",
    )

    parser.add_argument(
        "--batch-size",
        type=int,
        default=1000,
        help="Number of records per batch (default: 1000)",
    )

    parser.add_argument(
        "--tables",
        default=None,
        help="Comma-separated list of tables to migrate (default: all)",
    )

    parser.add_argument(
        "--skip-tables", default=None, help="Comma-separated list of tables to skip"
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview migration without making changes",
    )

    args = parser.parse_args()

    # Get MySQL URL
    mysql_url = args.mysql_url
    if not mysql_url:
        # Try to load from environment variables
        mysql_env = project_root / "scripts" / "postgres_migration" / ".env.mysql"
        if mysql_env.exists():
            load_dotenv(mysql_env)
        mysql_url = os.getenv("DATABASE_MYSQL_URL")

        if not mysql_url:
            print("❌ MySQL connection URL not provided")
            print("\nProvide via:")
            print("1. --mysql-url argument")
            print("2. DATABASE_MYSQL_URL in .env.mysql file")
            print("3. Enter manually below")
            mysql_url = input("\nMySQL URL: ").strip()

            if not mysql_url:
                print("❌ MySQL URL required")
                sys.exit(1)

    # Get PostgreSQL URL
    postgres_url = args.postgres_url
    if not postgres_url:
        # Try to load from environment variables
        postgres_env = project_root / "scripts" / "postgres_migration" / ".env.mysql"
        if postgres_env.exists():
            load_dotenv(postgres_env)
        postgres_url = os.getenv("DATABASE_POSTGRES_URL")

        # Fallback to main .env file
        if not postgres_url:
            postgres_url = os.getenv("DATABASE_URL")

    if not postgres_url:
        print("❌ PostgreSQL connection URL not found")
        print("\nProvide via:")
        print("1. --postgres-url argument")
        print("2. DATABASE_POSTGRES_URL in .env.mysql file")
        print("3. DATABASE_URL in .env file")
        sys.exit(1)

    # Parse table lists
    include_tables = args.tables.split(",") if args.tables else None
    exclude_tables = args.skip_tables.split(",") if args.skip_tables else None

    # Check required packages
    try:
        import MySQLdb
    except ImportError:
        print("❌ mysqlclient not installed")
        print("Install with: pip install mysqlclient")
        sys.exit(1)

    try:
        import psycopg
    except ImportError:
        print("❌ psycopg not installed")
        print("Install with: pip install psycopg[binary]")
        sys.exit(1)

    # Run migration
    migrator = DataMigrator(
        mysql_url=mysql_url,
        postgres_url=postgres_url,
        batch_size=args.batch_size,
        dry_run=args.dry_run,
    )

    migrator.run(include_tables=include_tables, exclude_tables=exclude_tables)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n⚠️  Migration interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Fatal error: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)
