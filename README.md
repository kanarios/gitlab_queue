# GitLab Merge Queue Bot

**Open-source alternative to GitLab Merge Trains (Premium feature)**

Automates the merge process for GitLab projects using fast-forward merge strategy, eliminating race conditions and keeping your main branch always green.

## Problem

When using fast-forward merge in GitLab, teams face a common race condition:

```
Dev A rebases → tries to merge
Dev B rebases → tries to merge
A merges first → B gets "branch out of date" error
B rebases again → while rebasing, C merges
B rebases again → endless cycle
```

Teams waste significant time on manual rebase operations.

## Solution

A bot that manages a merge queue:

1. Add `merge_queue` label to your MR
2. Bot automatically rebases your MR onto the target branch
3. Bot waits for the pipeline to pass
4. Bot merges your MR
5. Next MR in queue starts processing

No more manual rebasing. No more race conditions.

## Features

### Core
- **FIFO Queue** - First in, first out processing
- **Hotfix Priority** - MRs with `hotfix` label jump to front of queue
- **Automatic Rebase** - Rebases onto target branch before merge
- **Pipeline Waiting** - Waits for CI/CD pipeline to complete
- **Automatic Merge** - Merges when pipeline succeeds

### Reliability
- **Pipeline Retry** - Retries failed pipelines once before removing from queue
- **Conflict Detection** - Removes MRs with conflicts and notifies author
- **Circuit Breaker** - Protects against cascading failures when GitLab is down
- **Graceful Degradation** - Continues operating in degraded mode during outages
- **State Recovery** - Recovers queue state after restart

### Notifications
- **MR Comments** - Posts status updates on every state change
- **Queue Position** - Shows position and estimated wait time
- **Error Details** - Reports conflicts, failed jobs, and required actions

### Monitoring
- **Health Endpoints** - Liveness and readiness probes
- **Prometheus Metrics** - Queue length, API latency, operation counters
- **Structured Logging** - JSON logs with correlation IDs

### Webhook Integration
- **Real-time Updates** - Responds instantly to GitLab events
- **Polling Fallback** - Catches missed webhooks
- **Retry Queue** - Dead Letter Queue for failed webhook processing

## Quick Start

### Prerequisites

- Python 3.12+
- [uv](https://github.com/astral-sh/uv) package manager
- GitLab Personal Access Token with `api` scope

### Installation

```bash
# Clone the repository
git clone https://github.com/your-org/gitlab_queue.git
cd gitlab_queue/backend

# Install dependencies
uv sync
```

### Configuration

Create a `.env` file:

```bash
# Required
GITLAB_QUEUE_GITLAB_TOKEN=glpat-xxxxxxxxxxxxxxxxxxxx
GITLAB_QUEUE_GITLAB_PROJECT_ID=12345678
GITLAB_QUEUE_JWT_SECRET=$(openssl rand -hex 64)
GITLAB_QUEUE_WEBHOOK_SECRET=your-webhook-secret
```

### Run

```bash
cd backend
python -m gitlab_queue
```

The bot will start processing MRs with the `merge_queue` label.

## Configuration Reference

### Required Variables

| Variable | Description |
|----------|-------------|
| `GITLAB_QUEUE_GITLAB_TOKEN` | GitLab personal access token with `api` scope |
| `GITLAB_QUEUE_GITLAB_PROJECT_ID` | GitLab project ID (positive integer) |
| `GITLAB_QUEUE_JWT_SECRET` | JWT signing secret (min 64 chars) |
| `GITLAB_QUEUE_WEBHOOK_SECRET` | Webhook signature secret (required if webhooks enabled) |

### Optional Variables

#### GitLab Connection

| Variable | Default | Description |
|----------|---------|-------------|
| `GITLAB_QUEUE_GITLAB_URL` | `https://gitlab.com` | GitLab instance URL |
| `GITLAB_QUEUE_TARGET_BRANCH` | `master` | Target branch for merges |
| `GITLAB_QUEUE_QUEUE_LABEL` | `merge_queue` | Label to add MR to queue |
| `GITLAB_QUEUE_HOTFIX_LABEL` | `hotfix` | Label for priority processing |

#### Timing

| Variable | Default | Description |
|----------|---------|-------------|
| `GITLAB_QUEUE_POLL_INTERVAL_SECONDS` | `30` | Polling interval for fallback sync |
| `GITLAB_QUEUE_PIPELINE_TIMEOUT_SECONDS` | `7200` | Max pipeline wait time (2 hours) |
| `GITLAB_QUEUE_REBASE_TIMEOUT_SECONDS` | `300` | Max rebase wait time (5 minutes) |
| `GITLAB_QUEUE_STALE_MR_WARNING_HOURS` | `24` | Warn about stuck MRs after this time |

#### Retry Logic

| Variable | Default | Description |
|----------|---------|-------------|
| `GITLAB_QUEUE_PIPELINE_RETRY_COUNT` | `1` | Retry failed pipelines this many times |
| `GITLAB_QUEUE_API_MAX_RETRIES` | `5` | Max retries for API calls |

#### Rate Limiting

| Variable | Default | Description |
|----------|---------|-------------|
| `GITLAB_QUEUE_RATE_LIMIT_WARNING_THRESHOLD` | `0.8` | Warn at 80% of rate limit |
| `GITLAB_QUEUE_RATE_LIMIT_THROTTLE_DELAY_SECONDS` | `1.0` | Delay when throttling |
| `GITLAB_QUEUE_RATE_LIMIT_CRITICAL_THRESHOLD` | `0.95` | Critical at 95% of rate limit |

#### Circuit Breaker

| Variable | Default | Description |
|----------|---------|-------------|
| `GITLAB_QUEUE_CIRCUIT_BREAKER_FAILURE_THRESHOLD` | `5` | Failures before circuit opens |
| `GITLAB_QUEUE_CIRCUIT_BREAKER_HALF_OPEN_TIMEOUT_SECONDS` | `30` | Wait before retry attempt |
| `GITLAB_QUEUE_CIRCUIT_BREAKER_SUCCESS_THRESHOLD` | `1` | Successes to close circuit |

#### Webhook Retry Queue

| Variable | Default | Description |
|----------|---------|-------------|
| `GITLAB_QUEUE_WEBHOOK_RETRY_MAX_ATTEMPTS` | `3` | Max retry attempts |
| `GITLAB_QUEUE_WEBHOOK_RETRY_BASE_DELAY_SECONDS` | `30` | Initial backoff delay |
| `GITLAB_QUEUE_WEBHOOK_RETRY_MAX_DELAY_SECONDS` | `300` | Max backoff delay (5 min) |
| `GITLAB_QUEUE_WEBHOOK_DLQ_RETENTION_DAYS` | `30` | Keep failed events for 30 days |

#### Database

| Variable | Default | Description |
|----------|---------|-------------|
| `GITLAB_QUEUE_DATABASE_URL` | `sqlite+aiosqlite:///data/queue.db` | Database connection URL |

#### Server

| Variable | Default | Description |
|----------|---------|-------------|
| `GITLAB_QUEUE_WEBHOOK_ENABLED` | `true` | Enable webhook server |
| `GITLAB_QUEUE_WEBHOOK_HOST` | `127.0.0.1` | Server bind address |
| `GITLAB_QUEUE_WEBHOOK_PORT` | `8080` | Server port |
| `GITLAB_QUEUE_DASHBOARD_ENABLED` | `true` | Enable dashboard API |
| `GITLAB_QUEUE_CORS_ORIGINS` | `http://localhost:5173` | Allowed CORS origins |

#### OAuth (Optional - for Dashboard Authentication)

| Variable | Default | Description |
|----------|---------|-------------|
| `GITLAB_QUEUE_OAUTH_CLIENT_ID` | - | GitLab OAuth Application ID |
| `GITLAB_QUEUE_OAUTH_CLIENT_SECRET` | - | GitLab OAuth Application Secret |
| `GITLAB_QUEUE_OAUTH_REDIRECT_URI` | - | OAuth callback URL (e.g., `https://your-domain.com/auth/callback`) |

See [Configure OAuth Application](#5-configure-oauth-application-optional---for-dashboard) for setup instructions.

#### Logging

| Variable | Default | Description |
|----------|---------|-------------|
| `GITLAB_QUEUE_LOG_LEVEL` | `INFO` | Log level (DEBUG, INFO, WARNING, ERROR) |
| `GITLAB_QUEUE_LOG_FORMAT` | `json` | Log format (json or console) |

### Example `.env` File

```bash
# Required
GITLAB_QUEUE_GITLAB_TOKEN=glpat-xxxxxxxxxxxxxxxxxxxx
GITLAB_QUEUE_GITLAB_PROJECT_ID=12345678
GITLAB_QUEUE_JWT_SECRET=your-64-char-secret-key-here-generate-with-openssl-rand-hex-64
GITLAB_QUEUE_WEBHOOK_SECRET=your-webhook-secret

# Optional - customize as needed
GITLAB_QUEUE_GITLAB_URL=https://gitlab.example.com
GITLAB_QUEUE_TARGET_BRANCH=main
GITLAB_QUEUE_QUEUE_LABEL=merge_queue
GITLAB_QUEUE_HOTFIX_LABEL=hotfix
GITLAB_QUEUE_LOG_LEVEL=INFO
GITLAB_QUEUE_LOG_FORMAT=json
```

## GitLab Setup

### 1. Create Personal Access Token

1. Go to GitLab → User Settings → Access Tokens
2. Create token with `api` scope
3. Set `GITLAB_QUEUE_GITLAB_TOKEN` to the token value

### 2. Find Project ID

1. Go to your project → Settings → General
2. Project ID is shown at the top
3. Set `GITLAB_QUEUE_GITLAB_PROJECT_ID` to this value

### 3. Configure Webhook

1. Go to your project → Settings → Webhooks
2. Add new webhook:
   - **URL**: `https://your-bot-domain.com/webhooks/gitlab`
   - **Secret token**: Same value as `GITLAB_QUEUE_WEBHOOK_SECRET`
   - **Trigger**: Check "Merge request events" and "Pipeline events"
   - **SSL verification**: Enable if using HTTPS
3. Click "Add webhook"

### 4. Protected Branch Settings (Recommended)

1. Go to project → Settings → Repository → Protected Branches
2. For your target branch (e.g., `main`):
   - **Allowed to merge**: Maintainers (or your preference)
   - **Allowed to push**: No one (prevents direct pushes)
   - **Allowed to force push**: Disabled

### 5. Configure OAuth Application (Optional - for Dashboard)

To enable dashboard authentication with GitLab OAuth:

1. Go to GitLab → User Settings → Applications (or Admin → Applications for instance-wide)
2. Create a new application:
   - **Name**: `Merge Queue Bot Dashboard`
   - **Redirect URI**: `https://your-bot-domain.com/auth/callback`
   - **Confidential**: Yes (checked)
   - **Scopes**: Check `read_user` and `read_api`
3. Click "Save application"
4. Copy the **Application ID** and **Secret**
5. Set environment variables:
   ```bash
   GITLAB_QUEUE_OAUTH_CLIENT_ID=your-application-id
   GITLAB_QUEUE_OAUTH_CLIENT_SECRET=your-application-secret
   GITLAB_QUEUE_OAUTH_REDIRECT_URI=https://your-bot-domain.com/auth/callback
   ```

**Required OAuth Scopes:**

| Scope | Purpose |
|-------|---------|
| `read_user` | Access user profile (username, email, avatar) |
| `read_api` | Verify user has access to the project |

**Note:** OAuth is optional. If not configured, the dashboard API will be accessible without authentication. For production deployments, OAuth is strongly recommended.

## Deployment

### Local Development

```bash
cd backend

# Install dependencies
uv sync

# Set environment variables
export GITLAB_QUEUE_GITLAB_TOKEN="glpat-xxxx"
export GITLAB_QUEUE_GITLAB_PROJECT_ID="12345"
export GITLAB_QUEUE_JWT_SECRET="$(openssl rand -hex 64)"
export GITLAB_QUEUE_WEBHOOK_SECRET="dev-secret"
export GITLAB_QUEUE_WEBHOOK_HOST="0.0.0.0"  # Allow external connections

# Run
python -m gitlab_queue
```

For webhook testing locally, use a tunnel like ngrok:

```bash
ngrok http 8080
# Use the ngrok URL as your webhook URL in GitLab
```

### Docker

```bash
# Build image
docker build -f docker/Dockerfile.backend -t gitlab-queue:latest backend/

# Run container
docker run -d \
  --name gitlab-queue \
  -p 8080:8080 \
  -v gitlab-queue-data:/app/data \
  -e GITLAB_QUEUE_GITLAB_TOKEN=glpat-xxxx \
  -e GITLAB_QUEUE_GITLAB_PROJECT_ID=12345 \
  -e GITLAB_QUEUE_JWT_SECRET=your-secret \
  -e GITLAB_QUEUE_WEBHOOK_SECRET=webhook-secret \
  -e GITLAB_QUEUE_WEBHOOK_HOST=0.0.0.0 \
  gitlab-queue:latest
```

### Docker Compose

```bash
cd docker

# Create .env file in backend/ directory
cp ../backend/.env.example ../backend/.env
# Edit .env with your values

# Start
docker-compose up -d

# View logs
docker-compose logs -f

# Stop
docker-compose down
```

### Kubernetes (Hints)

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: gitlab-queue
spec:
  replicas: 1  # Single instance per project
  template:
    spec:
      containers:
      - name: gitlab-queue
        image: gitlab-queue:latest
        ports:
        - containerPort: 8080
        envFrom:
        - secretRef:
            name: gitlab-queue-secrets
        livenessProbe:
          httpGet:
            path: /health
            port: 8080
          initialDelaySeconds: 10
          periodSeconds: 30
        readinessProbe:
          httpGet:
            path: /ready
            port: 8080
          initialDelaySeconds: 5
          periodSeconds: 10
        volumeMounts:
        - name: data
          mountPath: /app/data
      volumes:
      - name: data
        persistentVolumeClaim:
          claimName: gitlab-queue-data
```

## API Reference

### Health Endpoints

```bash
# Liveness probe - always returns 200 if process is alive
curl http://localhost:8080/health

# Readiness probe - returns 503 if not ready to accept traffic
curl http://localhost:8080/ready

# Detailed health - component status breakdown
curl http://localhost:8080/health/detailed

# Prometheus metrics
curl http://localhost:8080/metrics
```

### Webhook Endpoint

```bash
# GitLab sends webhooks here
POST /webhooks/gitlab
Headers:
  X-Gitlab-Token: your-webhook-secret
  Content-Type: application/json
```

### Dashboard API

```bash
# Get full queue status (active queue + history + stats)
curl http://localhost:8080/api/queue

# Get only active queue items
curl http://localhost:8080/api/queue/active

# Get only statistics
curl http://localhost:8080/api/queue/stats

# Get specific MR status
curl http://localhost:8080/api/queue/123
```

### Dead Letter Queue API

```bash
# List DLQ entries
curl http://localhost:8080/api/dlq

# Get DLQ statistics
curl http://localhost:8080/api/dlq/stats

# Get single DLQ entry
curl http://localhost:8080/api/dlq/{entry_id}

# Retry a DLQ entry
curl -X POST http://localhost:8080/api/dlq/{entry_id}/retry

# Delete a DLQ entry
curl -X DELETE http://localhost:8080/api/dlq/{entry_id}
```

## Architecture

### Component Overview

```
                                    ┌─────────────────┐
                                    │    GitLab       │
                                    │    Server       │
                                    └────────┬────────┘
                                             │
                    ┌────────────────────────┼────────────────────────┐
                    │                        │                        │
                    ▼                        ▼                        │
            ┌───────────────┐       ┌───────────────┐                 │
            │   Webhooks    │       │  Polling      │                 │
            │   /webhooks/* │       │  Scheduler    │                 │
            └───────┬───────┘       └───────┬───────┘                 │
                    │                       │                         │
                    └───────────┬───────────┘                         │
                                │                                     │
                                ▼                                     │
                    ┌───────────────────────┐                         │
                    │    Queue Manager      │◄────────────────────────┤
                    │    (SQLite)           │                         │
                    └───────────┬───────────┘                         │
                                │                                     │
                                ▼                                     │
                    ┌───────────────────────┐                         │
                    │     Processor         │─────────────────────────┘
                    │  (State Machine)      │
                    └───────────┬───────────┘
                                │
                                ▼
                    ┌───────────────────────┐
                    │     Notifier          │
                    │  (MR Comments)        │
                    └───────────────────────┘
```

### State Machine

```
┌────────┐    label    ┌────────┐   ┌─────────┐   ┌─────────┐   ┌────────┐
│  new   │ ──added──→  │ queued │ ─→│rebasing │ ─→│ testing │ ─→│merging │
└────────┘             └────────┘   └─────────┘   └─────────┘   └────────┘
                            ↑            │              │            │
                            │            │              │            │
                            │      ┌─────↓──────┐       │            │
                            │      │   failed   │←──────┘            │
                            │      │(conflicts) │                    │
                            │      └────────────┘                    │
                            │                                        ↓
                            │                                  ┌─────────┐
                            └──────────────────────────────────│ merged  │
                                                               └─────────┘
```

### Key Design Decisions

1. **Single Project per Instance** - Deploy one bot per GitLab project for isolation
2. **SQLite Storage** - Simple, single-file database for queue and history
3. **Webhook-Primary** - Real-time updates via webhooks, polling as fallback
4. **Non-Interrupting Hotfix** - Hotfix jumps queue but doesn't interrupt current processing
5. **Mandatory MR Feedback** - Every state change posts a comment to the MR

## Monitoring

### Health Check Usage

```bash
# For Docker health check
HEALTHCHECK --interval=30s --timeout=10s --retries=3 \
  CMD curl -f http://localhost:8080/health || exit 1

# For load balancer
# Use /ready for traffic routing decisions
# Use /health for container lifecycle
```

### Prometheus Metrics

| Metric | Type | Description |
|--------|------|-------------|
| `merge_queue_length` | Gauge | Current queue length |
| `merge_queue_mr_duration_seconds` | Histogram | Time from queue to merge |
| `merge_queue_operations_total` | Counter | Operations by type and status |
| `merge_queue_gitlab_api_latency_seconds` | Histogram | GitLab API response time |
| `merge_queue_circuit_breaker_state` | Gauge | Circuit breaker state (0=closed, 1=open, 2=half-open) |

### Log Format

JSON logs include:

```json
{
  "timestamp": "2024-01-15T10:30:00Z",
  "level": "info",
  "event": "mr_merged",
  "mr_iid": 123,
  "duration_seconds": 180,
  "request_id": "abc-123"
}
```

## Troubleshooting

### Common Errors

#### "Missing required environment variable"

```
MissingEnvValueError: GITLAB_QUEUE_GITLAB_TOKEN is required
```

Set all required environment variables. See Configuration Reference.

#### "GitLab API returned 401"

```
GitLab authentication failed: 401 Unauthorized
```

Your GitLab token is invalid or expired. Create a new token with `api` scope.

#### "Circuit breaker is OPEN"

```
Circuit breaker is OPEN, failing fast
```

GitLab API had multiple failures. The bot will automatically retry after the half-open timeout (default 30s). Check GitLab status.

#### "Rebase conflict detected"

```
Cannot rebase: conflicts in src/file.py
```

The MR has merge conflicts. Resolve them locally, push, and re-add the queue label.

#### "Webhook signature verification failed"

```
Invalid webhook signature
```

`GITLAB_QUEUE_WEBHOOK_SECRET` doesn't match the secret configured in GitLab. Update to match.

### Debug Logging

Enable debug logs for detailed information:

```bash
export GITLAB_QUEUE_LOG_LEVEL=DEBUG
export GITLAB_QUEUE_LOG_FORMAT=console  # Easier to read
python -m gitlab_queue
```

### Checking Component Health

```bash
curl http://localhost:8080/health/detailed | jq
```

Response shows status of each component:
- `database` - SQLite connection
- `gitlab_api` - GitLab API availability
- `processor` - Main processing loop
- `webhook_server` - HTTP server

## Contributing

### Development Setup

```bash
cd backend

# Install all dependencies including dev
uv sync --all-extras

# Run linting
uv run ruff check .

# Run type checking
uv run mypy src/

# Run formatter
uv run ruff format .
```

### Running Tests

```bash
# Run all tests
uv run vedro run scenarios/

# Run with verbose output
uv run vedro run scenarios/ -v

# Run specific test file
uv run vedro run scenarios/unit/queue_add_mr.py

# Run in random order
uv run vedro run scenarios/ --order-random
```

### Code Style

- **Formatter**: Ruff (line length 120)
- **Linter**: Ruff
- **Type Checker**: mypy (strict mode)
- **Test Framework**: Vedro (BDD-style)

### Pull Request Process

1. Create a feature branch
2. Make changes
3. Run `uv run ruff check . && uv run mypy src/`
4. Run `uv run vedro run scenarios/`
5. Submit PR

## License

MIT License - see LICENSE file for details.
