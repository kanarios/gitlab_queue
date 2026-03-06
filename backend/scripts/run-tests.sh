#!/usr/bin/env bash
set -euo pipefail

# Run backend tests

cd "$(dirname "$0")/.."

# Run unit tests (fast, run on every commit)
echo "Running unit tests..."
uv run vedro run scenarios/unit/ scenarios/models/ scenarios/core/ --fail-fast

echo "All tests passed!"
