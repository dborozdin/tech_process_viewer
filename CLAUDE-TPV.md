# Tech Process Viewer — просмотр технологических процессов

## Назначение

Основное приложение платформы для навигации по иерархии производственных процессов. Позволяет просматривать изделия (летательные аппараты), их бизнес-процессы, фазы, технологические процессы и операции с документами, материалами и характеристиками.

**Порт:** 5000  
**URL:** http://localhost:5000/

## Домен

**Tech Process Viewer** — обозреватель технологических процессов изготовления:

- **Изделия (Aircrafts)** — список изделий из папки "Aircrafts" в PSS
- **Бизнес-процессы** — процессы, привязанные к изделию (с организацией-исполнителем)
- **Фазы** — подпроцессы первого уровня внутри бизнес-процесса
- **Техпроцессы** — технологические процессы внутри фазы
- **Детали техпроцесса** — операции, документы, материалы и характеристики для конкретного техпроцесса

## Техническая архитектура

### Стек
- **Backend**: Flask (Python), порт 5000
- **Frontend**: Vanilla JS + jQuery, HTML-страницы в `static/templates/`
- **БД**: PSS REST API на порту 7239
- **API-слой**: общий пакет `api/` (`create_pss_app`, `DatabaseAPI`, `query_helpers`)

### Точка входа
```
tech_process_viewer_app.py
```

### Структура страниц

| URL | Шаблон | Назначение |
|-----|--------|------------|
| `/` | `static/templates/index.html` | Список изделий (aircraft) |
| `/processes` | `static/templates/processes.html` | Бизнес-процессы изделия |
| `/phases` | `static/templates/phases.html` | Фазы процесса |
| `/technical_processes` | `static/templates/tech-processes.html` | Техпроцессы фазы |
| `/technical_process_details` | `static/templates/technical_process_details.html` | Детали техпроцесса |

### JavaScript-модули (`static/js/`)

| Файл | Назначение |
|------|------------|
| `db-connection.js` | Общий модуль подключения к БД (используется всеми приложениями) |
| `common.js` | Хлебные крошки, навигация |
| `products.js` | Логика страницы изделий |
| `processes.js` | Логика страницы процессов |
| `phases.js` | Логика страницы фаз |
| `tech-processes.js` | Логика страницы техпроцессов |
| `technical_process_details.js` | Логика страницы деталей |
| `crud-ui.js` | CRUD-операции (создание/редактирование/удаление) |

## REST API

### Собственные эндпоинты (в `tech_process_viewer_app.py`)

```
GET  /api/aircraft                           — список изделий из папки "Aircrafts"
GET  /api/processes/<aircraft_id>            — бизнес-процессы изделия
GET  /api/phases/<process_id>               — фазы бизнес-процесса
GET  /api/technical_processes/<phase_id>     — техпроцессы фазы
GET  /api/technical_process_details/<id>     — полные детали техпроцесса (операции, документы, материалы, характеристики)
```

### Зарегистрированные Flask-Smorest blueprint'ы

- `auth` — `/api/connect`, `/api/disconnect`, `/api/status`
- `crud_routes` — CRUD-операции

## Бизнес-логика

Все функции загрузки данных декорированы `@track_performance` из `api/query_helpers.py`:

- `fetch_aircrafts_from_folder()` — загрузка изделий из папки "Aircrafts" (batch-запросы)
- `fetch_processes(aircraft_id)` — бизнес-процессы с исполнителями
- `fetch_phases_or_tp(process_id, element_type)` — рекурсивная загрузка подпроцессов
- `get_tp_details(tech_proc_id)` — полные детали: операции, документы, материалы, характеристики

### Оптимизация

Все запросы к PSS используют batch-загрузку (`batch_query_by_ids`) для предотвращения N+1 проблемы:
- PDF'ы из папки → одним запросом
- Изделия по ID → одним запросом
- Документы → одним запросом
- Типы документов → одним запросом
- Характеристики → одним запросом

## Использование общего API-слоя

```python
from tech_process_viewer.api.app_helpers import create_pss_app, get_api
from tech_process_viewer.api.query_helpers import query_apl, batch_query_by_ids, track_performance

app = create_pss_app(__name__, static_folder='static', template_folder='static/templates', port=5000)
```

## Запуск

```bash
cd tech_process_viewer
python tech_process_viewer_app.py
# Открыть http://localhost:5000/
```

### VS Code Debug

Конфигурация: **"Tech Process Viewer (5000)"**

```json
{
    "name": "Tech Process Viewer (5000)",
    "type": "debugpy",
    "program": "${workspaceFolder}/tech_process_viewer_app.py",
    "env": {
        "FLASK_ENV": "development",
        "LOG_LEVEL": "DEBUG"
    }
}
```

## Связь с другими приложениями

- **Общий API-слой** — использует `create_pss_app()`, `DatabaseAPI`, `query_helpers` из `api/`
- **Общие шаблоны** — делит `static/templates/` и `static/js/` с Entity Viewer и API Docs
- **API Docs** — регистрирует только `auth` и `crud_routes` blueprint'ы; полный набор — в API Docs на порту 5004
