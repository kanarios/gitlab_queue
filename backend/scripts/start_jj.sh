#!/usr/bin/env bash
set -euo pipefail

# Start JJ mock server for testing
# Requires: jj (pip install jj)

PORT="${JJ_PORT:-8080}"

cd "$(dirname "$0")/.."

echo "Starting JJ mock server on port $PORT..."
echo "Press Ctrl+C to stop"

# Run JJ mock server
uv run jj --port "$PORT"
