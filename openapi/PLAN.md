# PSS API — план объединения и Try-all UI (2026-04-20)

> Этот файл специально вынесен на диск, чтобы пережить compact и продолжить работу даже после сжатия контекста. Не удалять до завершения всех этапов.

## Контекст

В проекте сейчас **два параллельных REST API** для одних и тех же сущностей:

| Префикс | Файлы | Стиль | Видны в OpenAPI |
|---|---|---|---|
| `/api/{object}` | [api/routes/crud_routes.py](../api/routes/crud_routes.py) — 25 CRUD endpoints (создан в текущей сессии) | plain Flask Blueprint | ✅ через ручной [api/openapi_crud_paths.py](../api/openapi_crud_paths.py) (monkey-patch `to_dict()`) |
| `/api/v1/{object}` | [api/routes/products.py](../api/routes/products.py), `business_processes.py`, `documents.py`, `resources.py`, `organizations.py`, `entity_viewer.py`, `auth.py` (~30 endpoints) | flask-smorest + Marshmallow | ✅ автоматически |

Marshmallow-схемы лежат в [api/schemas/](../api/schemas/) (`product_schemas.py`, `bp_schemas.py`, `document_schemas.py`, `resource_schemas.py`, `common_schemas.py`). Большинство уже подходит для CRUD — нужно только дописать характеристики.

UI: [api_docs_app.py](../api_docs_app.py) на порту 5004 → `/api/docs` (Swagger UI), `/api/redoc`, `/api/openapi.json`.

Тестовый раннер: [test_api_swagger.py](../test_api_swagger.py) — Playwright + page.evaluate(fetch). 25 сценариев T01–T25, видео `api_test_video.webm`, отчёт `api_test_results.html`. На текущий момент 25/25 PASS.

## Цели

1. **Унифицировать API**: один префикс `/api/v1/`, авто-OpenAPI, использование схем из `api/schemas/`. Удалить `crud_routes.py` и `openapi_crud_paths.py`.
2. **Try-all UI** в Swagger: в каждой группе (tag-блоке) добавить кнопку «Run all», под группой — спойлер с таблицей результатов. История сохраняется в `openapi/test_API_results_<group>.json`.
3. **Конфиг** в `openapi/test_API_settings.json`: тестовая БД + сервер приложений + тестовые данные на каждую группу.

## Последовательность работ

### Этап 0 — pre-commit cleanup (СНАЧАЛА)

- [ ] **Обновить `.gitignore`**: убедиться что `__pycache__/` и `*.pyc` есть (они есть, но проверить что не tracked).
- [ ] **`git rm --cached`** любые tracked .pyc/`__pycache__` (если найдутся).
- [ ] **Commit** новых артефактов из этой сессии:
  - `api_test_video.webm` (5.5 MB)
  - `api_test_results.html`
  - `test_api_swagger.py`
  - `api/openapi_crud_paths.py`
  - `api_docs_app.py` (изменения)
  - **НЕ** коммитить `.claude/scheduled_tasks.lock`
  - Сообщение: «API Docs (5004): описание 25 CRUD endpoints в OpenAPI + Playwright runner 25/25 PASS»

### Этап 1 — объединение API

#### 1.1 Дополнить схемы

- [ ] Создать [api/schemas/characteristic_schemas.py](../api/schemas/characteristic_schemas.py):
  - `CharacteristicSchema` (sys_id, name, description, id)
  - `CharacteristicListResponseSchema`
  - `CharacteristicValueSchema` (sys_id, characteristic_name, characteristic_id, value, scope, subtype, unit)
  - `CharacteristicValueCreateSchema` (item_id, characteristic_id, value, subtype, item_type)
  - `CharacteristicValueUpdateSchema` (value, subtype)
  - `CharacteristicValueListResponseSchema`
  - `CharacteristicValueResponseSchema` (success, message, data{sys_id})

#### 1.2 Перенести CRUD-handlers в Smorest blueprints

| Из crud_routes.py | В Smorest blueprint | Новый путь (под /api/v1/) |
|---|---|---|
| POST `/api/products` | products.py | POST `/api/v1/products/` |
| PUT `/api/products/{pdf_id}` | products.py | PUT `/api/v1/products/{pdf_id}` |
| DELETE `/api/products/{pdf_id}` | products.py | DELETE `/api/v1/products/{pdf_id}` |
| POST `/api/products/bom` | products.py | POST `/api/v1/products/bom` |
| DELETE `/api/products/bom/{bom_id}` | products.py | DELETE `/api/v1/products/bom/{bom_id}` |
| GET `/api/products/{pdf_id}/bom` | products.py | GET `/api/v1/products/{pdf_id}/bom` |
| POST `/api/business-processes` | business_processes.py | POST `/api/v1/business-processes/` |
| PUT `/api/business-processes/{bp_id}` | business_processes.py | PUT `/api/v1/business-processes/{bp_id}` |
| DELETE `/api/business-processes/{bp_id}` | business_processes.py | DELETE `/api/v1/business-processes/{bp_id}` |
| POST `/api/business-processes/{bp_id}/elements` | business_processes.py | POST `/api/v1/business-processes/{bp_id}/elements` |
| DELETE `/api/business-processes/{bp_id}/elements/{child_id}` | business_processes.py | DELETE `/api/v1/business-processes/{bp_id}/elements/{child_id}` |
| POST `/api/business-processes/{bp_id}/link-product` | business_processes.py | POST `/api/v1/business-processes/{bp_id}/link-product` |
| POST `/api/documents/upload` | documents.py | POST `/api/v1/documents/upload` |
| POST `/api/document-references` | documents.py | POST `/api/v1/documents/references` |
| DELETE `/api/document-references/{ref_id}` | documents.py | DELETE `/api/v1/documents/references/{ref_id}` |
| GET `/api/documents/search` | documents.py | GET `/api/v1/documents/search` |
| GET `/api/characteristics` | НОВЫЙ characteristics.py | GET `/api/v1/characteristics/` |
| GET `/api/characteristics/values/{item_id}` | characteristics.py | GET `/api/v1/characteristics/values/{item_id}` |
| POST `/api/characteristics/values` | characteristics.py | POST `/api/v1/characteristics/values` |
| PUT `/api/characteristics/values/{value_id}` | characteristics.py | PUT `/api/v1/characteristics/values/{value_id}` |
| DELETE `/api/characteristics/values/{value_id}` | characteristics.py | DELETE `/api/v1/characteristics/values/{value_id}` |
| POST `/api/resources` | resources.py | POST `/api/v1/resources/` |
| PUT `/api/resources/{resource_id}` | resources.py | PUT `/api/v1/resources/{resource_id}` |
| DELETE `/api/resources/{resource_id}` | resources.py | DELETE `/api/v1/resources/{resource_id}` |
| GET `/api/resource-types` | resources.py | GET `/api/v1/resources/types` |

- [ ] Каждый — через `MethodView` + `@blp.arguments(...)` + `@blp.response(...)` + `@blp.alt_response(401/500, ErrorSchema)`. Описание в `@blp.doc()`.
- [ ] Делегировать на те же `api.products_api.create_product(...)` / etc.

#### 1.3 Подключить characteristics blueprint

- [ ] Создать [api/routes/characteristics.py](../api/routes/characteristics.py).
- [ ] Зарегистрировать в [api_docs_app.py](../api_docs_app.py): `api.register_blueprint(characteristics_blp)`.

#### 1.4 Удалить старое

- [ ] `git rm api/routes/crud_routes.py`
- [ ] `git rm api/openapi_crud_paths.py`
- [ ] Из [api_docs_app.py](../api_docs_app.py) убрать импорт `crud_routes` и вызов `register_crud_paths`.

#### 1.5 Обновить тест-раннер

- [ ] [test_api_swagger.py](../test_api_swagger.py): пути `/api/...` → `/api/v1/...` (кроме `/api/connect`, `/api/disconnect`, `/api/status`, `/api/dblist` — они в auth blueprint и остаются на /api/).
- [ ] Прогнать, должно быть 25/25 PASS.
- [ ] Перезаписать видео `api_test_video.webm` и `api_test_results.html`.

#### 1.6 Commit Этапа 1

- Сообщение: «API merge: 25 CRUD endpoints перенесены из crud_routes.py в /api/v1/ Smorest. test_api_swagger 25/25 PASS на новых путях.»

### Этап 2 — Try-all UI

#### 2.1 Конфиг

- [ ] [openapi/test_API_settings.json](test_API_settings.json):
```json
{
  "db": {
    "server_port": "http://localhost:7239",
    "db": "pss_moma_08_07_2025",
    "user": "Administrator",
    "password": ""
  },
  "groups": {
    "CRUD: Products": {
      "scenarios": [
        {"id": "create_assembly", "method": "POST", "path": "/api/v1/products/",
         "body": {"id": "RUNNER-ASSY", "name": "RunnerAssy"}, "save_as": "assy_pdf"},
        {"id": "create_component", "method": "POST", "path": "/api/v1/products/",
         "body": {"id": "RUNNER-COMP", "name": "RunnerComp"}, "save_as": "comp_pdf"},
        {"id": "update_assembly", "method": "PUT", "path": "/api/v1/products/{assy_pdf}",
         "body": {"name": "RunnerAssyEdited"}},
        {"id": "delete_assembly", "method": "DELETE", "path": "/api/v1/products/{assy_pdf}"}
      ]
    }
    /* и так для каждой группы */
  }
}
```

#### 2.2 Server endpoints

Новый Smorest blueprint `api/routes/test_runner.py`:

- `POST /api/v1/test-runner/run` — body: `{"group": "CRUD: Products"}`. Запускает все scenarios группы по очереди (с pre-step connect к БД). Возвращает JSON-отчёт. Сохраняет в `openapi/test_API_results_<safe_group>.json`.
- `POST /api/v1/test-runner/run-all` — все группы.
- `GET /api/v1/test-runner/history?group=...` — последний JSON-отчёт.

JSON-отчёт:
```json
{
  "group": "CRUD: Products",
  "started_at": "...", "finished_at": "...",
  "summary": {"total": 4, "passed": 4, "failed": 0},
  "results": [
    {"scenario": "create_assembly", "method": "POST", "path": "/api/v1/products/",
     "status": "PASS", "duration_ms": 1234, "http_status": 201,
     "response_preview": {"data":{"pdf_id":815959}}},
    ...
  ]
}
```

#### 2.3 Swagger UI plugin

- [ ] [static/test_runner_plugin.js](../static/test_runner_plugin.js) — JavaScript-плагин для Swagger UI:
  - Регистрируется через `presets` Swagger UI.
  - В каждый tag-section вставляет кнопку **«▶ Run all»**.
  - При клике: POST `/api/v1/test-runner/run` для текущей группы → анимация загрузки → таблица результатов в `<details>` под группой.
  - При загрузке UI: автоматически GET `/history?group=...` для каждой группы → если есть, показывает прошлый результат свёрнутым.
  - Таблица: scenario id | method+path | duration ms | PASS/FAIL | preview / error.
- [ ] [static/templates/swagger_ui.html](../static/templates/swagger_ui.html) (или где Swagger UI рендерится): подключить `test_runner_plugin.js` и `presets: [TestRunnerPlugin]` в SwaggerUIBundle config.

#### 2.4 Verify + commit

- [ ] Открыть http://localhost:5004/api/docs — каждый CRUD-tag имеет «Run all», под ним спойлер.
- [ ] Кликнуть по каждой группе, увидеть PASS, увидеть JSON в `openapi/test_API_results_*.json`.
- [ ] Reload — увидеть автоматическую загрузку прошлых результатов.
- [ ] Commit: «Test-runner для каждой OpenAPI-группы: settings.json + server endpoints + Swagger UI plugin»

## Чек-лист готовности

- [ ] Один префикс `/api/v1/` для всех CRUD endpoints
- [ ] crud_routes.py и openapi_crud_paths.py удалены
- [ ] test_api_swagger.py 25/25 PASS на новых путях
- [ ] В Swagger UI каждая группа имеет «Run all» + спойлер с таблицей
- [ ] Конфиг в openapi/test_API_settings.json
- [ ] История в openapi/test_API_results_*.json (gitignored или коммитится — решить)
- [ ] Все три commit'а на main
