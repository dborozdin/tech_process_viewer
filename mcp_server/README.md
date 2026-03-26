# MCP-сервер PSS Database / PSS Database MCP Server

## Описание / Overview

MCP-сервер (Model Context Protocol) для интеграции базы данных PSS с Claude Code и другими MCP-совместимыми клиентами. Предоставляет инструменты для просмотра схемы данных, поиска сущностей и выполнения запросов к базе данных PSS.

MCP server for integrating the PSS database with Claude Code and other MCP-compatible clients. Provides tools for browsing the data schema, searching entities, and querying the PSS database.

---

## Установка / Installation

### Зависимости / Dependencies

```bash
pip install mcp
```

### Переменные окружения / Environment Variables

| Переменная / Variable | Описание / Description | По умолчанию / Default |
|---|---|---|
| `PSS_SERVER` | URL сервера PSS / PSS server URL | `http://localhost:7239` |
| `PSS_DB` | Имя базы данных / Database name | `ils_lessons12` |
| `PSS_USER` | Имя пользователя / Username | `Administrator` |
| `PSS_PASSWORD` | Пароль / Password | _(пустой / empty)_ |

---

## Подключение к Claude Code / Connecting to Claude Code

### 1. Добавьте конфигурацию MCP-сервера / Add MCP server configuration

Создайте или отредактируйте файл `.claude/settings.json` в корне проекта:

Create or edit `.claude/settings.json` in the project root:

```json
{
  "mcpServers": {
    "pss-database": {
      "command": "python",
      "args": ["mcp_server/server.py"],
      "cwd": "C:\\python_projects\\express_api\\tech_process_viewer",
      "env": {
        "PSS_SERVER": "http://localhost:7239",
        "PSS_DB": "ils_lessons12",
        "PSS_USER": "Administrator",
        "PSS_PASSWORD": ""
      }
    }
  }
}
```

### 2. Перезапустите Claude Code / Restart Claude Code

После добавления конфигурации перезапустите Claude Code. Сервер запустится автоматически.

After adding the configuration, restart Claude Code. The server will start automatically.

### 3. Проверьте подключение / Verify connection

В Claude Code выполните команду `/mcp` для просмотра подключённых серверов. Сервер `pss-database` должен отображаться в списке.

In Claude Code, run `/mcp` to view connected servers. The `pss-database` server should appear in the list.

---

## Доступные инструменты / Available Tools

| Инструмент / Tool | Описание / Description |
|---|---|
| `list_entity_categories` | Просмотр категорий данных схемы / Browse data schema categories |
| `search_entities` | Поиск типов сущностей по ключевому слову / Search entity types by keyword |
| `get_entity_schema` | Получить атрибуты и связи сущности / Get entity attributes and relationships |
| `get_entity_description` | Описание сущности на русском языке / Get entity description in Russian |
| `query_instances` | Запросить экземпляры из БД с фильтрами / Query instances with filters |
| `get_instance` | Получить экземпляр по sys_id / Get instance by sys_id |
| `execute_apl_query` | Выполнить SELECT APL-запрос / Execute SELECT APL query |
| `get_folder_tree` | Иерархия папок / Folder hierarchy |
| `get_product_tree` | Дерево входимости изделия (BOM) / Product BOM tree |

---

## Запуск вручную / Manual Run

Для отладки можно запустить сервер напрямую:

For debugging, you can run the server directly:

```bash
cd C:\python_projects\express_api\tech_process_viewer
python -m mcp_server.server
```

Логи выводятся в stderr. Протокол MCP работает через stdin/stdout.

Logs are written to stderr. The MCP protocol communicates via stdin/stdout.

---

## Примеры использования в Claude Code / Usage Examples

После подключения сервера можно обращаться к данным PSS естественным языком:

After connecting, you can query PSS data using natural language:

- "Покажи структуру сущности product_version"
- "Найди все организации в базе данных"
- "Какие изделия есть в папке Проект?"
- "Show me the BOM for product #12345"
- "What entity types are related to manufacturing processes?"
