# Code Style и Соглашения для Frontend (E2E UI) тестов

> Данный документ содержит соглашения, специфичные для **frontend** и **E2E UI** тестов на базе Playwright.
> 
> **Важно:** Перед прочтением ознакомьтесь с [CommonCodeStyles.md](CommonCodeStyles.md) — общими правилами для всех проектов.

---

## Содержание

1. [Именование в FE тестах](#1-именование-в-fe-тестах)
2. [Page Object](#2-page-object)
3. [Локаторы](#3-локаторы)
4. [Контексты для UI](#4-контексты-для-ui)
5. [Шаги тестов](#5-шаги-тестов)
6. [Скриншотные проверки](#6-скриншотные-проверки)
7. [Allure лейблы и теги](#7-allure-лейблы-и-теги)
8. [Работа с внешними ресурсами](#8-работа-с-внешними-ресурсами)
9. [Playwright специфика](#9-playwright-специфика)

---

## 1. Именование в FE тестах

### Subject с заглавной буквы

В FE тестах `subject` **пишется с заглавной буквы**:

```python
# ✅ FE тест
subject = "Open booking form as auth user"

# BE тест (для сравнения)
subject = "get all dashboards after add layer"
```

### Guest и User в названии шагов

Уточняйте тип пользователя:
- **`guest`** — неавторизованный пользователь
- **`user`** — авторизованный пользователь

```python
async def when_guest_opens_add_review_popup(self):
    await self.page.goto(self.url)

async def when_user_opens_add_review_popup(self):
    await self.page.goto(self.url)
```

### Формула названия файла

```
{action}_{object}_{condition}_by_{method}.py
```

**Компоненты:**
- `action` — бизнесовое действие (`open`, `close`, `click`, `show`)
- `object` — объект действия (`booking_form`, `thanks_popup`)
- `condition` — условия (`as_demo_user`, `with_error`)
- `by_{method}` — способ выполнения (`by_click_btn`, `by_press_esc`, `by_URL`)

### Примеры именования

```python
# close_thanks_popup_by_press_esc.py
subject = "Close thanks popup by press Esc"

async def when_guest_press_esc_to_close_popup(self):
    await self.page.keyboard.press('Escape')
```

```python
# close_thanks_popup_by_click_close_btn.py
subject = "Close thanks popup by click close btn"

async def when_guest_clicks_close_btn_in_popup(self):
    await self.close_btn.click()
```

### Когда указывать `by URL`

**Восстановление на страницу** = переход по прямой ссылке:

```python
# open_add_review_popup_by_URL.py
subject = "Open add review popup by URL"

async def when_guest_opens_add_review_popup(self):
    await self.page.goto(f"{self.region}/firm/{self.branch_id}/tab/reviews/addreview")
```

### Когда НЕ нужно `by ...`

Если бизнесовое действие **равно** фактическому:

```python
# click_similar_org_ads_banner.py — не click_...by_click
subject = "Click similar org ads banner"

async def when_guest_clicks_similar_org_ads_banner(self):
    await self.banner.click()
```

---

## 2. Page Object

### Структура директории

```
interfaces/web/pages/
├── booking/
│   ├── booking_page.py
│   └── my_booking_page.py
├── error_message/
│   ├── error_page.py
│   └── not_found.py
├── hotel/
│   └── hotel_page.py
├── page.py              # Базовый класс OtelloPage
└── __init__.py
```

**Правило:** Каждый фрейм/страница в отдельной папке.

❌ **Плохо**
```
pages/
├── error_page.py
├── booking_page.py
├── not_found.py
└── my_booking_page.py
```

### Базовый класс страницы

Общие элементы выносятся в `OtelloPage`:

```python
class OtelloPage(BasePage):
    """Базовый класс для всех страниц Otello"""
    
    @property
    def mobile_header(self):
        return MobileHeader(self, data_n='wat-mobile-header')
    
    @property
    def sidebar(self):
        return Sidebar(self, data_n='wat-sidebar')
```

### Описание элементов как property

```python
class ProfilePage(OtelloPage):
    LOCATOR_NAME = 'wat-profile'

    @property
    def avatar(self):
        return BaseImage(self, data_n='wat-default-avatar')
    
    @property
    def edit_button(self):
        return BaseButton(self, data_n='wat-edit-profile-btn')
```

### Вложенные элементы

Дочерние элементы описываем **внутри класса родителя**:

✅ **Хорошо**
```python
class RoomMinicard(BaseElement):
    LOCATOR_NAME = 'wat-hotel-info'

    @property
    def title(self):
        return BaseText(self, data_n='wat-minicard-body')

    @property
    def photo(self):
        return BaseImage(self, data_n='wat-minicard-photo')


class HotelPage(OtelloPage):
    LOCATOR = '/hotel'

    @property
    def minicard(self):
        return RoomMinicard(self)
```

❌ **Плохо**
```python
# Все элементы на одном уровне — нарушена иерархия
class HotelPage(OtelloPage):
    @property
    def minicard(self):
        return RoomMinicard(self)

    @property
    def minicard_body(self):  # Должен быть внутри RoomMinicard!
        return MinicardBody(self)

    @property
    def minicard_photo(self):  # Должен быть внутри RoomMinicard!
        return MinicardPhoto(self)
```

### Уровни вложенности

**Один уровень** — определение внутри родительского класса:

```python
class ParentElement:
    @property
    def child1(self):
        return BaseElement(self, data_n='wat-child1')

    @property
    def child2(self):
        return BaseElement(self, data_n='wat-child-2')
```

**Больше одного уровня** — выносим в отдельный файл:

```python
# amenities.py
class AmenityItem(BaseElement):
    LOCATOR_NAME = 'wat-amenity-item'

    @property
    def icon(self):
        return BaseImage(self, data_n='wat-amenity-icon')


class Amenities(BaseElement):
    LOCATOR_NAME = 'wat-amenities-container'

    @property
    def item(self):
        return AmenityItem(self)
```

### Правила нейминга классов

Включайте **тип элемента** в суффикс:
- `Section` — большие верхнеуровневые блоки
- `Block`, `Card`, `Banner`, `Widget` — внутри секций
- `Modal` — модальные окна (не `Popup`!)

```python
# ✅ Хорошо
class HotelInfoSection(BaseElement):
    LOCATOR_NAME = 'wat-hotel-info-section'

class SupportWidget(BaseElement):
    LOCATOR_NAME = 'wat-support-widget'

class GuestsModal(BaseModal):  # Не GuestsPopup!
    LOCATOR_NAME = 'wat-modal'
```

### Комментарии для описания элементов

```python
# Секция, которая содержит основную информацию и фото отеля
class HotelInfoSection(BaseElement):
    LOCATOR_NAME = 'wat-hotel-info-section'
    ...
```

---

## 3. Локаторы

### Формат локаторов

```python
# В компоненте
<Text locatorName='wat-title-text'>

# В Page Object
return BaseText(self, data_n='wat-title-text')
```

### Импорт локаторов

```javascript
// ✅ Хорошо
import { locator } from 'shared/lib/dx'

// ❌ Плохо
import { locator } from '../../../lib/dx'
```

### НЕ привязывайте к странице

Для шаренных элементов **не используйте** название страницы:

❌ **Плохо**: `wat-profile-back-button`
✅ **Хорошо**: `wat-back-button`

### Типы элементов в локаторах

Локаторы должны содержать **тип элемента**:

```python
# ✅ Хорошо
LOCATOR_NAME = 'wat-hotel-info-section'
LOCATOR_NAME = 'wat-support-widget'

# ❌ Плохо
LOCATOR_NAME = 'wat-hotel-info'
LOCATOR_NAME = 'wat-support'
```

**Исключение** — текстовые элементы могут использовать суффиксы контента:
```python
# ✅ Допустимо для текста
data_n='wat-accommodation-info'
data_n='wat-error-message'
data_n='wat-page-title'
```

### Локаторы для скелетонов

```javascript
// Скелетон (загрузка)
<SectionSkeleton 
  skeletonLocatorName="wat-reviews-block" 
  locatorState="loading" 
/>

// Загруженный блок
<Section 
  locatorName="wat-reviews-block" 
  locatorState="loaded" 
/>
```

**Правило:** Локатор одинаковый, различаются `data-s`:
- `data-s='loading'` — скелетон
- `data-s='loaded'` — загруженный контент

### Не описывайте лишние локаторы

Локаторы, которые **не нужны для тестов здесь и сейчас**, не описываем — они засоряют код и не поддерживаются.

---

## 4. Контексты для UI

### Структура контекстов

Файлы контекстов располагаются в `contexts/`:
```
contexts/
├── hotel/
├── profile/
├── booking/
├── sber_loyalty/
└── __init__.py
```

### Гарантирующие assert-ы

❌ **Плохо** — нет гарантии состояния
```python
@vedro.context
async def opened_edit_profile_page(user: dict) -> EditProfilePage:
    page = await opened_profile_page(user)
    await page.edit_profile_button.tap()
    page = page.as_page(EditProfilePage)
    assert await page.is_visible()  # Недостаточно!
    return page
```

✅ **Хорошо** — проверяем конкретный элемент
```python
@vedro.context
async def opened_edit_profile_page(user: dict) -> EditProfilePage:
    page = await opened_profile_page(user)
    await page.edit_profile_button.tap()
    page = page.as_page(EditProfilePage)
    assert await page.form.is_visible()  # Конкретный элемент формы
    return page
```

### Проверка моков в контекстах

```python
@vedro.context
async def opened_search_page(items: list, markers: list) -> SearchPage:
    async with mocked_search_markers(items=items) as markers_mock:
        page = await opened_page(SearchPage, url, platform=Platforms.DESKTOP)
    
    assert await page.header.is_visible()
    assert await page.map.wait_for_loading()
    
    # Проверяем запросы в мок
    assert markers_mock.history == SearchMarkersHistorySchema.len(1)
    assert markers_mock.history[0]['request'] == SearchMarkersRequestSchema
    
    return page
```

### НЕ проверяйте видимость перед действиями

Методы Playwright (`tap()`, `click()`, `fill()`) **сами проверяют видимость**.

❌ **Плохо**
```python
@vedro.context
async def opened_delete_booking_modal(page: MyBookingPage):
    assert await page.delete_button.is_visible()  # Избыточно!
    await page.delete_button.tap()
    assert await page.delete_modal.is_visible()
```

✅ **Хорошо**
```python
@vedro.context
async def opened_delete_booking_modal(page: MyBookingPage):
    await page.delete_button.tap()  # tap() сам дождётся видимости
    assert await page.delete_modal.is_visible()
```

---

## 5. Шаги тестов

### Подготовка данных ближе к использованию

```python
def given_user_data_prepared(self):
    self.user_input_data = fake(UserInputSchema)

def given_backend_response_prepared(self):
    self.backend_items = fake(BackendResponseSchema)

async def when_submit_form(self):
    async with mocked_backend(self.backend_items):
        await self.page.form.submit(self.user_input_data)
```

### НЕ выносите моки из контекстов наружу

❌ **Плохо**
```python
async def given_restored_on_asset_page(self):
    async with mocked_rubricator([]) as self.rubricator_mock:
        self.app = await restored_on_asset_page(
            asset=self.asset,
            filters=self.filters,
        )
```

✅ **Хорошо** — мок внутри контекста
```python
async def given_restored_on_asset_page(self):
    # mocked_rubricator внутри restored_on_asset_page
    self.app = await restored_on_asset_page(
        asset=self.asset,
        filters=self.filters,
    )
```

### Проверки в then/and

**Порядок проверок:**
1. Быстрые — история моков, параметры запросов
2. Медленные — UI элементы

```python
def then_request_params_correct(self):
    assert self.mock.history[0]['request'].body == expected

async def and_ui_element_visible(self):
    assert await self.page.element.is_visible()
```

### Объединение и разделение проверок

**Объединяйте** если относятся к одному элементу:
```python
async def and_color_settings_displayed(self):
    assert await self.widget.color_settings.is_visible()
    assert await self.widget.color_settings.line_color.is_visible()
    assert await self.widget.color_settings.opacity.is_visible()
```

**Разделяйте** если:
- Относятся к разным частям интерфейса
- Требуют разной логики (ретраи vs без ретраев)

```python
async def and_line_visualization_button_displayed(self):
    assert await self.widget.general_settings.line_btn.is_visible()

@retry_default
async def and_settings_count_correct(self):
    assert len(await self.widget.settings_sections.get()) == 2
```

---

## 6. Скриншотные проверки

### Добавление скриншотного теста

1. Добавить лейбл `SCREENSHOTS`
2. Вызвать `make_screenshot_for_comparison()`

```python
@allure_labels(SCREENSHOTS, Feature.HOTEL, Story.HOTEL_CARD, Priority.P1)
class Scenario(vedro.Scenario):
    subject = "Open hotel card with amenities"

    async def then_hotel_card_displayed_correctly(self):
        await self.page.make_screenshot_for_comparison()
```

### Какой скриншот делать

| Тип | Когда использовать |
|-----|-------------------|
| **Экран** | Новый компонент, проверка расположения относительно других элементов |
| **Контейнер** | Опасаемся нестабильностей на странице, но важно видеть соседей |
| **Элемент** | Уже есть скриншот элемента со страницей в другом месте |

### Правила оформления

1. Скриншоты в шагах `then_/and_`
2. **Разные шаги** для разных скриншотов (иначе перезапись)
3. Перед скриншотом — `is_visible()` для прогрузки
4. Скриншот **перед** функциональными проверками

```python
async def then_page_screenshot(self):
    assert await self.page.content.is_visible()  # Дождаться прогрузки
    await self.page.make_screenshot_for_comparison()

async def and_content_is_correct(self):
    assert await self.page.content.text == expected
```

### Параметры скриншота

```python
# Фокус на элемент
await self.page.make_screenshot_for_comparison(
    focus_on=self.page.payment.discounts.locator
)

# Маска для игнорирования элементов
await self.page.make_screenshot_for_comparison(
    focus_on=self.page.similar_hotels.locator,
    mask=[self.page.similar_hotels.photo.locator]
)

# С анимацией
await self.page.make_screenshot_for_comparison(
    disable_animation=False
)
```

---

## 7. Allure лейблы и теги

### Обязательные лейблы

Каждый тест **должен** иметь:
- `Feature` (может быть несколько)
- `Story` (один)
- `Priority` (один)
- `Platform` (Desktop/Mobile)

```python
@allure_labels(
    Feature.HOTEL.ROOM_AMENITIES,
    Story.HOTEL_CARD,
    Priority.P0,
    Platform.DESKTOP
)
class Scenario(vedro.Scenario):
    ...
```

### Мануальные тесты

```python
@allure_labels(MANUAL, Feature.HOTEL.AMENITIES, Story.HOTEL_CARD, Priority.P1)
```

### Закрепление Allure ID

При изменении пути/имени файла — закрепите ID:

**Непараметризованный тест:**
```python
@allure_labels(Feature.BOOKING.FORM, Story.BOOKING, Priority.P0, AllureID('107830'))
```

**Параметризованный тест:**
```python
@allure_labels(Feature.BOOKING.FORM, Story.BOOKING, Priority.P0)
class Scenario(vedro.Scenario):
    subject = 'Open hotel card with {stars} stars'

    @params[allure_labels(AllureID('107831'))](5.0)
    @params[allure_labels(AllureID('107832'))](4.5)
    def __init__(self, stars):
        self.stars = stars
```

### Платформа в параметризованных тестах

```python
@allure_labels(Feature.BOOKING.FORM, Story.BOOKING, Priority.P0)
class Scenario(vedro.Scenario):
    subject = 'Open booking form ({platform})'

    @params(Platforms.MOBILE)
    @params(Platforms.DESKTOP)
    def __init__(self, platform):
        self.platform = platform
```

---

## 8. Работа с внешними ресурсами

### НЕ тестируйте переходы tap-ом

Если кнопка ведёт на **внешний ресурс** — проверяйте атрибуты, а не кликайте:

```python
async def then_link_has_correct_href(self):
    href = await self.page.external_link.get_attribute('href')
    assert href == "https://external-site.com/path"

async def and_link_opens_in_new_tab(self):
    target = await self.page.external_link.get_attribute('target')
    assert target == "_blank"
```

**Правило НЕ распространяется** на переходы между внутренними страницами.

---

## 9. Playwright специфика

### Actionability

Методы Playwright автоматически проверяют:
- `tap()` — видимость, enabled
- `click()` — видимость, enabled
- `fill()` — видимость, enabled, editable
- `text_content()` — видимость

[Документация Playwright](https://playwright.dev/python/docs/actionability)

### Ожидания

```python
# ✅ Хорошо — используем встроенные ожидания
await self.page.button.click()  # Сам дождётся

# ❌ Плохо — явное ожидание перед действием
await self.page.button.wait_for(state='visible')
await self.page.button.click()
```

### Матчеры

```python
from interfaces.ui.expect import expect

async def then_element_visible(self):
    assert await expect(self.page.element).to_be_visible()
    assert await expect(self.page.items).to_have_count(10)
```

Используйте как есть:
- `match_text`
- `match_url`
- `match_erid`

---

## Чек-лист для FE тестов

- [ ] Subject с заглавной буквы
- [ ] Указан guest/user в шагах
- [ ] Page Object структурирован по папкам
- [ ] Локаторы не привязаны к странице
- [ ] Типы элементов в названиях классов и локаторах
- [ ] Нет избыточных проверок видимости
- [ ] Скриншоты в отдельных шагах
- [ ] Все обязательные Allure лейблы указаны
- [ ] Внешние ссылки проверяются по атрибутам
