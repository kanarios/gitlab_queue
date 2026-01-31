#!/bin/bash
# Pre-push hook for Alembic migration checks
# Install: ln -sf ../../scripts/pre-push-check.sh .git/hooks/pre-push

set -e -o pipefail

cd "$(git rev-parse --show-toplevel)/backend"

echo "Checking Alembic migrations..."

# Check for single head (count only revision lines, not log output)
HEADS=$(alembic heads 2>/dev/null | grep -cE '^[a-f0-9]+ ' || echo "0")
if [ "$HEADS" -ne 1 ]; then
    echo "ERROR: Multiple Alembic heads detected!"
    alembic heads
    echo "Run: alembic merge heads -m 'merge heads'"
    exit 1
fi
echo "✓ Single Alembic head"

echo "All pre-push checks passed!"
