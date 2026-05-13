#!/bin/bash
# ============================================================
# AILife Project - Database Migration Runner
# PostgreSQL 15 + pgvector
# ============================================================
# Usage: ./run_migrations.sh postgresql://user:pass@host:port/dbname

set -e

DATABASE_URL="${1:-$DATABASE_URL}"

if [ -z "$DATABASE_URL" ]; then
    echo "Error: Please provide a database connection string or set DATABASE_URL environment variable."
    echo "Usage: ./run_migrations.sh postgresql://user:pass@host:port/dbname"
    exit 1
fi

echo "============================================================"
echo "  AILife Database Migration"
echo "  Target: $(echo "$DATABASE_URL" | sed -E 's/:\/\/[^:]+:[^@]+/:\/\/\*\*\*:\*\*\*/')"
echo "============================================================"

# Get script directory for finding SQL files
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Execute SQL files in order
for file in $(ls *.sql | sort); do
    echo ""
    echo "[$file] Running..."
    psql "$DATABASE_URL" -f "$file" -v ON_ERROR_STOP=1
    echo "[$file] Done."
done

echo ""
echo "============================================================"
echo "  Migration completed successfully!"
echo "============================================================"
