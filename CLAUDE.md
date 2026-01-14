# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

GitLab Merge Queue Bot - an open-source alternative to GitLab's Premium Merge Trains feature. Automates MR merging using fast-forward strategy with automatic rebase, pipeline waiting, and safe merging.

## Development Commands

### Backend (from `/backend` directory)

```bash
# Install dependencies
make install              # uv sync

# Run development server with hot-reload
make dev

# Run tests (Vedro BDD framework)
make test                 # All tests
make test-v               # Verbose
make test-random          # Random order (find ordering bugs)
uv run vedro run scenarios/unit/queue_add_mr.py  # Single file

# Code quality
make check                # lint + typecheck
make lint                 # ruff check src/ scenarios/
make format               # ruff format src/ scenarios/
make typecheck            # mypy src/

# Docker
make docker-build && make docker-up
```

### Frontend (from `/frontend` directory)

```bash
npm run dev               # Development server
npm run build             # Production build
npm run lint              # ESLint
npm run format            # Prettier
npm run type-check        # TypeScript check
npm run test:run          # Run all tests
```

## Architecture

```
┌─────────────────────────────────────────────────┐
│ API Layer (FastAPI)                             │
│ routes.py, websocket.py, auth/                  │
└────────────────────┬────────────────────────────┘
                     │
┌────────────────────┴────────────────────────────┐
│ Webhooks & Scheduler (APScheduler)              │
│ webhooks/router.py, core/scheduler.py           │
└────────────────────┬────────────────────────────┘
                     │
┌────────────────────┴────────────────────────────┐
│ Core Processing (Async)                         │
│ processor.py, state_machine.py, queue.py        │
└────────────────────┬────────────────────────────┘
                     │
┌────────────────────┴────────────────────────────┐
│ GitLab Client + Circuit Breaker                 │
│ clients/gitlab.py, utils/circuit_breaker.py     │
└────────────────────┬────────────────────────────┘
                     │
┌────────────────────┴────────────────────────────┐
│ SQLite + SQLAlchemy async                       │
│ db/database.py, db/models.py                    │
└─────────────────────────────────────────────────┘
```

### State Machine

MR lifecycle with all transitions (per ADR-006: every transition triggers MR comment):

```
┌─────────────────────────────────── HAPPY PATH ────────────────────────────────────┐
│                                                                                   │
│  QUEUED ──start_processing──► REBASING ──rebase_complete──► TESTING               │
│ (initial)                                                      │                  │
│                                                                │                  │
│                                                       pipeline_success            │
│                                                                │                  │
│                                                                ▼                  │
│                                              MERGING ──merge_success──► MERGED    │
│                                                                        (final)    │
└───────────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────── FAILURE PATHS ─────────────────────────────────┐
│                                                                                   │
│  REBASING ──rebase_failed (conflict)────┐                                         │
│                                         │                                         │
│  TESTING  ──pipeline_failed─────────────┼───► FAILED (final)                      │
│                                         │                                         │
│  MERGING  ──merge_failed────────────────┘                                         │
│                                                                                   │
└───────────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────── REMOVAL PATH ──────────────────────────────────┐
│                                                                                   │
│  QUEUED ────┐                                                                     │
│  REBASING ──┼── mark_removed ──► REMOVED (final)                                  │
│  TESTING ───┤                                                                     │
│  MERGING ───┘                                                                     │
│                                                                                   │
│  Triggers: label removed from MR, MR closed                                       │
└───────────────────────────────────────────────────────────────────────────────────┘
```

**States:** `queued` (initial), `rebasing`, `testing`, `merging`, `merged` (final), `failed` (final), `removed` (final)

**Special notifications (no state change):**
- `notify_pipeline_retry` - stays in TESTING, retries failed pipeline
- `notify_position_changed` - stays in QUEUED, position updated
- `notify_stale_warning` - warning after extended queue time

### Key Modules

- `main.py` - Application initialization
- `config.py` - environ-config based settings
- `core/processor.py` - Main merge processing loop
- `core/queue.py` - Queue management (FIFO + hotfix priority)
- `clients/gitlab.py` - GitLab API client with rate limiting
- `webhooks/handlers.py` - GitLab webhook event handlers

## Testing

Uses **Vedro** (BDD-style), not pytest. Tests are in `scenarios/`:
- `scenarios/unit/` - Unit tests
- `scenarios/integration/` - Full workflow tests

Example structure:
```python
class Scenario__add_mr_to_empty_queue(vedro.Scenario):
    subject = "add MR to empty queue"

    async def given_empty_queue(self): ...
    async def when_mr_is_added(self): ...
    async def then_item_should_be_at_position_1(self): ...
```

## Code Quality Standards

- **Line length**: 100 chars (ruff configured)
- **Type hints**: Required everywhere (mypy strict mode)
- **Async**: All I/O must be async
- **Logging**: Use `get_logger(__name__)` for structlog

## Configuration

All env vars prefixed with `GITLAB_QUEUE_`. Required:
- `GITLAB_TOKEN` - GitLab API token
- `GITLAB_PROJECT_ID` - Target project ID
- `JWT_SECRET` - 64+ char secret
- `WEBHOOK_SECRET` - Webhook signature verification

## Key Design Decisions

1. **Single project per instance** - One bot deployment per GitLab project
2. **SQLite storage** - Simple, no external DB dependencies
3. **Webhook-primary** - Real-time via webhooks, polling as fallback
4. **Non-interrupting hotfix** - Hotfix jumps queue but doesn't interrupt current MR
5. **Mandatory notifications** - Every state change posts MR comment
