# CLAUDE.md

## Платформа PSS — обзор приложений

Проект содержит 5 Flask-приложений и MCP-сервер, объединённых общим API-слоем (`api/`) для работы с базой данных PSS (ayatzk) через REST API.


| Приложение    | Порт | Точка входа        | Документация                                   |
| ------------------------- | ---------- | ------------------------------ | ------------------------------------------------------------ |
| **Tech Process Viewer** | 5000     | `tech_process_viewer_app.py` | [CLAUDE-TPV.md](CLAUDE-TPV.md)                             |
| **ILS Reports Agent**   | 5001     | `ILS_reports_agent/app.py`   | [ILS_reports_agent/CLAUDE.md](ILS_reports_agent/CLAUDE.md) |
| **PSS-aiR**             | 5002     | `PSS-aiR/app.py`             | [PSS-aiR/CLAUDE.md](PSS-aiR/CLAUDE.md)                     |
| **Entity Viewer**       | 5003     | `entity_viewer_app.py`       | [CLAUDE-EV.md](CLAUDE-EV.md)                               |
| **API Docs / Swagger**  | 5004     | `api_docs_app.py`            | [CLAUDE-API-DOCS.md](CLAUDE-API-DOCS.md)                   |
| **MCP Server**          | stdio    | `mcp_server/server.py`       | [CLAUDE-MCP.md](CLAUDE-MCP.md)                             |

### Конфигурации запуска VS Code

Все 5 приложений имеют конфигурации Debug в `.vscode/launch.json`:

- **"Tech Process Viewer (5000)"** — `tech_process_viewer_app.py`
- **"ILS Reports Agent (5001)"** — `ILS_reports_agent.app` (module)
- **"PSS-aiR (5002)"** — `PSS-aiR/app.py`
- **"Entity Viewer (5003)"** — `entity_viewer_app.py`
- **"API Docs / Swagger (5004)"** — `api_docs_app.py`

Запуск из терминала:

```bash
# Tech Process Viewer
python tech_process_viewer_app.py

# ILS Reports Agent
python -m ILS_reports_agent.app

# PSS-aiR
python PSS-aiR/app.py

# Entity Viewer
python entity_viewer_app.py

# API Docs
python api_docs_app.py

# MCP Server (запускается Claude Code автоматически)
python mcp_server/server.py
```

### Общая архитектура

```
api/                    # Общий API-слой (DatabaseAPI, flask-smorest blueprint'ы, схемы)
├── pss_api.py          #   PSS REST клиент
├── pss_*_api.py        #   Доменные API (products, folders, documents, processes, etc.)
├── routes/             #   Flask-Smorest blueprint'ы (auth, products, entity_viewer, etc.)
├── schemas/            #   Marshmallow-схемы для OpenAPI
├── app_helpers.py      #   create_pss_app() — фабрика Flask-приложений
└── query_helpers.py    #   query_apl(), batch_query_by_ids(), track_performance()

static/                 # Общие статические файлы (JS, CSS, HTML-шаблоны)
└── templates/          #   Jinja2-шаблоны для TPV и Entity Viewer

mcp_server/             # MCP-сервер (40+ инструментов для AI-ассистентов)
ILS_reports_agent/      # AI-агент (LLM + MCP bridge)
PSS-aiR/                # PDM веб-клиент (трёхпанельный SPA)
```

Три приложения (Tech Process Viewer, Entity Viewer, API Docs) используют `create_pss_app()` фабрику из `api/app_helpers.py` и общие `static/` ресурсы. PSS-aiR использует общий `api/pss_api.py` но имеет собственную структуру Flask с отдельными routes/services. ILS Reports Agent имеет собственный PSS-клиент и не зависит от `create_pss_app()`.

## Правила синхронизации

- **При изменении классов доступа к данным PSS в папке `api/` (файлы `pss_*.py`) — обязательно обновить MCP сервер (`mcp_server/server.py`)**, чтобы MCP-инструменты соответствовали актуальному API. Это касается добавления/удаления/изменения методов, параметров и схем данных.
- **Перед добавлением APL-запросов к PSS — проверить существование сущности и атрибутов через schema-инструменты MCP** (`schema_get_entity`, `schema_search`). Словарь: `doc/apl_pss_a.dict`. Не использовать в коде имена сущностей или атрибутов, которых нет в словаре. Если нужная сущность не найдена — уточнить у пользователя правильное имя.

## APL-запросы к PSS

- **LIKE в APL** используется без дополнительных wildcard-символов: `.name LIKE "значение"` (НЕ `"*значение*"`). Формат описан в `db_schema_doc/REST API PSS AYATZK.yaml`.

## Тестирование в браузере (Playwright)

- Когда пользователь просит протестировать что-то в браузере — **всегда запускать Playwright с `headless=False`**, чтобы пользователь видел выполнение на экране в отдельном окне Chromium.
- Использовать `slow_mo=500` для наглядности, если тест включает UI-взаимодействие (клики, ввод текста, переключение элементов).
- Пример: `browser = p.chromium.launch(headless=False, slow_mo=500)`

### Сценарии проверки UI

- **При добавлении/изменении функций интерфейса** — обязательно создать или обновить `test_ui_scenarios.py` и `TEST_SCENARIOS.md` в папке приложения.
- Сценарии **последовательные** — каждый продолжает с состояния предыдущего.
- Результат записывается в HTML-файл `test_results.html`.

### Pipeline тестирования PSS-aiR

Полный цикл проверки CRUD-интерфейса PSS-aiR:

1. **Убить процесс PSS-сервера** (`AplNetTransportServTCP.exe`) — сервер нестабилен и может зависать на write-операциях
2. **Запустить PSS-сервер**: `"C:\Program Files (x86)\PSS_MUI\AplNetTransportServTCP.exe" /p:7239`
3. **Подключить PSS-aiR** к БД `pss_moma_08_07_2025`
4. **Запустить тесты**: `python PSS-aiR/test_ui_scenarios.py`
5. Скрипт **автоматически перезапускает PSS-сервер** при обнаружении зависания (ensure + recovery)
6. При неуспехе скрипт повторяет прогон (до 5 раз или 2 часов)
7. Результат: `PSS-aiR/test_results.html`

- Перечень тестов: [`PSS-aiR/TEST_SCENARIOS.md`](PSS-aiR/TEST_SCENARIOS.md)
- Скрипт: [`PSS-aiR/test_ui_scenarios.py`](PSS-aiR/test_ui_scenarios.py)
- Результаты: [`PSS-aiR/test_results.html`](PSS-aiR/test_results.html)
