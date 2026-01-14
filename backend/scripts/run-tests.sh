#!/usr/bin/env bash
set -euo pipefail

# Run backend tests with JJ mock server
# If JJ_MOCK_URL is not set, starts a temporary JJ server

cd "$(dirname "$0")/.."

JJ_PORT="${JJ_PORT:-8080}"
JJ_MOCK_URL="${JJ_MOCK_URL:-http://localhost:$JJ_PORT}"
STARTED_JJ=false

# Check if JJ mock server is already running
check_jj_server() {
    curl -s -o /dev/null -w "%{http_code}" "$JJ_MOCK_URL/" 2>/dev/null | grep -q "200\|404" && return 0 || return 1
}

# Start JJ mock server in background
start_jj_server() {
    echo "Starting JJ mock server on port $JJ_PORT..."
    uv run jj --port "$JJ_PORT" &
    JJ_PID=$!
    STARTED_JJ=true
    
    # Wait for server to be ready (max 10 seconds)
    for i in {1..20}; do
        if check_jj_server; then
            echo "JJ mock server started (PID: $JJ_PID)"
            return 0
        fi
        sleep 0.5
    done
    
    echo "ERROR: Failed to start JJ mock server"
    kill $JJ_PID 2>/dev/null || true
    return 1
}

# Cleanup function
cleanup() {
    if [ "$STARTED_JJ" = true ] && [ -n "${JJ_PID:-}" ]; then
        echo "Stopping JJ mock server (PID: $JJ_PID)..."
        kill $JJ_PID 2>/dev/null || true
        wait $JJ_PID 2>/dev/null || true
    fi
}

# Set trap for cleanup
trap cleanup EXIT

# Check if JJ server is available, start one if not
if ! check_jj_server; then
    start_jj_server || exit 1
fi

# Export JJ_MOCK_URL for tests
export JJ_MOCK_URL

# Run unit tests (fast, run on every commit)
echo "Running unit tests..."
uv run vedro run scenarios/unit/ scenarios/models/ scenarios/core/ --fail-fast

echo "All tests passed!"
