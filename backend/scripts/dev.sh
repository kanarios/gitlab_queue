#!/usr/bin/env bash
set -euo pipefail

# Development script with hot reload
# Requires: uv, watchfiles

cd "$(dirname "$0")/.."

echo "Starting gitlab_queue in development mode..."
echo "Press Ctrl+C to stop"

# Use watchfiles for hot reload if available
if uv run python -c "import watchfiles" 2>/dev/null; then
    uv run watchfiles --filter python "python -m gitlab_queue" src/
else
    echo "Note: Install watchfiles for auto-reload: uv add --dev watchfiles"
    uv run python -m gitlab_queue
fi
