#!/bin/bash

# Shell script to remove all migration files except __init__.py
# Usage: ./remove_old_migrations.sh [apps_directory]

set -e  # Exit on any error

# Default apps directory (can be overridden by argument)
APPS_DIR="${1:-apps}"

echo "🗑️  Removing old migration files..."

# Check if apps directory exists
if [ ! -d "$APPS_DIR" ]; then
    echo "❌ Error: Directory '$APPS_DIR' not found!"
    echo "Usage: $0 [apps_directory]"
    echo "Example: $0 apps"
    exit 1
fi

echo "📂 Scanning directory: $APPS_DIR"

# Find all migration directories
MIGRATION_DIRS=$(find "$APPS_DIR" -type d -name "migrations" 2>/dev/null)

if [ -z "$MIGRATION_DIRS" ]; then
    echo "ℹ️  No migration directories found in '$APPS_DIR'"
    exit 0
fi

TOTAL_REMOVED=0

# Process each migration directory
while IFS= read -r migration_dir; do
    echo ""
    echo "📁 Processing: $migration_dir"

    # Find and remove migration files (excluding __init__.py)
    FILES_TO_REMOVE=$(find "$migration_dir" -maxdepth 1 -type f -name "*.py" ! -name "__init__.py" 2>/dev/null)

    if [ -n "$FILES_TO_REMOVE" ]; then
        while IFS= read -r file; do
            echo "   Removing: $(basename "$file")"
            rm -f "$file"
            TOTAL_REMOVED=$((TOTAL_REMOVED + 1))
        done <<< "$FILES_TO_REMOVE"
    else
        echo "   ℹ️  No migration files to remove"
    fi
done <<< "$MIGRATION_DIRS"

echo ""
echo "✅ Removed $TOTAL_REMOVED migration files"
echo "📝 __init__.py files were kept"
echo ""
echo "🔄 Next steps:"
echo "   1. Run: python manage.py makemigrations"
echo "   2. Run: python manage.py migrate"

# Make the script executable
chmod +x "$0" 2>/dev/null || true