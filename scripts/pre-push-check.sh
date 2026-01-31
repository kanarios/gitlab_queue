#!/bin/bash
# Pre-push hook for Alembic migration checks
# Install: ln -sf ../../scripts/pre-push-check.sh .git/hooks/pre-push

set -e

cd "$(git rev-parse --show-toplevel)/backend"

echo "Checking Alembic migrations..."

# Check for single head (don't suppress errors)
HEADS=$(alembic heads | wc -l | tr -d ' ')
if [ "$HEADS" -ne 1 ]; then
    echo "ERROR: Multiple Alembic heads detected!"
    echo "Run: alembic merge heads -m 'merge heads'"
    exit 1
fi
echo "✓ Single Alembic head"

echo "All pre-push checks passed!"
