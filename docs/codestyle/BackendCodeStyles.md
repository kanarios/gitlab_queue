# Code Style и Соглашения для Backend тестов

> Данный документ содержит соглашения, специфичные для **backend** тестов (API, Workers, Kafka, gRPC).
> 
> **Важно:** Перед прочтением ознакомьтесь с [CommonCodeStyles.md](CommonCodeStyles.md) — общими правилами для всех проектов.

---

## Содержание

1. [Именование в BE тестах](#1-именование-в-be-тестах)
2. [Структура папок](#2-структура-папок)
3. [Проверка кодов ответа](#3-проверка-кодов-ответа)
4. [Работа с API](#4-работа-с-api)
5. [Воркеры](#5-воркеры)
6. [Kafka](#6-kafka)
7. [Работа с БД](#7-работа-с-бд)
8. [Работа со временем](#8-работа-со-временем)
9. [Обработка логов воркеров](#9-обработка-логов-воркеров)
10. [Интерфейсы](#10-интерфейсы)

---

## 1. Именование в BE тестах

### Subject со строчной буквы

В BE тестах `subject` **пишется со строчной буквы**:

```python
# ✅ BE тест
subject = "get all dashboards after add layer"

# FE тест (для сравнения)
subject = "Open booking form as auth user"
```

### Название отражает метод из when

В названии теста и `subject` должен присутствовать **метод**, который выполняется в шаге `when_`:

```python
# Файл: get_user_by_id.py
subject = "get user by id with valid token"

async def when_get_user_by_id(self):
    self.response = await Api().get_user(self.user_id)
```

### Бизнес-смысл важнее HTTP метода

Называйте по **бизнесовому смыслу**, даже если HTTP метод другой:

```python
# Тестируем получение офферов, хотя метод POST
# ✅ Правильно
subject = "get search offers by geo_id with required params"

# ❌ Неправильно
subject = "post search offers request"  # Технический, а не бизнесовый смысл
```

### Негативные сценарии

**Бизнесово-негативные** (ожидаем ошибку) — `try to`:
```python
subject = "try to get tags when user check return error {status_code}"
```

**Валидная логика с пустым результатом** (P0, P1):
```python
subject = "do not send notification when user disabled"
subject = "get no reviews for new hotel"
subject = "get empty list when no items match filter"
```

### Приоритеты сценариев

| Приоритет | Описание | Примеры |
|-----------|----------|---------|
| **P0** | Падение = невозможность пользования | `open booking form`, `get user profile` |
| **P1** | Падение = неудобства, но можно пользоваться | `open booking form with empty personal info` |
| **P2** | Падение = несущественные неудобства | Проверки текста в некритичных местах |

---

## 2. Структура папок

### Организация по методам

```
scenarios/
├── users/
│   ├── get_user/
│   │   ├── get_user_by_id.py
│   │   └── get_user_with_invalid_token.py
│   ├── create_user/
│   │   ├── create_user_with_valid_data.py
│   │   └── try_to_create_user_without_required_fields.py
│   └── delete_user/
│       └── delete_user_by_id.py
├── import_booking_from_kafka/
│   └── ...
└── export_to_kafka/
    ├── post_review.py
    └── no_events/
        └── any_trigger.py
```

### Правила структурирования

1. Папка с названием **группы метода** (из `when`)
2. Папка с названием **метода**
3. Подпапки по **типу ассета** или **сайд-эффекту** при необходимости:
   - `dynamic_asset/`, `user_asset/`, `urbi_asset/`
   - `no_events/`

### Исключение: Kafka экспорт

Тесты на экспорт в Kafka именуются по **триггеру**, а не по методу:

```
export_to_kafka/
├── post_review.py           # По триггеру
└── no_events/
    └── update_user.py       # Событие НЕ отправляется
```

---

## 3. Проверка кодов ответа

### В моках — библиотека jj

```python
from jj.http.codes import OK, NOT_FOUND, BAD_REQUEST
from jj.http.methods import GET, POST, PATCH

def mocked_endpoint(data: dict):
    return mocked_response(
        matcher=jj.match(GET, "/endpoint"),
        response=jj.Response(status=OK, json=data)
    )
```

### В контекстах — HTTPStatus

```python
from http import HTTPStatus

@vedro.context
def created_user(user_data: dict) -> dict:
    response = Api().create_user(user_data)
    assert response.status_code == HTTPStatus.CREATED, response
    return response.body
```

**Почему не схемы в контекстах?** При падении ошибки выводятся криво.

### В тестах — схемы

```python
# schemas/status_code.py
OkStatusSchema = schema.int(HTTPStatus.OK)
CreatedStatusSchema = schema.int(HTTPStatus.CREATED)
NoContentStatusSchema = schema.int(HTTPStatus.NO_CONTENT)
NotFoundStatusSchema = schema.int(HTTPStatus.NOT_FOUND)

# scenarios/test.py
def then_it_should_return_success(self):
    assert self.response.status_code == OkStatusSchema

def then_it_should_return_not_found(self):
    assert self.response.status_code == NotFoundStatusSchema
```

### Проверка ошибок

Проверяйте **последнюю часть** сообщения об ошибке:

```python
# Ответ сервиса:
# {"message": "Ошибка валидации: ('id1', 'id2'): тип: 'UNKNOWN': некорректный источник"}

def then_it_should_return_validation_error(self):
    assert self.response.body['message'] == schema.str.contains("некорректный источник")
```

### Response Body ошибок — через схемы

Дублирующие ошибки выносите в схемы:

```python
# schemas/errors.py
SomethingWentWrongErrorSchema = ErrorSchema + schema.dict({
    'user_error[ru]': schema.str('Что-то пошло не так'),
    'user_error[en]': schema.str('Something went wrong'),
    'user_error[ar]': schema.str('حدث خطأ ما'),
})

# scenarios/test.py
def then_it_should_return_error(self):
    assert self.response.body == SomethingWentWrongErrorSchema % {
        "error": Errors.not_found(f"Asset '{self.asset_id}'")
    }
```

---

## 4. Работа с API

### Структура интерфейсов

При **версионировании API** — разные файлы:

```
interfaces/
├── service_name.py          # Основная версия
├── service_name_v1_1.py     # Версия 1.1
└── service_name_v2.py       # Версия 2
```

### Контексты для API

```python
@vedro.context
def got_user_profile(user_id: str, token: str) -> dict:
    """
    Получает профиль пользователя.
    
    :param user_id: ID пользователя
    :param token: токен авторизации
    :return: данные профиля
    """
    response = Api().get_user_profile(user_id, headers={'Authorization': token})
    assert response.status_code == HTTPStatus.OK, response
    return response.body
```

### Генераторы данных и моки — раздельно

**Генератор** — формирует данные:
```python
# helpers/generators/realty/random_realty.py
def random_realty_items(**params) -> dict:
    """Генерирует данные для realty items"""
    return fake(RealtyItemsResultSchema % params)
```

**Мок** — только регистрирует и отдаёт данные:
```python
# mocks/market/mocked_realty_byid.py
@vedro.context
def mocked_realty_byid(payload: dict):
    """Мок для GET /realty/items/{id}"""
    matcher = jj.match(GET, f"/__market__/5.0/realty/items/{payload['result']['product']['id']}")
    response = jj.Response(status=OK, json=payload, headers=get_cors_headers())
    return mocked_response(matcher, response)
```

---

## 5. Воркеры

### batch_size / consumer_limit

Выбирайте так, чтобы **не создавать лишнего ожидания**:

```python
# Если batch_size = минимально необходимое количество для обработки
# → указываем значение по умолчанию 1
def worker_interface(batch_size: int = 1):
    pass

# Если batch_size только ограничивает выборку (воркер берёт всё что есть)
# → можно использовать значение из документации
def worker_interface(batch_size: int = 100):
    pass
```

### Явно указывайте размер батча

В сценариях и контекстах:

```python
async def when_worker_processes_messages(self):
    self.stdout, self.stderr = await Cli().worker_service(
        batch_size=1  # Явно указываем
    )
```

### Тестирование воркеров

Обязательный тест: **воркер не ждёт таймаут** после прочтения батча.

---

## 6. Kafka

### Генерация нового топика

В тестах на вычитывание — **генерируйте новый топик**, не используйте общий:

```python
def given_kafka_topic(self):
    self.topic = generate_unique_topic_name()
```

**Почему?** Избежание каскадного падения тестов.

### Хелперы vs Контексты для Kafka

| Тип | Когда использовать |
|-----|-------------------|
| **Хелпер** | Функция ничего не знает о конкретных топиках/структуре сообщений |
| **Контекст** | Функция знает о конкретных топиках и структуре |

```python
# helpers/kafka.py — универсальная функция
def consume_messages(topic: str, count: int) -> list:
    pass

# contexts/reviews/consumed_review_messages.py — знает о структуре
@vedro.context
def consumed_review_messages(topic: str) -> list[ReviewMessage]:
    messages = consume_messages(topic, count=10)
    return [ReviewMessage.from_dict(m) for m in messages]
```

### Именование тестов на Kafka

```
# Import — по сущности
scenarios/import/reviews/import_review.py

# Export — по триггеру
scenarios/export_to_kafka/post_review.py
scenarios/export_to_kafka/no_events/update_user.py
```

---

## 7. Работа с БД

### Главное правило

**Обращайтесь в БД только если нет других вариантов** проверить результаты теста.

### Именование шагов с БД

По названию **таблицы**:

```python
async def given_inserted_escobar_objects(self):
    self.id = fake(BranchSchema['id'])
    self.region_id = fake(BranchSchema['region_id'])
    await inserted_escobar_objects(self.id, self.region_id)
```

### Запрещено: SELECT *

Получайте только **нужные поля**:

```python
# ❌ Плохо
SELECT * FROM users WHERE id = %s

# ✅ Хорошо
SELECT id, name, email FROM users WHERE id = %s
```

**Причина:** проблемы при добавлении новых столбцов.

---

## 8. Работа со временем

### Время генерируется после запроса

Используйте **две зацепки**:

```python
def when_user_creates_entity(self):
    self.timestamp_before = timestamp_now()
    self.response = Api().create_entity(self.data)
    self.timestamp_after = timestamp_now()

def and_it_should_have_correct_created_at(self):
    created_at = self.response.body['created_at']
    assert datetime_timestamp_to_unix(created_at) == schema.int.min(
        self.timestamp_before
    ).max(
        self.timestamp_after
    )
```

### Время просто меняет формат

Проверяйте **неизменность**:

```python
def given_kafka_message(self):
    self.message = SomeSchema % {
        'payload': {
            'created_at': timestamp_now(),
        }
    }

def when_worker_imports_message(self):
    self.stdout, self.stderr = Cli().import_message(self.message)

def and_timestamp_should_be_preserved(self):
    imported = get_imported_entity()
    assert datetime_timestamp_to_unix(imported['created_at']) == \
        self.message['payload']['created_at']
```

---

## 9. Обработка логов воркеров

### Требования к воркерам

1. Логи в формате **JSON** (если возможно)
2. stdout и stderr направляются в **отдельный файл**
3. Декодирование байтов в **UTF-8**

### Разделение логов

| Поток | Содержимое |
|-------|-----------|
| **stderr** | Panic, Fatal, Error, Warning, не-JSON записи |
| **stdout** | Всё остальное |

### Стандартная проверка в контексте

```python
@vedro.context
def processed_messages_by_worker(**params) -> tuple[list, list]:
    stdout, stderr = Cli().worker_service(**params)
    assert stderr == schema.list.len(0), stderr  # Нет ошибок!
    return stdout, stderr
```

### Использование в тесте

```python
def when_worker_processes_messages(self):
    self.stdout, self.stderr = processed_messages_by_worker(
        topic=self.topic,
        batch_size=1
    )

def then_no_errors_in_stderr(self):
    assert self.stderr == schema.list.len(0)
```

### Если воркер логирует указатели

Проверяйте работу через **http/grpc ручки**:

```python
def and_entity_was_created(self):
    # Вместо проверки логов — проверяем через API
    response = Api().get_entity(self.entity_id)
    assert response.status_code == HTTPStatus.OK
```

---

## 10. Интерфейсы

### Docstring для интерфейсов

Описывайте **полноценный docstring**:

```python
class ReviewsApi:
    def get_reviews(
        self,
        entity_id: str,
        limit: int = 10,
        offset: int = 0,
    ) -> Response:
        """
        Получает список отзывов для сущности.
        
        :param entity_id: ID сущности
        :param limit: максимальное количество отзывов
        :param offset: смещение для пагинации
        :return: Response с телом ReviewsListSchema
        """
        pass
```

### CLI интерфейсы

```python
class ServiceCli:
    def import_reviews(
        self,
        topic: str,
        batch_size: int = 1,
        timeout: int = 30,
    ) -> tuple[list, list]:
        """
        Импортирует отзывы из Kafka топика.
        
        :param topic: название топика
        :param batch_size: размер батча
        :param timeout: таймаут ожидания в секундах
        :return: (stdout, stderr) — списки строк логов
        """
        pass
```

---

## Чек-лист для BE тестов

- [ ] Subject со строчной буквы
- [ ] Название отражает метод из when
- [ ] Негативные сценарии с `try to` или `do not/get no/get empty`
- [ ] Структура папок по методам
- [ ] HTTPStatus в контекстах, схемы в тестах
- [ ] Ошибки проверяются через schema.str.contains
- [ ] Новый топик для Kafka тестов
- [ ] Нет SELECT * в запросах к БД
- [ ] Воркеры с явным batch_size
- [ ] Проверка stderr воркеров на пустоту
- [ ] Прогон с `--repeats 30` перед MR

---

## Локальный прогон перед MR

```bash
# Прогнать новые тесты 30 раз для проверки стабильности
make e2e-run args="-vvv --repeats 30"
```
