# Спецификация: Единицы измерения (ЕИ)

## Обзор

Справочник «Единицы измерения» обеспечивает полный CRUD (просмотр, создание, редактирование, удаление) для единиц измерения в системе PSS.

## Иерархия сущностей PSS

```
apl_unit (#70) — базовая сущность
├── step_unit (#71) — единица STEP
│   ├── named_unit (#72) — именованная единица
│   │   ├── si_unit (#73) — единица СИ (prefix, name — перечисления)
│   │   ├── context_dependent_unit (#74) — контекстно-зависимая
│   │   └── conversion_based_unit (#75) — производная (conversion_factor)
│   └── derived_unit (#84) — составная единица
├── apl_descriptive_unit (#77) — описательная
├── apl_monetary_unit (#78) — денежная
├── apl_point_in_time_unit (#80) — момент времени
├── apl_enumeration_unit (#81) — перечислимая
├── apl_aggregation_unit (#82) — агрегированная
├── apl_table_unit (#509) — табличная
└── apl_reference_unit (#557) — ссылочная
```

## Атрибуты apl_unit

| Атрибут | Тип | Обяз. | Описание |
|---------|-----|-------|----------|
| id | identifier (STRING) | + | Обозначение |
| name | label (STRING) | + | Наименование |
| description | text (STRING) | + | Описание |
| code | code_type (STRING) | + | Код |
| GUID | STRING | — | Глобальный идентификатор |
| shown_id | label (STRING) | — | Отображаемый ID |
| name_eng | label (STRING) | — | Наименование (англ.) |

## REST API

### Эндпоинты

| Метод | URL | Описание | Параметры |
|-------|-----|----------|-----------|
| GET | `/api/references/units` | Список единиц | `limit` (int, по умолч. 100) |
| GET | `/api/references/units/<id>` | Детали единицы | `id` — sys_id |
| POST | `/api/references/units` | Создание | JSON: `{id, name, description, code, subtype}` |
| PUT | `/api/references/units/<id>` | Обновление | JSON: `{name, description, code, ...}` |
| DELETE | `/api/references/units/<id>` | Удаление | `id` — sys_id |

### Примеры запросов

**Список единиц:**
```http
GET /api/references/units?limit=50
→ {"units": [{"sys_id": 123, "id": "MM", "name": "Миллиметр", "description": "...", "code": "mm", "type": "si_unit"}, ...]}
```

**Создание SI единицы:**
```http
POST /api/references/units
Content-Type: application/json
{"id": "KG", "name": "Килограмм", "subtype": "si_unit"}
→ {"unit": {"sys_id": 456, "id": "KG", "name": "Килограмм", ...}}
```

**Обновление:**
```http
PUT /api/references/units/456
Content-Type: application/json
{"name": "Килограмм (обновлено)"}
→ {"unit": {"sys_id": 456, "name": "Килограмм (обновлено)", ...}}
```

**Удаление:**
```http
DELETE /api/references/units/456
→ {"message": "Unit deleted successfully"}
```

## Интерфейс

### Навигация

Справочники → Единицы измерения (📏) → таблица единиц

### Таблица единиц

| Колонка | Поле PSS | Описание |
|---------|----------|----------|
| ID | id | Обозначение единицы |
| Наименование | name | Название единицы |
| Описание | description | Описание |
| Код | code | Код единицы |
| Тип | type | Подтип сущности (si_unit, и т.д.) |
| Действия | — | Кнопки «Редактировать», «Удалить» |

### Формы

**Создание:**
- Обозначение (ID) — текстовое поле
- Наименование — обязательно
- Описание — текстовое поле
- Код — текстовое поле
- Тип единицы — выпадающий список (SI единица, Контекстно-зависимая, Производная, Описательная, Денежная)

**Редактирование:**
- Обозначение (ID) — заблокировано
- Остальные поля — редактируемые

**Удаление:**
- Диалог подтверждения с названием единицы

## MCP-инструменты

| Инструмент | Описание |
|------------|----------|
| `pdm_list_units` | Список единиц (существующий) |
| `pdm_get_unit` | Детали единицы по sys_id |
| `pdm_create_unit` | Создание единицы |
| `pdm_update_unit` | Обновление атрибутов |
| `pdm_delete_unit` | Удаление единицы |

## Тестирование

### API-тесты (`test_units_api.py`)
1. GET /api/references/units — список единиц
2. POST /api/references/units — создание тестовой единицы
3. GET /api/references/units/<id> — получение созданной
4. PUT /api/references/units/<id> — обновление
5. DELETE /api/references/units/<id> — удаление

### UI-тесты (`test_ui_scenarios.py`)
- T25: Просмотр списка единиц измерения
- T26: Создание единицы измерения
- T27: Редактирование единицы измерения
- T28: Удаление единицы измерения
