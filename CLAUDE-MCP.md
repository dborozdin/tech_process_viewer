# MCP Server — Model Context Protocol сервер для PSS

## Назначение

MCP-сервер (Model Context Protocol) для интеграции базы данных PSS с Claude Code и другими MCP-совместимыми AI-ассистентами. Предоставляет 40+ инструментов для просмотра схемы данных, поиска сущностей, выполнения APL-запросов и CRUD-операций.

**Транспорт:** stdio (stdin/stdout)  
**Порт:** не используется (работает через стандартные потоки)

## Техническая архитектура

### Стек
- **Протокол:** MCP (Model Context Protocol)
- **Транспорт:** stdio (через `mcp.server.stdio.stdio_server`)
- **БД:** PSS REST API на порту 7239
- **Зависимости:** `mcp` (MCP SDK), `requests`

### Точка входа
```
mcp_server/server.py
```

### Зависимости от других модулей

```python
from ILS_reports_agent.pss.api_client import PSSClient   # PSS REST клиент
from ILS_reports_agent.pss.schema import get_schema       # Парсер словаря + HTML
from api.ils_logstruct_api import ILSLogStructAPI         # Логистическая структура
from api.ils_tasks_api import ILSTasksAPI                 # Регламентные работы
```

## Категории инструментов

### Schema (исследование схемы данных)

| Инструмент | Описание |
|-----------|----------|
| `schema_list_categories` | Список категорий сущностей в схеме |
| `schema_search` | Поиск типов сущностей по ключевому слову |
| `schema_get_entity` | Полная схема сущности: атрибуты, типы, связи |
| `schema_describe` | Описание сущности на русском языке |

### Data (низкоуровневый доступ к данным)

| Инструмент | Описание |
|-----------|----------|
| `data_query` | Запрос экземпляров сущности с фильтром |
| `data_get_instance` | Получить экземпляр по sys_id со всеми атрибутами |
| `data_apl_query` | Выполнить произвольный APL SELECT-запрос |

### PDM (Product Data Management)

| Инструмент | Описание |
|-----------|----------|
| `pdm_search_products` | Поиск изделий по обозначению или наименованию |
| `pdm_get_product` | Полная информация об изделии |
| `pdm_get_product_full_info` | Все атрибуты изделия и его версии |
| `pdm_find_product_by_code` | Поиск изделия по точному обозначению (code1) |
| `pdm_get_bom` | Состав изделия (BOM) — дочерние компоненты с количествами |
| `pdm_get_folders` | Список папок |
| `pdm_get_folder_contents` | Содержимое папки |
| `pdm_get_documents` | Документы, привязанные к объекту |
| `pdm_get_processes` | Список техпроцессов для изделия |
| `pdm_get_process_hierarchy` | Иерархия техпроцесса: фазы и операции |
| `pdm_get_process_details` | Детали техпроцесса: операции, документы, ресурсы |
| `pdm_get_process_resources` | Ресурсы техпроцесса: материалы и нормы расхода |
| `pdm_get_characteristics` | Характеристики изделия |
| `pdm_get_characteristic_values` | Значения характеристик для объекта |
| `pdm_list_characteristic_types` | Список типов характеристик |
| `pdm_create_characteristic_value` | Создать значение характеристики |
| `pdm_update_characteristic_value` | Обновить значение характеристики |
| `pdm_delete_characteristic_value` | Удалить значение характеристики |
| `pdm_list_organizations` | Список организаций |
| `pdm_get_organization` | Детали организации |
| `pdm_list_units` | Список единиц измерения |
| `pdm_get_unit` | Детали единицы измерения |
| `pdm_create_unit` | Создать единицу измерения |
| `pdm_update_unit` | Обновить единицу измерения |
| `pdm_delete_unit` | Удалить единицу измерения |
| `pdm_get_classifiers` | Список систем классификаторов |
| `pdm_get_classifier_tree` | Дерево классификатора |
| `pdm_get_classifier_roots` | Корневые уровни классификатора |
| `pdm_get_classifier_children` | Дочерние уровни |
| `pdm_get_classifier_level` | Детали уровня классификатора |
| `pdm_create_classifier_system` | Создать систему классификаторов |
| `pdm_update_classifier_system` | Обновить систему классификаторов |
| `pdm_delete_classifier_system` | Удалить систему классификаторов |
| `pdm_create_classifier_level` | Создать уровень классификатора |
| `pdm_update_classifier_level` | Обновить уровень классификатора |
| `pdm_delete_classifier_level` | Удалить уровень классификатора |

### ILS (Integrated Logistic Support)

| Инструмент | Описание |
|-----------|----------|
| `ils_find_final_products` | Найти финальные изделия по наименованию или обозначению |
| `ils_get_logistic_structure` | Дерево логистической структуры компонента |
| `ils_get_tasks` | Технологические карты (работы) для компонента |

### Connection

| Инструмент | Описание |
|-----------|----------|
| `connect` | Подключиться к базе данных |
| `connection_status` | Проверить состояние подключения |

## Переменные окружения

| Переменная | По умолчанию | Описание |
|-----------|-------------|----------|
| `PSS_SERVER` | `http://localhost:7239` | URL сервера PSS |
| `PSS_DB` | `pss_moma_08_07_2025` | Имя базы данных |
| `PSS_USER` | `Administrator` | Пользователь |
| `PSS_PASSWORD` | _(пустой)_ | Пароль |

## Подключение к Claude Code

### 1. Конфигурация в `.claude/settings.json`

```json
{
  "mcpServers": {
    "pss-database": {
      "command": "python",
      "args": ["mcp_server/server.py"],
      "cwd": "C:\\python_projects\\express_api\\tech_process_viewer",
      "env": {
        "PSS_SERVER": "http://localhost:7239",
        "PSS_DB": "pss_moma_08_07_2025",
        "PSS_USER": "Administrator",
        "PSS_PASSWORD": ""
      }
    }
  }
}
```

### 2. Проверка подключения

В Claude Code: `/mcp` — сервер `pss-database` должен отображаться в списке.

### 3. Использование

После подключения можно обращаться к данным PSS естественным языком:
- "Покажи структуру сущности product_version"
- "Найди все организации в базе данных"
- "Покажи BOM для изделия #12345"

## Запуск вручную (для отладки)

```bash
cd C:\python_projects\express_api\tech_process_viewer
python -m mcp_server.server
# Или: python mcp_server/server.py
```

Логи выводятся в stderr. Протокол MCP работает через stdin/stdout.

## Связь с другими приложениями

- **ILS Reports Agent** — использует MCP-сервер через `mcp_bridge.py` для выполнения инструментов AI-агентом
- **API-слой** — использует `api/ils_logstruct_api.py` и `api/ils_tasks_api.py` из общего пакета
- **PSS-клиент** — использует `ILS_reports_agent/pss/api_client.py` и `ILS_reports_agent/pss/schema.py`

## Правило синхронизации

**При изменении классов доступа к данным PSS в папке `api/` (файлы `pss_*.py`) — обязательно обновить MCP сервер (`mcp_server/server.py`)**, чтобы MCP-инструменты соответствовали актуальному API.
