# API Docs / Swagger — документация OpenAPI для платформы PSS

## Назначение

Централизованный хаб OpenAPI-документации для всех REST API платформы. Предоставляет Swagger UI с встроенным test runner плагином, ReDoc-документацию и экспорт OpenAPI-спецификации в JSON/YAML.

**Порт:** 5004  
**Swagger UI:** http://localhost:5004/api/docs  
**ReDoc:** http://localhost:5004/api/redoc  
**OpenAPI JSON:** http://localhost:5004/api/openapi.json

## Домен

**API Docs** — агрегатор документации всех REST API проекта:

- **Swagger UI** — интерактивная документация с возможностью выполнения запросов
- **Test Runner Plugin** — кастомный JS-плагин для Swagger UI, позволяющий запускать тестовые сценарии прямо из интерфейса
- **ReDoc** — альтернативный рендерер документации
- **OpenAPI Spec Export** — автоматический экспорт `openapi.json` и `openapi.yaml` в папку `openapi/`

## Техническая архитектура

### Стек
- **Backend**: Flask (Python), порт 5004
- **API Documentation**: flask-smorest (автогенерация OpenAPI из Blueprint'ов и Marshmallow-схем)
- **Frontend**: Swagger UI (CDN) + кастомный плагин TestRunner

### Точка входа
```
api_docs_app.py
```

## Зарегистрированные Blueprint'ы

Это приложение регистрирует **все** REST API blueprint'ы проекта — это самый полный набор эндпоинтов:

| Blueprint | Префикс | Назначение |
|-----------|---------|------------|
| `auth` | `/api` | Подключение/отключение/статус |
| `business_processes` | `/api/v1/business-processes` | CRUD бизнес-процессов |
| `entity_viewer` | `/api/v1/entity-viewer` | Браузер сущностей |
| `products` | `/api/v1/products` | CRUD изделий |
| `documents` | `/api/v1/documents` | CRUD документов |
| `resources` | `/api/v1/resources` | CRUD ресурсов |
| `organizations` | `/api/v1/organizations` | CRUD организаций |
| `characteristics` | `/api/v1/characteristics` | CRUD характеристик |
| `test_runner` | `/api/v1/test-runner` | API test runner |

## Кастомный Swagger UI

Приложение переопределяет стандартный Swagger UI от flask-smorest для добавления плагина TestRunner:

```python
# Переопределение view-функции 'openapi_swagger_ui'
# Внедрение кастомного HTML с window.TestRunnerPlugin
```

### Test Runner Plugin

- **Файл:** `static/test_runner_plugin.js`
- **Функции:** добавляет панель "Test Runner" в Swagger UI для запуска тестовых сценариев без написания кода
- **Streaming:** эндпоинт `/api/v1/test-runner/run-stream` возвращает NDJSON-поток с live-результатами тестов

## Экспорт OpenAPI Spec

В режиме `DEBUG=True` приложение автоматически экспортирует OpenAPI-спецификацию после каждого запроса:

```
openapi/
├── openapi.json    — JSON-спецификация
└── openapi.yaml    — YAML-спецификация (если установлен PyYAML)
```

## Использование общего API-слоя

```python
from tech_process_viewer.api.app_helpers import create_pss_app

app = create_pss_app(__name__, static_folder='static', template_folder='static/templates', port=5004)
```

## Запуск

```bash
cd tech_process_viewer
python api_docs_app.py
# Swagger UI: http://localhost:5004/api/docs
# ReDoc:      http://localhost:5004/api/redoc
```

### VS Code Debug

Конфигурация: **"API Docs / Swagger (5004)"**

```json
{
    "name": "API Docs / Swagger (5004)",
    "type": "debugpy",
    "program": "${workspaceFolder}/api_docs_app.py",
    "env": {
        "FLASK_ENV": "development",
        "LOG_LEVEL": "DEBUG"
    }
}
```

## Связь с другими приложениями

- **Все приложения** — API Docs агрегирует документацию всех blueprint'ов из `api/routes/`
- **Entity Viewer** — entity_viewer blueprint используется и здесь, и на порту 5003
- **Tech Process Viewer** — разделяет `static/` и `static/js/db-connection.js`
- **PSS-aiR** — имеет свой независимый API (не flask-smorest), не включён в эту документацию
