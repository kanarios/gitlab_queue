# План миграции на d42 для генерации тестовых данных

> Этот документ описывает пошаговый план перехода от хардкодных тестовых данных к генерации через d42 схемы.

## Прогресс выполнения

| Задача | Статус | Дата |
|--------|--------|------|
| 1. Установить vedro-d42-validator | :white_check_mark: Выполнено | 2026-01-16 |
| 2. Настроить плагин в vedro.cfg.py | :white_check_mark: Выполнено | 2026-01-16 |
| 3. Создать _helpers.py | :white_check_mark: Выполнено | 2026-01-16 |
| 4. Создать secret.py | :white_check_mark: Выполнено | 2026-01-16 |
| 5. Создать author.py | :white_check_mark: Выполнено | 2026-01-16 |
| 6. Создать merge_request.py | :white_check_mark: Выполнено | 2026-01-16 |
| 7. Создать queue_item.py | :white_check_mark: Выполнено | 2026-01-16 |
| 8. Создать events/mr_event.py | :white_check_mark: Выполнено | 2026-01-16 |
| 9. Создать events/pipeline_event.py | :white_check_mark: Выполнено | 2026-01-16 |
| 10. Создать events/note_event.py | :white_check_mark: Выполнено | 2026-01-16 |
| 11. Создать events/__init__.py | :white_check_mark: Выполнено | 2026-01-16 |
| 12. Обновить schemas/__init__.py | :white_check_mark: Выполнено | 2026-01-16 |
| 13. Мигрировать тесты config/secret/ | :white_check_mark: Выполнено | 2026-01-16 |
| 14. Мигрировать webhooks/_helpers.py | :white_check_mark: Выполнено | 2026-01-16 |
| 15. Мигрировать api_helpers.py | :white_check_mark: Выполнено | 2026-01-16 |

### Замечания по реализации

**Отклонения от плана:**
- Создан дополнительный файл `constants.py` для `DATETIME_PATTERN`, `MAX_LABELS`, `SHA_LENGTH` — решает проблему циклических зависимостей между модулями
- Использован `schema.str.regex()` вместо `.len().regex()` — d42 не поддерживает цепочку `.len().regex()`, длина задаётся внутри regex паттерна (например `r"^[a-f0-9]{40}$"`)
- `GitLabTokenSchema` использует regex `r"^glpat-[a-zA-Z0-9_-]{20,44}$"` вместо `.len(26, 50).regex()`

---

## Содержание

1. [Цели и принципы](#1-цели-и-принципы)
2. [Текущее состояние](#2-текущее-состояние)
3. [Архитектура схем](#3-архитектура-схем)
4. [Правила использования d42](#4-правила-использования-d42)
5. [Задачи миграции](#5-задачи-миграции)
6. [Примеры реализации](#6-примеры-реализации)
7. [Чек-лист для ревью](#7-чек-лист-для-ревью)

---

## 1. Цели и принципы

### 1.1 Цели

- Заменить хардкодные тестовые данные (`"my-api-key-12345"`) на генерацию через `fake(Schema)`
- Обеспечить соответствие тестовых данных реальным ограничениям (длина, формат, диапазоны)
- Использовать d42 схемы для валидации ответов в ассертах
- Повысить читаемость и поддерживаемость тестов

### 1.2 Принципы (из CommonCodeStyles.md)

1. **Данные генерируются через `fake(Schema)`** — никакого хардкода
2. **Переопределение полей через `%`** — `fake(Schema % {"field": "value"})`
3. **Границы для схем обязательны** — `.len(min, max)`, `.min()`, `.max()`
4. **Опциональные поля явные** — через `optional()` из d42
5. **Форсирование опциональных полей** — через `make_required(schema, {"field"})`
6. **Невалидные данные после генерации** — `result = fake(Schema); result["field"] = invalid`
7. **Верхний лимит для списков** — избегать `.len(1, ...)`, использовать `.len(1, MAX_LIMIT)`

---

## 2. Текущее состояние

### 2.1 Установленные пакеты

```toml
# pyproject.toml
[dependency-groups]
dev = [
    "d42>=2.2.0",  # уже установлен
]
```

### 2.2 Существующие схемы

```
backend/scenarios/schemas/
├── __init__.py       # экспорт status_code схем
└── status_code.py    # OkStatusSchema, NotFoundStatusSchema и т.д.
```

### 2.3 Существующие enum'ы (использовать в схемах)

```python
# scenarios/library/
from scenarios.library import MRState, QueueState, Labels

class MRState(StrEnum):
    OPENED = "opened"
    CLOSED = "closed"
    MERGED = "merged"

class QueueState(StrEnum):
    QUEUED = "queued"
    REBASING = "rebasing"
    TESTING = "testing"
    MERGING = "merging"
    MERGED = "merged"
    FAILED = "failed"
    CONFLICT = "conflict"
    REMOVED = "removed"

class Labels(StrEnum):
    MERGE_QUEUE = "merge_queue"
    HOTFIX = "hotfix"
    FEATURE = "feature"
    BUG = "bug"
    URGENT = "urgent"
```

### 2.4 Существующие dataclass'ы (основа для схем)

| Dataclass | Файл |
|-----------|------|
| `Author` | `src/gitlab_queue/models/mr.py` |
| `MergeRequest` | `src/gitlab_queue/models/mr.py` |
| `Note` | `src/gitlab_queue/models/mr.py` |
| `QueueItem` | `src/gitlab_queue/models/queue_item.py` |
| `DashboardStats` | `src/gitlab_queue/models/queue_item.py` |
| `MergeRequestAttributes` | `src/gitlab_queue/models/events.py` |
| `MergeRequestEvent` | `src/gitlab_queue/models/events.py` |
| `PipelineAttributes` | `src/gitlab_queue/models/events.py` |
| `PipelineEvent` | `src/gitlab_queue/models/events.py` |
| `LabelChanges` | `src/gitlab_queue/models/events.py` |
| `NoteEvent` | `src/gitlab_queue/models/events.py` |

### 2.5 Установлено в рамках миграции

- `vedro-d42-validator>=0.1.0` — плагин для валидации в ассертах (добавлен в pyproject.toml)

---

## 3. Архитектура схем

### 3.1 Структура директорий

```
backend/scenarios/schemas/
├── __init__.py                 # экспорт всех схем ✅
├── _helpers.py                 # утилиты: enum_schema() ✅
├── constants.py                # DATETIME_PATTERN, MAX_LABELS, SHA_LENGTH ✅ (добавлено)
├── status_code.py              # уже было
│
├── # Базовые типы
├── secret.py                   # SecretValueSchema, GitLabTokenSchema, JWTSecretSchema ✅
├── author.py                   # AuthorSchema ✅
│
├── # Доменные модели
├── merge_request.py            # MergeRequestSchema, MRStateSchema, NoteSchema ✅
├── queue_item.py               # QueueItemSchema, QueueStateSchema, DashboardStatsSchema ✅
│
└── # Webhook события
    events/
    ├── __init__.py             # ✅
    ├── mr_event.py             # MergeRequestEventSchema, MRAttributesSchema, LabelChangesSchema ✅
    ├── pipeline_event.py       # PipelineEventSchema, PipelineAttributesSchema ✅
    └── note_event.py           # NoteEventSchema ✅
```

### 3.2 Соответствие dataclass → d42 schema

| Dataclass | d42 Schema | Файл схемы |
|-----------|------------|------------|
| `Author` | `AuthorSchema` | `author.py` |
| `MergeRequest` | `MergeRequestSchema` | `merge_request.py` |
| `Note` | `NoteSchema` | `merge_request.py` |
| `QueueItem` | `QueueItemSchema` | `queue_item.py` |
| `DashboardStats` | `DashboardStatsSchema` | `queue_item.py` |
| `MergeRequestAttributes` | `MRAttributesSchema` | `events/mr_event.py` |
| `MergeRequestEvent` | `MergeRequestEventSchema` | `events/mr_event.py` |
| `PipelineAttributes` | `PipelineAttributesSchema` | `events/pipeline_event.py` |
| `PipelineEvent` | `PipelineEventSchema` | `events/pipeline_event.py` |
| `LabelChanges` | `LabelChangesSchema` | `events/mr_event.py` |
| `NoteEvent` | `NoteEventSchema` | `events/note_event.py` |

---

## 4. Правила использования d42

### 4.1 Импорты

```python
from d42 import schema, fake, optional
from d42.utils import make_required
```

### 4.2 Генерация данных

```python
# Базовая генерация
self.secret_value = fake(SecretValueSchema)

# С переопределением поля
self.mr = fake(MergeRequestSchema % {"state": MRState.OPENED})

# С несколькими переопределениями
self.mr = fake(MergeRequestSchema % {
    "state": MRState.OPENED,
    "title": "Test MR for feature X",
})
```

### 4.3 Опциональные поля

```python
# Схема с опциональным полем
MergeRequestSchema = schema.dict({
    "iid": schema.int.min(1),
    "title": schema.str.len(1, 255),
    optional("web_url"): schema.str.len(1, 2048),  # может отсутствовать
})

# Генерация БЕЗ опционального поля (по умолчанию)
mr = fake(MergeRequestSchema)
# {'iid': 42, 'title': 'abc'}

# Генерация С опциональным полем
mr = fake(make_required(MergeRequestSchema, {"web_url"}))
# {'iid': 42, 'title': 'abc', 'web_url': 'https://...'}
```

### 4.4 Невалидные данные

```python
# Сначала генерируем валидные данные
result = fake(MergeRequestSchema)

# Затем делаем невалидными для негативного теста
result["iid"] = -1  # невалидный iid
```

### 4.5 Границы для схем

```python
# Правильно — явные границы
schema.str.len(1, 255)           # строка от 1 до 255 символов
schema.int.min(1).max(2**31-1)   # int32
schema.list(ItemSchema).len(0, 50)  # список от 0 до 50 элементов

# Неправильно — бесконечная генерация
schema.str.len(1, ...)           # может генерировать очень длинные строки
schema.list(ItemSchema).len(1, ...)  # может генерировать огромные списки
```

### 4.6 Enum в схемах

```python
from scenarios.schemas._helpers import enum_schema
from scenarios.library import MRState

# Создание схемы из enum
MRStateSchema = enum_schema(MRState)
# Эквивалентно: schema.any(schema.str("opened"), schema.str("closed"), schema.str("merged"))

# Использование в схеме
MergeRequestSchema = schema.dict({
    "state": MRStateSchema,
    # ...
})
```

### 4.7 Валидация в ассертах (после установки vedro-d42-validator)

```python
def then_response_should_match_schema(self):
    # Проверка по схеме
    assert self.response.body == MergeRequestSchema

def then_status_should_be_ok(self):
    # Проверка по схеме статус-кода
    assert self.response.status_code == OkStatusSchema
```

---

## 5. Задачи миграции

### Задача 1: Установить vedro-d42-validator

**Файл:** `backend/pyproject.toml`

**Изменения:**
```toml
[project.optional-dependencies]
dev = [
    # ... existing deps
    "vedro-d42-validator>=0.1.0",
]
```

---

### Задача 2: Настроить плагин в vedro.cfg.py

**Файл:** `backend/vedro.cfg.py`

**Изменения:**
```python
"""Vedro configuration for GitLab Queue Bot tests."""

import vedro
import vedro.plugins.director.rich as rich_reporter
import vedro_d42_validator


class Config(vedro.Config):
    """Vedro test framework configuration."""

    class Registry(vedro.Config.Registry):
        pass

    class Plugins(vedro.Config.Plugins):
        class RichReporter(rich_reporter.RichReporter):
            enabled = True
            show_scenario_spinner = True

        class D42Validator(vedro_d42_validator.D42Validator):
            enabled = True
```

---

### Задача 3: Создать _helpers.py

**Файл:** `backend/scenarios/schemas/_helpers.py`

**Содержимое:**
```python
"""Утилиты для создания d42 схем."""

from enum import StrEnum
from typing import Type

from d42 import schema


def enum_schema(enum_class: Type[StrEnum]):
    """Создать d42 схему из StrEnum.

    Генерирует схему, которая принимает любое значение из enum.

    Args:
        enum_class: Класс StrEnum для создания схемы.

    Returns:
        d42 schema, валидирующая значения enum.

    Example:
        >>> from scenarios.library import MRState
        >>> MRStateSchema = enum_schema(MRState)
        >>> fake(MRStateSchema)  # -> "opened" или "closed" или "merged"
    """
    return schema.any(*[schema.str(value) for value in enum_class])


__all__ = ["enum_schema"]
```

---

### Задача 4: Создать secret.py

**Файл:** `backend/scenarios/schemas/secret.py`

**Содержимое:**
```python
"""Схемы для секретных значений."""

from d42 import schema

# Общая схема для секретных строк
# Ограничения: минимум 8 символов (безопасность), максимум 256 (разумный лимит)
SecretValueSchema = schema.str.len(8, 256)

# GitLab Personal Access Token
# Формат: glpat-XXXXXXXXXXXXXXXXXXXX (26+ символов)
GitLabTokenSchema = schema.str.len(26, 50).regex(r"^glpat-[a-zA-Z0-9_-]+$")

# Webhook Secret
# Минимум 16 символов для безопасности
WebhookSecretSchema = schema.str.len(16, 128)

# JWT Secret
# Минимум 64 символа согласно валидации в Settings
JWTSecretSchema = schema.str.len(64, 256)

__all__ = [
    "GitLabTokenSchema",
    "JWTSecretSchema",
    "SecretValueSchema",
    "WebhookSecretSchema",
]
```

---

### Задача 5: Создать author.py

**Файл:** `backend/scenarios/schemas/author.py`

**Содержимое:**
```python
"""Схема для Author из src/gitlab_queue/models/mr.py."""

from d42 import optional, schema

# Соответствует dataclass Author:
# - id: int
# - name: str
# - username: str
# - avatar_url: str | None = None
AuthorSchema = schema.dict({
    "id": schema.int.min(1).max(2_147_483_647),  # int32 positive
    "name": schema.str.len(1, 255),
    "username": schema.str.len(1, 255).regex(r"^[a-zA-Z0-9_.-]+$"),
    optional("avatar_url"): schema.str.len(1, 2048),
})

__all__ = ["AuthorSchema"]
```

---

### Задача 6: Создать merge_request.py

**Файл:** `backend/scenarios/schemas/merge_request.py`

**Содержимое:**
```python
"""Схемы для MergeRequest и Note из src/gitlab_queue/models/mr.py."""

from d42 import optional, schema

from scenarios.library import MRState
from scenarios.schemas._helpers import enum_schema
from scenarios.schemas.author import AuthorSchema

# Лимиты
MAX_LABELS = 50  # GitLab limit
SHA_LENGTH = 40  # Git SHA-1 hex length

# Схема для MR state enum
MRStateSchema = enum_schema(MRState)

# Соответствует dataclass MergeRequest
MergeRequestSchema = schema.dict({
    "iid": schema.int.min(1).max(2_147_483_647),
    "title": schema.str.len(1, 255),
    "state": MRStateSchema,
    "labels": schema.list(schema.str.len(1, 255)).len(0, MAX_LABELS),
    "sha": schema.str.len(SHA_LENGTH, SHA_LENGTH).regex(r"^[a-f0-9]+$"),
    "source_branch": schema.str.len(1, 255),
    "target_branch": schema.str.len(1, 255),
    "merge_status": schema.str.len(1, 50),
    "author": AuthorSchema,
    optional("has_conflicts"): schema.bool,
    optional("rebase_in_progress"): schema.bool,
    optional("web_url"): schema.str.len(1, 2048),
})

# Соответствует dataclass Note
NoteSchema = schema.dict({
    "id": schema.int.min(1).max(2_147_483_647),
    "body": schema.str.len(1, 10_000),  # Markdown content
    "author": AuthorSchema,
    optional("system"): schema.bool,
})

__all__ = [
    "MAX_LABELS",
    "MRStateSchema",
    "MergeRequestSchema",
    "NoteSchema",
    "SHA_LENGTH",
]
```

---

### Задача 7: Создать queue_item.py

**Файл:** `backend/scenarios/schemas/queue_item.py`

**Содержимое:**
```python
"""Схемы для QueueItem и DashboardStats из src/gitlab_queue/models/queue_item.py."""

from d42 import optional, schema

from scenarios.library import QueueState
from scenarios.schemas._helpers import enum_schema
from scenarios.schemas.merge_request import MAX_LABELS

# Схема для queue state enum
QueueStateSchema = enum_schema(QueueState)

# ISO 8601 datetime string pattern
DATETIME_PATTERN = r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}"

# Соответствует dataclass QueueItem
QueueItemSchema = schema.dict({
    "mr_iid": schema.int.min(1).max(2_147_483_647),
    "title": schema.str.len(1, 255),
    "author_name": schema.str.len(1, 255),
    "author_username": schema.str.len(1, 255),
    "target_branch": schema.str.len(1, 255),
    "state": QueueStateSchema,
    "queued_at": schema.str.regex(DATETIME_PATTERN),  # ISO datetime
    optional("is_hotfix"): schema.bool,
    optional("author_avatar"): schema.str.len(1, 2048),
    optional("labels"): schema.list(schema.str.len(1, 255)).len(0, MAX_LABELS),
    optional("started_at"): schema.str.regex(DATETIME_PATTERN),
    optional("finished_at"): schema.str.regex(DATETIME_PATTERN),
    optional("pipeline_id"): schema.int.min(1).max(2_147_483_647),
    optional("pipeline_status"): schema.str.len(1, 50),
    optional("retry_count"): schema.int.min(0).max(100),
    optional("last_error"): schema.str.len(1, 10_000),
    optional("stale_warning_sent"): schema.bool,
})

# Соответствует dataclass DashboardStats
DashboardStatsSchema = schema.dict({
    "total_in_queue": schema.int.min(0),
    "merged_count": schema.int.min(0),
    "failed_count": schema.int.min(0),
    "success_rate": schema.float.min(0.0).max(100.0),
    "avg_wait_seconds": schema.float.min(0.0),
    "avg_processing_seconds": schema.float.min(0.0),
    "stats_window_days": schema.int.min(1).max(365),
})

__all__ = [
    "DATETIME_PATTERN",
    "DashboardStatsSchema",
    "QueueItemSchema",
    "QueueStateSchema",
]
```

---

### Задача 8: Создать events/mr_event.py

**Файл:** `backend/scenarios/schemas/events/mr_event.py`

**Содержимое:**
```python
"""Схемы для MR webhook событий из src/gitlab_queue/models/events.py."""

from d42 import optional, schema

from scenarios.library import MRState
from scenarios.schemas._helpers import enum_schema
from scenarios.schemas.merge_request import MAX_LABELS, SHA_LENGTH

MRStateSchema = enum_schema(MRState)

# MR actions from GitLab webhooks
MR_ACTIONS = [
    "open", "close", "reopen", "update", "merge",
    "approved", "unapproved", "labeled", "unlabeled",
]
MRActionSchema = schema.any(*[schema.str(a) for a in MR_ACTIONS])

# Соответствует dataclass LabelChanges
LabelChangesSchema = schema.dict({
    optional("previous"): schema.list(schema.str.len(1, 255)).len(0, MAX_LABELS),
    optional("current"): schema.list(schema.str.len(1, 255)).len(0, MAX_LABELS),
})

# Соответствует dataclass MergeRequestAttributes
MRAttributesSchema = schema.dict({
    "iid": schema.int.min(1).max(2_147_483_647),
    "title": schema.str.len(1, 255),
    "state": MRStateSchema,
    "action": MRActionSchema,
    "source_branch": schema.str.len(1, 255),
    "target_branch": schema.str.len(1, 255),
    "merge_status": schema.str.len(1, 50),
    optional("sha"): schema.str.len(SHA_LENGTH, SHA_LENGTH).regex(r"^[a-f0-9]+$"),
    optional("has_conflicts"): schema.bool,
    optional("rebase_in_progress"): schema.bool,
    optional("web_url"): schema.str.len(1, 2048),
})

# Соответствует dataclass MergeRequestEvent
MergeRequestEventSchema = schema.dict({
    "object_kind": schema.str("merge_request"),
    "event_type": schema.str("merge_request"),
    "project_id": schema.int.min(1).max(2_147_483_647),
    "object_attributes": MRAttributesSchema,
    "user_id": schema.int.min(1).max(2_147_483_647),
    "user_name": schema.str.len(1, 255),
    "user_username": schema.str.len(1, 255),
    optional("user_avatar"): schema.str.len(1, 2048),
    optional("labels"): schema.list(schema.str.len(1, 255)).len(0, MAX_LABELS),
    optional("label_changes"): LabelChangesSchema,
})

__all__ = [
    "LabelChangesSchema",
    "MR_ACTIONS",
    "MRActionSchema",
    "MRAttributesSchema",
    "MergeRequestEventSchema",
]
```

---

### Задача 9: Создать events/pipeline_event.py

**Файл:** `backend/scenarios/schemas/events/pipeline_event.py`

**Содержимое:**
```python
"""Схемы для Pipeline webhook событий из src/gitlab_queue/models/events.py."""

from d42 import optional, schema

from scenarios.schemas.merge_request import SHA_LENGTH
from scenarios.schemas.queue_item import DATETIME_PATTERN

# Pipeline statuses from GitLab
PIPELINE_STATUSES = [
    "pending", "running", "success", "failed",
    "canceled", "skipped", "manual", "scheduled",
]
PipelineStatusSchema = schema.any(*[schema.str(s) for s in PIPELINE_STATUSES])

# Соответствует dataclass PipelineAttributes
PipelineAttributesSchema = schema.dict({
    "id": schema.int.min(1).max(2_147_483_647),
    "status": PipelineStatusSchema,
    "sha": schema.str.len(SHA_LENGTH, SHA_LENGTH).regex(r"^[a-f0-9]+$"),
    "ref": schema.str.len(1, 255),
    optional("web_url"): schema.str.len(1, 2048),
    optional("created_at"): schema.str.regex(DATETIME_PATTERN),
})

# Соответствует dataclass PipelineEvent
PipelineEventSchema = schema.dict({
    "object_kind": schema.str("pipeline"),
    "project_id": schema.int.min(1).max(2_147_483_647),
    "object_attributes": PipelineAttributesSchema,
    optional("merge_request_iid"): schema.int.min(1).max(2_147_483_647),
})

__all__ = [
    "PIPELINE_STATUSES",
    "PipelineAttributesSchema",
    "PipelineEventSchema",
    "PipelineStatusSchema",
]
```

---

### Задача 10: Создать events/note_event.py

**Файл:** `backend/scenarios/schemas/events/note_event.py`

**Содержимое:**
```python
"""Схемы для Note webhook событий из src/gitlab_queue/models/events.py."""

from d42 import optional, schema

# Типы объектов для заметок
NOTEABLE_TYPES = ["MergeRequest", "Issue", "Commit", "Snippet"]
NoteableTypeSchema = schema.any(*[schema.str(t) for t in NOTEABLE_TYPES])

# Соответствует dataclass NoteEvent
NoteEventSchema = schema.dict({
    "object_kind": schema.str("note"),
    "event_type": schema.str("note"),
    "project_id": schema.int.min(1).max(2_147_483_647),
    "user_id": schema.int.min(1).max(2_147_483_647),
    "user_name": schema.str.len(1, 255),
    "user_username": schema.str.len(1, 255),
    "note_id": schema.int.min(1).max(2_147_483_647),
    "note_body": schema.str.len(1, 10_000),
    "noteable_type": NoteableTypeSchema,
    optional("merge_request_iid"): schema.int.min(1).max(2_147_483_647),
})

__all__ = [
    "NOTEABLE_TYPES",
    "NoteEventSchema",
    "NoteableTypeSchema",
]
```

---

### Задача 11: Создать events/__init__.py

**Файл:** `backend/scenarios/schemas/events/__init__.py`

**Содержимое:**
```python
"""Схемы для webhook событий."""

from scenarios.schemas.events.mr_event import (
    LabelChangesSchema,
    MR_ACTIONS,
    MRActionSchema,
    MRAttributesSchema,
    MergeRequestEventSchema,
)
from scenarios.schemas.events.note_event import (
    NOTEABLE_TYPES,
    NoteableTypeSchema,
    NoteEventSchema,
)
from scenarios.schemas.events.pipeline_event import (
    PIPELINE_STATUSES,
    PipelineAttributesSchema,
    PipelineEventSchema,
    PipelineStatusSchema,
)

__all__ = [
    # mr_event
    "LabelChangesSchema",
    "MR_ACTIONS",
    "MRActionSchema",
    "MRAttributesSchema",
    "MergeRequestEventSchema",
    # note_event
    "NOTEABLE_TYPES",
    "NoteEventSchema",
    "NoteableTypeSchema",
    # pipeline_event
    "PIPELINE_STATUSES",
    "PipelineAttributesSchema",
    "PipelineEventSchema",
    "PipelineStatusSchema",
]
```

---

### Задача 12: Обновить schemas/__init__.py

**Файл:** `backend/scenarios/schemas/__init__.py`

**Содержимое:**
```python
"""d42 схемы для тестовых данных."""

# Утилиты
from scenarios.schemas._helpers import enum_schema

# Базовые схемы
from scenarios.schemas.author import AuthorSchema
from scenarios.schemas.merge_request import (
    MAX_LABELS,
    MergeRequestSchema,
    MRStateSchema,
    NoteSchema,
    SHA_LENGTH,
)
from scenarios.schemas.queue_item import (
    DATETIME_PATTERN,
    DashboardStatsSchema,
    QueueItemSchema,
    QueueStateSchema,
)
from scenarios.schemas.secret import (
    GitLabTokenSchema,
    JWTSecretSchema,
    SecretValueSchema,
    WebhookSecretSchema,
)
from scenarios.schemas.status_code import (
    AcceptedStatusSchema,
    BadRequestStatusSchema,
    ConflictStatusSchema,
    CreatedStatusSchema,
    ForbiddenStatusSchema,
    InternalServerErrorStatusSchema,
    NoContentStatusSchema,
    NotFoundStatusSchema,
    OkStatusSchema,
    ServiceUnavailableStatusSchema,
    UnauthorizedStatusSchema,
    UnprocessableEntityStatusSchema,
)

# События
from scenarios.schemas.events import (
    LabelChangesSchema,
    MergeRequestEventSchema,
    MR_ACTIONS,
    MRActionSchema,
    MRAttributesSchema,
    NoteEventSchema,
    NoteableTypeSchema,
    NOTEABLE_TYPES,
    PipelineAttributesSchema,
    PipelineEventSchema,
    PIPELINE_STATUSES,
    PipelineStatusSchema,
)

__all__ = [
    # Утилиты
    "enum_schema",
    # Базовые
    "AuthorSchema",
    "DATETIME_PATTERN",
    "MAX_LABELS",
    "SHA_LENGTH",
    # Secret
    "GitLabTokenSchema",
    "JWTSecretSchema",
    "SecretValueSchema",
    "WebhookSecretSchema",
    # MergeRequest
    "MergeRequestSchema",
    "MRStateSchema",
    "NoteSchema",
    # QueueItem
    "DashboardStatsSchema",
    "QueueItemSchema",
    "QueueStateSchema",
    # Status codes
    "AcceptedStatusSchema",
    "BadRequestStatusSchema",
    "ConflictStatusSchema",
    "CreatedStatusSchema",
    "ForbiddenStatusSchema",
    "InternalServerErrorStatusSchema",
    "NoContentStatusSchema",
    "NotFoundStatusSchema",
    "OkStatusSchema",
    "ServiceUnavailableStatusSchema",
    "UnauthorizedStatusSchema",
    "UnprocessableEntityStatusSchema",
    # Events
    "LabelChangesSchema",
    "MergeRequestEventSchema",
    "MR_ACTIONS",
    "MRActionSchema",
    "MRAttributesSchema",
    "NoteEventSchema",
    "NoteableTypeSchema",
    "NOTEABLE_TYPES",
    "PipelineAttributesSchema",
    "PipelineEventSchema",
    "PIPELINE_STATUSES",
    "PipelineStatusSchema",
]
```

---

### Задача 13: Мигрировать тесты config/secret/

**Файлы для миграции:**

| Файл | Изменение |
|------|-----------|
| `create_secret_and_hide_value_in_str_representation.py` | `self.secret_value = fake(SecretValueSchema)` |
| `retrieve_actual_secret_value.py` | `self.secret_value = fake(SecretValueSchema)` |
| `secret_blocks_direct_access_to_secret_value.py` | `self.secret = Secret(fake(SecretValueSchema))` |
| `secret_attributes_cannot_be_deleted.py` | `self.secret = Secret(fake(SecretValueSchema))` |
| `secret_equality_uses_constant_time_comparison.py` | генерировать оба значения |
| `secret_is_hashable.py` | `self.secret = Secret(fake(SecretValueSchema))` |
| `secret_is_immutable.py` | `self.secret = Secret(fake(SecretValueSchema))` |
| `secret_length_returns_correct_value.py` | `self.secret_value = fake(SecretValueSchema)` |
| `secret_not_equal_to_non_secret_type.py` | `self.secret = Secret(fake(SecretValueSchema))` |
| `secret_not_leaked_in_format_string.py` | `self.secret_value = fake(SecretValueSchema)` |
| `secrets_with_same_value_have_same_hash.py` | `self.value = fake(SecretValueSchema)` |
| `different_secrets_are_not_equal.py` | генерировать два разных значения |

**Пример миграции:**

До:
```python
def given_secret(self):
    self.secret_value = "my-api-key-12345"
    self.secret = Secret(self.secret_value)
```

После:
```python
from d42 import fake
from scenarios.schemas import SecretValueSchema

def given_secret(self):
    self.secret_value = fake(SecretValueSchema)
    self.secret = Secret(self.secret_value)
```

---

### Задача 14: Мигрировать хелперы webhooks/mr_webhook/_helpers.py

**Файл:** `backend/scenarios/webhooks/mr_webhook/_helpers.py`

**Изменения:**
- Заменить хардкодные значения в `create_mr_event()` на генерацию через схемы
- Использовать `fake(MRAttributesSchema % {...})` для создания атрибутов

---

### Задача 15: Мигрировать api_helpers.py

**Файл:** `backend/scenarios/contexts/api_helpers.py`

**Изменения:**
- `created_test_queue_item()` — использовать `fake(QueueItemSchema % {...})`
- `created_mock_settings()` — использовать `fake(SecretValueSchema)` для секретов
- `created_test_jwt()` — использовать схемы для user данных

---

## 6. Примеры реализации

### 6.1 Тест с генерацией данных

```python
"""Unit tests for Secret class."""

import vedro
from d42 import fake

from gitlab_queue.config import Secret
from scenarios.schemas import SecretValueSchema


class Scenario(vedro.Scenario):
    subject = "retrieve actual secret value"

    def given_secret(self):
        self.secret_value = fake(SecretValueSchema)
        self.secret = Secret(self.secret_value)

    def when_getting_secret_value(self):
        self.retrieved = self.secret.get_secret_value()

    def then_it_should_return_original_value(self):
        assert self.retrieved == self.secret_value
```

### 6.2 Тест с переопределением полей

```python
"""Test: handle labeled action adds MR to queue."""

import vedro
from d42 import fake

from gitlab_queue.webhooks.handlers import MRWebhookHandler
from scenarios.library import Labels, MRState
from scenarios.schemas import MergeRequestEventSchema

from ._helpers import create_mock_gitlab_client, create_mock_queue_manager, created_mock_settings


class Scenario(vedro.Scenario):
    subject = "handle labeled action adds MR to queue"

    def given_handler(self):
        self.settings = created_mock_settings()
        self.gitlab_client = create_mock_gitlab_client()
        self.queue_manager = create_mock_queue_manager()
        self.handler = MRWebhookHandler(
            settings=self.settings,
            gitlab_client=self.gitlab_client,
            queue_manager=self.queue_manager,
        )
        # Генерация события с переопределением нужных полей
        self.event = fake(MergeRequestEventSchema % {
            "object_attributes": {
                "action": "labeled",
                "state": MRState.OPENED,
            },
            "labels": [Labels.MERGE_QUEUE],
            "label_changes": {
                "previous": [],
                "current": [Labels.MERGE_QUEUE],
            },
        })

    async def when_event_is_handled(self):
        await self.handler.handle(self.event)

    def then_mr_should_be_fetched_and_added(self):
        self.gitlab_client.get_mr.assert_called_once()
        self.queue_manager.add_to_queue.assert_called_once()
```

### 6.3 Тест с опциональными полями

```python
"""Test MR with web_url."""

import vedro
from d42 import fake
from d42.utils import make_required

from scenarios.schemas import MergeRequestSchema


class Scenario(vedro.Scenario):
    subject = "process MR with web_url"

    def given_mr_with_web_url(self):
        # Форсируем генерацию опционального поля web_url
        self.mr = fake(make_required(MergeRequestSchema, {"web_url"}))

    def when_processing_mr(self):
        # ...
        pass

    def then_web_url_should_be_present(self):
        assert "web_url" in self.mr
        assert self.mr["web_url"].startswith("http")
```

### 6.4 Тест с невалидными данными

```python
"""Test validation rejects invalid MR."""

import vedro
from d42 import fake

from scenarios.schemas import MergeRequestSchema


class Scenario(vedro.Scenario):
    subject = "try to process MR with invalid iid"

    def given_invalid_mr(self):
        # Сначала генерируем валидные данные
        self.mr = fake(MergeRequestSchema)
        # Затем делаем невалидными
        self.mr["iid"] = -1

    def when_validating_mr(self):
        # ...
        pass

    def then_validation_should_fail(self):
        # ...
        pass
```

---

## 7. Чек-лист для ревью

При ревью миграции проверять:

- [ ] Импорт `from d42 import fake` присутствует
- [ ] Нет хардкодных строк для тестовых данных
- [ ] Схемы имеют явные границы (`.len(min, max)`, `.min()`, `.max()`)
- [ ] Опциональные поля помечены через `optional()`
- [ ] Списки имеют верхний лимит (`.len(0, MAX_LIMIT)`)
- [ ] Enum'ы используются через `enum_schema()` или константы из `scenarios.library`
- [ ] Невалидные данные создаются после генерации, не через схему
- [ ] `make_required` импортируется из `d42.utils`, не из `d42`
- [ ] Схемы экспортируются через `__all__`
