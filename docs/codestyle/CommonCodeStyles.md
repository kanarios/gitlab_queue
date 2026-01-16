# Общие Code Style и Соглашения для всех проектов

> Данный документ содержит соглашения, применимые ко **всем** проектам автотестирования на базе фреймворка [vedro](https://vedro.io/).

---

## Содержание

1. [Философия тестирования](#1-философия-тестирования)
2. [Структура теста](#2-структура-теста)
3. [Именование шагов](#3-именование-шагов)
4. [Параметризация тестов](#4-параметризация-тестов)
5. [Контексты](#5-контексты)
6. [Моки](#6-моки)
7. [Схемы данных (d42)](#7-схемы-данных-d42)
8. [Константы](#8-константы)
9. [Проверки (assertions)](#9-проверки-assertions)
10. [Стиль кода Python](#10-стиль-кода-python)
11. [Комментарии и документация](#11-комментарии-и-документация)
12. [Работа с нестабильными тестами](#12-работа-с-нестабильными-тестами)
13. [Версионирование зависимостей](#13-версионирование-зависимостей)

---

## 1. Философия тестирования

### Тесты = Документация

- Тесты должны быть **читаемыми** и понятными
- Из тестов должен быть понятен **сценарий воспроизведения** действий
- Названия шагов, переменных и функций должны отражать:
  - действия пользователя
  - происходящее в приложении
  - взаимодействие с бэкендом

### Принципы атомарности

- Один тест — одно целевое действие
- Если требуется расширить тест новым `given` и новым `then` — скорее всего это **отдельный тест**

---

## 2. Структура теста

### Три блока: given → when → then

Каждый тест состоит из трёх логических блоков:

```python
class Scenario(vedro.Scenario):
    subject = "описание целевого действия"

    def given_preconditions(self):
        """Подготовка данных и состояния"""
        pass

    def when_action(self):
        """Целевое действие (всегда ОДНО)"""
        pass

    def then_expected_result(self):
        """Проверка результата"""
        pass

    def and_additional_check(self):
        """Дополнительные проверки"""
        pass
```

### Правила блоков

| Блок | Количество | Правила |
|------|------------|---------|
| `given_` | 0..N | Подготовка данных, моки, состояние приложения. **Без ассертов!** |
| `when_` | **1** | Одно целевое действие. Всегда ровно один шаг |
| `then_` | 1 | Первая проверка результата |
| `and_` | 0..N | Дополнительные проверки. **Без изменения состояния!** |

### Важно

- `when`-шаг **всегда один** в тесте
- Блоки `then` и `and` **не должны содержать действий**, изменяющих состояние приложения
- Если в тесте большое количество `then` (>2), оцените оправданность — возможно, стоит разнести на несколько тестов

✅ **Хорошо**
```python
class Scenario(vedro.Scenario):
    subject = "create new user with valid data"

    def given_user_data(self):
        self.user = fake(UserSchema)

    def when_create_user(self):
        self.response = Api().create_user(self.user)

    def then_user_created_successfully(self):
        assert self.response.status_code == HTTPStatus.CREATED

    def and_response_contains_user_id(self):
        assert self.response.body['id'] == schema.str
```

❌ **Плохо**
```python
class Scenario(vedro.Scenario):
    subject = "create and update user"

    def when_create_and_update_user(self):  # Два действия в одном шаге!
        self.user = Api().create_user(self.user_data)
        self.updated = Api().update_user(self.user['id'], self.new_data)

    def then_check_result(self):
        Api().delete_user(self.user['id'])  # Действие в проверке!
        assert self.updated['name'] == self.new_data['name']
```

### Один файл — один сценарий

Файл с тестом должен содержать **только класс сценария** и импорты. Никаких дополнительных функций, переменных, констант или хелперов в тестовом файле быть не должно.

**Почему:**
- Тест остаётся самодокументируемым и изолированным
- Вспомогательный код переиспользуется через контексты и хелперы
- Легче находить и поддерживать тесты

✅ **Хорошо**
```python
# scenarios/unit/queue/add_mr_to_empty_queue.py
import vedro
from scenarios.contexts.sqlite_client import initialized_test_database
from scenarios.contexts.helpers import create_test_mr

from gitlab_queue.core.queue import QueueManager


class Scenario(vedro.Scenario):
    subject = "add mr to empty queue"

    async def given_empty_queue(self):
        self.db = await initialized_test_database()
        self.queue = QueueManager(db=self.db)

    async def when_mr_is_added(self):
        self.mr = create_test_mr(iid=42)
        self.item = await self.queue.add_to_queue(self.mr)

    async def then_item_should_be_at_position_1(self):
        position = await self.queue.get_queue_position(42)
        assert position == 1
```

❌ **Плохо**
```python
# scenarios/unit/queue/add_mr_to_empty_queue.py
import vedro

from gitlab_queue.core.queue import QueueManager
from gitlab_queue.models.mr import Author, MergeRequest


# Хелпер внутри тестового файла — должен быть в contexts/helpers.py!
def create_test_mr(iid: int, title: str = "Test MR") -> MergeRequest:
    return MergeRequest(
        iid=iid,
        title=title,
        state="opened",
        author=Author(id=iid, name="Test", username="test"),
    )


# Константа внутри тестового файла — должна быть в library/!
DEFAULT_TIMEOUT = 30


class Scenario(vedro.Scenario):
    subject = "add mr to empty queue"
    # ...
```

---

## 3. Именование шагов

### Времена глаголов

| Блок | Время | Пример |
|------|-------|--------|
| `given_` | Прошедшее (Past Participle) | `given_user_created`, `given_opened_page` |
| `when_` | Настоящее (Present Simple) | `when_click_button`, `when_send_request` |
| `then_/and_` | Настоящее/Будущее | `then_it_should_return_success`, `and_user_is_visible` |

### Именование subject и файла

Формула именования:
```
subject = '{Action} {object} {condition: where, dataset}'
```

Компоненты:
- **Action** — действие пользователя (из шага `when`)
- **Object** — объект действия
- **Condition** — уточнение условий (где, с какими данными)

✅ **Хорошо**
```python
# Файл: open_booking_form_as_auth_user.py
subject = "Open booking form as auth user"

# Файл: click_locked_analytic_as_demo_user.py
subject = "Click locked analytic as demo user"

# Файл: close_deletion_popup_when_deleting_layer.py
subject = "Close deletion popup when deleting layer from project"
```

### Негативные сценарии

Для бизнесово негативных сценариев добавляем префикс `try to`:

```python
# Файл: try_to_send_review_as_guest.py
subject = "try to send review as guest"

# Файл: try_to_get_tags_with_error.py
subject = "try to get tags when user check return error {status_code}"
```

### Избегайте лишних предлогов

❌ **Плохо**: `Click on locked analytic`, `Select the number grouping`
✅ **Хорошо**: `Click locked analytic`, `Select number grouping`

---

## 4. Параметризация тестов

### Когда параметризовать

- Если тесты в разных файлах почти одинаковы по наполнению и шагам — объедините через параметризацию
- `subject` **должен быть уникален** для каждого набора параметров

### Правила параметризации

1. **Subject всегда на первом месте** в параметрах
2. **Избегайте вызова методов** в параметризации
3. Файл называется с обобщающим словом вместо параметра

✅ **Хорошо**
```python
# Файл: restore_on_projects_as_user.py
class Scenario(vedro.Scenario):
    subject = "Restore on projects as {user_plan} user"

    @params("free", FreePlanUser)
    @params("premium", PremiumPlanUser)
    def __init__(self, user_plan, user_schema):
        self.user_plan = user_plan
        self.user = fake(user_schema)
```

### Запрещено: вызов методов в параметризации

Причины запрета:
1. Добавляется неочевидное поведение
2. Замедляет запуск **любого** теста
3. Может приводить к некорректному состоянию

❌ **Плохо**
```python
@params(create_user())  # Метод вызывается при импорте!
def __init__(self, user):
    self.user = user
```

✅ **Хорошо — используйте lambda**
```python
@params(lambda: create_user())
def __init__(self, create_user_func):
    self.user = create_user_func()
```

✅ **Хорошо — передавайте функции отдельно**
```python
@params(create_user, "guest")
@params(create_user, "admin")
def __init__(self, factory, role):
    self.user = factory(role)
```

### Исключение: инициализация простых объектов

```python
@params(list())   # Допустимо
@params(dict())   # Допустимо
def __init__(self, empty_collection):
    self.collection = empty_collection
```

---

## 5. Контексты

### Что такое контекст

Контекст — метод, который гарантирует приведение сервиса в определённое состояние (открытие страницы, подготовка данных и т.д.).

### Правила контекстов

1. **Маркировка декоратором** `@vedro.context`
2. **Именование в прошедшем времени** (деепричастие)
3. **Обязательные assert-ы** для гарантии состояния
4. **Не принимает `self`** — это функция, не метод класса
5. **Добавляйте в `__init__.py`** для упрощения импорта

✅ **Хорошо**
```python
@vedro.context
async def opened_booking_form(checkout: dict) -> BookingPage:
    """
    Открывает форму бронирования.
    
    :param checkout: данные чекаута
    :return: объект страницы бронирования
    """
    page = await open_page(BookingPage, checkout)
    assert await page.form.is_visible()  # Гарантия состояния
    return page
```

❌ **Плохо**
```python
# Нет декоратора, неправильное именование
async def booking_card_is_opened():
    pass

# Нет гарантирующего assert
@vedro.context
async def opened_booking_form(checkout):
    return await open_page(BookingPage, checkout)
    # Нет проверки, что форма действительно открылась!
```

### Проверки в контекстах

В контекстах **обязательно проверяем**:
- Статус код ответа (для API)
- Видимость ключевого элемента (для UI)
- Историю моков (если мок использовался)

```python
@vedro.context
async def created_user(user_data: dict) -> dict:
    """Создаёт пользователя через API"""
    response = Api().create_user(user_data)
    assert response.status_code == HTTPStatus.CREATED, response
    return response.body
```

### Использование контекстов в шагах

В шагах `given_`, `then_` и `and_` используйте контексты, а не вызов методов напрямую.

```python
def given_user_created(self):
    self.user = created_user(self.user_data)  # Контекст

def given_opened_page(self):
    self.page = await opened_booking_form(self.checkout)  # Контекст
```

---

## 6. Моки

### Именование моков

Формула: `mocked_[service]_[endpoint]_[method:optional]_[result:optional]`

| Компонент | Описание | Пример |
|-----------|----------|--------|
| `service` | Название сервиса | `booking`, `auth`, `users` |
| `endpoint` | Эндпоинт | `visibility`, `me`, `items` |
| `method` | HTTP метод (если несколько) | `get`, `patch`, `post` |
| `result` | Тип результата (если ошибка/пусто) | `error`, `empty` |

✅ **Примеры**
```python
mocked_booking_get                  # Один метод
mocked_users_me_get                 # Несколько методов на эндпоинт
mocked_users_me_patch               
mocked_reviews_empty                # Пустой результат
mocked_booking_by_id_get_error      # Ошибка
```

### Структура папок моков

```
mocks/
├── service_name/
│   ├── mocked_service_endpoint_1.py
│   └── mocked_service_endpoint_2.py
├── another_service/
│   └── mocked_endpoint.py
└── __init__.py
```

**Правило:** в одном файле лежат моки только на **один URL**.

### Использование with для моков

Всегда используем **один `with` со скобками** — проще добавлять новые моки:

✅ **Хорошо**
```python
# Один мок
with mocked_smth():
    pass

# Несколько моков
with (
    mocked_smth_1(),
    mocked_smth_2(),
    mocked_smth_3(),
):
    pass
```

❌ **Плохо**
```python
with mocked_smth_1():
    with mocked_smth_2():
        with mocked_smth_3():  # Глубокая вложенность
            pass
```

### Сохранение истории моков

- **В тесте** — сохраняем историю в переменную с префиксом `history`:
```python
with mocked_endpoint() as self.history_endpoint:
    pass
```

- **В контексте** — сохраняем только если нужно проверить факт отправки запроса

### Моки НЕ маркируются `@vedro.context`

```python
# ❌ Неправильно
@vedro.context
def mocked_users():
    pass

# ✅ Правильно — обычная функция или asynccontextmanager
@asynccontextmanager
async def mocked_auth_user(user: dict):
    async with AsyncExitStack() as stack:
        mocks = {}
        mocks['token'] = await stack.enter_async_context(mocked_token())
        mocks['user'] = await stack.enter_async_context(mocked_users_me(user))
        yield mocks
```

---

## 7. Схемы данных (d42)

### Импорт из одной библиотеки

```python
from d42 import schema, fake
```

### Правила описания схем

1. **Ограничения соответствуют реальности** — верхние и нижние границы
2. **Все поля обязательные** — опциональные явно отмечены через `optional`
3. **Экспорт через `__all__`**:
```python
__all__ = ['UserSchema', 'BookingSchema']
```

### Опциональные поля

```python
from d42 import optional

CheckinRuleSchema = schema.dict({
    optional('deposit'): DepositSchema,
    'contacts': schema.list([ContactSchema]).len(1, 20),
    'description': schema.str.len(1, 10_000)
})
```

Для гарантированного наличия опционального поля используйте `make_required`:
```python
from d42 import make_required

data = fake(make_required(CheckinRuleSchema, {'deposit'}))
```

### Проверки по схемам

❌ **Плохо** — избыточные проверки
```python
# Проверка длины избыточна, если проверяем содержимое
assert response.body == schema.dict({
    'reviews': schema.list([ReviewSchema % {'id': 1}]).len(1)  # .len(1) лишний
})
```

✅ **Хорошо**
```python
assert response.body == schema.dict({
    'reviews': schema.list([ReviewSchema % {'id': 1}])  # Содержимое уже проверяет длину
})
```

### Проверка на пустоту

```python
# Пустой словарь
assert data == schema.dict.empty  # ✅ Правильно
assert data == schema.dict({})    # ❌ Неправильно — любой словарь

# Пустая строка
assert text == schema.str('')     # ✅ Правильно — видим содержимое при падении
assert text == schema.str.len(0)  # ❌ Неправильно — не видим содержимое
```

### Лимиты генерации

Всегда устанавливайте **верхний лимит** для генерации сущностей:

```python
# ❌ Плохо — бесконечная генерация
ItemsListSchema = schema.list(ItemSchema).len(1, ...)

# ✅ Хорошо — явный лимит
ITEMS_LIMIT = 100  # ограничение для предотвращения замедления тестов
ItemsListSchema = schema.list(ItemSchema).len(1, ITEMS_LIMIT)
```

---

## 8. Константы

### Когда выносить в константы

Строка выносится в константы, если встречается в тестах **более одного раза**.

### Организация констант

Используйте классы или `StrEnum` в папке `library/`:

```python
# library/user_status.py
from enum import StrEnum

class UserStatus(StrEnum):
    ACTIVE = 'active'
    UNCONFIRMED = 'unconfirmed'
    BLOCKED = 'blocked'
```

Преимущества `StrEnum`:
```python
# В схемах — автоматическое перечисление всех значений
StatusSchema = schema.any(*[schema.str(s) for s in UserStatus])
```

### HTTP статусы

Используйте `HTTPStatus` из стандартной библиотеки:

```python
from http import HTTPStatus

# В моках (jj)
from jj.http.codes import OK, NOT_FOUND

# В тестах
assert response.status_code == HTTPStatus.OK
```

---

## 9. Проверки (assertions)

### Порядок проверок

1. **Сначала** — быстрые проверки (параметры запроса, история моков)
2. **Потом** — медленные проверки (UI элементы с ретраями)

```python
def then_request_sent_correctly(self):
    # Быстрая проверка — история мока
    assert self.mock.history[0]['request'].body == expected_body

def and_ui_updated(self):
    # Медленная проверка — UI
    assert await self.page.element.text == expected_text
```

### Не дублируйте проверки

❌ **Плохо**
```python
def and_error_is_visible(self):
    assert await self.page.error.is_visible()  # Избыточно
    assert await self.page.error.text == "Error message"
```

✅ **Хорошо**
```python
def and_error_is_visible(self):
    # text_content() под капотом проверяет видимость
    assert await self.page.error.text == "Error message"
```

### Проверки без явного сайд-эффекта

Если сайд-эффект сложно проверить — опишите его комментарием:

```python
def and_it_should_save_retry_count_in_db(self):
    # Worker сохраняет retry_count в таблицу 'retry_counts'
    # Проверка происходит в тесте на Cli.retry_delivery()
    assert True
```

---

## 10. Стиль кода Python

### Форматирование

| Параметр | Значение |
|----------|----------|
| Длина строки | **120 символов** |
| Кавычки | Двойные `"` |
| Отступы | 4 пробела |

### Типизация

Используйте встроенные типы, **не** `typing.Dict`, `typing.List`:

```python
# ✅ Правильно
def context(id: str, user: dict) -> None:
    pass

def get_items(filters: list[str]) -> dict[str, Any]:
    pass

# ❌ Неправильно
from typing import Dict, List

def context(id: str, user: Dict) -> None:
    pass
```

### Форматирование аргументов

```python
# ✅ Хорошо — каждый аргумент на новой строке
def some_method(
    self,
    argument_1: dict[str, Any],
    argument_2: Callable,
    argument_3: str | None = None,
) -> OutputType:
    pass

# ❌ Плохо — сложно читать и добавлять аргументы
def some_method(self, argument_1: dict[str, Any], argument_2: Callable,
                argument_3: str | None = None) -> OutputType:
    pass
```

### Запрещено в тестах

- **`if`** — ведёт к нечитаемым тестам
- **Неиспользуемые переменные** — удаляйте после рефакторинга
- **`SELECT *`** — получайте только нужные поля

### Конфигурация

Используйте обращение к атрибутам:
```python
# ✅ Правильно
cfg.apple_export.path

# ❌ Неправильно
cfg['apple_export']['path']
```

---

## 11. Комментарии и документация

### Язык комментариев

**Русский язык** для комментариев в тестах.

### Когда писать комментарии

- Тест **не самый очевидный** по логике
- Объяснение **почему** выбраны определённые значения
- Ссылки на тикеты при временных решениях

### Docstring

Пишите только **при необходимости** — для контекстов и хелперов:

```python
@vedro.context
async def opened_asset_page(
    asset: dict,
    filters: list,
    user: dict | None = None,
) -> AssetPage:
    """
    Открывает страницу ассета.

    :param asset: данные ассета
    :param filters: список фильтров
    :param user: пользователь (по умолчанию генерируется)
    :return: объект страницы
    """
    pass
```

### Docstring для класса сценария

Docstring для класса `Scenario` **не нужен** — `subject` уже описывает назначение теста. Дублирование информации загромождает код.

✅ **Хорошо**
```python
class Scenario(vedro.Scenario):
    subject = "add mr to empty queue"

    async def given_empty_queue(self):
        ...
```

❌ **Плохо**
```python
class Scenario(vedro.Scenario):
    """Test adding MR to an empty queue."""  # Дублирует subject!

    subject = "add mr to empty queue"

    async def given_empty_queue(self):
        ...
```

---

## 12. Работа с нестабильными тестами

### Теги для flaky тестов

```python
class Scenario(vedro.Scenario):
    subject = 'Open existing hub page (desktop)'
    # TODO: OTELLO-7992
    tags = ['flaky']
```

**Обязательно:** комментарий с номером тикета для фикса!

### Параметризованные flaky тесты

Отмечайте только **проблемный набор параметров**:

✅ **Хорошо**
```python
@params("hotel_name", "general_info.name")
# TODO: OTELLO-5555
@params[scenario_tags('flaky')]("available_rooms", "offers_section")
@params("reviews", "reviews_block")
```

❌ **Плохо**
```python
# TODO: OTELLO-5555
tags = ['flaky']  # Помечен весь тест, хотя проблема в одном параметре

@params("hotel_name", "general_info.name")
@params("available_rooms", "offers_section")
@params("reviews", "reviews_block")
```

### Тесты на баги, которые не будут фиксить

**Если падает часть теста:**
```python
@params(Locale.ru_RU, CopyrightText.RUSSIAN)
@params(Locale.cs_CZ, CopyrightText.CZECH)  # Баг: cs_CZ возвращает английский текст
```

**Если падает весь шаг:**
```python
@assertion_skip(reason="Defect https://jira.example.com/browse/BUG-123")
def and_it_should_send_email(self):
    assert self.email_sent == True
```

---

## 13. Версионирование зависимостей

### requirements.in

Фиксируйте **диапазон версий**:

```
aiohttp>=3.0,<4.0
vedro>=1.9,<2.0
playwright>=1.40,<2.0
```

---

## Чек-лист перед созданием MR

- [ ] Тест проходит локально
- [ ] Subject уникален (для параметризованных тестов)
- [ ] Нет вызовов методов в параметризации
- [ ] Контексты имеют гарантирующие assert-ы
- [ ] Моки правильно именованы и структурированы
- [ ] Нет неиспользуемых переменных
- [ ] Комментарии на русском языке
- [ ] Типизация без `typing.Dict/List`
- [ ] Длина строки ≤ 120 символов

---

## Рефакторинг

**Рефакторингу есть предел!**

Если рефакторинг:
- Затрудняет прочтение MR
- Затрагивает более **7 файлов**

→ **Вынесите в отдельный MR**
