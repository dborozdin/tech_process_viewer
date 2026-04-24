# PSS-aiR — Product Data Management

## Назначение

Веб-клиент PDM (Product Data Management) для платформы ayatzk (PSS). Предоставляет трёхпанельный интерфейс для навигации по папкам, просмотра структуры изделий (BOM), техпроцессов, документов и генерации отчётов.

## Домен

**PDM (Product Data Management)** — управление конструкторскими и технологическими данными об изделиях:

- **Папки** — иерархическая организация объектов; папка может содержать другие папки, изделия, процессы, документы
- **Изделия (Products)** — версионируемые объекты с обозначением, наименованием, характеристиками и иерархической структурой входимости (BOM)
- **Структура изделия (BOM)** — дерево "из чего состоит": сборка → подсборки → детали, с количествами на каждом уровне
- **Характеристики** — расширяемый набор свойств изделия (property_definition)
- **Техпроцессы** — технологические процессы изготовления: процесс → фаза → операция, с нормами, материалами, документами
- **Документы** — прикрепляются к любым объектам через ссылки (document_reference)

## Техническая архитектура

### Стек
- **Backend**: Flask (Python), порт 5002
- **Frontend**: Vanilla JS SPA (один index.html, без сборки)
- **БД**: PSS REST API на порту 7239 (сервер приложений ayatzk)
- **Отчёты**: Jinja2-шаблоны с HTML-метаданными

### Структура
```
PSS-aiR/
├── CLAUDE.md                    # Этот файл
├── app.py                       # Flask app, подключение к БД, регистрация blueprints
├── __init__.py
├── services/                    # Бизнес-логика (все методы с @track_performance)
│   ├── folder_service.py        # Дерево папок, содержимое с типами
│   ├── product_service.py       # BOM по уровням (batch-запросы), характеристики
│   ├── document_service.py      # Документы для любых объектов
│   ├── process_service.py       # Техпроцессы (порт из app.py с оптимизацией)
│   └── report_service.py        # Фреймворк отчётов (авто-обнаружение шаблонов)
├── routes/                      # Тонкие Flask-маршруты → services
│   ├── folders.py               # /api/folders/*
│   ├── products.py              # /api/products/*
│   ├── documents.py             # /api/documents/*
│   ├── processes.py             # /api/processes/*
│   └── reports.py               # /api/reports/*
├── static/
│   └── index.html               # Vanilla JS SPA (трёхпанельный интерфейс)
└── reports/                     # Jinja2-шаблоны отчётов
    ├── README.md                # Инструкция: как добавить отчёт
    ├── bom_report.html          # Структура изделия
    └── process_report.html      # Структура техпроцессов
```

### Общий API-слой

PSS-aiR использует общие модули из `tech_process_viewer/api/`:
- `api/pss_api.py` — DatabaseAPI (подключение, CRUD, session management)
- `api/pss_folders_api.py` — операции с папками
- `api/pss_products_api.py` — операции с изделиями + поиск + характеристики
- `api/query_helpers.py` — `track_performance`, `query_apl`, `batch_query_by_ids`

### Паттерн подключения к БД

```python
# app.py хранит db_api в двух местах:
_db_api = None                    # глобальная переменная (для get_db_api())
app.config['db_api'] = _db_api   # Flask config (для routes через current_app)

# Routes получают db_api так:
db_api = current_app.config.get('db_api')
svc = ProductService(db_api) if db_api else None
```

## REST API

### Подключение
```
POST /api/connect         — подключение к БД (server_port, db, user, password)
POST /api/disconnect      — отключение
GET  /api/status          — проверка подключения
GET  /api/dblist?server=  — список доступных БД
```

### Папки
```
GET  /api/folders/tree               — дерево папок
GET  /api/folders/<id>/contents      — содержимое папки с типами
POST /api/folders                    — создание папки
```

### Изделия
```
GET  /api/products/<id>              — атрибуты + характеристики + документы
GET  /api/products/<id>/tree         — BOM-дерево (batch по уровням)
GET  /api/products/<id>/characteristics — характеристики
GET  /api/products/search?q=         — поиск по id/name
```

### Техпроцессы
```
GET  /api/processes/<product_id>     — список процессов для изделия
GET  /api/processes/<id>/hierarchy   — иерархия (процесс → фаза → операция)
GET  /api/processes/<id>/details     — полные детали (операции, документы, материалы)
```

### Документы
```
GET    /api/documents/<item_id>      — документы для объекта
POST   /api/documents/attach         — привязка документа (doc_id, item_id, item_type)
DELETE /api/documents/detach/<ref_id> — отвязка документа
GET    /api/documents/search?q=      — поиск документов
```

### Отчёты
```
GET  /api/reports                    — список доступных отчётов
GET  /api/reports/<name>?params      — рендеринг отчёта (HTML)
```

## PSS REST API (низкоуровневый)

Сервер: `http://localhost:7239/rest`

- `GET /rest/connect/{credentials}` — подключение, возвращает session_key
- `POST /rest/query` — выполнение APL-запроса (body = текст запроса)
- `GET /rest&size=N/load/t=e&ent=TYPE&all_attrs=true` — загрузка экземпляров
- `POST /rest/save` — создание/обновление/удаление (JSON payload)

### APL Query синтаксис
```
SELECT NO_CASE Ext_ FROM Ext_{entity_type} END_SELECT
SELECT NO_CASE Ext_ FROM Ext_{entity_type(.field = "value")} END_SELECT
SELECT NO_CASE Ext_ FROM Ext_{entity_type(.# = #123)} END_SELECT
SELECT NO_CASE Ext_ FROM Ext_{entity_type(.ref_field->other_entity.field = "value")} END_SELECT
```

## Ключевые PSS-сущности (PDM)

| Категория | Сущности | Описание |
|-----------|----------|----------|
| Папки | apl_folder, folder_version | Иерархическая организация объектов |
| Изделия | product_definition, product_definition_formation, product_version | Изделие, его формирование, версия |
| Структура | product_definition_usage, next_assembly_usage | Связи входимости (BOM) |
| Характеристики | apl_property_definition | Расширяемые свойства изделия |
| Документы | apl_document, apl_document_reference | Документ и привязка к объекту |
| Техпроцессы | apl_action, apl_action_method | Процесс/фаза/операция |
| Ресурсы | apl_resource, apl_action_resource | Материалы и нормы расхода |
| Организации | organization | Организации-исполнители |

## Метрики производительности

Все service-методы декорированы `@track_performance("operation_name")`:
- Считает **время выполнения** (секунды)
- Считает **количество запросов к БД** (thread-local счётчик)
- Логирует при `LOG_LEVEL=DEBUG`: `[PERF] get_product_tree: 0.234s, 5 DB queries`

По умолчанию `LOG_LEVEL=ERROR` (метрики не выводятся). В launch.json для debug: `"env": {"LOG_LEVEL": "DEBUG"}`.

### Оптимизация: batch-запросы

Вместо N+1 запросов (по одному на каждый элемент):
```python
# Плохо: N запросов
for doc_id in doc_ids:
    query_apl(f"SELECT ... Ext_{{#{doc_id}}} ...")

# Хорошо: 1 запрос через batch_query_by_ids()
results = batch_query_by_ids(api_instance, doc_ids)
```

BOM-дерево читается по уровням (BFS): ~max_depth запросов вместо N.

## Как добавить новый API-эндпоинт

1. Добавить метод в соответствующий сервис (`services/*.py`):
   - Декорировать `@track_performance("operation_name")`
   - Использовать `query_apl()` / `batch_query_by_ids()` для запросов
2. Добавить маршрут в `routes/*.py`:
   - Получить `db_api` из `current_app.config.get('db_api')`
   - Создать экземпляр сервиса, вызвать метод
3. Frontend: добавить метод в объект `API` в `index.html`

## Как добавить отчёт

См. [reports/README.md](reports/README.md). Кратко:

1. Создать Jinja2-шаблон в `reports/` с HTML-метаданными:
   ```html
   <!-- REPORT: Название отчёта -->
   <!-- DESCRIPTION: Описание -->
   <!-- PARAMS: param1 (type) - описание -->
   ```
2. Добавить обработчик данных в `report_service.py` → `get_report_data()`
3. Отчёт автоматически появится в списке `/api/reports`

## Запуск

```bash
cd tech_process_viewer
python PSS-aiR/app.py
# Открыть http://localhost:5002/
```

Или через VS Code: конфигурация "PSS-aiR (5002)".

## БД для экспериментов

- Сервер: `http://localhost:7239`
- База: `pss_moma_08_07_2025`
- Пользователь: `Administrator` (без пароля)

## Тестирование справочников

При добавлении API/UI для новых справочников PSS-aiR:

1. **API-тест**: создать `test_<name>_api.py` в папке `PSS-aiR/` по шаблону `test_units_api.py`
   - Отчёт: `<name>_report.html`
2. **UI-тест**: создать `test_<name>_ui.py` в папке `PSS-aiR/` по шаблону `test_units_ui.py`
   - Отчёт: `<name>_ui_report.html`
3. **Подключение к БД** всегда через `POST /api/connect` (параметры: `server_port`, `db`, `user`, `password`)
4. **Отключение** всегда через `POST /api/disconnect`
5. **LIKE в APL** не работает с кириллицей — фильтровать на Python-стороне
