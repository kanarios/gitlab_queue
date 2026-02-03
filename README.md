<div align="center">

# 🚂 GitLab Merge Queue Bot

**Open-source alternative to GitLab Merge Trains (Premium feature)**

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT) [![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/) [![React 19](https://img.shields.io/badge/react-19-61dafb.svg)](https://react.dev) [![FastAPI](https://img.shields.io/badge/FastAPI-009688.svg)](https://fastapi.tiangolo.com) [![Docker](https://img.shields.io/badge/docker-ready-2496ED.svg)](https://docker.com)

[![Backend Image](https://img.shields.io/badge/ghcr.io-backend-blue?logo=docker)](https://ghcr.io/kanarios/gitlab_queue-backend) [![Frontend Image](https://img.shields.io/badge/ghcr.io-frontend-blue?logo=docker)](https://ghcr.io/kanarios/gitlab_queue-frontend)

[![Status: Alpha](https://img.shields.io/badge/status-alpha-orange)](https://github.com/kanarios/gitlab_queue) [![Built with Claude Code](https://img.shields.io/badge/built%20with-Claude%20Code-blueviolet)](https://claude.ai/code)

**Stop fighting rebase wars. Let the bot handle the queue.**

[Demo](#-demo) • [Quick Start](#-quick-start) • [Features](#-features) • [Dashboard](#-dashboard) • [Documentation](#-documentation)

</div>

---

<div align="center">

🆓 **Free** alternative to $29/user/month Premium feature &nbsp;•&nbsp; ⚡ **Real-time** dashboard with WebSocket &nbsp;•&nbsp; 🔥 **Hotfix priority** without interrupting current work

🛡️ **Circuit breaker** protects against GitLab outages &nbsp;•&nbsp; 📊 **Built-in analytics** and historical insights &nbsp;•&nbsp; 🔄 **State recovery** survives restarts

</div>

---

## 🎯 The Problem

When using fast-forward merge strategy in GitLab, teams face a frustrating race condition:

```
Developer A: rebases MR → tries to merge
Developer B: rebases MR → tries to merge
A merges first → B gets "branch out of date" error 😤
B rebases again → while rebasing, C merges
B rebases again → endless cycle of frustration 🔄
```

**Result:** Hours wasted on manual rebase operations. Angry engineers. Slow delivery.

## ✅ The Solution

A bot that manages a merge queue - no more manual rebasing, no more race conditions:

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                                                                             │
│   1️⃣  Add 'merge_queue' label to your MR                                    │
│                           ↓                                                 │
│   2️⃣  Bot automatically rebases your MR onto target branch                  │
│                           ↓                                                 │
│   3️⃣  Bot waits for pipeline to pass                                        │
│                           ↓                                                 │
│   4️⃣  Bot merges your MR                                                    │
│                           ↓                                                 │
│   5️⃣  Next MR in queue starts processing                                    │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

**You get:** A comment on your MR with position, ETA, and status updates. Then walk away.

---

## 📺 Demo

<div align="center">

<!--
📸 Screenshots coming soon! Add your own:
- docs/assets/demo.gif - Main workflow demo
- docs/assets/dashboard.png - Dashboard view
- docs/assets/analytics.png - Analytics page
-->

| Dashboard | Analytics | History |
|:-:|:-:|:-:|
| ![Dashboard](docs/assets/dashboard.png) | ![Analytics](docs/assets/analytics.png) | ![History](docs/assets/history.png) |

*Real-time queue monitoring • Historical analytics • Full merge history*

</div>

### How It Works

```
Developer                      Bot                           GitLab
    │                           │                              │
    │── Add 'merge_queue' ─────►│                              │
    │   label to MR             │                              │
    │                           │                              │
    │◄─ "Added to queue #3" ────│                              │
    │                           │                              │
    │         ... time passes, other MRs merge ...             │
    │                           │                              │
    │◄─ "Your turn! Rebasing" ──│                              │
    │                           │── Rebase MR ────────────────►│
    │                           │◄─ Rebase complete ───────────│
    │                           │                              │
    │◄─ "Running pipeline" ─────│                              │
    │                           │── Wait for pipeline ────────►│
    │                           │◄─ Pipeline success ──────────│
    │                           │                              │
    │                           │── Merge MR ─────────────────►│
    │◄─ "Successfully merged!"──│◄─ Merge complete ────────────│
    │                           │                              │
```

---

## 🤔 Why This Over GitLab Merge Trains?

| Feature | GitLab Merge Trains | This Bot |
|:--------|:--------------------|:----------|
| **Price** | 💰 $29/user/month (Premium) | 🆓 **Free & Open Source** |
| **Self-hosted** | ❌ GitLab SaaS or Premium only | ✅ **Your infrastructure** |
| **Real-time Dashboard** | ❌ Basic UI | ✅ **WebSocket live updates** |
| **Analytics & Insights** | ❌ Limited | ✅ **Full historical data & trends** |
| **Hotfix Priority** | ⚠️ Interrupts current work | ✅ **Non-interrupting queue jump** |
| **Dead Letter Queue** | ❌ Lost webhooks | ✅ **Retry failed events** |
| **Circuit Breaker** | ❌ | ✅ **Graceful degradation** |
| **State Recovery** | ❌ | ✅ **Survives restarts** |
| **MR Feedback** | ⚠️ Basic | ✅ **Detailed status on every change** |
| **Single Bot Comment** | ❌ Spam comments | ✅ **One pinned, updated comment** |

---

## ✨ Features

### 🚀 Core Queue Management

| Feature | Description |
|---------|-------------|
| **FIFO Queue** | Fair first-in-first-out processing |
| **Hotfix Priority** | MRs with `hotfix` label jump to front (without interrupting current work!) |
| **Automatic Rebase** | Rebases onto target branch before merge |
| **Pipeline Waiting** | Waits for CI/CD pipeline to complete |
| **Auto-rebase During Testing** | If target branch changes while pipeline runs, auto-rebases without losing progress |
| **Pipeline Retry** | Retries failed pipelines once before failing |
| **Automatic Merge** | Merges when pipeline succeeds |

### 🛡️ Reliability & Resilience

| Feature | Description |
|---------|-------------|
| **Circuit Breaker** | Protects against cascading failures when GitLab is down |
| **Adaptive Rate Limiting** | Smoothly throttles requests approaching GitLab limits |
| **Webhook + Polling** | Real-time webhooks with polling fallback for reliability |
| **Dead Letter Queue (DLQ)** | Failed webhooks are retried with exponential backoff |
| **State Recovery** | Recovers queue state after restart - no lost MRs |
| **Graceful Shutdown** | Clean shutdown without losing work |

### 📊 Dashboard & Analytics

| Feature | Description |
|---------|-------------|
| **Real-time Updates** | WebSocket live queue monitoring |
| **Queue Visualization** | See active MR progress (rebasing → testing → merging) |
| **History & Search** | Full merge history with filtering |
| **Analytics Dashboard** | Throughput, success rate, queue depth trends |
| **Dark Mode** | Easy on the eyes |

### 🔐 Security

| Feature | Description |
|---------|-------------|
| **GitLab OAuth** | Secure dashboard authentication |
| **Webhook Verification** | Signature verification for GitLab webhooks |
| **Secret Sanitization** | Sensitive data redacted from logs |
| **JWT Authentication** | Secure API access |

### 📢 Notifications

Every state change posts an update to your MR:

- 📥 **Queued**: Position in queue + estimated wait time
- 🔄 **Rebasing**: Rebase started
- 🧪 **Testing**: Pipeline link + progress
- ⚠️ **Conflict**: Which files have conflicts
- ❌ **Failed**: What went wrong + how to fix
- ✅ **Merged**: Success confirmation

---

## 🚀 Quick Start

### Option 1: One-Line Install (Recommended)

**Interactive mode:**
```bash
curl -fsSL https://raw.githubusercontent.com/kanarios/gitlab_queue/main/install.sh | bash
```

**Non-interactive mode (CI/CD):**
```bash
# Using environment variables
export GITLAB_TOKEN=glpat-xxxxxxxxxxxx
export GITLAB_PROJECT_ID=12345678
export WEBHOOK_SECRET=my-webhook-secret
curl -fsSL https://raw.githubusercontent.com/kanarios/gitlab_queue/main/install.sh | bash

# Or using command-line flags
curl -fsSL .../install.sh | bash -s -- \
  --token glpat-xxxxxxxxxxxx \
  --project-id 12345678 \
  --webhook-secret my-secret \
  --no-dashboard \
  --auto-start
```

The installer will:
- Auto-detect interactive vs CI/CD mode
- Use environment variables or flags in CI/CD
- Generate all necessary files
- Optionally start the bot

### Option 2: Manual Docker Compose

```bash
# Create a directory for the bot
mkdir gitlab-queue && cd gitlab-queue

# Download the required files
curl -O https://raw.githubusercontent.com/kanarios/gitlab_queue/main/docker/docker-compose.prod.yml
curl -O https://raw.githubusercontent.com/kanarios/gitlab_queue/main/docker/Caddyfile
curl -O https://raw.githubusercontent.com/kanarios/gitlab_queue/main/docker/.env.prod.example

# Create your .env file
cp .env.prod.example .env
nano .env  # Edit with your settings

# Start the bot
docker compose -f docker-compose.prod.yml up -d
```

### Option 3: Single Container (Backend Only)

```bash
docker run -d \
  --name gitlab-queue \
  -p 8080:8080 \
  -v gitlab-queue-data:/app/data \
  -e GITLAB_QUEUE_GITLAB_TOKEN=glpat-xxxxxxxxxxxx \
  -e GITLAB_QUEUE_GITLAB_PROJECT_ID=12345678 \
  -e GITLAB_QUEUE_JWT_SECRET=$(openssl rand -hex 64) \
  -e GITLAB_QUEUE_WEBHOOK_SECRET=your-webhook-secret \
  -e GITLAB_QUEUE_WEBHOOK_HOST=0.0.0.0 \
  ghcr.io/kanarios/gitlab_queue-backend:latest
```

### Option 4: Build from Source

```bash
git clone https://github.com/kanarios/gitlab_queue.git
cd gitlab_queue/docker

# Create .env file and edit with your settings
cp .env.prod.example .env && nano .env

# Build and start
docker compose up -d --build
```

### Option 5: Local Development

```bash
git clone https://github.com/kanarios/gitlab_queue.git
cd gitlab_queue/backend

# Install dependencies (requires uv)
uv sync

# Set environment variables
export GITLAB_QUEUE_GITLAB_TOKEN=glpat-xxxxxxxxxxxx
export GITLAB_QUEUE_GITLAB_PROJECT_ID=12345678
export GITLAB_QUEUE_JWT_SECRET=$(openssl rand -hex 64)
export GITLAB_QUEUE_WEBHOOK_SECRET=your-webhook-secret

# Run
python -m gitlab_queue
```

### 3 Steps to Get Started

1. **Get GitLab Token**: User Settings → Access Tokens → Create with `api` scope
2. **Get Project ID**: Your Project → Settings → General (shown at top)
3. **Configure Webhook**: Your Project → Settings → Webhooks → Add:
   - URL: `https://your-domain.com/webhooks/gitlab`
   - Secret: same as `GITLAB_QUEUE_WEBHOOK_SECRET`
   - Triggers: ✅ Merge request events, ✅ Pipeline events

---

## 📊 Dashboard

The bot comes with a beautiful React dashboard for monitoring and analytics.

### Queue View
- **Active MR**: See current processing with live progress bar
- **Queue List**: Upcoming MRs with position and author
- **Connection Status**: WebSocket health indicator

### Analytics View
- **KPIs**: Total processed, avg wait time, success rate, daily throughput
- **Charts**: Queue depth over time, hourly processing, outcome distribution
- **Period Selection**: 7 days, 30 days, 90 days

### History View
- **Full History**: All processed MRs
- **Filtering**: By status (merged, failed, conflict, timeout)
- **Search**: Find specific MRs by title
- **Details**: Failure reasons, pipeline links

### Features
- 🌙 **Dark Mode**: Toggle or follow system preference
- ♿ **Accessible**: Full ARIA support
- 📱 **Responsive**: Works on mobile
- ⚡ **Real-time**: WebSocket live updates

---

## 📖 Documentation

<details>
<summary><strong>🚀 Installation Script Reference</strong></summary>

The `install.sh` script supports both interactive and non-interactive (CI/CD) modes.

### Interactive Mode

```bash
curl -fsSL https://raw.githubusercontent.com/kanarios/gitlab_queue/main/install.sh | bash
```

### Non-Interactive Mode (CI/CD)

```bash
# Using environment variables
export GITLAB_TOKEN=glpat-xxxxxxxxxxxx
export GITLAB_PROJECT_ID=12345678
curl -fsSL https://raw.githubusercontent.com/kanarios/gitlab_queue/main/install.sh | bash

# Or using flags
curl -fsSL .../install.sh | bash -s -- \
  --token glpat-xxx --project-id 12345 --no-dashboard --auto-start
```

<details>
<summary>All available options</summary>

| Flag | Environment Variable | Default | Description |
|------|---------------------|---------|-------------|
| `--token` | `GITLAB_TOKEN` | - | GitLab Personal Access Token (required) |
| `--project-id` | `GITLAB_PROJECT_ID` | - | GitLab Project ID (required) |
| `--webhook-secret` | `WEBHOOK_SECRET` | auto-generated | Webhook signature secret |
| `--gitlab-url` | `GITLAB_URL` | `https://gitlab.com` | GitLab instance URL |
| `--target-branch` | `TARGET_BRANCH` | `master` | Target branch for merges |
| `--queue-label` | `QUEUE_LABEL` | `merge_queue` | Label to trigger queue |
| `--hotfix-label` | `HOTFIX_LABEL` | `hotfix` | Label for priority MRs |
| `--install-dir` | `INSTALL_DIR` | `gitlab-queue` | Installation directory |
| `--port` | `HTTP_PORT` | `80` | HTTP port |
| `--https-port` | `HTTPS_PORT` | `443` | HTTPS port |
| `--dashboard` | `INSTALL_DASHBOARD=true` | `true` | Install with dashboard |
| `--no-dashboard` | `INSTALL_DASHBOARD=false` | - | Backend only |
| `--auto-start` | `AUTO_START=true` | `false` in CI | Start after install |
| `--no-start` | `AUTO_START=false` | - | Don't start services |

</details>

<details>
<summary>GitLab CI example</summary>

```yaml
deploy-merge-queue:
  stage: deploy
  image: docker:latest
  services:
    - docker:dind
  variables:
    GITLAB_TOKEN: $MERGE_QUEUE_TOKEN
    GITLAB_PROJECT_ID: $CI_PROJECT_ID
    WEBHOOK_SECRET: $MERGE_QUEUE_WEBHOOK_SECRET
    AUTO_START: "true"
  script:
    - apk add --no-cache curl bash
    - curl -fsSL https://raw.githubusercontent.com/kanarios/gitlab_queue/main/install.sh | bash
```

</details>

<details>
<summary>GitHub Actions example</summary>

```yaml
- name: Install Merge Queue Bot
  env:
    GITLAB_TOKEN: ${{ secrets.GITLAB_TOKEN }}
    GITLAB_PROJECT_ID: ${{ secrets.GITLAB_PROJECT_ID }}
    WEBHOOK_SECRET: ${{ secrets.WEBHOOK_SECRET }}
    AUTO_START: "true"
  run: |
    curl -fsSL https://raw.githubusercontent.com/kanarios/gitlab_queue/main/install.sh | bash
```

</details>

</details>

<details>
<summary><strong>📋 Configuration Reference</strong></summary>

### Required Variables

| Variable | Description |
|----------|-------------|
| `GITLAB_QUEUE_GITLAB_TOKEN` | GitLab personal access token with `api` scope |
| `GITLAB_QUEUE_GITLAB_PROJECT_ID` | GitLab project ID (positive integer) |
| `GITLAB_QUEUE_JWT_SECRET` | JWT signing secret (min 64 chars) |
| `GITLAB_QUEUE_WEBHOOK_SECRET` | Webhook signature secret |

### GitLab Connection

| Variable | Default | Description |
|----------|---------|-------------|
| `GITLAB_QUEUE_GITLAB_URL` | `https://gitlab.com` | GitLab instance URL |
| `GITLAB_QUEUE_TARGET_BRANCH` | `master` | Target branch for merges |
| `GITLAB_QUEUE_QUEUE_LABEL` | `merge_queue` | Label to add MR to queue |
| `GITLAB_QUEUE_HOTFIX_LABEL` | `hotfix` | Label for priority processing |

### Timing

| Variable | Default | Description |
|----------|---------|-------------|
| `GITLAB_QUEUE_POLL_INTERVAL_SECONDS` | `30` | Polling interval for fallback sync |
| `GITLAB_QUEUE_PIPELINE_POLL_INTERVAL_SECONDS` | `5` | Pipeline status check interval |
| `GITLAB_QUEUE_PIPELINE_TIMEOUT_SECONDS` | `7200` | Max pipeline wait time (2 hours) |
| `GITLAB_QUEUE_REBASE_TIMEOUT_SECONDS` | `300` | Max rebase wait time (5 minutes) |
| `GITLAB_QUEUE_REBASE_CHECK_INTERVAL_SECONDS` | `30` | Interval to check if rebase needed during testing |
| `GITLAB_QUEUE_STALE_MR_WARNING_HOURS` | `24` | Warn about stuck MRs after this time |

### Retry Logic

| Variable | Default | Description |
|----------|---------|-------------|
| `GITLAB_QUEUE_PIPELINE_RETRY_COUNT` | `1` | Retry failed pipelines this many times |
| `GITLAB_QUEUE_API_MAX_RETRIES` | `5` | Max retries for API calls |
| `GITLAB_QUEUE_MERGE_STATUS_RETRY_MAX` | `10` | Max retries when merge_status is 'checking' |
| `GITLAB_QUEUE_MERGE_STATUS_RETRY_DELAY_SECONDS` | `5.0` | Delay between merge status retries |
| `GITLAB_QUEUE_MAX_REBASE_DURING_TESTING` | `3` | Max auto-rebases while pipeline runs |

### Rate Limiting

| Variable | Default | Description |
|----------|---------|-------------|
| `GITLAB_QUEUE_RATE_LIMIT_WARNING_THRESHOLD` | `0.8` | Warn at 80% of rate limit |
| `GITLAB_QUEUE_RATE_LIMIT_THROTTLE_DELAY_SECONDS` | `1.0` | Delay when throttling |
| `GITLAB_QUEUE_RATE_LIMIT_CRITICAL_THRESHOLD` | `0.95` | Critical at 95% of rate limit |

### Circuit Breaker

| Variable | Default | Description |
|----------|---------|-------------|
| `GITLAB_QUEUE_CIRCUIT_BREAKER_FAILURE_THRESHOLD` | `5` | Failures before circuit opens |
| `GITLAB_QUEUE_CIRCUIT_BREAKER_HALF_OPEN_TIMEOUT_SECONDS` | `30` | Wait before retry attempt |
| `GITLAB_QUEUE_CIRCUIT_BREAKER_SUCCESS_THRESHOLD` | `1` | Successes to close circuit |

### Webhook Retry Queue

| Variable | Default | Description |
|----------|---------|-------------|
| `GITLAB_QUEUE_WEBHOOK_RETRY_MAX_ATTEMPTS` | `3` | Max retry attempts |
| `GITLAB_QUEUE_WEBHOOK_RETRY_BASE_DELAY_SECONDS` | `30` | Initial backoff delay |
| `GITLAB_QUEUE_WEBHOOK_RETRY_MAX_DELAY_SECONDS` | `300` | Max backoff delay (5 min) |
| `GITLAB_QUEUE_WEBHOOK_DLQ_RETENTION_DAYS` | `30` | Keep failed events for 30 days |

### Server

| Variable | Default | Description |
|----------|---------|-------------|
| `GITLAB_QUEUE_WEBHOOK_ENABLED` | `true` | Enable webhook server |
| `GITLAB_QUEUE_WEBHOOK_HOST` | `127.0.0.1` | Server bind address |
| `GITLAB_QUEUE_WEBHOOK_PORT` | `8080` | Server port |
| `GITLAB_QUEUE_DASHBOARD_ENABLED` | `true` | Enable dashboard API |
| `GITLAB_QUEUE_CORS_ORIGINS` | `http://localhost:5173` | Allowed CORS origins |
| `GITLAB_QUEUE_DATABASE_URL` | `sqlite+aiosqlite:///data/queue.db` | Database connection URL |

### OAuth (Optional - for Dashboard Authentication)

| Variable | Description |
|----------|-------------|
| `GITLAB_QUEUE_OAUTH_CLIENT_ID` | GitLab OAuth Application ID |
| `GITLAB_QUEUE_OAUTH_CLIENT_SECRET` | GitLab OAuth Application Secret |
| `GITLAB_QUEUE_OAUTH_REDIRECT_URI` | OAuth callback URL |

### Logging

| Variable | Default | Description |
|----------|---------|-------------|
| `GITLAB_QUEUE_LOG_LEVEL` | `INFO` | Log level (DEBUG, INFO, WARNING, ERROR) |
| `GITLAB_QUEUE_LOG_FORMAT` | `json` | Log format (json or console) |

</details>

<details>
<summary><strong>🔧 GitLab Setup</strong></summary>

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
   - **Allowed to merge**: Maintainers
   - **Allowed to push**: No one (prevents direct pushes)
   - **Allowed to force push**: Disabled

### 5. Configure OAuth Application (Optional - for Dashboard)

1. Go to GitLab → User Settings → Applications
2. Create a new application:
   - **Name**: `Merge Queue Bot Dashboard`
   - **Redirect URI**: `https://your-bot-domain.com/auth/callback`
   - **Confidential**: Yes
   - **Scopes**: `read_user` and `read_api`
3. Copy Application ID and Secret to environment variables

</details>

<details>
<summary><strong>🚢 Deployment Options</strong></summary>

### Docker Compose (Recommended)

```bash
cd docker
docker-compose up -d
```

Includes:
- Backend container
- Frontend container
- Caddy reverse proxy (auto SSL)

### Kubernetes

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
        image: ghcr.io/kanarios/gitlab_queue-backend:latest
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

### Local with ngrok (for testing webhooks)

```bash
# Terminal 1: Run the bot
cd backend && python -m gitlab_queue

# Terminal 2: Expose locally
ngrok http 8080
# Use the ngrok URL as your webhook URL in GitLab
```

</details>

<details>
<summary><strong>🔌 API Reference</strong></summary>

### Health Endpoints

```bash
# Liveness probe
curl http://localhost:8080/health

# Readiness probe
curl http://localhost:8080/ready

# Detailed component status
curl http://localhost:8080/health/detailed

# Prometheus metrics
curl http://localhost:8080/metrics
```

### Queue API

```bash
# Get full queue status
curl http://localhost:8080/api/queue

# Get active queue only
curl http://localhost:8080/api/queue/active

# Get queue statistics
curl http://localhost:8080/api/queue/stats

# Get specific MR status
curl http://localhost:8080/api/queue/123
```

### History API

```bash
# Get merge history (paginated)
curl "http://localhost:8080/api/history?page=1&per_page=20"

# Filter by status
curl "http://localhost:8080/api/history?status=merged"

# Search by title
curl "http://localhost:8080/api/history?search=fix%20bug"
```

### Analytics API

```bash
# Get summary KPIs
curl "http://localhost:8080/api/analytics/summary?period=30d"

# Get hourly data
curl "http://localhost:8080/api/analytics/hourly?period=7d"

# Get outcome distribution
curl "http://localhost:8080/api/analytics/outcomes?period=30d"

# Get failure reasons
curl "http://localhost:8080/api/analytics/failure-reasons?period=30d"
```

### Dead Letter Queue API

```bash
# List DLQ entries
curl http://localhost:8080/api/dlq

# Get DLQ statistics
curl http://localhost:8080/api/dlq/stats

# Retry a DLQ entry
curl -X POST http://localhost:8080/api/dlq/{entry_id}/retry

# Delete a DLQ entry
curl -X DELETE http://localhost:8080/api/dlq/{entry_id}
```

### WebSocket API

Connect: `ws://localhost:8080/ws`

| Event | Payload | Description |
|-------|---------|-------------|
| `queue:updated` | `{queue: MR[], stats: Stats}` | Full queue state update |
| `mr:status_changed` | `{iid, oldStatus, newStatus}` | MR state transition |
| `mr:completed` | `{iid, status, finishedAt, failureReason}` | MR finished processing |

### Webhook Endpoint

```
POST /webhooks/gitlab
Headers:
  X-Gitlab-Token: your-webhook-secret
  Content-Type: application/json
```

</details>

---

## 🏗️ Architecture

### System Overview

```
                    ┌─────────────────────────────────────────────────────────┐
                    │                      GitLab Server                      │
                    └────────────────────────────┬────────────────────────────┘
                                                 │
                      ┌──────────────────────────┼──────────────────────────┐
                      │                          │                          │
                      ▼                          ▼                          │
              ┌───────────────┐         ┌───────────────┐                   │
              │   Webhooks    │         │   Polling     │                   │
              │   (instant)   │         │  (fallback)   │                   │
              └───────┬───────┘         └───────┬───────┘                   │
                      │                         │                           │
                      └────────────┬────────────┘                           │
                                   │                                        │
                      ┌────────────▼────────────┐                           │
                      │     Queue Manager       │                           │
                      │       (SQLite)          │◄──────────────────────────┤
                      └────────────┬────────────┘                           │
                                   │                                        │
              ┌────────────────────┼────────────────────┐                   │
              │                    │                    │                   │
              ▼                    ▼                    ▼                   │
      ┌───────────────┐   ┌───────────────┐   ┌───────────────┐             │
      │  Retry/DLQ    │   │   Processor   │   │   WebSocket   │             │
      │   Manager     │   │ State Machine │   │   Manager     │             │
      └───────────────┘   └───────┬───────┘   └───────┬───────┘             │
                                  │                   │                     │
                                  │                   │                     │
                      ┌───────────▼───────────┐       │                     │
                      │      Notifier         │───────┘                     │
                      │   (MR Comments)       │─────────────────────────────┘
                      └───────────────────────┘
                                  │
                      ┌───────────▼───────────┐
                      │   React Dashboard     │
                      │   (Frontend SPA)      │
                      └───────────────────────┘
```

### State Machine

```
                         ┌─────────────────────────────────────────────┐
                         │               🎯 HAPPY PATH                 │
                         │                                             │
┌─────────┐              │  ┌─────────┐    ┌─────────┐    ┌─────────┐  │   ┌────────┐
│         │              │  │         │    │         │    │         │  │   │        │
│ QUEUED  │──────────────┼─►│REBASING │───►│ TESTING │───►│ MERGING │──┼──►│ MERGED │
│         │              │  │         │    │         │    │         │  │   │   ✅   │
└────┬────┘              │  └────┬────┘    └────┬────┘    └────┬────┘  │   └────────┘
     │                   │       │              │              │       │
     │                   └───────┼──────────────┼──────────────┼───────┘
     │                           │              │              │
     │                           ▼              ▼              ▼
     │                    ┌──────────────────────────────────────────┐
     │                    │              ❌ FAILED                   │
     │                    │   (conflict / pipeline fail / timeout)   │
     │                    └──────────────────────────────────────────┘
     │
     ▼
┌─────────┐
│ REMOVED │ ◄── label removed or MR closed
│   🚫    │
└─────────┘
```

### Key Design Decisions

| Decision | Rationale |
|----------|-----------|
| **Single project per instance** | Isolation, security, simpler config |
| **SQLite storage** | Zero dependencies, single file backup |
| **Webhook-primary, polling-fallback** | Real-time + reliability |
| **Non-interrupting hotfix** | Hotfix priority without wasting current work |
| **Mandatory MR feedback** | Users always know what's happening |
| **Single pinned comment** | Clean MR history, no spam |

---

## 📈 Monitoring

### Health Checks

```bash
# Docker health check
HEALTHCHECK --interval=30s --timeout=10s --retries=3 \
  CMD curl -f http://localhost:8080/health || exit 1

# Detailed status
curl http://localhost:8080/health/detailed | jq
```

### Prometheus Metrics

| Metric | Type | Description |
|--------|------|-------------|
| `merge_queue_length` | Gauge | Current queue length |
| `merge_queue_mr_duration_seconds` | Histogram | Time from queue to merge |
| `merge_queue_operations_total` | Counter | Operations by type and status |
| `merge_queue_gitlab_api_latency_seconds` | Histogram | GitLab API response time |
| `merge_queue_circuit_breaker_state` | Gauge | 0=closed, 1=open, 2=half-open |

### Log Format

JSON structured logs with correlation IDs:

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

---

## 🔧 Troubleshooting

<details>
<summary><strong>Common Issues</strong></summary>

### "Missing required environment variable"

```
MissingEnvValueError: GITLAB_QUEUE_GITLAB_TOKEN is required
```

Set all required environment variables. See [Configuration Reference](#-documentation).

### "GitLab API returned 401"

```
GitLab authentication failed: 401 Unauthorized
```

Your GitLab token is invalid or expired. Create a new token with `api` scope.

### "Circuit breaker is OPEN"

```
Circuit breaker is OPEN, failing fast
```

GitLab API had multiple failures. The bot will automatically retry after 30s. Check GitLab status.

### "Rebase conflict detected"

```
Cannot rebase: conflicts in src/file.py
```

The MR has merge conflicts. Resolve them locally, push, and re-add the queue label.

### "Webhook signature verification failed"

```
Invalid webhook signature
```

`GITLAB_QUEUE_WEBHOOK_SECRET` doesn't match GitLab webhook config. Ensure they match exactly.

### Dashboard shows "Disconnected"

WebSocket connection lost. Check:
1. Backend is running (`curl http://localhost:8080/health`)
2. CORS origins are configured correctly
3. No proxy blocking WebSocket upgrade

### DLQ entries piling up

Check `/api/dlq/stats` for failure patterns. Common causes:
- GitLab API downtime
- Invalid webhook payloads
- Network issues

Retry entries with `POST /api/dlq/{id}/retry` or investigate with `GET /api/dlq/{id}`.

</details>

<details>
<summary><strong>Debug Mode</strong></summary>

```bash
export GITLAB_QUEUE_LOG_LEVEL=DEBUG
export GITLAB_QUEUE_LOG_FORMAT=console
python -m gitlab_queue
```

</details>

---

## 🤝 Contributing

### Development Setup

```bash
cd backend

# Install all dependencies
uv sync --all-extras

# Run checks
make check    # lint + typecheck
make format   # auto-format code
make test     # run all tests
```

### Running Tests

```bash
# All tests (Vedro BDD framework)
uv run vedro run scenarios/

# Verbose output
uv run vedro run scenarios/ -v

# Single test file
uv run vedro run scenarios/unit/queue_add_mr.py

# Random order (find ordering bugs)
uv run vedro run scenarios/ --order-random
```

### Code Style

- **Formatter/Linter**: Ruff (line length 100)
- **Type Checker**: mypy (strict mode)
- **Test Framework**: Vedro (BDD-style)

### Pull Request Process

1. Fork the repository
2. Create a feature branch
3. Make changes
4. Run `make check && make test`
5. Submit PR

---

## 📄 License

MIT License - see [LICENSE](LICENSE) for details.

---

<div align="center">

**[⬆ Back to Top](#-gitlab-merge-queue-bot)**

Made with ❤️ for developers tired of rebase wars

[![Star History](https://api.star-history.com/svg?repos=kanarios/gitlab_queue&type=Date)](https://star-history.com/#kanarios/gitlab_queue&Date)

</div>
