"""
Tool definitions for the ILS Report Agent.
Each tool is described as an OpenAI-compatible function schema.
"""

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "list_entity_categories",
            "description": (
                "Список категорий (разделов) сущностей в схеме данных. "
                "Каждая категория содержит список имён сущностей. "
                "Используй для навигации по схеме, когда нужно понять какие группы данных есть в системе."
            ),
            "parameters": {
                "type": "object",
                "properties": {},
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_entities",
            "description": (
                "Поиск сущностей по ключевому слову в имени, описании, разделе или атрибутах. "
                "Возвращает список совпадений с оценкой релевантности. "
                "Используй когда нужно найти сущность по теме запроса."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "keyword": {
                        "type": "string",
                        "description": "Ключевое слово для поиска (на русском или английском)",
                    },
                },
                "required": ["keyword"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_entity_schema",
            "description": (
                "Получить полную схему сущности: атрибуты, типы данных, связи с другими сущностями. "
                "Используй для понимания структуры данных конкретной сущности перед запросом."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "entity_name": {
                        "type": "string",
                        "description": "Имя сущности (например, 'apl_ils_element', 'organization')",
                    },
                },
                "required": ["entity_name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_entity_description",
            "description": (
                "Получить описание сущности на русском языке: "
                "назначение, раздел, базовый тип, список атрибутов с описаниями. "
                "Используй когда нужно понять назначение сущности."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "entity_name": {
                        "type": "string",
                        "description": "Имя сущности",
                    },
                },
                "required": ["entity_name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_reverse_references",
            "description": (
                "Получить список сущностей, которые ссылаются на указанную сущность (обратные связи). "
                "Показывает, из каких сущностей и через какой атрибут идёт ссылка. "
                "Используй для навигации: например, чтобы узнать, какие сущности связаны с изделием."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "entity_name": {
                        "type": "string",
                        "description": "Имя сущности, для которой нужно найти обратные связи",
                    },
                },
                "required": ["entity_name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "save_knowledge",
            "description": (
                "Сохранить полезное знание о структуре данных или способах работы с ними "
                "для использования в будущих сессиях. Вызывай когда пользователь объясняет "
                "как правильно находить или связывать данные, какие сущности и атрибуты использовать, "
                "или любую доменную информацию, которая поможет в будущих запросах."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "topic": {
                        "type": "string",
                        "description": "Краткая тема знания (например, 'Поиск компонентов элемента ИЛС')",
                    },
                    "content": {
                        "type": "string",
                        "description": "Подробное описание знания: какие сущности, атрибуты, запросы использовать",
                    },
                },
                "required": ["topic", "content"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "ask_user",
            "description": (
                "Задать уточняющий вопрос пользователю. "
                "Используй ТОЛЬКО когда запрос неоднозначен и невозможно определить, "
                "какие именно данные нужны. Не используй для подтверждения — "
                "действуй по лучшей гипотезе, когда контекст достаточен."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "question": {
                        "type": "string",
                        "description": "Уточняющий вопрос для пользователя на русском языке",
                    },
                },
                "required": ["question"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "count_instances",
            "description": (
                "Подсчитать количество экземпляров сущности в базе данных. "
                "Быстрая операция, не возвращает сами данные. "
                "Можно добавить фильтр в формате APL."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "entity_type": {
                        "type": "string",
                        "description": "Имя типа сущности (например, 'organization')",
                    },
                    "filters": {
                        "type": "string",
                        "description": (
                            "Опциональный фильтр APL. Примеры: "
                            "'.name LIKE \"test\"', '.# = #123', "
                            "'.status = \"active\"'"
                        ),
                    },
                },
                "required": ["entity_type"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "query_instances",
            "description": (
                "Запросить экземпляры сущности из базы данных с опциональным фильтром. "
                "Возвращает список экземпляров с их атрибутами. Каждый экземпляр содержит "
                "поле sys_id — уникальный числовой идентификатор, который можно использовать "
                "в последующих запросах для поиска связанных объектов (через .# = #sys_id). "
                "Поддерживает пагинацию (start, size)."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "entity_type": {
                        "type": "string",
                        "description": "Имя типа сущности",
                    },
                    "filters": {
                        "type": "string",
                        "description": (
                            "Опциональный фильтр APL. Примеры: "
                            "'.name LIKE \"Boeing\"', '.id = \"DOC-001\"'"
                        ),
                    },
                    "start": {
                        "type": "integer",
                        "description": "Начальный индекс (для пагинации, по умолчанию 0)",
                        "default": 0,
                    },
                    "size": {
                        "type": "integer",
                        "description": "Максимальное количество результатов (по умолчанию 50)",
                        "default": 50,
                    },
                },
                "required": ["entity_type"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_instance_by_id",
            "description": (
                "Получить один экземпляр по его sys_id (числовой системный идентификатор). "
                "sys_id берётся из результатов query_instances или execute_apl_query — "
                "НЕ нужно спрашивать его у пользователя. Возвращает все атрибуты экземпляра."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "sys_id": {
                        "type": "integer",
                        "description": "Системный ID экземпляра (числовой)",
                    },
                    "entity_type": {
                        "type": "string",
                        "description": "Опциональный тип сущности (для оптимизации)",
                    },
                },
                "required": ["sys_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "execute_apl_query",
            "description": (
                "Выполнить произвольный SELECT APL-запрос к базе данных. "
                "Используй для сложных запросов с навигацией по связям. "
                "ТОЛЬКО SELECT запросы (чтение). Синтаксис:\n"
                "SELECT NO_CASE Ext_ FROM Ext_{entity_type(.field = \"value\")} END_SELECT\n"
                "SELECT NO_CASE Ext_ FROM Ext_{entity(.ref->other.field = \"val\")} END_SELECT\n"
                "SELECT NO_CASE Ext2 FROM Ext_{#123} Ext2{other_entity(.# IN #Ext_)} END_SELECT\n"
                ".# = #ID для фильтрации по sys_id (берётся из результатов предыдущих запросов), "
                ".field LIKE 'value' для строк.\n"
                "Пример цепочки: сначала найди объект через query_instances, возьми его sys_id, "
                "затем используй .# = #sys_id для поиска связанных объектов."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "APL SELECT запрос",
                    },
                    "size": {
                        "type": "integer",
                        "description": "Максимальное количество результатов (по умолчанию 100)",
                        "default": 100,
                    },
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_logistic_structure",
            "description": (
                "Получить полную логистическую структуру (дерево состава) изделия/компонента. "
                "Возвращает дерево элементов ИЛС с компонентами, типами (система/связка), "
                "классификацией LRU/SRU, количеством в узле и ключевыми характеристиками. "
                "Используй когда пользователь спрашивает о составе изделия, структуре, "
                "компонентах, входящих в изделие, или дереве ИЛС/ЛСИ. "
                "ВАЖНО: передай sys_id компонента, если он известен из предыдущего запроса "
                "(это самый надёжный способ). Если sys_id неизвестен — передай обозначение или название. "
                "После получения результата используй format_html_report для представления."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "component_designation": {
                        "type": "string",
                        "description": (
                            "Обозначение (id) или название (name_rus) компонента/изделия. "
                            "Если известен sys_id — можно передать пустую строку ''."
                        ),
                    },
                    "sys_id": {
                        "type": "integer",
                        "description": (
                            "Системный ID компонента из результата предыдущего запроса "
                            "(query_instances или execute_apl_query). "
                            "Самый надёжный способ — используй если доступен."
                        ),
                    },
                    "max_depth": {
                        "type": "integer",
                        "description": "Максимальная глубина дерева (по умолчанию 10)",
                        "default": 10,
                    },
                },
                "required": ["component_designation"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "format_html_report",
            "description": (
                "Сформировать HTML-отчёт из подготовленных данных. "
                "Используй когда все нужные данные собраны и нужно представить их пользователю. "
                "Передай заголовок, описание и данные для таблицы."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "title": {
                        "type": "string",
                        "description": "Заголовок отчёта",
                    },
                    "description": {
                        "type": "string",
                        "description": "Краткое описание содержимого отчёта",
                    },
                    "columns": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Названия столбцов таблицы",
                    },
                    "rows": {
                        "type": "array",
                        "items": {
                            "type": "array",
                            "items": {"type": "string"},
                        },
                        "description": "Строки таблицы (массив массивов строк)",
                    },
                },
                "required": ["title", "columns", "rows"],
            },
        },
    },
]

# High-level tools that encapsulate domain logic (one call instead of many)
HIGH_LEVEL_TOOLS = ["get_logistic_structure"]
