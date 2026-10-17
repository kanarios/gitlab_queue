#!/usr/bin/env bash
set -euo pipefail

# Run backend tests

cd "$(dirname "$0")/.."

# Run local suites, including queue and MR webhook regressions, on every commit.
echo "Running backend tests..."
uv run vedro run scenarios/unit/ scenarios/models/ scenarios/core/ scenarios/webhooks/mr_webhook/ --fail-fast

echo "All tests passed!"
