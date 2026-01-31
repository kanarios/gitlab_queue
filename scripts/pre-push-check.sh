#!/bin/bash
# Pre-push hook for Alembic migration checks
# Install: ln -sf ../../scripts/pre-push-check.sh .git/hooks/pre-push

set -e

cd "$(git rev-parse --show-toplevel)/backend"

echo "Checking Alembic migrations..."

# Check for single head
HEADS=$(alembic heads 2>/dev/null | wc -l | tr -d ' ')
if [ "$HEADS" -ne 1 ]; then
    echo "ERROR: Multiple Alembic heads detected!"
    echo "Run: alembic merge heads -m 'merge heads'"
    exit 1
fi
echo "✓ Single Alembic head"

# Check for migration files in staged changes
MIGRATION_FILES=$(git diff --cached --name-only | grep -E "migrations/versions/.*\.py$" || true)
if [ -n "$MIGRATION_FILES" ]; then
    echo "✓ Migration files detected, will be validated in CI"
fi

echo "All pre-push checks passed!"
