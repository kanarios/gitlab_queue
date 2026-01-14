# GitLab Merge Queue Bot - Implementation Plan

> **Дата создания:** 2025-12-01
> **Тип проекта:** New Feature Development
> **Репозиторий:** gitlab_queue

---

## Executive Summary

Создание сервиса для управления очередью Merge Request в GitLab — open-source альтернативы Merge Trains из Premium подписки GitLab. Бот автоматизирует процесс слияния MR в master, гарантируя что master всегда остается зеленым.

### Проблема

При использовании Fast-Forward merge в GitLab возникает race condition:
```
Dev A ребейзится → пытается слить
Dev B ребейзится → пытается слить
A сливается первым → B получает конфликт
B снова ребейзится → пока ребейзится, C уже слился
```

Команда тратит значительное время на ручные rebase операции.

### Решение

Бот-диспетчер, который:
1. Управляет очередью MR через label `merge_queue`
2. Автоматически ребейзит каждый MR на актуальный master
3. Дожидается прохождения pipeline
4. Мержит последовательно, гарантируя отсутствие конфликтов

---

## Architecture Decision Records (ADR)

### ADR-001: Scope — Single Project per Instance

**Решение:** Один инстанс бота обслуживает один проект GitLab.

**Обоснование:**
- Простота конфигурации и деплоя
- Изоляция ошибок — проблема в одном проекте не влияет на другие
- Параллелизация — можно запустить несколько инстансов для разных проектов
- Простота масштабирования через Docker Compose реплики

**Для multi-project:** Запустить несколько контейнеров с разными конфигурациями.

### ADR-002: Hotfix Priority — Non-Interrupting

**Решение:** Hotfix вставляется в начало очереди, но НЕ прерывает текущую обработку.

**Обоснование:**
- Прерывание потенциально опасно — MR может остаться в неопределенном состоянии
- Ожидание завершения текущего MR (обычно <30 мин) — приемлемая задержка
- Упрощает state machine — нет состояния "приостановлен"

**Поведение:**
```
Queue: [A(processing), B, C] → Hotfix D arrives
Result: [A(processing), D, B, C]
```

### ADR-003: Webhook-Primary Architecture

**Решение:** Гибридный подход — Webhooks как primary, polling как fallback.

**Обоснование:**
- Webhooks обеспечивают мгновенную реакцию (vs 5 сек polling delay)
- Снижают нагрузку на GitLab API (меньше rate limit рисков)
- Polling остается для recovery после пропущенных webhooks
- Polling interval увеличен до 30 сек (fallback only)

**Trade-off:** Требует публичный endpoint (ngrok/tunneling для dev).

### ADR-004: SQLite-Only Storage

**Решение:** Использовать только SQLite для всех данных (очередь + история + аналитика).

**Обоснование:**
- Проще в деплое — один файл базы данных
- Достаточно для команд до 50 MR/день
- Нет необходимости в отдельном Redis сервисе
- SQLite WAL mode обеспечивает concurrent reads

**Реализация:**
- Очередь хранится в таблице `merge_requests` с `status IN ('queued', 'rebasing', 'testing', 'merging')`
- In-memory кэш для текущей очереди (обновляется при каждом изменении)
- Async SQLite через `aiosqlite`

**Файл:** `data/queue.db` — один файл с 4 таблицами

**Data Retention Strategy:**
- `merge_requests` — только активная очередь (~10-50 записей)
- `merge_requests_history` — завершённые MR (retention: 1 год)
- `analytics_hourly` — почасовые снапшоты (retention: 30 дней)
- `analytics_daily` — дневная статистика (хранить вечно, ~365 записей/год)

**Database Schema:**
```sql
-- Активная очередь (только MR в процессе обработки)
CREATE TABLE merge_requests (
    id INTEGER PRIMARY KEY,
    iid INTEGER NOT NULL UNIQUE,       -- GitLab MR IID
    title TEXT NOT NULL,
    author_name TEXT NOT NULL,
    author_username TEXT NOT NULL,
    author_avatar TEXT,
    status TEXT NOT NULL,              -- queued, rebasing, testing, merging
    is_hotfix BOOLEAN DEFAULT FALSE,
    labels TEXT,                       -- JSON array
    target_branch TEXT NOT NULL,
    queued_at TIMESTAMP NOT NULL,
    started_at TIMESTAMP,
    pipeline_id INTEGER,
    pipeline_status TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- История завершённых MR (retention: 1 год)
CREATE TABLE merge_requests_history (
    id INTEGER PRIMARY KEY,
    iid INTEGER NOT NULL,
    title TEXT NOT NULL,
    author_name TEXT NOT NULL,
    author_username TEXT NOT NULL,
    author_avatar TEXT,
    status TEXT NOT NULL,              -- merged, failed, conflict, timeout, removed
    is_hotfix BOOLEAN DEFAULT FALSE,
    labels TEXT,
    target_branch TEXT NOT NULL,
    queued_at TIMESTAMP NOT NULL,
    started_at TIMESTAMP,
    finished_at TIMESTAMP NOT NULL,
    wait_time_seconds INTEGER,         -- время в очереди
    processing_time_seconds INTEGER,   -- время обработки
    failure_reason TEXT,
    pipeline_id INTEGER,
    pipeline_status TEXT,
    pipeline_duration_seconds INTEGER,
    pipeline_failed_jobs TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Почасовые снапшоты (retention: 30 дней)
CREATE TABLE analytics_hourly (
    id INTEGER PRIMARY KEY,
    timestamp TIMESTAMP NOT NULL,
    queue_depth INTEGER NOT NULL,
    processed_count INTEGER NOT NULL,
    success_count INTEGER NOT NULL,
    failed_count INTEGER NOT NULL,
    avg_wait_time_seconds INTEGER
);

-- Дневная статистика (хранить вечно)
CREATE TABLE analytics_daily (
    id INTEGER PRIMARY KEY,
    date DATE NOT NULL UNIQUE,
    total_processed INTEGER NOT NULL,
    success_count INTEGER NOT NULL,
    failed_count INTEGER NOT NULL,
    conflict_count INTEGER NOT NULL,
    timeout_count INTEGER NOT NULL,
    hotfix_count INTEGER NOT NULL,
    avg_wait_time_seconds INTEGER,
    avg_processing_time_seconds INTEGER,
    max_queue_depth INTEGER
);

-- Индексы
CREATE INDEX idx_mr_status ON merge_requests(status);
CREATE INDEX idx_mr_queued_at ON merge_requests(queued_at);
CREATE INDEX idx_history_finished_at ON merge_requests_history(finished_at);
CREATE INDEX idx_history_status ON merge_requests_history(status);
CREATE INDEX idx_hourly_timestamp ON analytics_hourly(timestamp);
CREATE INDEX idx_daily_date ON analytics_daily(date);
```

**Операции переноса данных:**
```sql
-- При завершении MR: перенос из активной очереди в историю
INSERT INTO merge_requests_history
    (iid, title, author_name, author_username, author_avatar, status, is_hotfix,
     labels, target_branch, queued_at, started_at, finished_at,
     wait_time_seconds, processing_time_seconds, failure_reason,
     pipeline_id, pipeline_status, pipeline_duration_seconds, pipeline_failed_jobs)
SELECT
    iid, title, author_name, author_username, author_avatar, ?, is_hotfix,
    labels, target_branch, queued_at, started_at, CURRENT_TIMESTAMP,
    CAST((julianday(started_at) - julianday(queued_at)) * 86400 AS INTEGER),
    CAST((julianday(CURRENT_TIMESTAMP) - julianday(started_at)) * 86400 AS INTEGER),
    ?, pipeline_id, pipeline_status, ?, ?
FROM merge_requests WHERE iid = ?;

DELETE FROM merge_requests WHERE iid = ?;

-- Ежедневная агрегация (cron в 00:05)
INSERT INTO analytics_daily (date, total_processed, success_count, failed_count,
    conflict_count, timeout_count, hotfix_count, avg_wait_time_seconds,
    avg_processing_time_seconds, max_queue_depth)
SELECT
    DATE(finished_at),
    COUNT(*),
    SUM(CASE WHEN status = 'merged' THEN 1 ELSE 0 END),
    SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END),
    SUM(CASE WHEN status = 'conflict' THEN 1 ELSE 0 END),
    SUM(CASE WHEN status = 'timeout' THEN 1 ELSE 0 END),
    SUM(CASE WHEN is_hotfix THEN 1 ELSE 0 END),
    AVG(wait_time_seconds),
    AVG(processing_time_seconds),
    (SELECT MAX(queue_depth) FROM analytics_hourly
     WHERE DATE(timestamp) = DATE('now', '-1 day'))
FROM merge_requests_history
WHERE DATE(finished_at) = DATE('now', '-1 day');

-- Cleanup (cron ежедневно)
DELETE FROM merge_requests_history WHERE finished_at < datetime('now', '-365 days');
DELETE FROM analytics_hourly WHERE timestamp < datetime('now', '-30 days');
VACUUM;  -- Освободить место после DELETE
```

**Размер через год (при 50 MR/день):**
- `merge_requests`: ~50 записей × 500 bytes = ~25 KB
- `merge_requests_history`: ~18,000 записей × 600 bytes = ~10 MB
- `analytics_hourly`: ~720 записей × 50 bytes = ~36 KB
- `analytics_daily`: ~365 записей × 100 bytes = ~36 KB
- **Итого:** ~10 MB (SQLite справится без проблем)

### ADR-005: State Machine Design

**Состояния MR в очереди:**
```
                                    ┌─────────┐
                                    │ removed │
                                    └─────────┘
                                         ↑
                                    (label removed/
                                     MR closed/
                                     timeout)
                                         │
┌────────┐    label    ┌────────┐   ┌────┴────┐   ┌─────────┐   ┌────────┐
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

**Transitions (каждый transition = комментарий в MR):**
- `queued → rebasing`: MR на позиции 1, начало обработки → 💬 "Processing started, rebasing..."
- `rebasing → testing`: Rebase успешен, pipeline запущен → 💬 "Rebase complete, waiting for pipeline..."
- `rebasing → failed`: Конфликт при rebase → 💬 "Rebase failed: conflicts in X files"
- `testing → merging`: Pipeline успешен → 💬 "Pipeline passed, merging..."
- `testing → failed`: Pipeline провален (после 1 retry) → 💬 "Pipeline failed, removed from queue"
- `merging → merged`: Merge успешен → 💬 "Successfully merged!"
- `* → removed`: Label удален / MR закрыт / timeout → 💬 "Removed from queue"

### ADR-006: Mandatory MR Feedback

**Решение:** Каждое изменение состояния MR в очереди ОБЯЗАТЕЛЬНО сопровождается комментарием.

**Обоснование:**
- Разработчик должен понимать что происходит с его MR без логов бота
- Уменьшает количество вопросов "почему не мержится?"
- Прозрачность процесса повышает доверие к системе
- Комментарии служат audit trail

**Типы комментариев:**
| Event | Comment |
|-------|---------|
| Added to queue | Position, estimated wait time |
| Position changed | New position (when someone ahead merged/removed) |
| Processing started | "Your turn, rebasing now..." |
| Rebase complete | "Rebase done, waiting for pipeline" |
| Pipeline running | Link to pipeline |
| Pipeline retry | "Pipeline failed, retrying (1/1)..." |
| Pipeline success | "Pipeline passed, merging..." |
| Merge success | "Successfully merged!" |
| Conflict detected | List of conflicted files |
| Pipeline failed | Failed jobs list, removal notice |
| Removed (manual) | "Removed from queue (label removed)" |
| Timeout | "Removed: exceeded max wait time" |

**Реализация:**
- Single pinned comment (обновляется, не создается новый)
- Markdown formatting с emoji для visual scanning
- Timestamp каждого обновления

### ADR-007: WebSocket для Real-time Updates

**Решение:** WebSocket для push-уведомлений о изменениях очереди.

**События:**
- `queue:updated` — изменение очереди
- `mr:status_changed` — смена статуса MR
- `mr:added` / `mr:removed` — добавление/удаление
- `stats:updated` — обновление метрик

### ADR-008: GitLab OAuth Authentication

**Решение:** Доступ к дашборду только для членов GitLab проекта через OAuth.

**Обоснование:**
- Безопасность — только авторизованные пользователи видят данные
- Интеграция с GitLab — не нужно отдельной системы пользователей
- Можно проверять права доступа к проекту

**Flow:**
1. Пользователь заходит на дашборд → redirect на GitLab OAuth
2. GitLab авторизует → callback с code
3. Backend обменивает code на access_token
4. Проверяем что пользователь имеет доступ к project_id
5. Выдаем JWT для дальнейших запросов

### ADR-009: Read-Only Dashboard

**Решение:** Dashboard только для просмотра, без возможности управления очередью.

**Обоснование:**
- Управление через GitLab labels — единый источник правды
- Проще в реализации и тестировании
- Меньше рисков случайного удаления MR из очереди

### ADR-010: Monorepo Structure

**Решение:** Monorepo с отдельными директориями для backend и frontend.

```
gitlab_queue/
├── backend/           # Python (FastAPI)
├── frontend/          # TypeScript (Vite + React)
├── docker/
└── roadmap/
```

---

## Technology Stack

### Backend Stack

| Component | Library | Version | Rationale |
|-----------|---------|---------|-----------|
| **Runtime** | Python | 3.12+ | Modern async features, type hints |
| **HTTP Client** | httpx | 0.27+ | Modern, HTTP/2, async, retry support |
| **Web Framework** | FastAPI | 0.115+ | Webhooks receiver, async native |
| **Database** | aiosqlite | 0.20+ | Async SQLite driver |
| **ORM** | SQLAlchemy | 2.0+ | Async support, type hints |
| **Migrations** | Alembic | 1.13+ | Schema versioning |
| **WebSocket** | FastAPI WebSocket | - | Built-in |
| **Auth** | PyJWT | 2.8+ | JWT tokens для сессий |
| **Retry Logic** | tenacity | 9.0+ | Battle-tested, async support |
| **State Machine** | python-statemachine | 2.0+ | Full async callbacks |
| **Configuration** | environ-config | 24.0+ | Type-safe env vars, attrs-based, declarative |
| **Data Models** | adaptix | 3.0+ | Dataclass serialization, no model coupling, fast |
| **Logging** | structlog | 24.0+ | Structured JSON, async friendly |
| **Testing** | vedro | 1.12+ | BDD-style scenarios, async из коробки, function-based тесты |
| **HTTP Mocking** | jj | 2.13+ | Remote HTTP mock, client-server architecture, async support |

### Frontend Stack

| Component | Library | Version | Rationale |
|-----------|---------|---------|-----------|
| **Runtime** | TypeScript | 5.0+ | Type safety |
| **Build** | Vite | 6.0+ | Fast HMR, ESM native |
| **UI Framework** | React | 19.x | Component-based UI |
| **Animations** | Framer Motion | 12.x | Smooth animations |
| **Charts** | Recharts | 3.x | Analytics visualizations |
| **Icons** | Lucide React | 0.555+ | Modern icon set |
| **Styling** | Tailwind CSS | 3.x | Utility-first CSS |
| **WebSocket** | Native WebSocket | - | Browser API |

### Infrastructure

| Component | Technology | Notes |
|-----------|------------|-------|
| **Database** | SQLite | WAL mode, single file |
| **Container Runtime** | Docker | Production deployment |
| **Orchestration** | Docker Compose | Local/single-server deployment |
| **Reverse Proxy** | Caddy (optional) | HTTPS for webhooks |

---

## Project Structure

```
gitlab_queue/
├── backend/                        # Python backend
│   ├── src/
│   │   └── gitlab_queue/
│   │       ├── __init__.py
│   │       ├── main.py
│   │       ├── config.py
│   │       ├── core/
│   │       │   ├── queue.py            # SQLite-based queue (was Redis)
│   │       │   ├── processor.py
│   │       │   ├── state_machine.py
│   │       │   ├── notifier.py
│   │       │   └── scheduler.py
│   │       ├── clients/
│   │       │   └── gitlab.py           # GitLab API client
│   │       ├── db/                     # Database layer
│   │       │   ├── __init__.py
│   │       │   ├── database.py         # SQLAlchemy async setup
│   │       │   ├── models.py           # ORM models
│   │       │   └── repositories.py     # Data access
│   │       ├── auth/                   # GitLab OAuth
│   │       │   ├── __init__.py
│   │       │   ├── oauth.py            # OAuth flow
│   │       │   ├── jwt.py              # JWT utils
│   │       │   └── middleware.py       # Auth middleware
│   │       ├── api/                    # Dashboard API
│   │       │   ├── __init__.py
│   │       │   ├── routes.py           # REST endpoints
│   │       │   ├── websocket.py        # WebSocket manager
│   │       │   └── schemas.py          # API schemas
│   │       ├── models/
│   │       │   ├── __init__.py
│   │       │   ├── mr.py               # MergeRequest dataclass
│   │       │   ├── pipeline.py         # Pipeline dataclass
│   │       │   ├── queue_item.py       # QueueItem dataclass
│   │       │   ├── events.py           # Webhook event dataclasses
│   │       │   └── retorts.py          # Adaptix Retort instances
│   │       ├── webhooks/
│   │       │   ├── __init__.py
│   │       │   ├── router.py           # FastAPI webhook routes
│   │       │   └── handlers.py         # Event handlers
│   │       └── utils/
│   │           ├── __init__.py
│   │           ├── logging.py
│   │           ├── retry.py
│   │           └── shutdown.py
│   ├── migrations/                     # Alembic
│   │   └── versions/
│   ├── scenarios/                      # Vedro scenarios (tests)
│   │   ├── contexts/
│   │   │   ├── __init__.py
│   │   │   ├── sqlite_client.py        # SQLite test context
│   │   │   └── jj_gitlab_mock.py       # JJ Remote Mock
│   │   ├── interfaces/
│   │   │   └── __init__.py
│   │   ├── unit/
│   │   └── integration/
│   ├── vedro.cfg.py
│   ├── pyproject.toml
│   └── alembic.ini
│
├── frontend/                           # React dashboard
│   ├── src/
│   │   ├── App.tsx
│   │   ├── main.tsx
│   │   ├── types.ts
│   │   ├── api/                        # API client
│   │   │   ├── client.ts               # REST client with auth
│   │   │   └── websocket.ts            # WS client with reconnect
│   │   ├── auth/                       # Auth
│   │   │   ├── AuthContext.tsx
│   │   │   ├── useAuth.ts
│   │   │   └── ProtectedRoute.tsx
│   │   ├── components/
│   │   │   ├── Layout.tsx
│   │   │   └── StatusBadge.tsx
│   │   └── pages/
│   │       ├── Login.tsx               # Login page
│   │       ├── Dashboard.tsx
│   │       ├── History.tsx
│   │       └── Analytics.tsx
│   ├── index.html
│   ├── package.json
│   ├── vite.config.ts
│   ├── tsconfig.json
│   └── tailwind.config.js
│
├── docker/
│   ├── Dockerfile.backend
│   ├── Dockerfile.frontend
│   ├── nginx.conf                      # SPA routing + API proxy
│   ├── docker-compose.yml
│   └── docker-compose.dev.yml
│
├── data/                               # SQLite database (volume mount)
│   └── queue.db
│
└── roadmap/
    └── initial_plan.md
```

---

## Configuration Schema

```python
# backend/src/gitlab_queue/config.py
import environ
from environ import bool_var, var, group

@environ.config(prefix="GITLAB_QUEUE")
class Settings:
    """Application configuration loaded from environment variables."""

    # GitLab Connection
    gitlab_url: str = var(default="https://gitlab.com")
    gitlab_token: str = var()  # Required, no default
    gitlab_project_id: int = var(converter=int)  # Required

    # Target Branch
    target_branch: str = var(default="master")

    # Queue Labels
    queue_label: str = var(default="merge_queue")
    hotfix_label: str = var(default="hotfix")

    # Timing
    poll_interval_seconds: int = var(default=30, converter=int)
    pipeline_timeout_seconds: int = var(default=7200, converter=int)  # 2 hours
    rebase_timeout_seconds: int = var(default=300, converter=int)     # 5 minutes

    # Retry Logic
    pipeline_retry_count: int = var(default=1, converter=int)
    api_max_retries: int = var(default=5, converter=int)

    # Database
    database_url: str = var(default="sqlite+aiosqlite:///data/queue.db")

    # GitLab OAuth
    oauth_client_id: str | None = var(default=None)
    oauth_client_secret: str | None = var(default=None)
    oauth_redirect_uri: str | None = var(default=None)
    jwt_secret: str = var()  # Required for dashboard auth
    jwt_expiration_hours: int = var(default=24, converter=int)

    # Webhook Server
    webhook_enabled: bool = bool_var(default=True)
    webhook_host: str = var(default="0.0.0.0")
    webhook_port: int = var(default=8080, converter=int)
    webhook_secret: str | None = var(default=None)

    # Dashboard
    dashboard_enabled: bool = bool_var(default=True)
    cors_origins: str = var(default="http://localhost:5173")  # Vite dev server

    # Monitoring
    log_level: str = var(default="INFO")
    log_format: str = var(default="json")  # json or console


# Load settings from environment
def load_settings() -> Settings:
    """Load settings from environment variables."""
    return environ.to_config(Settings)
```

### Environment Variables

```bash
# .env.example

# Required
GITLAB_QUEUE_GITLAB_TOKEN=glpat-xxxxxxxxxxxxxxxxxxxx
GITLAB_QUEUE_GITLAB_PROJECT_ID=12345678
GITLAB_QUEUE_JWT_SECRET=your-jwt-secret-key

# Optional - GitLab
GITLAB_QUEUE_GITLAB_URL=https://gitlab.com
GITLAB_QUEUE_TARGET_BRANCH=master
GITLAB_QUEUE_QUEUE_LABEL=merge_queue
GITLAB_QUEUE_HOTFIX_LABEL=hotfix

# Optional - Timing
GITLAB_QUEUE_POLL_INTERVAL_SECONDS=30
GITLAB_QUEUE_PIPELINE_TIMEOUT_SECONDS=7200
GITLAB_QUEUE_REBASE_TIMEOUT_SECONDS=300

# Optional - Database
GITLAB_QUEUE_DATABASE_URL=sqlite+aiosqlite:///data/queue.db

# Optional - GitLab OAuth (for dashboard)
GITLAB_QUEUE_OAUTH_CLIENT_ID=your-oauth-app-id
GITLAB_QUEUE_OAUTH_CLIENT_SECRET=your-oauth-app-secret
GITLAB_QUEUE_OAUTH_REDIRECT_URI=http://localhost:8080/auth/callback

# Optional - Webhook
GITLAB_QUEUE_WEBHOOK_ENABLED=true
GITLAB_QUEUE_WEBHOOK_PORT=8080
GITLAB_QUEUE_WEBHOOK_SECRET=your-webhook-secret

# Optional - Dashboard
GITLAB_QUEUE_DASHBOARD_ENABLED=true
GITLAB_QUEUE_CORS_ORIGINS=http://localhost:5173

# Optional - Logging
GITLAB_QUEUE_LOG_LEVEL=INFO
GITLAB_QUEUE_LOG_FORMAT=json
```

---

## Detailed Implementation Tasks

### Phase 1: Foundation (Tasks 1-15)

#### [DONE]Task 1: Project Setup

**Файлы:** `pyproject.toml`, `.gitignore`, `README.md`

**Действия:**
- Инициализировать проект с pyproject.toml (UV)
- Настроить linting (Ruff) и formatting (Ruff)
- Настроить type checking (mypy)
- Создать базовую структуру директорий

**Acceptance Criteria:**
- [ ] `uv sync` выполняется без ошибок
- [ ] `ruff check .` проходит
- [ ] `mypy src/` проходит
- [ ] Базовая структура директорий создана

---

#### [DONE] Task 2: Configuration Module

**Файлы:** `src/gitlab_queue/config.py`

**Действия:**
- Реализовать environ-config класс с `@environ.config` декоратором
- Добавить конверторы типов (`converter=int`, `bool_var`)
- Создать `load_settings()` функцию для загрузки конфигурации
- Создать `.env.example`

**Пример реализации:**
```python
import environ
from environ import bool_var, var

@environ.config(prefix="GITLAB_QUEUE")
class Settings:
    gitlab_url: str = var(default="https://gitlab.com")
    gitlab_token: str = var()  # Required
    gitlab_project_id: int = var(converter=int)
    webhook_enabled: bool = bool_var(default=True)

def load_settings() -> Settings:
    return environ.to_config(Settings)
```

**Acceptance Criteria:**
- [ ] Все env переменные загружаются корректно через environ-config
- [ ] Конверсия типов работает (int, bool)
- [ ] Токены не логируются (реализовать `__repr__` override или отдельный Secret wrapper)
- [ ] Отсутствующие required поля дают `MissingEnvValueError`

---

#### [DONE] Task 3: Logging Setup

**Файлы:** `src/gitlab_queue/utils/logging.py`

**Действия:**
- Настроить structlog для JSON логирования
- Реализовать QueueHandler для non-blocking логов
- Добавить context variables для request tracking
- Настроить log levels

**Acceptance Criteria:**
- [x] Логи выводятся в JSON формате
- [x] Логи содержат timestamp, level, event, context
- [x] Logging не блокирует event loop
- [x] Sensitive данные (токены) не логируются

---

#### [DONE] Task 4: Database Setup (SQLite + SQLAlchemy)

**Файлы:** `backend/src/gitlab_queue/db/database.py`

**Действия:**
- Создать async SQLAlchemy engine с WAL mode
- Настроить async session factory
- Реализовать health check метод
- Добавить graceful shutdown
- Обернуть в context manager

**Пример реализации:**
```python
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker

engine = create_async_engine(
    "sqlite+aiosqlite:///data/queue.db",
    connect_args={"check_same_thread": False},
    echo=False
)

# Enable WAL mode
async def init_db():
    async with engine.begin() as conn:
        await conn.execute(text("PRAGMA journal_mode=WAL"))

async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
```

**Acceptance Criteria:**
- [ ] Подключение к SQLite работает с aiosqlite
- [ ] WAL mode включен для concurrent reads
- [ ] Async sessions работают корректно
- [ ] Health check возвращает статус
- [ ] Graceful shutdown закрывает соединения

---

#### [DONE] Task 5: GitLab API Client - Base

**Файлы:** `src/gitlab_queue/clients/gitlab.py`

**Действия:**
- Создать async httpx client для GitLab API
- Реализовать authentication через token
- Добавить rate limit handling (429 backoff)
- Добавить общий error handling

**Acceptance Criteria:**
- [ ] GET/POST/PUT запросы работают
- [ ] Token передается в headers
- [ ] 429 ответы приводят к backoff
- [ ] 4xx/5xx логируются с деталями

---

#### [DONE] Task 6: GitLab Client - MR Operations

**Файлы:** `src/gitlab_queue/clients/gitlab.py`

**Действия:**
- Реализовать `get_mr(iid)` — получение MR по IID
- Реализовать `list_mrs_with_label(label)` — список MR с label
- Реализовать `rebase_mr(iid)` — запуск rebase через API
- Реализовать `check_rebase_status(iid)` — проверка статуса rebase

**Acceptance Criteria:**
- [ ] Все методы возвращают типизированные модели
- [ ] Обработка 404 (MR не найден)
- [ ] Rebase асинхронный — возвращает сразу, статус отдельно
- [ ] Timeout для rebase операции

---

#### [DONE] Task 7: GitLab Client - Pipeline Operations

**Файлы:** `src/gitlab_queue/clients/gitlab.py`

**Действия:**
- Реализовать `get_mr_pipelines(iid)` — список pipelines для MR
- Реализовать `get_pipeline_status(pipeline_id)` — статус pipeline
- Реализовать `retry_pipeline_job(job_id)` — ретрай конкретного job

**Acceptance Criteria:**
- [ ] Возвращается последний pipeline для MR
- [ ] Статусы: pending, running, success, failed, canceled
- [ ] Retry job работает

---

#### [DONE] Task 8: GitLab Client - Merge & Comment Operations

**Файлы:** `src/gitlab_queue/clients/gitlab.py`

**Действия:**
- Реализовать `merge_mr(iid)` — выполнение merge
- Реализовать `add_comment(iid, body)` — добавление комментария
- Реализовать `update_comment(iid, note_id, body)` — обновление комментария
- Реализовать `add_or_update_pinned_comment(iid, body)` — single pinned comment

**Acceptance Criteria:**
- [ ] Merge использует fast-forward strategy
- [ ] Проверка merge_status перед merge
- [ ] Комментарий добавляется с markdown
- [ ] Pinned comment обновляется, а не дублируется

---

#### [DONE] Task 9: Data Models (Dataclasses + Adaptix)

**Файлы:** `src/gitlab_queue/models/mr.py`, `src/gitlab_queue/models/pipeline.py`, `src/gitlab_queue/models/retorts.py`

**Действия:**
- Создать MergeRequest dataclass (iid, title, state, labels, sha, etc.)
- Создать Pipeline dataclass (id, status, sha, created_at)
- Создать QueueItem dataclass (mr_iid, state, queued_at, retry_count)
- Создать Retort instances для сериализации GitLab API ↔ dataclass ↔ SQLite

**Пример реализации:**
```python
# src/gitlab_queue/models/mr.py
from dataclasses import dataclass
from datetime import datetime

@dataclass(frozen=True, slots=True)
class MergeRequest:
    iid: int
    title: str
    state: str  # opened, merged, closed
    labels: list[str]
    sha: str
    source_branch: str
    target_branch: str
    merge_status: str
    has_conflicts: bool = False

@dataclass(frozen=True, slots=True)
class Pipeline:
    id: int
    status: str  # pending, running, success, failed, canceled
    sha: str
    created_at: datetime

@dataclass(slots=True)
class QueueItem:
    mr_iid: int
    state: str  # queued, rebasing, testing, merging, merged, failed
    queued_at: datetime
    retry_count: int = 0
    last_error: str | None = None


# src/gitlab_queue/models/retorts.py
from adaptix import Retort, loader, name_mapping, P
from datetime import datetime, timezone

# Retort для GitLab API responses
gitlab_retort = Retort(
    recipe=[
        # GitLab returns ISO timestamps
        loader(datetime, lambda x: datetime.fromisoformat(x.replace("Z", "+00:00"))),
        # Map GitLab field names if needed
        name_mapping(P[MergeRequest], map={"web_url": "url"}),
    ]
)

# Retort для SQLite JSON storage
sqlite_retort = Retort(
    recipe=[
        # Store datetime as ISO string
        loader(datetime, datetime.fromisoformat),
    ]
)

# Usage:
# mr = gitlab_retort.load(api_response, MergeRequest)
# sqlite_data = sqlite_retort.dump(queue_item)
```

**Acceptance Criteria:**
- [ ] Dataclass модели — чистые, без serialization logic
- [ ] GitLab API responses парсятся через `gitlab_retort.load()`
- [ ] QueueItem сериализуется через `sqlite_retort.dump()`
- [ ] Типизация корректная (frozen для immutable, slots для performance)
- [ ] Separation of concerns — модели не знают о serialization

---

#### [DONE] Task 10: Queue Manager - Core Operations

**Файлы:** `backend/src/gitlab_queue/core/queue.py`

**Действия:**
- Реализовать `add_to_queue(mr_iid, priority=False)` — добавление в очередь (INSERT в SQLite)
- Реализовать `remove_from_queue(mr_iid)` — обновление status на 'removed'
- Реализовать `get_queue_position(mr_iid)` — позиция в очереди (ORDER BY queued_at)
- Реализовать `get_next_mr()` — следующий MR для обработки (status='queued', ORDER BY is_hotfix DESC, queued_at ASC)

**SQLite Query Examples:**
```sql
-- Add to queue
INSERT INTO merge_requests (iid, title, ..., status, is_hotfix, queued_at)
VALUES (?, ?, ..., 'queued', ?, CURRENT_TIMESTAMP);

-- Get queue position
SELECT COUNT(*) + 1 FROM merge_requests
WHERE status IN ('queued', 'rebasing', 'testing', 'merging')
AND queued_at < (SELECT queued_at FROM merge_requests WHERE iid = ?);

-- Get next MR
SELECT * FROM merge_requests
WHERE status = 'queued'
ORDER BY is_hotfix DESC, queued_at ASC
LIMIT 1;
```

**Acceptance Criteria:**
- [ ] FIFO порядок для обычных MR
- [ ] Hotfix вставляется в начало (is_hotfix=TRUE приоритет)
- [ ] Транзакции для консистентности данных
- [ ] Идемпотентность add/remove

---

#### [DONE] Task 11: Queue Manager - State Operations

**Файлы:** `backend/src/gitlab_queue/core/queue.py`

**Действия:**
- Реализовать `get_mr_state(mr_iid)` — текущее состояние MR (SELECT status)
- Реализовать `update_mr_state(mr_iid, state, **extra)` — обновление состояния (UPDATE)
- Реализовать `get_queue_stats()` — статистика очереди (COUNT GROUP BY status)
- Реализовать `cleanup_old_entries()` — очистка старых записей (DELETE WHERE finished_at < 90 days)

**SQLite Query Examples:**
```sql
-- Get MR state
SELECT status, started_at, failure_reason FROM merge_requests WHERE iid = ?;

-- Update state
UPDATE merge_requests
SET status = ?, started_at = COALESCE(started_at, CURRENT_TIMESTAMP)
WHERE iid = ?;

-- Get queue stats
SELECT status, COUNT(*) as count FROM merge_requests
WHERE status IN ('queued', 'rebasing', 'testing', 'merging')
GROUP BY status;

-- Cleanup old entries (>90 days)
DELETE FROM merge_requests
WHERE finished_at < datetime('now', '-90 days');
```

**Acceptance Criteria:**
- [ ] Состояние хранится в SQLite таблице merge_requests
- [ ] finished_at заполняется для завершенных MR
- [ ] Статистика: длина очереди, по состояниям
- [ ] Cleanup удаляет записи старше 90 дней

---

#### [DONE] Task 12: State Machine Implementation (с обязательными нотификациями)

**Файлы:** `src/gitlab_queue/core/state_machine.py`

**Действия:**
- Реализовать MRStateMachine с состояниями:
  - queued, rebasing, testing, merging, merged, failed, removed
- Добавить transition guards (can_rebase, can_merge, etc.)
- Добавить async callbacks (on_enter_*, on_exit_*)
- **ОБЯЗАТЕЛЬНО:** Каждый callback вызывает `notifier.notify()` — см. ADR-006
- Интегрировать с Queue Manager

**Пример интеграции с Notifier:**
```python
class MRStateMachine:
    def __init__(self, notifier: MRNotifier, queue: QueueManager):
        self.notifier = notifier
        self.queue = queue

    async def on_enter_queued(self, mr_iid: int):
        position = await self.queue.get_queue_position(mr_iid)
        total = await self.queue.get_queue_length()
        await self.notifier.notify(mr_iid, "queued",
            position=position, total=total,
            estimated_minutes=position * 15,
            queued_at=datetime.now()
        )

    async def on_enter_failed(self, mr_iid: int, reason: str, **details):
        # reason: "conflict", "pipeline_failed", "timeout"
        await self.notifier.notify(mr_iid, reason, **details)
```

**Acceptance Criteria:**
- [ ] Все transitions определены
- [ ] Invalid transitions выбрасывают exception
- [ ] Callbacks выполняются async
- [ ] State persisted в SQLite
- [ ] **КАЖДЫЙ on_enter_* callback вызывает notifier.notify()**
- [ ] Нет "тихих" переходов — всегда есть комментарий

---

#### [DONE] Task 13: Main Processor Loop

**Файлы:** `src/gitlab_queue/core/processor.py`

**Действия:**
- Реализовать главный processing loop:
  1. Получить следующий MR из очереди
  2. Выполнить rebase
  3. Дождаться pipeline
  4. Выполнить merge или обработать ошибку
- Добавить cancellable sleep между итерациями
- Интегрировать state machine

**Acceptance Criteria:**
- [ ] Loop работает continuous
- [ ] Graceful stop через shutdown event
- [ ] Ошибки не останавливают loop
- [ ] Каждый шаг логируется

---

#### [DONE] Task 14: Graceful Shutdown

**Файлы:** `src/gitlab_queue/utils/shutdown.py`, `src/gitlab_queue/main.py`

**Действия:**
- Настроить signal handlers (SIGTERM, SIGINT)
- Реализовать shutdown event
- Дождаться завершения текущей операции
- Закрыть все соединения

**Acceptance Criteria:**
- [ ] SIGTERM инициирует graceful shutdown
- [ ] Текущий MR дообрабатывается или rollback
- [ ] SQLite соединения закрываются
- [ ] HTTP client закрывается
- [ ] Exit code 0 при clean shutdown

---

#### [DONE] Task 15: Application Entry Point

**Файлы:** `src/gitlab_queue/main.py`

**Действия:**
- Инициализировать все компоненты
- Валидировать конфигурацию на старте
- Проверить GitLab permissions
- Запустить processor loop
- Логировать startup info

**Acceptance Criteria:**
- [ ] `python -m gitlab_queue` запускает приложение
- [ ] Startup логи содержат версию, project, target branch
- [ ] Ошибка конфигурации → exit code 1 с понятным сообщением
- [ ] Отсутствие GitLab доступа → exit code 1

---

### Phase 2: Webhook Integration (Tasks 16-22)

#### [DONE] Task 16: FastAPI Application Setup

**Файлы:** `src/gitlab_queue/webhooks/router.py`

**Действия:**
- Создать FastAPI app для webhooks
- Настроить CORS (если нужно)
- Добавить health check endpoint `/health`
- Настроить lifespan events

**Acceptance Criteria:**
- [ ] Server запускается на указанном порту
- [ ] `/health` возвращает 200 OK
- [ ] Lifespan корректно инициализирует dependencies

---

#### [DONE] Task 17: Webhook Event Models (Dataclasses + Adaptix)

**Файлы:** `src/gitlab_queue/models/events.py`

**Действия:**
- Создать dataclass модели для webhook payloads:
  - MergeRequestEvent
  - PipelineEvent
  - NoteEvent (комментарии)
- Создать Retort для парсинга webhook payloads
- Добавить signature validation (отдельная функция)

**Пример реализации:**
```python
# src/gitlab_queue/models/events.py
from dataclasses import dataclass
from adaptix import Retort, name_mapping, P

@dataclass(frozen=True, slots=True)
class MergeRequestEventData:
    iid: int
    title: str
    state: str
    action: str  # open, close, reopen, update, merge, labeled, unlabeled
    labels: list[str]

@dataclass(frozen=True, slots=True)
class MergeRequestEvent:
    object_kind: str  # "merge_request"
    event_type: str
    project_id: int
    object_attributes: MergeRequestEventData

@dataclass(frozen=True, slots=True)
class PipelineEvent:
    object_kind: str  # "pipeline"
    project_id: int
    merge_request_iid: int | None
    status: str
    sha: str

# Retort для webhook payloads
webhook_retort = Retort(
    recipe=[
        name_mapping(
            P[MergeRequestEvent].object_attributes,
            map={"action": "action", "iid": "iid"}
        ),
    ]
)

# Usage:
# event = webhook_retort.load(payload, MergeRequestEvent)
```

**Acceptance Criteria:**
- [ ] Все event types парсятся через `webhook_retort.load()`
- [ ] Signature validation работает (отдельная функция с hmac)
- [ ] Неизвестные events логируются и пропускаются
- [ ] Dataclass модели — immutable (frozen=True)

---

#### [DONE] Task 18: Webhook Handlers - MR Events

**Файлы:** `src/gitlab_queue/webhooks/handlers.py`

**Действия:**
- Обработать `merge_request` event actions:
  - `labeled` — добавить в очередь если label = queue_label
  - `unlabeled` — удалить из очереди если label = queue_label
  - `merge` — удалить из очереди (уже смержен)
  - `close` — удалить из очереди
  - `update` — если новые commits, restart processing

**Acceptance Criteria:**
- [ ] Label добавление → MR в очереди
- [ ] Label удаление → MR удален из очереди
- [ ] MR merge → cleanup
- [ ] Push новых коммитов → restart if processing

---

#### [DONE] Task 19: Webhook Handlers - Pipeline Events

**Файлы:** `src/gitlab_queue/webhooks/handlers.py`

**Действия:**
- Обработать `pipeline` events:
  - `success` — transition to merging if MR in testing state
  - `failed` — retry или fail
  - `canceled` — log and handle

**Acceptance Criteria:**
- [ ] Pipeline success → trigger merge
- [ ] Pipeline fail → retry once → then remove
- [ ] Only react to pipelines for MRs in queue

---

#### [DONE] Task 20: Integrate Webhook Server with Processor

**Файлы:** `src/gitlab_queue/main.py`

**Действия:**
- Запустить FastAPI server в отдельном task
- Координировать с processor loop через async events
- Обеспечить thread-safe queue operations

**Acceptance Criteria:**
- [x] Webhook и processor работают параллельно
- [x] Webhook события обрабатываются немедленно
- [x] Нет race conditions на queue operations

---

#### [DONE] Task 21: Webhook Retry Queue

**Файлы:** `src/gitlab_queue/webhooks/handlers.py`

**Действия:**
- Создать retry queue для failed webhook processing
- Dead letter queue для полностью failed events
- Периодический retry processing

**Acceptance Criteria:**
- [ ] Failed handlers retry 3 раза
- [ ] DLQ для постоянных failures
- [ ] Логирование всех retries

---

#### [DONE] Task 22: Polling Fallback

**Файлы:** `src/gitlab_queue/core/scheduler.py`

**Действия:**
- Реализовать periodic polling (каждые 30 сек)
- Обнаруживать missed webhook events
- Синхронизировать состояние очереди с GitLab

**Acceptance Criteria:**
- [ ] Polling работает даже без webhooks
- [ ] Находит MR с label, которые не в очереди
- [ ] Не дублирует MR уже в очереди

---

### Phase 3: Error Handling & Recovery (Tasks 23-30)

#### [DONE] Task 23: Retry Logic with Tenacity

**Файлы:** `src/gitlab_queue/utils/retry.py`

**Действия:**
- Создать retry decorators для:
  - GitLab API calls
  - SQLite operations
  - Rebase operations
- Exponential backoff с jitter
- Отдельные стратегии для разных ошибок

**Acceptance Criteria:**
- [ ] Transient errors retry автоматически
- [ ] 4xx client errors не retry
- [ ] Backoff не превышает max_wait
- [ ] Все retries логируются

---

#### [DONE] Task 24: Circuit Breaker

**Файлы:** `src/gitlab_queue/clients/gitlab.py`

**Действия:**
- Добавить circuit breaker для GitLab API
- Настроить thresholds (5 failures → open)
- Реализовать half-open state
- Логировать state changes

**Acceptance Criteria:**
- [ ] 5 consecutive failures → circuit open
- [ ] Circuit open → immediate fail для новых requests
- [ ] Half-open после timeout → пробует 1 request
- [ ] Success в half-open → circuit closed

---

#### [DONE] Task 25: Conflict Detection & Reporting

**Файлы:** `src/gitlab_queue/core/processor.py`

**Действия:**
- Детектировать merge conflicts при rebase
- Парсить conflicted files из API response
- Форматировать informative comment для MR
- Удалять из очереди и notify

**Acceptance Criteria:**
- [ ] Конфликты определяются корректно
- [ ] Комментарий содержит список conflicted files
- [ ] MR удаляется из очереди
- [ ] Label НЕ удаляется (пользователь сам решает)

---

#### [DONE] Task 26: Pipeline Failure Handling

**Файлы:** `src/gitlab_queue/core/processor.py`

**Действия:**
- Детектировать failed pipeline
- Определить failed jobs
- Retry logic: 1 retry для flakies
- После 2го failure — удалить из очереди с комментарием

**Acceptance Criteria:**
- [ ] First failure → retry
- [ ] Second failure → remove from queue
- [ ] Комментарий содержит failed job names
- [ ] Логирование failure причин

---

#### [DONE] Task 27: State Recovery After Restart

**Файлы:** `src/gitlab_queue/core/processor.py`

**Действия:**
- На старте: загрузить state из SQLite
- Сверить с GitLab API (MRs с labels)
- Reconcile conflicts:
  - MR in SQLite but no label → mark as removed
  - MR with label but not in SQLite → add to queue
  - MR in processing state → reset to queued

**Acceptance Criteria:**
- [ ] Restart не теряет queue
- [ ] Orphaned SQLite entries cleanup
- [ ] Missing MRs добавляются
- [ ] Processing state reset to queued

---

#### [DONE] Task 28: Timeout Handling

**Файлы:** `src/gitlab_queue/core/processor.py`

**Действия:**
- Pipeline timeout: 2 hours max wait
- Rebase timeout: 5 minutes
- На timeout: remove from queue, comment
- Общий MR timeout: 24h in queue

**Acceptance Criteria:**
- [ ] Pipeline stuck → timeout и удаление
- [ ] Rebase hung → timeout и retry
- [ ] Stale MRs (>24h) → warning comment

---

#### [DONE] Task 29: Rate Limit Handling

**Файлы:** `src/gitlab_queue/clients/gitlab.py`

**Действия:**
- Парсить RateLimit headers из responses
- Implement adaptive throttling
- Pause polling если approaching limit
- Log rate limit status

**Acceptance Criteria:**
- [ ] 429 response → wait for Retry-After
- [ ] Approaching limit (>80%) → slow down
- [ ] Rate limit info в логах
- [ ] Не блокирует event loop во время wait

---

#### [DONE] Task 30: Graceful Degradation

**Файлы:** `src/gitlab_queue/main.py`

**Действия:**
- SQLite unavailable → retry connection indefinitely
- GitLab unavailable → pause processing, keep webhook server
- Partial failures → continue with available operations

**Acceptance Criteria:**
- [ ] SQLite disconnect → reconnect with backoff
- [ ] GitLab 5xx → pause и retry
- [ ] Webhook server stays up during GitLab outage
- [ ] Health endpoint reflects actual status

---

### Phase 4: Monitoring & Operations (Tasks 31-38)

#### [DONE] Task 31: Structured Logging Enhancement

**Файлы:** `src/gitlab_queue/utils/logging.py`

**Действия:**
- Добавить request/operation context
- Добавить timing metrics в logs
- Добавить queue stats periodic logging
- Ensure sensitive data redaction

**Acceptance Criteria:**
- [ ] Каждый log entry имеет correlation ID
- [ ] Operation duration логируется
- [ ] Queue length логируется периодически
- [ ] Tokens/secrets не в логах

---

#### [DONE] Task 32: MR Comments Template System (обязательная обратная связь)

**Файлы:** `src/gitlab_queue/utils/comments.py`, `src/gitlab_queue/core/notifier.py`

**Действия:**
- Создать `MRNotifier` класс для управления комментариями
- Реализовать single pinned comment (один комментарий, обновляется при каждом событии)
- Создать шаблоны для ВСЕХ событий жизненного цикла MR
- Интегрировать notifier в state machine callbacks

**MRNotifier класс:**
```python
# src/gitlab_queue/core/notifier.py
from dataclasses import dataclass
from datetime import datetime

@dataclass
class MRNotifier:
    gitlab_client: GitLabClient
    project_id: int
    _comment_cache: dict[int, int] = field(default_factory=dict)  # mr_iid -> note_id

    async def notify(self, mr_iid: int, status: str, **context) -> None:
        """Update or create pinned comment for MR."""
        body = self._render_template(status, **context)

        if mr_iid in self._comment_cache:
            await self.gitlab_client.update_comment(
                mr_iid, self._comment_cache[mr_iid], body
            )
        else:
            note_id = await self.gitlab_client.add_comment(mr_iid, body)
            self._comment_cache[mr_iid] = note_id
```

**Шаблоны комментариев (все события):**

```python
TEMPLATES = {
    # === QUEUE EVENTS ===
    "queued": '''
## 🤖 Merge Queue Bot

**Status:** ⏳ Added to queue
**Position:** {position} of {total}
**Estimated wait:** ~{estimated_minutes} min
**Queued at:** {queued_at}

---
_Bot will automatically rebase and merge when your turn comes._
_Remove `{queue_label}` label to exit queue._
''',

    "position_changed": '''
## 🤖 Merge Queue Bot

**Status:** ⏳ Waiting in queue
**Position:** {position} of {total} _(was {old_position})_
**Estimated wait:** ~{estimated_minutes} min

---
_Your position changed because MRs ahead were processed._
''',

    # === PROCESSING EVENTS ===
    "rebasing": '''
## 🤖 Merge Queue Bot

**Status:** 🔄 Rebasing
**Started at:** {started_at}

Your turn! Rebasing onto `{target_branch}`...

---
_This usually takes 1-2 minutes._
''',

    "rebase_complete": '''
## 🤖 Merge Queue Bot

**Status:** ✅ Rebase complete
**Rebased at:** {rebased_at}

Waiting for pipeline to start...

---
_Pipeline should start automatically._
''',

    "testing": '''
## 🤖 Merge Queue Bot

**Status:** 🧪 Pipeline running
**Pipeline:** [{pipeline_id}]({pipeline_url})
**Started at:** {started_at}

Waiting for pipeline to complete...

---
_If pipeline fails, bot will retry once before removing from queue._
''',

    "pipeline_retry": '''
## 🤖 Merge Queue Bot

**Status:** 🔁 Pipeline retry ({retry_count}/{max_retries})
**Previous pipeline:** [{old_pipeline_id}]({old_pipeline_url}) — ❌ Failed
**New pipeline:** [{pipeline_id}]({pipeline_url})

Retrying due to failed jobs: {failed_jobs}

---
_This is the last retry attempt._
''',

    # === SUCCESS EVENTS ===
    "merging": '''
## 🤖 Merge Queue Bot

**Status:** 🚀 Merging
**Pipeline:** [{pipeline_id}]({pipeline_url}) — ✅ Passed

Pipeline passed! Merging into `{target_branch}`...
''',

    "merged": '''
## 🤖 Merge Queue Bot

**Status:** ✅ Successfully merged!
**Merged at:** {merged_at}
**Time in queue:** {duration}

🎉 Your changes are now in `{target_branch}`.

---
_Thank you for using Merge Queue Bot!_
''',

    # === FAILURE EVENTS ===
    "conflict": '''
## 🤖 Merge Queue Bot

**Status:** ❌ Rebase conflict
**Failed at:** {failed_at}

Cannot rebase onto `{target_branch}` due to conflicts in:
{conflicted_files}

**Action required:**
1. Resolve conflicts locally
2. Push updated branch
3. Re-add `{queue_label}` label to rejoin queue

---
_MR has been removed from queue._
''',

    "pipeline_failed": '''
## 🤖 Merge Queue Bot

**Status:** ❌ Pipeline failed
**Pipeline:** [{pipeline_id}]({pipeline_url})
**Failed at:** {failed_at}

Pipeline failed after {retry_count} attempt(s).

**Failed jobs:**
{failed_jobs}

**Action required:**
1. Fix failing tests/jobs
2. Push updated branch
3. Re-add `{queue_label}` label to rejoin queue

---
_MR has been removed from queue._
''',

    "timeout": '''
## 🤖 Merge Queue Bot

**Status:** ⏰ Timeout
**Failed at:** {failed_at}
**Time in queue:** {duration}

MR exceeded maximum wait time ({max_wait} hours).

**Possible reasons:**
- Pipeline taking too long
- Stuck in rebasing state

**Action required:**
Re-add `{queue_label}` label to rejoin queue.

---
_MR has been removed from queue._
''',

    # === REMOVAL EVENTS ===
    "removed_label": '''
## 🤖 Merge Queue Bot

**Status:** 🚪 Removed from queue
**Removed at:** {removed_at}
**Was at position:** {position}

Label `{queue_label}` was removed.

---
_Add label back to rejoin queue._
''',

    "removed_closed": '''
## 🤖 Merge Queue Bot

**Status:** 🚪 Removed from queue
**Removed at:** {removed_at}

MR was closed.
''',
}
```

**Интеграция с State Machine:**
```python
# src/gitlab_queue/core/state_machine.py
class MRStateMachine:
    def __init__(self, notifier: MRNotifier, ...):
        self.notifier = notifier

    async def on_enter_rebasing(self, mr_iid: int):
        await self.notifier.notify(mr_iid, "rebasing",
            started_at=datetime.now(),
            target_branch=self.target_branch
        )

    async def on_enter_testing(self, mr_iid: int, pipeline_id: int):
        await self.notifier.notify(mr_iid, "testing",
            pipeline_id=pipeline_id,
            pipeline_url=f"{self.gitlab_url}/-/pipelines/{pipeline_id}",
            started_at=datetime.now()
        )
    # ... etc for all transitions
```

**Acceptance Criteria:**
- [ ] КАЖДЫЙ transition в state machine вызывает `notifier.notify()`
- [ ] Single pinned comment — один комментарий на MR, обновляется
- [ ] Все 14 шаблонов реализованы
- [ ] Markdown рендерится корректно в GitLab
- [ ] Emoji для visual scanning
- [ ] Timestamps в каждом комментарии
- [ ] Actionable messages — что делать при ошибке
- [ ] Links на pipelines кликабельны

---

#### [DONE] Task 33: Health Check Endpoint

**Файлы:** `src/gitlab_queue/webhooks/router.py`

**Действия:**
- `/health` — basic liveness
- `/ready` — full readiness (SQLite, GitLab connected)
- `/metrics` — Prometheus format metrics (optional)

**Acceptance Criteria:**
- [ ] `/health` returns 200 если process alive
- [ ] `/ready` returns 503 если SQLite/GitLab down
- [ ] Docker HEALTHCHECK использует `/health`

---

#### [DONE] Task 34: Prometheus Metrics (Optional)

**Файлы:** `src/gitlab_queue/utils/metrics.py`

**Действия:**
- Metrics:
  - `merge_queue_length` (gauge)
  - `merge_queue_mr_duration_seconds` (histogram)
  - `merge_queue_operations_total` (counter by type/status)
  - `merge_queue_gitlab_api_latency_seconds` (histogram)
- Expose via `/metrics` endpoint

**Acceptance Criteria:**
- [ ] Prometheus can scrape `/metrics`
- [ ] All metrics have help text
- [ ] Labels для type и status

---

#### [DONE] Task 35: Queue Status Dashboard Data

**Файлы:** `src/gitlab_queue/core/queue.py`

**Действия:**
- Endpoint для queue status:
  - Current queue (MRs, positions, states)
  - Recent history (last 10 merged)
  - Statistics (avg wait time, success rate)
- JSON format для consumption

**Acceptance Criteria:**
- [ ] `/api/queue` returns current state
- [ ] Includes all MRs with metadata
- [ ] Historical stats available

---

#### [DONE] Task 36: Docker Setup

**Файлы:** `docker/Dockerfile`, `docker/docker-compose.yml`

**Действия:**
- Multi-stage Dockerfile (builder + runtime)
- Non-root user
- Health check
- Docker Compose с SQLite volume
- Volume для SQLite persistence

**Acceptance Criteria:**
- [ ] `docker compose up` запускает всё
- [ ] Image size < 200MB
- [ ] Runs as non-root
- [ ] Health checks работают
- [ ] SQLite data persisted

---

#### [DONE] Task 37: README Documentation

**Файлы:** `README.md`

**Секции:**
1. Overview / Problem statement
2. Features
3. Quick Start
4. Configuration Reference
5. GitLab Setup (Protected Branches, Webhooks)
6. Deployment Options (Docker, Kubernetes hints)
7. Monitoring
8. Troubleshooting / FAQ
9. Contributing

**Acceptance Criteria:**
- [ ] Copy-paste ready commands
- [ ] Screenshots где нужно
- [ ] All env vars documented
- [ ] Common errors explained

---

#### [DONE] Task 38: Development Tooling

**Файлы:** `scripts/dev.sh`, `Makefile`

**Действия:**
- `make dev` — запуск с hot reload
- `make test` — запуск Vedro тестов (`vedro run scenarios/`)
- `make test-random` — запуск в random order (`vedro run scenarios/ --order-random`)
- `make test-v` — verbose mode (`vedro run scenarios/ -v`)
- `make lint` — linting
- `make format` — formatting
- `make docker-build` — build image
- `make docker-up` — запуск в Docker

**Makefile snippet:**
```makefile
.PHONY: test test-random test-v

test:
	vedro run scenarios/

test-random:
	vedro run scenarios/ --order-random

test-v:
	vedro run scenarios/ -v

test-changed:
	vedro run scenarios/ --changed-against-branch=main
```

**Acceptance Criteria:**
- [ ] One command для каждой операции
- [ ] Dev mode с auto-reload
- [ ] Pre-commit hooks настроены
- [ ] `make test` запускает все Vedro сценарии

---

### Phase 5: Testing with Vedro (Tasks 39-45)

> **Vedro** — BDD-style тестовый фреймворк с нативной поддержкой async.
> Документация: https://vedro.io/docs/quick-start

#### [DONE] Task 39: Vedro Test Infrastructure

**Файлы:** `vedro.cfg.py`, `scenarios/contexts/`, `pyproject.toml`

**Действия:**
- Установить vedro и jj: `pip install vedro jj aiosqlite`
- Создать `vedro.cfg.py` с базовой конфигурацией
- Создать contexts для SQLite (in-memory) и GitLab API (jj Remote Mock)
- Настроить `vedro-coverage` плагин для coverage
- Запустить JJ mock server для тестов

**vedro.cfg.py пример:**
```python
import vedro
import vedro.plugins.director.rich as rich_reporter

class Config(vedro.Config):
    class Plugins(vedro.Config.Plugins):
        class RichReporter(rich_reporter.RichReporter):
            enabled = True
            show_scenario_spinner = True
```

**Context пример (scenarios/contexts/sqlite_client.py):**
```python
import vedro
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker

@vedro.context
async def test_db():
    """Provides in-memory SQLite for testing."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async_session = async_sessionmaker(engine, class_=AsyncSession)
    async with async_session() as session:
        yield session

    await engine.dispose()
```

**JJ Remote Mock Context (scenarios/contexts/jj_gitlab_mock.py):**
```python
import vedro
import jj
from jj.mock import mocked

JJ_MOCK_URL = "http://localhost:8080"

@vedro.context
def gitlab_mock_server():
    """Provides JJ mock server URL for GitLab API mocking."""
    return JJ_MOCK_URL

@vedro.context
async def mock_gitlab_get_mr(mr_iid: int, mr_data: dict):
    """Mock GitLab GET /merge_requests/:iid endpoint."""
    matcher = jj.match("GET", f"/api/v4/projects/*/merge_requests/{mr_iid}")
    response = jj.Response(status=200, json=mr_data)
    async with mocked(matcher, response) as mock:
        yield mock

@vedro.context
async def mock_gitlab_list_mrs(label: str, mrs_data: list):
    """Mock GitLab GET /merge_requests with label filter."""
    matcher = jj.match("GET", "/api/v4/projects/*/merge_requests", params={"labels": label})
    response = jj.Response(status=200, json=mrs_data)
    async with mocked(matcher, response) as mock:
        yield mock

@vedro.context
async def mock_gitlab_rebase(mr_iid: int, success: bool = True):
    """Mock GitLab PUT /merge_requests/:iid/rebase endpoint."""
    matcher = jj.match("PUT", f"/api/v4/projects/*/merge_requests/{mr_iid}/rebase")
    if success:
        response = jj.Response(status=202, json={"rebase_in_progress": True})
    else:
        response = jj.Response(status=409, json={"message": "Merge conflict"})
    async with mocked(matcher, response) as mock:
        yield mock

@vedro.context
async def mock_gitlab_merge(mr_iid: int, success: bool = True):
    """Mock GitLab PUT /merge_requests/:iid/merge endpoint."""
    matcher = jj.match("PUT", f"/api/v4/projects/*/merge_requests/{mr_iid}/merge")
    if success:
        response = jj.Response(status=200, json={"state": "merged"})
    else:
        response = jj.Response(status=405, json={"message": "Not mergeable"})
    async with mocked(matcher, response) as mock:
        yield mock
```

**Запуск JJ Mock Server (перед тестами):**
```bash
# В отдельном терминале или через docker-compose
jj --port 8080

# Или через Docker
docker run -p 8080:80 ghcr.io/jj-mock/jj
```

**Acceptance Criteria:**
- [ ] `vedro run scenarios/` выполняет все тесты
- [ ] Async scenarios работают из коробки
- [ ] JJ mock server запущен и доступен
- [ ] SQLite in-memory для изолированных тестов
- [ ] No real network calls — все через JJ Remote Mock

---

#### [DONE] Task 40: Queue Manager Scenarios

**Файлы:** `scenarios/unit/queue_*.py`

**Сценарии (function-based syntax):**
```python
# scenarios/unit/queue_add_mr.py
from vedro import scenario, given, when, then
from contexts.sqlite_client import test_db

@scenario()
async def add_mr_to_empty_queue():
    with given:
        db = await test_db()
        queue = QueueManager(db, project_id=123)
        mr_iid = 42

    with when:
        await queue.add_to_queue(mr_iid)

    with then:
        position = await queue.get_queue_position(mr_iid)
        assert position == 1
```

**Тесты:**
- `queue_add_mr.py` — добавление в очередь (empty, non-empty, duplicate)
- `queue_remove_mr.py` — удаление из очереди
- `queue_hotfix_priority.py` — приоритет hotfix
- `queue_fifo_order.py` — FIFO порядок

**Acceptance Criteria:**
- [ ] >90% coverage для queue.py
- [ ] Edge cases covered через параметризованные сценарии
- [ ] Concurrent operations tested

---

#### [DONE] Task 41: State Machine Scenarios

**Файлы:** `scenarios/unit/state_machine_*.py`

**Сценарии:**
```python
# scenarios/unit/state_machine_transitions.py
from vedro import scenario, given, when, then

@scenario()
async def transition_queued_to_rebasing():
    with given:
        sm = MRStateMachine(initial_state="queued")

    with when:
        await sm.start_processing()

    with then:
        assert sm.current_state == "rebasing"

@scenario()
async def invalid_transition_raises_error():
    with given:
        sm = MRStateMachine(initial_state="merged")

    with when:
        error = None
        try:
            await sm.start_processing()
        except InvalidTransitionError as e:
            error = e

    with then:
        assert error is not None
```

**Acceptance Criteria:**
- [ ] All states reachable
- [ ] All transitions tested
- [ ] Guards работают
- [ ] Async callbacks executed

---

#### [DONE] Task 42: GitLab Client Scenarios (с JJ Remote Mock)

**Файлы:** `scenarios/unit/gitlab_client_*.py`, `scenarios/contexts/jj_gitlab_mock.py`

**Сценарий с JJ Remote Mock:**
```python
# scenarios/unit/gitlab_client_get_mr.py
from vedro import scenario, given, when, then
import jj
from jj.mock import mocked
from gitlab_queue.clients.gitlab import GitLabClient
from gitlab_queue.config import Settings

JJ_MOCK_URL = "http://localhost:8080"

@scenario()
async def get_mr_returns_mr_data():
    with given("GitLab API returns MR data"):
        mr_data = {"iid": 42, "title": "Test MR", "state": "opened", "labels": ["merge_queue"]}
        matcher = jj.match("GET", "/api/v4/projects/123/merge_requests/42")
        response = jj.Response(status=200, json=mr_data)

    async with mocked(matcher, response):
        with when("client fetches MR"):
            settings = Settings(gitlab_url=JJ_MOCK_URL, gitlab_project_id=123, gitlab_token="test")
            client = GitLabClient(settings)
            result = await client.get_mr(42)

        with then("MR data is returned"):
            assert result.iid == 42
            assert result.title == "Test MR"
            assert "merge_queue" in result.labels

@scenario()
async def get_mr_handles_404():
    with given("GitLab API returns 404"):
        matcher = jj.match("GET", "/api/v4/projects/123/merge_requests/999")
        response = jj.Response(status=404, json={"message": "Not found"})

    async with mocked(matcher, response):
        with when("client fetches non-existent MR"):
            settings = Settings(gitlab_url=JJ_MOCK_URL, gitlab_project_id=123, gitlab_token="test")
            client = GitLabClient(settings)
            result = await client.get_mr(999)

        with then("None is returned"):
            assert result is None

@scenario()
async def get_mr_handles_rate_limit():
    with given("GitLab API returns 429 rate limit"):
        matcher = jj.match("GET", "/api/v4/projects/123/merge_requests/42")
        response = jj.Response(status=429, headers={"Retry-After": "60"})

    async with mocked(matcher, response):
        with when("client fetches MR"):
            settings = Settings(gitlab_url=JJ_MOCK_URL, gitlab_project_id=123, gitlab_token="test")
            client = GitLabClient(settings)
            # Should trigger retry logic

        with then("RateLimitError is raised"):
            # Verify retry behavior via JJ history
            pass
```

**Проверка истории запросов (JJ History):**
```python
@scenario()
async def rebase_sends_correct_request():
    with given("GitLab API accepts rebase"):
        matcher = jj.match("PUT", "/api/v4/projects/123/merge_requests/42/rebase")
        response = jj.Response(status=202, json={"rebase_in_progress": True})

    async with mocked(matcher, response) as mock:
        with when("client triggers rebase"):
            settings = Settings(gitlab_url=JJ_MOCK_URL, gitlab_project_id=123, gitlab_token="test")
            client = GitLabClient(settings)
            await client.rebase_mr(42)

        with then("correct request was sent"):
            history = await mock.fetch_history()
            assert len(history) == 1
            assert history[0].method == "PUT"
            assert "PRIVATE-TOKEN" in history[0].headers
```

**Тесты:**
- `gitlab_client_get_mr.py` — successful API calls via JJ mock
- `gitlab_client_errors.py` — error handling (404, 429, 500) via JJ responses
- `gitlab_client_retry.py` — retry logic с JJ history проверкой
- `gitlab_client_circuit_breaker.py` — circuit breaker с серией JJ 500 responses

**Acceptance Criteria:**
- [ ] All API methods tested через JJ Remote Mock
- [ ] Error scenarios covered через JJ Response status codes
- [ ] Request history проверяется через `mock.fetch_history()`
- [ ] Realistic HTTP responses от JJ mock server

---

#### [DONE] Task 43: Processor Scenarios (с JJ Remote Mock)

**Файлы:** `scenarios/unit/processor_*.py`

**Сценарии с JJ mock для полного flow:**
```python
# scenarios/unit/processor_happy_path.py
from vedro import scenario, given, when, then
import jj
from jj.mock import mocked
from contexts.sqlite_client import test_db
from gitlab_queue.core.processor import Processor
from gitlab_queue.core.queue import QueueManager
from gitlab_queue.clients.gitlab import GitLabClient
from gitlab_queue.config import Settings

JJ_MOCK_URL = "http://localhost:8080"

@scenario()
async def process_mr_successfully():
    with given("MR in queue and GitLab API mocked for success flow"):
        # Setup SQLite queue
        db = await test_db()
        queue = QueueManager(db, project_id=123)
        await queue.add_to_queue(42)

        # Setup JJ mocks for full flow
        mr_data = {"iid": 42, "title": "Test MR", "state": "opened", "sha": "abc123"}
        pipeline_data = {"id": 1, "status": "success", "sha": "abc123"}

        get_mr_matcher = jj.match("GET", "/api/v4/projects/123/merge_requests/42")
        get_mr_response = jj.Response(status=200, json=mr_data)

        rebase_matcher = jj.match("PUT", "/api/v4/projects/123/merge_requests/42/rebase")
        rebase_response = jj.Response(status=202, json={"rebase_in_progress": False})

        pipelines_matcher = jj.match("GET", "/api/v4/projects/123/merge_requests/42/pipelines")
        pipelines_response = jj.Response(status=200, json=[pipeline_data])

        merge_matcher = jj.match("PUT", "/api/v4/projects/123/merge_requests/42/merge")
        merge_response = jj.Response(status=200, json={"state": "merged"})

        comment_matcher = jj.match("POST", "/api/v4/projects/123/merge_requests/42/notes")
        comment_response = jj.Response(status=201, json={"id": 1})

    async with mocked(get_mr_matcher, get_mr_response), \
               mocked(rebase_matcher, rebase_response), \
               mocked(pipelines_matcher, pipelines_response), \
               mocked(merge_matcher, merge_response) as merge_mock, \
               mocked(comment_matcher, comment_response):

        with when("processor runs one cycle"):
            settings = Settings(gitlab_url=JJ_MOCK_URL, gitlab_project_id=123, gitlab_token="test")
            gitlab = GitLabClient(settings)
            processor = Processor(queue, gitlab)
            await processor.process_next()

        with then("MR is merged"):
            # Verify merge was called
            history = await merge_mock.fetch_history()
            assert len(history) == 1
            # Verify queue state
            state = await queue.get_mr_state(42)
            assert state == "merged"

@scenario()
async def process_mr_with_conflict():
    with given("GitLab returns rebase conflict"):
        db = await test_db()
        queue = QueueManager(db, project_id=123)
        await queue.add_to_queue(42)

        mr_data = {"iid": 42, "title": "Test MR", "state": "opened"}
        get_mr_matcher = jj.match("GET", "/api/v4/projects/123/merge_requests/42")
        get_mr_response = jj.Response(status=200, json=mr_data)

        rebase_matcher = jj.match("PUT", "/api/v4/projects/123/merge_requests/42/rebase")
        rebase_response = jj.Response(status=409, json={"message": "Merge conflict"})

        comment_matcher = jj.match("POST", "/api/v4/projects/123/merge_requests/42/notes")
        comment_response = jj.Response(status=201, json={"id": 1})

    async with mocked(get_mr_matcher, get_mr_response), \
               mocked(rebase_matcher, rebase_response), \
               mocked(comment_matcher, comment_response) as comment_mock:

        with when("processor tries to process MR"):
            settings = Settings(gitlab_url=JJ_MOCK_URL, gitlab_project_id=123, gitlab_token="test")
            gitlab = GitLabClient(settings)
            processor = Processor(queue, gitlab)
            await processor.process_next()

        with then("MR is removed from queue with conflict comment"):
            state = await queue.get_mr_state(42)
            assert state == "failed"
            # Verify conflict comment was posted
            history = await comment_mock.fetch_history()
            assert len(history) == 1
            assert "conflict" in history[0].body.lower()
```

**Тесты:**
- `processor_happy_path.py` — Full flow с JJ mocks для всех GitLab endpoints
- `processor_conflict.py` — Conflict handling (JJ returns 409)
- `processor_pipeline_failure.py` — Pipeline failure + retry (JJ returns failed pipeline)
- `processor_timeout.py` — Timeout handling (slow JJ responses)
- `processor_shutdown.py` — Graceful shutdown

**Acceptance Criteria:**
- [x] Full flow tested с real HTTP через JJ mock
- [x] All error paths tested через JJ response status codes
- [x] Request history verification через `mock.fetch_history()`
- [x] Graceful shutdown tested

---

#### [DONE] Task 44: Integration Scenarios - Webhook Flow (с JJ Remote Mock)

**Файлы:** `scenarios/integration/webhook_*.py`

**Сценарии с JJ mock для обратных вызовов GitLab:**
```python
# scenarios/integration/webhook_mr_labeled.py
from vedro import scenario, given, when, then
import jj
from jj.mock import mocked
from httpx import AsyncClient
from fastapi.testclient import TestClient
from contexts.sqlite_client import test_db

JJ_MOCK_URL = "http://localhost:8080"

@scenario()
async def mr_labeled_adds_to_queue():
    with given("webhook server running and GitLab API mocked"):
        # Setup SQLite
        db = await test_db()

        # Setup app with JJ mock URL
        app = create_app(gitlab_url=JJ_MOCK_URL, db=db)
        client = TestClient(app)

        # Webhook payload
        webhook_payload = create_mr_labeled_event(mr_iid=42, label="merge_queue")

        # Mock GitLab API responses (для комментария о добавлении в очередь)
        mr_data = {"iid": 42, "title": "Test MR", "state": "opened"}
        get_mr_matcher = jj.match("GET", "/api/v4/projects/*/merge_requests/42")
        get_mr_response = jj.Response(status=200, json=mr_data)

        comment_matcher = jj.match("POST", "/api/v4/projects/*/merge_requests/42/notes")
        comment_response = jj.Response(status=201, json={"id": 1})

    async with mocked(get_mr_matcher, get_mr_response), \
               mocked(comment_matcher, comment_response) as comment_mock:

        with when("webhook received"):
            response = client.post("/webhook", json=webhook_payload)

        with then("MR added to queue and comment posted"):
            assert response.status_code == 200
            # Check SQLite queue
            queue_length = await queue.get_queue_length()
            assert queue_length == 1
            # Verify comment was posted to GitLab
            history = await comment_mock.fetch_history()
            assert len(history) == 1
            assert "queue" in history[0].body.lower()

@scenario()
async def mr_unlabeled_removes_from_queue():
    with given("MR in queue and webhook server running"):
        db = await test_db()
        queue = QueueManager(db, project_id=123)
        # Pre-populate queue
        await queue.add_to_queue(42)

        app = create_app(gitlab_url=JJ_MOCK_URL, db=db)
        client = TestClient(app)

        webhook_payload = create_mr_unlabeled_event(mr_iid=42, label="merge_queue")

        # Mock GitLab API for removal comment
        comment_matcher = jj.match("POST", "/api/v4/projects/*/merge_requests/42/notes")
        comment_response = jj.Response(status=201, json={"id": 1})

    async with mocked(comment_matcher, comment_response):

        with when("unlabel webhook received"):
            response = client.post("/webhook", json=webhook_payload)

        with then("MR removed from queue"):
            assert response.status_code == 200
            queue_length = await queue.get_queue_length()
            assert queue_length == 0

@scenario()
async def pipeline_success_triggers_merge():
    with given("MR in testing state and pipeline success webhook"):
        db = await test_db()
        queue = QueueManager(db, project_id=123)
        # Pre-populate queue with MR in testing state
        await queue.add_to_queue(42)
        await queue.update_mr_state(42, "testing")

        app = create_app(gitlab_url=JJ_MOCK_URL, db=db)
        client = TestClient(app)

        webhook_payload = create_pipeline_event(mr_iid=42, status="success", sha="abc123")

        # Mock GitLab API for merge
        merge_matcher = jj.match("PUT", "/api/v4/projects/*/merge_requests/42/merge")
        merge_response = jj.Response(status=200, json={"state": "merged"})

        comment_matcher = jj.match("POST", "/api/v4/projects/*/merge_requests/42/notes")
        comment_response = jj.Response(status=201, json={"id": 1})

    async with mocked(merge_matcher, merge_response) as merge_mock, \
               mocked(comment_matcher, comment_response):

        with when("pipeline success webhook received"):
            response = client.post("/webhook", json=webhook_payload)

        with then("MR is merged"):
            assert response.status_code == 200
            # Verify merge API was called
            history = await merge_mock.fetch_history()
            assert len(history) == 1
```

**Тесты:**
- `webhook_mr_labeled.py` — Label добавление через webhook + JJ mock для комментария
- `webhook_mr_unlabeled.py` — Label удаление через webhook
- `webhook_pipeline_events.py` — Pipeline success/failure через webhook
- `webhook_signature_validation.py` — Проверка webhook secret

**Acceptance Criteria:**
- [ ] End-to-end webhook flow works с real HTTP calls через JJ
- [ ] FastAPI TestClient + JJ Remote Mock интеграция
- [ ] GitLab callbacks (comments, merge) мокируются через JJ
- [ ] Request history проверяется через `mock.fetch_history()`

---

#### [DONE] Task 45: Integration Scenarios - Full Flow (с JJ Remote Mock)

**Файлы:** `scenarios/integration/full_flow_*.py`

**Сценарии с JJ mock для полного E2E flow:**
```python
# scenarios/integration/full_flow_multiple_mrs.py
from vedro import scenario, given, when, then
import jj
from jj.mock import mocked
from contexts.sqlite_client import test_db
from gitlab_queue.core.processor import Processor
from gitlab_queue.core.queue import QueueManager
from gitlab_queue.clients.gitlab import GitLabClient
from gitlab_queue.config import Settings

JJ_MOCK_URL = "http://localhost:8080"

def create_mr_mock(mr_iid: int):
    """Helper to create JJ matchers for a single MR."""
    mr_data = {"iid": mr_iid, "title": f"MR #{mr_iid}", "state": "opened", "sha": f"sha{mr_iid}"}
    pipeline_data = {"id": mr_iid * 10, "status": "success", "sha": f"sha{mr_iid}"}

    return {
        "get_mr": (
            jj.match("GET", f"/api/v4/projects/*/merge_requests/{mr_iid}"),
            jj.Response(status=200, json=mr_data)
        ),
        "rebase": (
            jj.match("PUT", f"/api/v4/projects/*/merge_requests/{mr_iid}/rebase"),
            jj.Response(status=202, json={"rebase_in_progress": False})
        ),
        "pipelines": (
            jj.match("GET", f"/api/v4/projects/*/merge_requests/{mr_iid}/pipelines"),
            jj.Response(status=200, json=[pipeline_data])
        ),
        "merge": (
            jj.match("PUT", f"/api/v4/projects/*/merge_requests/{mr_iid}/merge"),
            jj.Response(status=200, json={"state": "merged"})
        ),
        "comment": (
            jj.match("POST", f"/api/v4/projects/*/merge_requests/{mr_iid}/notes"),
            jj.Response(status=201, json={"id": 1})
        ),
    }

@scenario()
async def process_multiple_mrs_in_order():
    with given("3 MRs in queue with JJ mocks for all"):
        db = await test_db()
        queue = QueueManager(db, project_id=123)

        # Add MRs in order
        for mr_iid in [10, 20, 30]:
            await queue.add_to_queue(mr_iid)

        # Create JJ mocks for all 3 MRs
        mr_mocks = {iid: create_mr_mock(iid) for iid in [10, 20, 30]}

        # Collect all merge matchers for order verification
        merge_mocks = {}

    # Setup all mocks using JJ
    async with jj.RemoteMock(JJ_MOCK_URL) as remote:
        # Register all mocks
        for mr_iid, mocks in mr_mocks.items():
            for name, (matcher, response) in mocks.items():
                mock = await remote.add(matcher, response)
                if name == "merge":
                    merge_mocks[mr_iid] = mock

        with when("processor runs until queue empty"):
            settings = Settings(gitlab_url=JJ_MOCK_URL, gitlab_project_id=123, gitlab_token="test")
            gitlab = GitLabClient(settings)
            processor = Processor(queue, gitlab)

            while await queue.get_queue_length() > 0:
                await processor.process_next()

        with then("all MRs merged in FIFO order"):
            # Verify each MR was merged
            for mr_iid in [10, 20, 30]:
                history = await merge_mocks[mr_iid].fetch_history()
                assert len(history) == 1, f"MR {mr_iid} should be merged exactly once"

            # Verify queue is empty
            assert await queue.get_queue_length() == 0

@scenario()
async def hotfix_jumps_to_front_of_queue():
    with given("2 MRs in queue, then hotfix arrives"):
        db = await test_db()
        queue = QueueManager(db, project_id=123)

        # Add regular MRs
        await queue.add_to_queue(10)
        await queue.add_to_queue(20)

        # Add hotfix with priority
        await queue.add_to_queue(99, priority=True)

        # JJ mocks for all MRs
        hotfix_merge_matcher = jj.match("PUT", "/api/v4/projects/*/merge_requests/99/merge")
        hotfix_merge_response = jj.Response(status=200, json={"state": "merged"})

        # Setup all success mocks
        get_any_mr = jj.match("GET", "/api/v4/projects/*/merge_requests/*")
        get_mr_response = jj.Response(status=200, json={"iid": 99, "state": "opened", "sha": "hotfix"})

        rebase_any = jj.match("PUT", "/api/v4/projects/*/merge_requests/*/rebase")
        rebase_response = jj.Response(status=202, json={"rebase_in_progress": False})

        pipelines_any = jj.match("GET", "/api/v4/projects/*/merge_requests/*/pipelines")
        pipelines_response = jj.Response(status=200, json=[{"id": 1, "status": "success"}])

        comment_any = jj.match("POST", "/api/v4/projects/*/merge_requests/*/notes")
        comment_response = jj.Response(status=201, json={"id": 1})

    async with mocked(get_any_mr, get_mr_response), \
               mocked(rebase_any, rebase_response), \
               mocked(pipelines_any, pipelines_response), \
               mocked(hotfix_merge_matcher, hotfix_merge_response) as hotfix_mock, \
               mocked(comment_any, comment_response):

        with when("processor runs one cycle"):
            settings = Settings(gitlab_url=JJ_MOCK_URL, gitlab_project_id=123, gitlab_token="test")
            gitlab = GitLabClient(settings)
            processor = Processor(queue, gitlab)
            await processor.process_next()

        with then("hotfix is processed first"):
            history = await hotfix_mock.fetch_history()
            assert len(history) == 1, "Hotfix should be merged first"

@scenario()
async def restart_recovery_continues_processing():
    with given("MR stuck in 'rebasing' state after restart"):
        db = await test_db()
        queue = QueueManager(db, project_id=123)
        # Simulate state after crash — MR in rebasing state
        await queue.add_to_queue(42)
        await queue.update_mr_state(42, "rebasing")

        # JJ mocks
        mr_data = {"iid": 42, "title": "Test MR", "state": "opened", "sha": "new_sha"}
        get_mr_matcher = jj.match("GET", "/api/v4/projects/*/merge_requests/42")
        get_mr_response = jj.Response(status=200, json=mr_data)

        rebase_matcher = jj.match("PUT", "/api/v4/projects/*/merge_requests/42/rebase")
        rebase_response = jj.Response(status=202, json={"rebase_in_progress": False})

        pipelines_matcher = jj.match("GET", "/api/v4/projects/*/merge_requests/42/pipelines")
        pipelines_response = jj.Response(status=200, json=[{"id": 1, "status": "success", "sha": "new_sha"}])

        merge_matcher = jj.match("PUT", "/api/v4/projects/*/merge_requests/42/merge")
        merge_response = jj.Response(status=200, json={"state": "merged"})

        comment_matcher = jj.match("POST", "/api/v4/projects/*/merge_requests/42/notes")
        comment_response = jj.Response(status=201, json={"id": 1})

    async with mocked(get_mr_matcher, get_mr_response), \
               mocked(rebase_matcher, rebase_response), \
               mocked(pipelines_matcher, pipelines_response), \
               mocked(merge_matcher, merge_response) as merge_mock, \
               mocked(comment_matcher, comment_response):

        with when("processor runs recovery and continues"):
            settings = Settings(gitlab_url=JJ_MOCK_URL, gitlab_project_id=123, gitlab_token="test")
            gitlab = GitLabClient(settings)
            processor = Processor(queue, gitlab)
            await processor.recover_state()  # Recovery on startup
            await processor.process_next()

        with then("MR is eventually merged"):
            history = await merge_mock.fetch_history()
            assert len(history) == 1
```

**Тесты:**
- `full_flow_multiple_mrs.py` — Multiple MRs processed in FIFO order
- `full_flow_hotfix.py` — Hotfix priority (jumps to front)
- `full_flow_restart.py` — Restart recovery (state from SQLite + JJ mock)
- `full_flow_concurrent.py` — Concurrent webhook + polling (race conditions)

**Запуск в random order для anti-flaky:**
```bash
vedro run scenarios/ --order-random
```

**Docker Compose для тестов с JJ Mock Server:**
```yaml
# docker/docker-compose.test.yml
services:
  jj-mock:
    image: ghcr.io/jj-mock/jj
    ports:
      - "8080:80"
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:80/__jj__/health"]
      interval: 5s
      timeout: 3s
      retries: 3

  tests:
    build: .
    depends_on:
      jj-mock:
        condition: service_healthy
    environment:
      - JJ_MOCK_URL=http://jj-mock:80
      - DATABASE_URL=sqlite+aiosqlite:///:memory:
    command: vedro run scenarios/
```

**Makefile команды для тестов с JJ:**
```makefile
.PHONY: test-with-jj

test-with-jj:
	docker compose -f docker/docker-compose.test.yml up --build --abort-on-container-exit

test-jj-up:
	docker compose -f docker/docker-compose.test.yml up -d jj-mock

test-jj-down:
	docker compose -f docker/docker-compose.test.yml down
```

**Acceptance Criteria:**
- [ ] Complex E2E scenarios tested с JJ Remote Mock
- [ ] Race conditions detected via `--order-random`
- [ ] JJ mock server в docker-compose для CI
- [ ] Request history проверяется для verification
- [ ] FIFO и priority ordering verified через JJ mock calls

---

### Phase 6: Database Layer (Tasks 46-50)

#### [DONE] Task 46: SQLite + SQLAlchemy Setup

**Файлы:** `backend/src/gitlab_queue/db/database.py`, `backend/pyproject.toml`

**Действия:**
- Добавить `aiosqlite`, `sqlalchemy[asyncio]` в зависимости
- Создать async engine с WAL mode
- Настроить Alembic для миграций
- Создать `db/database.py` с async session factory

**Acceptance Criteria:**
- [x] `aiosqlite` и `sqlalchemy` установлены
- [x] Async engine с WAL mode работает
- [x] Alembic настроен для миграций
- [x] Session factory создает async sessions

---

#### [DONE] Task 47: Database Models

**Файлы:** `backend/src/gitlab_queue/db/models.py`

**Действия:**
- SQLAlchemy модели для 4 таблиц:
  - `MergeRequest` — активная очередь
  - `MergeRequestHistory` — завершённые MR
  - `AnalyticsHourly` — почасовые снапшоты
  - `AnalyticsDaily` — дневная статистика
- Индексы для быстрого поиска
- Timestamps с timezone

**Acceptance Criteria:**
- [ ] ORM модели соответствуют схеме из ADR-004 (4 таблицы)
- [ ] Индексы созданы для всех таблиц
- [ ] Timestamps корректные

---

#### [DONE] Task 48: Repository Pattern

**Файлы:** `backend/src/gitlab_queue/db/repositories.py`

**Действия:**
- `MergeRequestRepository`:
  - CRUD для активной очереди (`merge_requests`)
  - `complete_mr(iid, status, failure_reason)` — перенос MR в history:
    ```python
    async def complete_mr(self, iid: int, status: str, failure_reason: str | None = None):
        """Move MR from active queue to history."""
        mr = await self.get_by_iid(iid)
        if not mr:
            return

        history_record = MergeRequestHistory(
            iid=mr.iid,
            title=mr.title,
            author_name=mr.author_name,
            # ... copy all fields
            status=status,
            finished_at=datetime.utcnow(),
            wait_time_seconds=(mr.started_at - mr.queued_at).total_seconds() if mr.started_at else None,
            processing_time_seconds=(datetime.utcnow() - mr.started_at).total_seconds() if mr.started_at else None,
            failure_reason=failure_reason,
        )
        self.session.add(history_record)
        await self.session.delete(mr)
    ```
  - Поиск по статусу
- `HistoryRepository`:
  - Поиск с пагинацией и фильтрацией
  - `get_history(page, per_page, status_filter, date_from, date_to)`
  - `get_stats_for_period(date_from, date_to)`
- `AnalyticsRepository`:
  - Hourly snapshots: `save_hourly_snapshot()`
  - Daily aggregation: `aggregate_daily(date)`
  - Метрики для дашборда: `get_metrics(period)`
- Unit of Work pattern для транзакций

**Acceptance Criteria:**
- [ ] CRUD операции работают для активной очереди
- [ ] `complete_mr()` корректно переносит MR в history
- [ ] История доступна с пагинацией и фильтрами
- [ ] Транзакции обеспечивают консистентность

---

#### [DONE] Task 49: Migrate Queue Logic to SQLite

**Файлы:** `backend/src/gitlab_queue/core/queue.py`

**Действия:**
- Заменить Redis операции на SQLite через repositories
- In-memory кэш текущей очереди
- Обновление кэша при каждом изменении

**Acceptance Criteria:**
- [ ] Queue operations работают через SQLite
- [ ] In-memory кэш синхронизирован
- [ ] Нет зависимостей от Redis

---

#### [DONE] Task 50: Data Retention & Analytics Jobs

**Файлы:** `backend/src/gitlab_queue/jobs/analytics.py`, `backend/src/gitlab_queue/jobs/cleanup.py`

**Действия:**

1. **Hourly Snapshot Job** (каждый час в :00):
   ```python
   async def save_hourly_snapshot():
       """Capture current queue state."""
       snapshot = AnalyticsHourly(
           timestamp=datetime.utcnow().replace(minute=0, second=0),
           queue_depth=await repo.count_active(),
           processed_count=await repo.count_processed_last_hour(),
           success_count=await repo.count_by_status('merged', last_hour=True),
           failed_count=await repo.count_by_status('failed', last_hour=True),
           avg_wait_time_seconds=await repo.avg_wait_time(last_hour=True),
       )
       session.add(snapshot)
   ```

2. **Daily Aggregation Job** (cron: 00:05):
   ```python
   async def aggregate_daily(date: date):
       """Aggregate yesterday's data into daily stats."""
       stats = await history_repo.get_stats_for_date(date)
       daily = AnalyticsDaily(
           date=date,
           total_processed=stats.total,
           success_count=stats.merged,
           failed_count=stats.failed,
           conflict_count=stats.conflicts,
           timeout_count=stats.timeouts,
           hotfix_count=stats.hotfixes,
           avg_wait_time_seconds=stats.avg_wait,
           avg_processing_time_seconds=stats.avg_processing,
           max_queue_depth=await analytics_repo.max_queue_depth(date),
       )
       session.add(daily)
   ```

3. **Cleanup Jobs**:
   - **Hourly cleanup** (30 дней retention):
     ```sql
     DELETE FROM analytics_hourly WHERE timestamp < date('now', '-30 days');
     ```
   - **History cleanup** (1 год retention):
     ```sql
     DELETE FROM merge_requests_history WHERE finished_at < date('now', '-1 year');
     ```
   - После cleanup: `VACUUM` для освобождения места

4. **Scheduler Setup** (APScheduler):
   ```python
   scheduler.add_job(save_hourly_snapshot, 'cron', minute=0)
   scheduler.add_job(aggregate_daily, 'cron', hour=0, minute=5, args=[date.today() - timedelta(days=1)])
   scheduler.add_job(cleanup_hourly, 'cron', hour=1, minute=0)
   scheduler.add_job(cleanup_history, 'cron', day=1, hour=2)  # Monthly
   ```

**Acceptance Criteria:**
- [ ] Hourly snapshots создаются в :00
- [ ] Daily aggregation работает корректно в 00:05
- [ ] Cleanup удаляет данные старше retention периода
- [ ] VACUUM освобождает место после cleanup
- [ ] Метрики доступны для дашборда

---

### Phase 7: GitLab OAuth (Tasks 51-53)

#### [DONE] Task 51: OAuth Configuration

**Файлы:** `backend/src/gitlab_queue/auth/oauth.py`, `README.md`

**Действия:**
- Добавить OAuth env variables (client_id, client_secret, redirect_uri)
- GitLab Application setup instructions в README
- Scopes: `read_user`, `read_api`

**Acceptance Criteria:**
- [ ] OAuth config загружается
- [ ] README содержит инструкции по настройке GitLab App
- [ ] Scopes документированы

---

#### [DONE] Task 52: Auth Endpoints

**Файлы:** `backend/src/gitlab_queue/auth/oauth.py`, `backend/src/gitlab_queue/api/routes.py`

**Действия:**
- `GET /auth/login` — redirect to GitLab
- `GET /auth/callback` — exchange code for token
- `GET /auth/me` — current user info
- `POST /auth/logout` — invalidate JWT

**API Endpoints:**
```
GET  /auth/login                   → Redirect to GitLab OAuth
GET  /auth/callback                → GitLab callback, returns JWT
GET  /auth/me                      → Current user info
POST /auth/logout                  → Invalidate session
```

**Acceptance Criteria:**
- [ ] OAuth flow работает end-to-end
- [ ] Callback обменивает code на token
- [ ] User info возвращается корректно

---

#### [DONE] Task 53: JWT & Middleware

**Файлы:** `backend/src/gitlab_queue/auth/jwt.py`, `backend/src/gitlab_queue/auth/middleware.py`

**Действия:**
- JWT generation с expiration
- Auth middleware для protected routes
- Project access validation (user has access to project_id)

**Acceptance Criteria:**
- [ ] JWT генерируется с expiration
- [ ] Middleware блокирует неавторизованные запросы
- [ ] Проверка доступа к проекту работает

---

### Phase 8: Dashboard API (Tasks 54-58)

#### [DONE] Task 54: REST API Routes

**Файлы:** `backend/src/gitlab_queue/api/routes.py`

**Действия:**
- `/api/queue` — текущая очередь из SQLite (status IN active states)
- `/api/history` — завершенные MR с пагинацией
- `/api/analytics/*` — метрики

**API Endpoints:**
```
# Queue (live)
GET  /api/queue                    → MergeRequest[]
GET  /api/queue/stats              → QueueStats

# History
GET  /api/history                  → MergeRequest[] (paginated)
GET  /api/history?search=...       → filtered by title/author/iid
GET  /api/history/{iid}            → MergeRequest

# Analytics
GET  /api/analytics/summary        → { totalProcessed, avgWaitTime, successRate, dailyThroughput }
GET  /api/analytics/hourly?hours=24 → HourlyDataPoint[]
GET  /api/analytics/outcomes       → { success, failed, conflict }[]
GET  /api/analytics/failure-reasons → { reason, count, percentage }[]
```

**Acceptance Criteria:**
- [ ] Queue endpoint возвращает active MRs
- [ ] History с пагинацией и поиском
- [ ] Analytics endpoints работают

---

#### [DONE] Task 55: WebSocket Manager

**Файлы:** `backend/src/gitlab_queue/api/websocket.py`

**Действия:**
- ConnectionManager для broadcast
- JWT validation для WS connections
- Интеграция с state machine → broadcast на каждый transition

**WebSocket Events:**
```
WS /ws/queue

# Server → Client events:
{
  "type": "queue:updated",
  "data": { "queue": MergeRequest[], "stats": QueueStats }
}

{
  "type": "mr:status_changed",
  "data": { "iid": 1042, "oldStatus": "rebasing", "newStatus": "testing" }
}

{
  "type": "mr:completed",
  "data": MergeRequest  // with finishedAt, failureReason
}
```

**Acceptance Criteria:**
- [ ] WebSocket connections работают
- [ ] JWT validation для WS
- [ ] Broadcast на каждый state change

---

#### [DONE] Task 56: API Schemas

**Файлы:** `backend/src/gitlab_queue/api/schemas.py`

**Действия:**
- Adaptix retorts для API responses
- Query parameter validation
- Pagination schema

**Acceptance Criteria:**
- [ ] Schemas для всех endpoints
- [ ] Validation работает
- [ ] Pagination consistent

---

#### [DONE] Task 57: CORS Configuration

**Файлы:** `backend/src/gitlab_queue/webhooks/router.py`

**Действия:**
- CORS для frontend origin
- Credentials support для cookies/JWT

**Acceptance Criteria:**
- [x] CORS позволяет frontend origin
- [x] Credentials передаются

---

#### [DONE] Task 58: API Testing

**Файлы:** `backend/scenarios/integration/api_*.py`

**Действия:**
- Vedro scenarios для всех endpoints
- WebSocket testing с JJ mock
- Auth flow testing

**Acceptance Criteria:**
- [ ] Все endpoints покрыты тестами
- [ ] WebSocket тесты работают
- [ ] Auth flow протестирован

---

### Phase 9: Frontend Integration (Tasks 59-70)

> **Обновлено:** 2025-12-07 — расширено с 6 до 12 задач для production-ready качества.
> **Решения:** snake_case напрямую (как в backend), Vitest + RTL (без E2E Playwright).

#### Выявленные несоответствия типов

| Frontend (types.ts) | Backend (schemas.py) | Действие |
|---------------------|---------------------|----------|
| `author.avatar` | `author.avatar_url` | Переименовать |
| `iid` | `mr_iid` | Переименовать |
| `targetBranch` | `target_branch` | Переименовать |
| `isHotfix` | `is_hotfix` | Переименовать |
| `queuedAt` | `queued_at` | Переименовать |
| `startedAt` | `started_at` | Переименовать |
| `finishedAt` | `finished_at` | Переименовать |
| `failureReason` | `failure_reason` | Переименовать |
| `pipeline.jobs_failed` | ❌ не существует | **УДАЛИТЬ** |
| `pipeline.duration_seconds` | ❌ не существует | **УДАЛИТЬ** |

---

#### [DONE] Task 59: Project Foundation & Cleanup

**Файлы:** `frontend/`

**Действия:**
1. Переместить `design/gitlab-queue-commander/` → `frontend/`
2. Удалить `mockData.ts` полностью
3. Удалить simulation logic из `App.tsx` (строки 27-96)
4. Удалить simulation buttons из `Dashboard.tsx`
5. Настроить strict TypeScript (`tsconfig.json`: strict, noImplicitAny, strictNullChecks)
6. Добавить ESLint + Prettier
7. Создать `.env.example` с `VITE_API_URL`, `VITE_WS_URL`, `VITE_GITLAB_URL`

**Acceptance Criteria:**
- [ ] Нет файлов с mock данными
- [ ] `npm run build` проходит без ошибок
- [ ] TypeScript strict mode включен
- [ ] ESLint проходит без warnings

---

#### [DONE] Task 60: Type Synchronization with Backend

**Файлы:** `frontend/src/types.ts`

**Решение:** Использовать snake_case напрямую во frontend (как в backend) — без трансформации.

**Действия:**
1. Переименовать все поля в snake_case (соответствие backend schemas.py)
2. Удалить несуществующие поля (`jobs_failed`, `duration_seconds`)
3. Добавить WebSocket event types с discriminated unions
4. Добавить nullable типы (`| null`) где backend возвращает null

**Новые типы:**
```typescript
export type MRStatus =
  | 'queued' | 'rebasing' | 'testing' | 'merging'
  | 'merged' | 'failed' | 'conflict' | 'timeout' | 'removed';

export interface Author {
  name: string;
  username: string;
  avatar_url: string | null;
}

export interface PipelineInfo {
  id: number;
  status: string | null;
}

export interface MergeRequest {
  mr_iid: number;
  title: string;
  author: Author;
  status: MRStatus;
  labels: string[];
  is_hotfix: boolean;
  queued_at: string;
  started_at: string | null;
  finished_at: string | null;
  target_branch: string;
  pipeline: PipelineInfo | null;
  failure_reason: string | null;
}

export type WSEvent =
  | { type: 'queue:updated'; data: { queue: MergeRequest[] } }
  | { type: 'mr:status_changed'; data: { iid: number; old_status: string; new_status: string } }
  | { type: 'mr:completed'; data: { iid: number; status: string; finished_at: string } };
```

**Acceptance Criteria:**
- [ ] Все поля переименованы в snake_case
- [ ] `jobs_failed` и `duration_seconds` удалены
- [ ] Nullable поля типизированы как `| null`
- [ ] WebSocket events имеют type guards
- [ ] `npm run build` проходит без type errors

---

#### [DONE] Task 61: Authentication Flow

**Файлы:** `frontend/src/auth/`, `frontend/src/pages/Login.tsx`, `frontend/src/pages/AuthCallback.tsx`

**Решение по Token Storage:** `localStorage` (backend возвращает token в response body)

**Действия:**
1. Создать `auth/storage.ts` — getToken, setToken, clearToken
2. Создать `auth/api.ts` — login redirect, callback handler, getCurrentUser, logout
3. Создать `pages/Login.tsx` — страница с кнопкой "Login with GitLab"
4. Создать `pages/AuthCallback.tsx` — обработка `/auth/callback`
5. Добавить auth check в `App.tsx` при mount
6. Обработать OAuth ошибки (user denied, invalid state, network error)

**Acceptance Criteria:**
- [ ] Login redirect работает
- [ ] Callback обрабатывает success и error cases
- [ ] Token сохраняется в localStorage
- [ ] `/auth/me` вызывается при mount для валидации
- [ ] Expired token → redirect to login
- [ ] Loading state во время auth check

---

#### [DONE] Task 62: API Client Layer

**Файлы:** `frontend/src/api/`

**Действия:**
1. Создать `api/client.ts` — базовый fetch wrapper с JWT header
2. Создать `api/history.ts` — getHistory, getHistoryItem
3. Создать `api/analytics.ts` — getSummary, getHourly, getOutcomes, getFailureReasons
4. Создать `api/queue.ts` — getQueue, getQueueStats
5. Добавить 401 interceptor → logout + redirect
6. Добавить request cancellation через AbortController

**Acceptance Criteria:**
- [ ] Все API endpoints типизированы
- [ ] 401 → automatic logout и redirect
- [ ] Errors трансформируются в типизированные ApiError
- [ ] Request cancellation работает

---

#### [DONE] Task 63: WebSocket Integration

**Файлы:** `frontend/src/api/websocket.ts`, `frontend/src/hooks/useWebSocket.ts`

**Действия:**
1. Создать WebSocket manager class с state machine
2. Реализовать exponential backoff reconnect (1s, 2s, 4s, 8s, max 30s)
3. Типизировать все events через discriminated unions
4. Добавить connection state: connecting | connected | disconnected | error
5. Создать React hook `useWebSocket()`

**Acceptance Criteria:**
- [ ] Reconnect с exponential backoff
- [ ] Auth errors (code 1008) не reconnect
- [ ] Connection state доступен в UI
- [ ] Type guards для всех event types
- [ ] Disconnect при logout

---

#### [DONE] Task 64: Dashboard Page Integration

**Файлы:** `frontend/src/pages/Dashboard.tsx`

**Действия:**
1. Удалить simulation props и buttons
2. Подключить WebSocket для real-time updates
3. Заменить hardcoded URL на configurable `${VITE_GITLAB_URL}/project/-/merge_requests/${iid}`
4. Вычислять duration из `started_at` timestamp
5. Добавить loading skeleton при initial load
6. Добавить connection status indicator

**Acceptance Criteria:**
- [ ] Нет simulation buttons
- [ ] WebSocket updates отображаются в реальном времени
- [ ] Duration обновляется каждую секунду
- [ ] GitLab URL configurable через env
- [ ] Loading skeleton при первой загрузке

---

#### [DONE] Task 65: History Page Integration

**Файлы:** `frontend/src/pages/History.tsx`

**Действия:**
1. Удалить client-side filtering
2. Добавить server-side pagination через `?page=&per_page=`
3. Добавить server-side search через `?search=`
4. Добавить status filter через `?status=`
5. Debounce search input (300ms)
6. Sync filters с URL query params

**Acceptance Criteria:**
- [ ] Нет client-side filtering
- [ ] Pagination работает (next/prev pages)
- [ ] Search debounced и cancellable
- [ ] Filters сохраняются в URL

---

#### [DONE] Task 66: Analytics Page Integration

**Файлы:** `frontend/src/pages/Analytics.tsx`

**Действия:**
1. Удалить `generateAnalyticsData()` и hardcoded pieData
2. Удалить hardcoded failure reasons array
3. Fetch данные параллельно: summary, hourly, outcomes, failure-reasons
4. Transform data для Recharts format
5. Конвертировать `avg_wait_time_seconds` → minutes для display
6. Добавить time range selector (7d, 30d, 90d)
7. Loading skeleton для каждого chart отдельно

**Acceptance Criteria:**
- [ ] Все данные из реальных API endpoints
- [ ] Parallel fetching для performance
- [ ] Time range selector работает
- [ ] Partial failure handling
- [ ] Правильная конвертация units (seconds → minutes)

---

#### [DONE] Task 67: Error Handling & Loading States

**Файлы:** `frontend/src/components/`

**Действия:**
1. Создать `ErrorBoundary.tsx` — global error boundary
2. Создать `ErrorDisplay.tsx` — компонент отображения ошибок
3. Создать `LoadingSkeleton.tsx` — скелетоны для queue, history, charts
4. Создать `ConnectionIndicator.tsx` — WebSocket status badge
5. Добавить toast notifications для transient errors
6. Добавить retry button для failed requests

**Acceptance Criteria:**
- [ ] Unhandled errors не crash'ат приложение
- [ ] User видит понятное сообщение об ошибке
- [ ] Retry button позволяет повторить
- [ ] Loading skeletons для всех async data
- [ ] Connection status виден пользователю

---

#### [DONE] Task 68: Layout & Configuration

**Файлы:** `frontend/src/components/Layout.tsx`, `frontend/src/config.ts`

**Действия:**
1. Создать `config.ts` — centralized configuration
2. Удалить hardcoded "MergeBot", version, status из Layout
3. Добавить user info в header (из `/auth/me`)
4. Добавить logout button
5. Health status — fetch из `/health` или `/ready`

**Acceptance Criteria:**
- [ ] Нет hardcoded strings в Layout
- [ ] User info отображается в header
- [ ] Logout button работает
- [ ] Config values из environment variables

---

#### [DONE] Task 69: Accessibility & Dark Mode

**Файлы:** All components

**Действия:**
1. Добавить ARIA labels ко всем interactive elements
2. Добавить keyboard navigation (Tab, Enter, Escape)
3. Добавить focus indicators
4. Fix dark mode — detect system preference
5. Persist dark mode preference в localStorage
6. Добавить `prefers-reduced-motion` support для Framer Motion

**Acceptance Criteria:**
- [ ] Keyboard navigation работает везде
- [ ] Screen reader читает контент корректно
- [ ] Dark mode respects system preference
- [ ] Dark mode preference persisted
- [ ] Animations отключаются при `prefers-reduced-motion`

---

#### [DONE] Task 70: Testing Setup

**Файлы:** `frontend/src/__tests__/`, `frontend/vitest.config.ts`

**Действия:**
1. Настроить Vitest + React Testing Library
2. Написать тесты для auth flow
3. Написать тесты для API client (с mock fetch)
4. Написать тесты для WebSocket reconnect logic
5. Написать тесты для data transformers
6. Настроить coverage reports (target: 80% на business logic)

**Acceptance Criteria:**
- [ ] Vitest настроен и работает
- [ ] Auth flow покрыт тестами
- [ ] WebSocket logic покрыта тестами
- [ ] Coverage ≥80% на utils и business logic

---

#### Структура файлов Phase 9

```
frontend/
├── src/
│   ├── api/
│   │   ├── client.ts          # Base fetch wrapper с JWT
│   │   ├── history.ts         # History API calls
│   │   ├── analytics.ts       # Analytics API calls
│   │   ├── queue.ts           # Queue API calls
│   │   └── websocket.ts       # WebSocket manager
│   ├── auth/
│   │   ├── storage.ts         # Token storage (localStorage)
│   │   └── api.ts             # Auth API calls
│   ├── utils/
│   │   ├── duration.ts        # Duration formatting
│   │   └── date.ts            # Date formatting
│   ├── hooks/
│   │   ├── useWebSocket.ts    # WebSocket React hook
│   │   ├── useDarkMode.ts     # Dark mode hook
│   │   └── useAuth.ts         # Auth state hook
│   ├── components/
│   │   ├── Layout.tsx
│   │   ├── StatusBadge.tsx
│   │   ├── ErrorBoundary.tsx
│   │   ├── ErrorDisplay.tsx
│   │   ├── LoadingSkeleton.tsx
│   │   └── ConnectionIndicator.tsx
│   ├── pages/
│   │   ├── Login.tsx
│   │   ├── AuthCallback.tsx
│   │   ├── Dashboard.tsx
│   │   ├── History.tsx
│   │   └── Analytics.tsx
│   ├── types.ts               # Все типы (snake_case как в backend)
│   ├── config.ts
│   ├── App.tsx
│   └── main.tsx
├── __tests__/
│   ├── auth.test.ts
│   ├── api-client.test.ts
│   └── websocket.test.ts
├── .env.example
├── tsconfig.json              # Strict mode
├── eslint.config.js
├── vitest.config.ts
└── package.json
```

---

### Phase 10: Docker & Deployment (Tasks 71-73)

#### [DONE] Task 71: Multi-stage Frontend Build

**Файлы:** `docker/Dockerfile.frontend`, `docker/nginx.conf`

**Действия:**
- Dockerfile.frontend (build + nginx)
- nginx.conf для SPA routing + API proxy

**Acceptance Criteria:**
- [ ] Frontend builds в Docker
- [ ] nginx SPA routing работает
- [ ] API proxy настроен

---

#### [DONE] Task 72: Updated Docker Compose

**Файлы:** `docker/docker-compose.yml`

**Действия:**
- Backend service (Python + SQLite volume)
- Frontend service (nginx)
- Caddy для HTTPS + routing
- Удален Redis service

**Acceptance Criteria:**
- [ ] docker compose up запускает всё
- [ ] SQLite volume persisted
- [ ] HTTPS через Caddy

---

#### [DONE] Task 73: Development Environment

**Файлы:** `docker/docker-compose.dev.yml`

**Действия:**
- docker-compose.dev.yml
- Vite dev server с proxy
- Hot reload для backend

**Acceptance Criteria:**
- [ ] Dev environment работает
- [ ] Hot reload для frontend и backend
- [ ] Proxy настроен

---

## Mermaid Diagrams

### System Architecture

```mermaid
graph TB
    subgraph GitLab
        GL[GitLab API]
        WH[Webhooks]
    end

    subgraph Backend
        WS[Webhook Server<br/>FastAPI]
        API[Dashboard API<br/>REST + WebSocket]
        PROC[Processor Loop]
        Q[Queue Manager]
        SM[State Machine]
        GLC[GitLab Client]
        AUTH[OAuth + JWT]
    end

    subgraph Frontend
        DASH[React Dashboard]
    end

    subgraph Storage
        SQLITE[(SQLite)]
    end

    WH -->|Events| WS
    WS -->|Update Queue| Q
    PROC -->|Get Next MR| Q
    PROC -->|Transitions| SM
    SM -->|Persist State| Q
    Q -->|Read/Write| SQLITE
    PROC -->|API Calls| GLC
    GLC -->|HTTP| GL
    GLC -->|Comments| GL
    DASH -->|REST/WS| API
    API -->|Query| SQLITE
    API -->|Auth| AUTH
    AUTH -->|OAuth| GL
```

### Processing Flow

```mermaid
sequenceDiagram
    participant Dev as Developer
    participant GL as GitLab
    participant Bot as Merge Queue Bot
    participant SQLite
    participant Dashboard

    Dev->>GL: Add label "merge_queue"
    GL->>Bot: Webhook: labeled
    Bot->>SQLite: Add to queue
    Bot->>GL: Comment: "Added to queue, position 1"
    Bot-->>Dashboard: WebSocket: queue:updated

    loop Every tick
        Bot->>SQLite: Get next MR
        Bot->>GL: Rebase MR
        GL-->>Bot: Rebase success
        Bot->>SQLite: State: testing
        Bot-->>Dashboard: WebSocket: mr:status_changed

        loop Wait for pipeline
            Bot->>GL: Get pipeline status
            GL-->>Bot: running/success/failed
        end

        alt Pipeline Success
            Bot->>GL: Merge MR
            GL-->>Bot: Merged
            Bot->>GL: Comment: "Successfully merged!"
            Bot->>SQLite: State: merged
            Bot-->>Dashboard: WebSocket: mr:completed
        else Pipeline Failed
            Bot->>GL: Comment: "Pipeline failed, removing from queue"
            Bot->>SQLite: State: failed
            Bot-->>Dashboard: WebSocket: mr:completed
        end
    end
```

### State Machine

```mermaid
stateDiagram-v2
    [*] --> queued: label added
    queued --> rebasing: position 1
    rebasing --> testing: rebase success
    rebasing --> failed: conflicts
    testing --> merging: pipeline success
    testing --> testing: retry (once)
    testing --> failed: pipeline failed x2
    merging --> merged: merge success
    merging --> failed: merge error

    queued --> removed: label removed
    rebasing --> removed: label removed
    testing --> removed: label removed / timeout

    merged --> [*]
    failed --> [*]
    removed --> [*]
```

---

## Risk Analysis

### High Risk

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| Race condition при concurrent updates | Medium | High | SQLite transactions, optimistic locking |
| GitLab API rate limiting | Medium | High | Adaptive throttling, webhook-first |
| Bot crash during merge | Low | Critical | State recovery, idempotent operations |
| Token expiration | Low | High | Health check, alerts |

### Medium Risk

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| Flaky tests блокируют очередь | High | Medium | Smart retry, per-job retry |
| SQLite file locked | Low | High | WAL mode, retry logic |
| Webhook delivery failure | Medium | Medium | Polling fallback |
| Manual merge bypass | Medium | Medium | Branch protection validation |

### Low Risk

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| GitLab API changes | Low | Medium | Version pinning, integration tests |
| Resource exhaustion | Low | Medium | Queue limits, monitoring |
| Configuration errors | Medium | Low | Validation on startup |

---

## Success Metrics

### Functional Metrics

- **Merge success rate:** >99% автоматических merge без ручного вмешательства
- **False positives:** <1% MR удаленных из очереди без причины
- **Queue throughput:** Обработка минимум 20 MR/час (зависит от pipeline duration)

### Operational Metrics

- **Uptime:** 99.9% availability
- **Recovery time:** <5 минут после restart
- **API error rate:** <0.1% (исключая rate limits)

### Developer Experience

- **Time to merge:** Среднее время от добавления label до merge
- **Queue position accuracy:** 100% точность отображения позиции
- **Comment clarity:** <5% вопросов "почему MR не мержится"

---

## Dependencies & Prerequisites

### GitLab Requirements

- GitLab Free (CE) или выше
- Maintainer role для bot user
- Protected branch settings настроены
- Webhook endpoint доступен (для webhook mode)

### Infrastructure Requirements

- Docker + Docker Compose
- SQLite 3.35+ (bundled with Python)
- Network access к GitLab API
- (Optional) Public endpoint для webhooks

### Development Requirements

- Python 3.12+
- UV
- Docker для local testing
- Vedro для тестирования (`pip install vedro`)
- Adaptix для сериализации (`pip install adaptix`)
- environ-config для конфигурации (`pip install environ-config`)

---

## References

### Official Documentation

- [GitLab Merge Requests API](https://docs.gitlab.com/api/merge_requests/)
- [GitLab Merge Trains](https://docs.gitlab.com/ci/pipelines/merge_trains/)
- [GitLab Webhooks](https://docs.gitlab.com/user/project/integrations/webhook_events/)
- [GitLab Rate Limits](https://docs.gitlab.com/security/rate_limits/)

### Open Source References

- [marge-bot](https://gitlab.com/marge-org/marge-bot) — mature GitLab merge bot
- [python-gitlab](https://python-gitlab.readthedocs.io/) — Python GitLab API client
- [httpx](https://www.python-httpx.org/) — async HTTP client
- [aiosqlite](https://aiosqlite.omnilib.dev/) — async SQLite Python client
- [SQLAlchemy](https://docs.sqlalchemy.org/) — Python ORM with async support
- [Adaptix](https://adaptix.readthedocs.io/) — dataclass serialization, separation of concerns, fast
- [environ-config](https://github.com/hynek/environ-config) — declarative env config, attrs-based
- [Vedro](https://vedro.io/docs/quick-start) — BDD-style тестовый фреймворк с async support
- [JJ Remote Mock](https://jj-mock.io/) — Remote HTTP mock server, async support, client-server architecture

### Best Practices

- [Asyncio Patterns for Services](https://www.elastic.co/blog/async-patterns-building-python-service)
- [Graceful Shutdowns with asyncio](https://roguelynn.com/words/asyncio-graceful-shutdowns/)
- [Merge Queues Best Practices](https://earthly.dev/blog/merge-queues/)

---

## Timeline Estimate

**Total estimated tasks:** 67 tasks

**Recommended implementation order:**
1. Phase 1 (Foundation): Tasks 1-15
2. Phase 2 (Webhooks): Tasks 16-22
3. Phase 3 (Error Handling): Tasks 23-30
4. Phase 4 (Operations): Tasks 31-38
5. Phase 5 (Testing): Tasks 39-45
6. Phase 6 (Database Layer): Tasks 46-50
7. Phase 7 (GitLab OAuth): Tasks 51-53
8. Phase 8 (Dashboard API): Tasks 54-58
9. Phase 9 (Frontend Integration): Tasks 59-64
10. Phase 10 (Docker & Deployment): Tasks 65-67

**MVP (Minimum Viable Product):** Tasks 1-15, 23-28, 36-37, 39-43, 46-50
- Core functionality without webhooks
- Polling-only mode
- Basic error handling
- SQLite storage
- Docker deployment
- Essential tests

**Full Dashboard:** Tasks 51-67 (after MVP)
- GitLab OAuth authentication
- REST + WebSocket API
- React frontend
- Real-time updates
- Analytics

---

## Change Log

| Date | Version | Changes |
|------|---------|---------|
| 2025-12-01 | 1.0.0 | Initial plan created |
| 2025-12-01 | 1.1.0 | Replaced pytest with Vedro testing framework |
| 2025-12-02 | 1.2.0 | Added JJ Remote Mock for HTTP mocking (Tasks 39-45 updated) |
| 2025-12-02 | 1.3.0 | Replaced Pydantic with Adaptix + environ-config (Tasks 2, 9, 17 updated) |
| 2025-12-02 | 1.3.1 | Switched to UV only (removed Poetry) |
| 2025-12-02 | 1.4.0 | Added ADR-006: Mandatory MR Feedback, MRNotifier, 14 comment templates |
| 2025-12-02 | 2.0.0 | **Web Dashboard**: Replaced Redis with SQLite (ADR-004), added frontend stack (TypeScript/Vite/React), new ADRs 007-010 (WebSocket, OAuth, Read-only, Monorepo), 22 new tasks (46-67), 5 new phases (6-10), monorepo structure |
| 2025-12-07 | 2.1.0 | **Phase 9 expanded**: 6 tasks → 12 tasks (59-70). Added: type sync with backend, OAuth callback handling, WebSocket reconnect logic, accessibility, Vitest testing. Removed: Vite proxy, auth context abstraction. Using snake_case directly in frontend. Phase 10 renumbered (71-73). |
