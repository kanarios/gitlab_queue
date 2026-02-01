#!/bin/bash
# Pre-push hook for Alembic migration checks
# Install: ln -sf ../../scripts/pre-push-check.sh .git/hooks/pre-push

set -e -o pipefail

cd "$(git rev-parse --show-toplevel)/backend"

echo "Checking Alembic migrations..."

# Run alembic heads and capture both output and exit status
ALEMBIC_OUTPUT=$(uv run alembic heads 2>&1) || {
    echo "ERROR: alembic command failed:"
    echo "$ALEMBIC_OUTPUT"
    exit 1
}

# Count revision lines in successful output
HEADS=$(echo "$ALEMBIC_OUTPUT" | grep -c '(head)' || true)

if [ "$HEADS" -eq 0 ]; then
    echo "ERROR: No Alembic heads found."
    echo "Check that migrations exist and alembic.ini is configured correctly."
    echo "Output:"
    echo "$ALEMBIC_OUTPUT"
    exit 1
fi

if [ "$HEADS" -gt 1 ]; then
    echo "ERROR: Multiple Alembic heads detected!"
    echo "$ALEMBIC_OUTPUT"
    echo "Run: alembic merge heads -m 'merge heads'"
    exit 1
fi

echo "✓ Single Alembic head"

echo "All pre-push checks passed!"
