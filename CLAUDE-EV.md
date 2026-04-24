# Entity Viewer — универсальный просмотрщик сущностей PSS

## Назначение

Универсальный браузер сущностей базы данных PSS. Позволяет просматривать, создавать, редактировать и удалять экземпляры любых типов сущностей, зарегистрированных в схеме данных. Включает встроенный API test runner для проверки CRUD-операций.

**Порт:** 5003  
**URL:** http://localhost:5003/

## Домен

**Entity Viewer** — инструмент администратора/разработчика для работы с БД PSS:

- **Просмотр типов сущностей** — список всех entity types с количеством экземпляров и фильтрацией
- **Схема сущности** — атрибуты, супертип, подтипы, связи
- **Просмотр экземпляров** — постраничный список с серверным offset
- **CRUD** — создание, редактирование, удаление экземпляров
- **API Test Runner** — автоматический прогон CRUD-операций для любого типа сущности

## Техническая архитектура

### Стек
- **Backend**: Flask (Python), порт 5003
- **Frontend**: Bootstrap + Vanilla JS
- **БД**: PSS REST API на порту 7239
- **API-слой**: общий пакет `api/` с Flask-Smorest blueprint'ами

### Точка входа
```
entity_viewer_app.py
```

### Структура страниц

| URL | Шаблон | Назначение |
|-----|--------|------------|
| `/` или `/entity-viewer` | `static/templates/entity_viewer/index.html` | Браузер типов сущностей (Bootstrap cards) |
| `/entity-viewer/entity/<name>` | `static/templates/entity_viewer/instances.html` | Список экземпляров типа |
| `/entity-viewer/instance/<id>` | `static/templates/entity_viewer/instance_detail.html` | Детали/редактирование экземпляра |

### Ключевые зависимости

- `dict_parser.py` — парсер словаря данных PSS (`.dict` файл) для получения схем сущностей
- `api/routes/entity_viewer.py` — Flask-Smorest blueprint с REST API

## REST API (через Flask-Smorest)

Blueprint `entity_viewer` зарегистрирован через Flask-Smorest — все эндпоинты доступны с префиксом `/api/v1/entity-viewer/` и документированы в OpenAPI.

```
GET    /api/v1/entity-viewer/entity-types        — список типов сущностей с количеством экземпляров
GET    /api/v1/entity-viewer/entity-types/<name>  — схема сущности (атрибуты, супертип, подтипы)
GET    /api/v1/entity-viewer/entity/<name>/instances — экземпляры (с пагинацией: ?offset=&limit=)
POST   /api/v1/entity-viewer/entity/<name>/instances — создать экземпляр
GET    /api/v1/entity-viewer/instances/<id>       — получить экземпляр по sys_id
PUT    /api/v1/entity-viewer/instances/<id>       — обновить экземпляр
DELETE /api/v1/entity-viewer/instances/<id>       — удалить экземпляр
```

Дополнительно зарегистрирован blueprint `auth`:
```
POST /api/connect        — подключение к БД
POST /api/disconnect     — отключение
GET  /api/status         — статус подключения
```

## Бизнес-логика

- **Схемы** загружаются через `dict_parser.get_dict_parser()` — парсит `doc/apl_pss_a.dict`
- **Экземпляры** запрашиваются через PSS REST API: `GET /rest&size=N&start=M/load/t=e&ent=TYPE&all_attrs=true`
- **CRUD** через `POST /rest/save` с JSON-payload
- **Пагинация** — серверная, с offset и limit

## Использование общего API-слоя

```python
from tech_process_viewer.api.app_helpers import create_pss_app

app = create_pss_app(__name__, static_folder='static', template_folder='static/templates', port=5003)
```

## Запуск

```bash
cd tech_process_viewer
python entity_viewer_app.py
# Открыть http://localhost:5003/
```

### VS Code Debug

Конфигурация: **"Entity Viewer (5003)"**

```json
{
    "name": "Entity Viewer (5003)",
    "type": "debugpy",
    "program": "${workspaceFolder}/entity_viewer_app.py",
    "env": {
        "FLASK_ENV": "development",
        "LOG_LEVEL": "DEBUG"
    }
}
```

## Связь с другими приложениями

- **Общий API-слой** — использует `create_pss_app()`, `dict_parser.py`
- **Общие шаблоны** — делит `static/templates/` и `static/js/db-connection.js` с Tech Process Viewer и API Docs
- **API Docs** — полная OpenAPI-документация entity_viewer blueprint'а доступна на порту 5004
- **MCP Server** — schema-инструменты MCP используют те же данные словаря, что и Entity Viewer
