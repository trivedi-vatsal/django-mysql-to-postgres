# Django MySQL to PostgreSQL Migration: The Complete Guide

This guide provides a fast, streamlined process for migrating your Django application from MySQL to PostgreSQL. It is designed to be fast, easy to use, and require minimal effort.

## ⚡ Quick Assessment

Answer these questions to choose the right migration path for you.

1. **Do you need to preserve existing data?**
    - ✅ **Yes, this is a production or staging environment.**

        → Follow **[Path B: Data Migration](#path-b-data-migration)**.
    - ❌ **No, this is for development or testing.**

        → Follow **[Path A: Fresh Migration](#path-a-fresh-migration)**.

2. **What is your goal?**
    - **To start with a clean, empty PostgreSQL database:**

        → **[Path A: Fresh Migration](#path-a-fresh-migration)**.
    - **To move all existing MySQL data to PostgreSQL:**

        → **[Path B: Data Migration](#path-b-data-migration)**.

## 🛠️ Scripts Overview

This project includes scripts to automate the migration process.

| Script | Purpose | When to Use |
| :--- | :--- | :--- |
| `test_connection.py` | Validates the Django database connection to PostgreSQL. | After configuring `settings.py`. |
| `reset_database.py` | **Deletes all data** and tables from the PostgreSQL database. | **Path A**, before running migrations. |
| `migrate_data.py` | Migrates schema and data from MySQL to PostgreSQL. | **Path B**, for the main data transfer. |
| `remove_old_migrations.sh` | Deletes old Django migration files from your apps. | After a successful migration, to clean up. |

---

## 1. Environment Setup (Required for Both Paths)

Prepare your local machine and Django project.

### Install PostgreSQL

Use your system's package manager.

```powershell
# Windows (using winget)
winget install PostgreSQL.PostgreSQL.17
```

```bash
# macOS (using Homebrew)
brew install postgresql@17
brew services start postgresql@17
```

```bash
# Linux (Ubuntu/Debian)
sudo apt update && sudo apt install postgresql-17
```

### Create Database and User

Connect to PostgreSQL and run these SQL commands:

```sql
CREATE DATABASE your_app_db;
CREATE USER your_app_user WITH PASSWORD 'your_password';
GRANT ALL PRIVILEGES ON DATABASE your_app_db TO your_app_user;
ALTER ROLE your_app_user SET client_encoding TO 'utf8';
ALTER ROLE your_app_user SET default_transaction_isolation TO 'read committed';
ALTER ROLE your_app_user SET timezone TO 'UTC';
```

### Configure Django

1. **Install the PostgreSQL driver:**

    ```bash
    pip install psycopg[binary]
    ```

2. **Update `settings.py`:**
    Replace your `DATABASES` configuration with this:

    ```python
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.postgresql',
            'NAME': 'your_app_db',
            'USER': 'your_app_user',
            'PASSWORD': 'your_password',
            'HOST': 'localhost',
            'PORT': '5432',
        }
    }
    ```

3. **Test the Connection:**
    This is a critical step to ensure your settings are correct.

    ```bash
    python scripts/test_connection.py
    ```

    > If this fails, double-check your `settings.py` and ensure the PostgreSQL server is running.

## 2. Execute Migration

Follow the steps for your chosen path.

### Path A: Fresh Migration

**Goal:** Create a new, empty database with the correct schema. Ideal for development and testing.

```mermaid
graph LR
    A[Setup Environment] --> B(Reset Database);
    B --> C(Run Django Migrations);
    C --> D(Validate);
```

1. **Reset the Database (Optional):**
    If your PostgreSQL database is not empty, run this script. **Warning: This deletes all data.**

    ```bash
    python scripts/reset_database.py
    ```

2. **Run Django Migrations:**
    This command creates your database schema in PostgreSQL.

    ```bash
    python manage.py makemigrations
    python manage.py migrate
    ```

3. **Create a Superuser (Optional):**

    ```bash
    python manage.py createsuperuser
    ```

---

### Path B: Data Migration

**Goal:** Migrate your schema and all data from MySQL to PostgreSQL. Use for production.

```mermaid
graph LR
    A[Setup Environment] --> B(Backup MySQL);
    B --> C(Run Data Migration Script);
    C --> D(Validate);
```

1. **Backup Your MySQL Database:**
    **Do not skip this critical step.**

    ```bash
    mysqldump -u username -p your_mysql_db > mysql_backup.sql
    ```

2. **Run the Data Migration Script:**
    This script handles the schema and data transfer.

    First, perform a **dry run** to check for potential issues without changing data:

    ```bash
    python scripts/migrate_data.py --dry-run
    ```

    If the dry run is successful, execute the full migration:

    ```bash
    python scripts/migrate_data.py
    ```

## 3. Validate the Migration

After migrating, verify that everything works as expected.

1. **Run Django Tests:**

    ```bash
    python manage.py test
    ```

2. **Perform a Manual Check:**
    - [ ] Can you log into the Django admin?
    - [ ] Can you create, read, update, and delete objects?
    - [ ] Are all site features working correctly?

3. **Verify Data Integrity (for Path B):**
    Check for mismatched row counts or orphaned records.

    ```sql
    -- Example: Check for orphaned records in a 'child_table'
    SELECT COUNT(*) FROM child_table c
    LEFT JOIN parent_table p ON c.parent_id = p.id
    WHERE p.id IS NULL;
    ```

## 4. Post-Migration Cleanup (Optional)

After you have confirmed the migration was successful, you can remove old Django migration files.

```bash
# For Linux/macOS or Git Bash on Windows
sh scripts/remove_old_migrations.sh
```

## 5. Troubleshooting

| Issue | Solution |
| :--- | :--- |
| **Connection Error** | Verify `settings.py`, check if PostgreSQL is running, and ensure the firewall is not blocking port 5432. |
| **Data Type Mismatch** | The `migrate_data.py` script handles most common types. For custom or rare types, you may need to use `pgloader` with a custom load file. |
| **Slow Performance** | Run `ANALYZE;` in PostgreSQL to update table statistics. Use `EXPLAIN ANALYZE` on slow queries to identify missing indexes. |
| **Foreign Key Errors** | The script attempts to migrate tables in the correct order. If you still have issues, you may need to temporarily disable triggers or manually import tables in a specific order. |

---

Migration complete! You can now run your application on PostgreSQL.
