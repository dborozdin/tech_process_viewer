"""
MCP server for Claude Code integration with PSS database.

Exposes PSS data model browsing and querying capabilities via
the Model Context Protocol (stdio transport).

Tool categories (by prefix):
    schema_*   — metadata: entity types, attributes, relationships
    data_*     — low-level data access: APL queries, instances
    pdm_*      — high-level PDM operations: products, BOM, folders, documents

Environment variables:
    PSS_SERVER   — PSS REST API base URL (default: http://localhost:7239)
    PSS_DB       — Database name (default: pss_moma_08_07_2025)
    PSS_USER     — Username (default: Administrator)
    PSS_PASSWORD — Password (default: empty)
"""

import asyncio
import json
import logging
import os
import sys

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

# Add project root to path so imports work
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

# Also add express_api/ for tech_process_viewer package imports
_EXPRESS_API_ROOT = os.path.dirname(_PROJECT_ROOT)
if _EXPRESS_API_ROOT not in sys.path:
    sys.path.insert(0, _EXPRESS_API_ROOT)

from ILS_reports_agent.pss.api_client import PSSClient
from ILS_reports_agent.pss.schema import get_schema
from api.ils_logstruct_api import ILSLogStructAPI
from api.ils_tasks_api import ILSTasksAPI

logger = logging.getLogger("mcp.pss")

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

PSS_SERVER = os.environ.get("PSS_SERVER", "http://localhost:7239")
PSS_DB = os.environ.get("PSS_DB", "pss_moma_08_07_2025")
PSS_USER = os.environ.get("PSS_USER", "Administrator")
PSS_PASSWORD = os.environ.get("PSS_PASSWORD", "")

# Schema file paths
DICT_FILE_PATH = os.path.join(_EXPRESS_API_ROOT, "doc", "apl_pss_a.dict")
HTML_SCHEMA_PATH = os.path.join(_PROJECT_ROOT, "db_schema_doc", "apl_pss_a_1419_data.htm")

# ---------------------------------------------------------------------------
# Globals
# ---------------------------------------------------------------------------

_client: PSSClient | None = None
_schema = None
_db_api = None  # DatabaseAPI instance for high-level operations
_ils_logstruct_api: ILSLogStructAPI | None = None
_ils_tasks_api: ILSTasksAPI | None = None

server = Server("pss-database")


def _get_client() -> PSSClient:
    """Get or create a connected PSS client."""
    global _client
    if _client is None or not _client.connected:
        rest_url = f"{PSS_SERVER}/rest"
        _client = PSSClient(rest_url)
        _client.connect(PSS_DB, PSS_USER, PSS_PASSWORD)
        logger.info("Connected to PSS: %s / %s", PSS_SERVER, PSS_DB)
    return _client


def _get_schema():
    """Get or create schema instance."""
    global _schema
    if _schema is None:
        _schema = get_schema(DICT_FILE_PATH, HTML_SCHEMA_PATH)
        logger.info("Schema loaded: %d entities", len(_schema.entities))
    return _schema


def _get_db_api():
    """Get or create DatabaseAPI instance for high-level operations."""
    global _db_api
    if _db_api is None:
        from tech_process_viewer.api.pss_api import DatabaseAPI
        credentials = f"user={PSS_USER}&db={PSS_DB}"
        url_db_api = PSS_SERVER + "/rest"
        _db_api = DatabaseAPI(url_db_api, credentials)
        _db_api.reconnect_db()
        logger.info("DatabaseAPI connected: %s / %s", PSS_SERVER, PSS_DB)
    return _db_api


def _get_ils_logstruct_api() -> ILSLogStructAPI:
    """Get or create ILSLogStructAPI instance."""
    global _ils_logstruct_api
    if _ils_logstruct_api is None:
        _ils_logstruct_api = ILSLogStructAPI(_get_client())
        logger.info("ILSLogStructAPI initialized")
    return _ils_logstruct_api


def _get_ils_tasks_api() -> ILSTasksAPI:
    """Get or create ILSTasksAPI instance."""
    global _ils_tasks_api
    if _ils_tasks_api is None:
        _ils_tasks_api = ILSTasksAPI(_get_client())
        logger.info("ILSTasksAPI initialized")
    return _ils_tasks_api


def _json_response(data) -> list[TextContent]:
    """Wrap data as MCP TextContent JSON response."""
    return [TextContent(type="text", text=json.dumps(data, ensure_ascii=False, indent=2))]


def _error_response(message: str) -> list[TextContent]:
    """Return an error response."""
    return [TextContent(type="text", text=json.dumps({"error": message}, ensure_ascii=False))]


def _simplify_instance(inst):
    """Simplify PSS instance for readable output."""
    if not isinstance(inst, dict):
        return inst
    result = {"sys_id": inst.get("id"), "type": inst.get("type")}
    attrs = inst.get("attributes", {})
    for key, val in attrs.items():
        if isinstance(val, dict) and "id" in val:
            result[key] = f"#{val['id']} ({val.get('type', '')})"
        elif isinstance(val, list):
            result[key] = f"[{len(val)} items]"
        else:
            result[key] = val
    return result


# ---------------------------------------------------------------------------
# Tool definitions — organized by category prefix
# ---------------------------------------------------------------------------

TOOLS = [
    # ==================== connection — Server/DB connection ====================
    Tool(
        name="connection_status",
        description="Проверить состояние подключения к БД.",
        inputSchema={"type": "object", "properties": {}, "required": []},
    ),
    Tool(
        name="connect",
        description="Подключиться к базе данных PSS или переподключиться к другой.",
        inputSchema={
            "type": "object",
            "properties": {
                "server": {
                    "type": "string",
                    "description": "URL сервера PSS (например, 'http://localhost:7239'). По умолчанию из env.",
                },
                "db": {
                    "type": "string",
                    "description": "Имя базы данных (например, 'pss_moma_08_07_2025'). По умолчанию из env.",
                },
                "user": {
                    "type": "string",
                    "description": "Имя пользователя (например, 'Administrator'). По умолчанию из env.",
                },
                "password": {
                    "type": "string",
                    "description": "Пароль (по умолчанию пустой)",
                },
            },
            "required": [],
        },
    ),

    # ==================== schema_* — Metadata ====================
    Tool(
        name="schema_list_categories",
        description="Список категорий сущностей в схеме данных.",
        inputSchema={"type": "object", "properties": {}, "required": []},
    ),
    Tool(
        name="schema_search",
        description="Поиск типов сущностей по ключевому слову.",
        inputSchema={
            "type": "object",
            "properties": {
                "keyword": {
                    "type": "string",
                    "description": "Ключевое слово (на русском или английском)",
                },
            },
            "required": ["keyword"],
        },
    ),
    Tool(
        name="schema_get_entity",
        description="Полная схема сущности: атрибуты, типы, связи.",
        inputSchema={
            "type": "object",
            "properties": {
                "entity_name": {
                    "type": "string",
                    "description": "Имя типа сущности (например, 'apl_product_definition_formation', 'organization')",
                },
            },
            "required": ["entity_name"],
        },
    ),
    Tool(
        name="schema_describe",
        description="Описание сущности на русском языке.",
        inputSchema={
            "type": "object",
            "properties": {
                "entity_name": {
                    "type": "string",
                    "description": "Имя типа сущности",
                },
            },
            "required": ["entity_name"],
        },
    ),

    # ==================== data_* — Low-level data access ====================
    Tool(
        name="data_query",
        description="Запросить экземпляры сущности с фильтром.",
        inputSchema={
            "type": "object",
            "properties": {
                "entity_type": {
                    "type": "string",
                    "description": "Имя типа сущности (например, 'organization', 'apl_folder', 'product')",
                },
                "filters": {
                    "type": "string",
                    "description": "APL-фильтр (опционально). Примеры: '.name LIKE \"test*\"', '.code1 = \"ABC\"'",
                },
                "limit": {
                    "type": "integer",
                    "description": "Макс. результатов (по умолч. 50, макс. 200)",
                    "default": 50,
                },
            },
            "required": ["entity_type"],
        },
    ),
    Tool(
        name="data_get_instance",
        description="Получить один экземпляр по sys_id со всеми атрибутами.",
        inputSchema={
            "type": "object",
            "properties": {
                "sys_id": {
                    "type": "integer",
                    "description": "Системный идентификатор (числовой ID объекта в БД)",
                },
            },
            "required": ["sys_id"],
        },
    ),
    Tool(
        name="data_apl_query",
        description="Выполнить произвольный APL SELECT-запрос к базе данных.",
        inputSchema={
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "APL SELECT-запрос",
                },
            },
            "required": ["query"],
        },
    ),

    # ==================== pdm_* — High-level PDM operations ====================
    Tool(
        name="pdm_search_products",
        description="Найти изделия PDM по обозначению или наименованию.",
        inputSchema={
            "type": "object",
            "properties": {
                "text": {
                    "type": "string",
                    "description": "Текст для поиска (часть обозначения или наименования)",
                },
                "limit": {
                    "type": "integer",
                    "description": "Макс. результатов (по умолч. 50)",
                    "default": 50,
                },
            },
            "required": ["text"],
        },
    ),
    Tool(
        name="pdm_get_product",
        description="Получить полную информацию об изделии по sys_id.",
        inputSchema={
            "type": "object",
            "properties": {
                "product_id": {
                    "type": "integer",
                    "description": "sys_id изделия (apl_product_definition_formation)",
                },
            },
            "required": ["product_id"],
        },
    ),
    Tool(
        name="pdm_get_bom",
        description="Состав изделия (BOM) — дочерние компоненты с количествами.",
        inputSchema={
            "type": "object",
            "properties": {
                "product_id": {
                    "type": "integer",
                    "description": "sys_id изделия (apl_product_definition_formation) — родитель",
                },
            },
            "required": ["product_id"],
        },
    ),
    Tool(
        name="pdm_get_folders",
        description="Список папок в базе, с опциональным фильтром по имени.",
        inputSchema={
            "type": "object",
            "properties": {
                "name_filter": {
                    "type": "string",
                    "description": "Фильтр по имени папки (опционально, поддерживает * для LIKE)",
                },
            },
            "required": [],
        },
    ),
    Tool(
        name="pdm_get_folder_contents",
        description="Содержимое папки: вложенные папки, изделия, документы.",
        inputSchema={
            "type": "object",
            "properties": {
                "folder_id": {
                    "type": "integer",
                    "description": "sys_id папки (apl_folder)",
                },
            },
            "required": ["folder_id"],
        },
    ),
    Tool(
        name="pdm_get_documents",
        description="Документы, привязанные к объекту по sys_id.",
        inputSchema={
            "type": "object",
            "properties": {
                "item_id": {
                    "type": "integer",
                    "description": "sys_id объекта, к которому привязаны документы",
                },
            },
            "required": ["item_id"],
        },
    ),
    Tool(
        name="pdm_get_characteristics",
        description="Характеристики (свойства) изделия по sys_id.",
        inputSchema={
            "type": "object",
            "properties": {
                "product_id": {
                    "type": "integer",
                    "description": "sys_id изделия (apl_product_definition_formation)",
                },
            },
            "required": ["product_id"],
        },
    ),
    Tool(
        name="pdm_find_product_by_code",
        description="Найти изделие по точному обозначению (code1).",
        inputSchema={
            "type": "object",
            "properties": {
                "code": {
                    "type": "string",
                    "description": "Точное обозначение изделия (поле code1)",
                },
            },
            "required": ["code"],
        },
    ),

    Tool(
        name="pdm_get_product_full_info",
        description="Все атрибуты изделия и его версии по sys_id.",
        inputSchema={
            "type": "object",
            "properties": {
                "product_id": {
                    "type": "integer",
                    "description": "sys_id изделия (apl_product_definition_formation)",
                },
            },
            "required": ["product_id"],
        },
    ),

    # ==================== pdm_* — Tech Processes, Organizations, Resources ====================
    Tool(
        name="pdm_get_processes",
        description="Список техпроцессов для изделия по его sys_id.",
        inputSchema={
            "type": "object",
            "properties": {
                "product_id": {
                    "type": "integer",
                    "description": "sys_id изделия (apl_product_definition_formation)",
                },
            },
            "required": ["product_id"],
        },
    ),
    Tool(
        name="pdm_get_process_hierarchy",
        description="Иерархия техпроцесса: фазы и операции.",
        inputSchema={
            "type": "object",
            "properties": {
                "process_id": {
                    "type": "integer",
                    "description": "sys_id процесса (apl_action_method)",
                },
            },
            "required": ["process_id"],
        },
    ),
    Tool(
        name="pdm_get_process_details",
        description="Детали техпроцесса: операции, документы, ресурсы.",
        inputSchema={
            "type": "object",
            "properties": {
                "process_id": {
                    "type": "integer",
                    "description": "sys_id техпроцесса (apl_action_method)",
                },
            },
            "required": ["process_id"],
        },
    ),
    Tool(
        name="pdm_list_organizations",
        description="Список организаций в базе данных.",
        inputSchema={
            "type": "object",
            "properties": {
                "name_filter": {
                    "type": "string",
                    "description": "Фильтр по имени (LIKE, опционально)",
                },
                "limit": {
                    "type": "integer",
                    "description": "Макс. результатов (по умолч. 100)",
                    "default": 100,
                },
            },
            "required": [],
        },
    ),
    Tool(
        name="pdm_get_organization",
        description="Детали организации по sys_id.",
        inputSchema={
            "type": "object",
            "properties": {
                "org_id": {
                    "type": "integer",
                    "description": "sys_id организации",
                },
            },
            "required": ["org_id"],
        },
    ),
    Tool(
        name="pdm_get_process_resources",
        description="Ресурсы техпроцесса: материалы и нормы расхода.",
        inputSchema={
            "type": "object",
            "properties": {
                "process_id": {
                    "type": "integer",
                    "description": "sys_id процесса (apl_action_method)",
                },
            },
            "required": ["process_id"],
        },
    ),
    Tool(
        name="pdm_list_units",
        description="Список единиц измерения в базе.",
        inputSchema={
            "type": "object",
            "properties": {
                "limit": {
                    "type": "integer",
                    "description": "Макс. результатов (по умолч. 100)",
                    "default": 100,
                },
            },
            "required": [],
        },
    ),
    # ── Характеристики (apl_characteristic / apl_characteristic_value) ──
    Tool(
        name="pdm_list_characteristic_types",
        description="Список типов характеристик в базе.",
        inputSchema={
            "type": "object",
            "properties": {
                "limit": {
                    "type": "integer",
                    "description": "Макс. результатов (по умолч. 500)",
                    "default": 500,
                },
            },
            "required": [],
        },
    ),
    Tool(
        name="pdm_get_characteristic_values",
        description="Значения характеристик для объекта по sys_id.",
        inputSchema={
            "type": "object",
            "properties": {
                "item_id": {
                    "type": "integer",
                    "description": "sys_id объекта, к которому привязаны значения характеристик",
                },
            },
            "required": ["item_id"],
        },
    ),
    # ==================== ILS — Logistic structure ====================
    Tool(
        name="ils_find_final_products",
        description="Найти финальные изделия по наименованию или обозначению.",
        inputSchema={
            "type": "object",
            "properties": {
                "search_text": {
                    "type": "string",
                    "description": (
                        "Текст для фильтрации по наименованию (name_rus) "
                        "или обозначению (id). "
                        "Если не указан — возвращаются все финальные изделия."
                    ),
                },
                "limit": {
                    "type": "integer",
                    "description": "Макс. количество результатов (по умолч. 50)",
                    "default": 50,
                },
            },
            "required": [],
        },
    ),
    Tool(
        name="ils_get_logistic_structure",
        description="Дерево логистической структуры компонента по sys_id.",
        inputSchema={
            "type": "object",
            "properties": {
                "component_id": {
                    "type": "integer",
                    "description": "sys_id компонента (apl_lss3_component)",
                },
                "max_depth": {
                    "type": "integer",
                    "description": "Максимальная глубина обхода дерева (по умолч. 10)",
                    "default": 10,
                },
            },
            "required": ["component_id"],
        },
    ),
    Tool(
        name="ils_get_tasks",
        description="Технологические карты (работы) для компонента по sys_id.",
        inputSchema={
            "type": "object",
            "properties": {
                "component_id": {
                    "type": "integer",
                    "description": "sys_id компонента (apl_lss3_component)",
                },
            },
            "required": ["component_id"],
        },
    ),
]


# ---------------------------------------------------------------------------
# Tool handlers
# ---------------------------------------------------------------------------

@server.list_tools()
async def list_tools() -> list[Tool]:
    return TOOLS


@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    try:
        # Connection tools
        if name == "connection_status":
            return _handle_connection_status()
        elif name == "connect":
            return _handle_connect(arguments)
        # Schema tools
        elif name == "schema_list_categories":
            return _handle_list_categories()
        elif name == "schema_search":
            return _handle_search_entities(arguments)
        elif name == "schema_get_entity":
            return _handle_get_entity_schema(arguments)
        elif name == "schema_describe":
            return _handle_get_entity_description(arguments)
        # Data tools
        elif name == "data_query":
            return _handle_query_instances(arguments)
        elif name == "data_get_instance":
            return _handle_get_instance(arguments)
        elif name == "data_apl_query":
            return _handle_execute_apl_query(arguments)
        # PDM tools
        elif name == "pdm_search_products":
            return _handle_pdm_search_products(arguments)
        elif name == "pdm_get_product":
            return _handle_pdm_get_product(arguments)
        elif name == "pdm_get_bom":
            return _handle_pdm_get_bom(arguments)
        elif name == "pdm_get_folders":
            return _handle_pdm_get_folders(arguments)
        elif name == "pdm_get_folder_contents":
            return _handle_pdm_get_folder_contents(arguments)
        elif name == "pdm_get_documents":
            return _handle_pdm_get_documents(arguments)
        elif name == "pdm_get_characteristics":
            return _handle_pdm_get_characteristics(arguments)
        elif name == "pdm_find_product_by_code":
            return _handle_pdm_find_by_code(arguments)
        elif name == "pdm_get_product_full_info":
            return _handle_pdm_get_product_full_info(arguments)
        # PDM tools — processes, organizations, resources
        elif name == "pdm_get_processes":
            return _handle_pdm_get_processes(arguments)
        elif name == "pdm_get_process_hierarchy":
            return _handle_pdm_get_process_hierarchy(arguments)
        elif name == "pdm_get_process_details":
            return _handle_pdm_get_process_details(arguments)
        elif name == "pdm_list_organizations":
            return _handle_pdm_list_organizations(arguments)
        elif name == "pdm_get_organization":
            return _handle_pdm_get_organization(arguments)
        elif name == "pdm_get_process_resources":
            return _handle_pdm_get_process_resources(arguments)
        elif name == "pdm_list_units":
            return _handle_pdm_list_units(arguments)
        elif name == "pdm_list_characteristic_types":
            return _handle_pdm_list_characteristic_types(arguments)
        elif name == "pdm_get_characteristic_values":
            return _handle_pdm_get_characteristic_values(arguments)
        # ILS tools
        elif name == "ils_find_final_products":
            return _handle_ils_find_final_products(arguments)
        elif name == "ils_get_logistic_structure":
            return _handle_ils_get_logistic_structure(arguments)
        elif name == "ils_get_tasks":
            return _handle_ils_get_tasks(arguments)
        else:
            return _error_response(f"Unknown tool: {name}")
    except ConnectionError as e:
        return _error_response(f"PSS connection error: {e}")
    except Exception as e:
        logger.exception("Tool %s failed", name)
        return _error_response(f"Tool execution error: {e}")


# ==================== Connection handlers ====================

def _reconnect(server_url: str, db: str, user: str, password: str):
    """Disconnect existing sessions and reconnect with new parameters."""
    global _client, _db_api, _ils_logstruct_api, _ils_tasks_api, PSS_SERVER, PSS_DB, PSS_USER, PSS_PASSWORD

    # Disconnect existing client
    if _client is not None:
        try:
            _client.disconnect()
        except Exception:
            pass
        _client = None

    # Disconnect existing DatabaseAPI
    if _db_api is not None:
        try:
            _db_api.disconnect_db()
        except Exception:
            pass
        _db_api = None

    _ils_logstruct_api = None
    _ils_tasks_api = None

    # Update globals
    PSS_SERVER = server_url
    PSS_DB = db
    PSS_USER = user
    PSS_PASSWORD = password

    # Create new connections
    _get_client()
    _get_db_api()


def _handle_connection_status() -> list[TextContent]:
    connected = _client is not None and getattr(_client, 'connected', False)
    return _json_response({
        "connected": connected,
        "server": PSS_SERVER,
        "db": PSS_DB,
        "user": PSS_USER,
    })


def _handle_connect(arguments: dict) -> list[TextContent]:
    srv = arguments.get("server", PSS_SERVER)
    db = arguments.get("db", PSS_DB)
    user = arguments.get("user", PSS_USER)
    password = arguments.get("password", PSS_PASSWORD)

    try:
        _reconnect(srv, db, user, password)
        return _json_response({
            "connected": True,
            "server": srv,
            "db": db,
            "user": user,
        })
    except Exception as e:
        return _error_response(f"Connection failed: {e}")


# ==================== Schema handlers ====================

def _handle_list_categories() -> list[TextContent]:
    schema = _get_schema()
    categories = schema.get_categories()
    return _json_response(categories)


def _handle_search_entities(arguments: dict) -> list[TextContent]:
    keyword = arguments.get("keyword", "")
    if not keyword:
        return _error_response("keyword is required")
    schema = _get_schema()
    results = schema.search_entities(keyword)
    return _json_response(results)


def _handle_get_entity_schema(arguments: dict) -> list[TextContent]:
    entity_name = arguments.get("entity_name", "")
    if not entity_name:
        return _error_response("entity_name is required")
    schema = _get_schema()
    result = schema.get_entity_schema(entity_name)
    if result is None:
        return _error_response(f"Entity '{entity_name}' not found. Use schema_search to find the correct name.")
    return _json_response(result)


def _handle_get_entity_description(arguments: dict) -> list[TextContent]:
    entity_name = arguments.get("entity_name", "")
    if not entity_name:
        return _error_response("entity_name is required")
    schema = _get_schema()
    result = schema.get_entity_description(entity_name)
    if result is None:
        return _error_response(f"Entity '{entity_name}' not found.")
    return [TextContent(type="text", text=result)]


# ==================== Data handlers ====================

def _handle_query_instances(arguments: dict) -> list[TextContent]:
    entity_type = arguments.get("entity_type", "")
    if not entity_type:
        return _error_response("entity_type is required")

    filters = arguments.get("filters")
    limit = min(arguments.get("limit", 50), 200)

    client = _get_client()
    instances = client.query_instances(entity_type, filters=filters, size=limit)

    return _json_response({
        "entity_type": entity_type,
        "count": len(instances),
        "instances": [_simplify_instance(i) for i in instances],
    })


def _handle_get_instance(arguments: dict) -> list[TextContent]:
    sys_id = arguments.get("sys_id")
    if sys_id is None:
        return _error_response("sys_id is required")

    client = _get_client()
    instance = client.get_instance(int(sys_id))

    if instance is None:
        return _error_response(f"Instance with sys_id={sys_id} not found.")
    return _json_response(_simplify_instance(instance))


def _handle_execute_apl_query(arguments: dict) -> list[TextContent]:
    query = arguments.get("query", "").strip()
    if not query:
        return _error_response("query is required")

    query_upper = query.upper().lstrip()
    if not query_upper.startswith("SELECT"):
        return _error_response(
            "Only SELECT queries are allowed. "
            "The query must start with SELECT."
        )

    client = _get_client()
    result = client.query_apl(query)

    if "error" in result:
        return _error_response(f"APL query error: {result['error']}")

    instances = result.get("instances", [])
    return _json_response({
        "count_all": result.get("count_all", 0),
        "returned": len(instances),
        "instances": [_simplify_instance(i) for i in instances],
    })


# ==================== PDM handlers ====================

def _handle_pdm_search_products(arguments: dict) -> list[TextContent]:
    text = arguments.get("text", "")
    if not text:
        return _error_response("text is required")
    limit = arguments.get("limit", 50)

    db_api = _get_db_api()
    results = db_api.products_api.search_products(text, limit=limit)

    simplified = []
    for inst in results:
        attrs = inst.get("attributes", {})
        simplified.append({
            "sys_id": inst.get("id"),
            "id": attrs.get("id", ""),
            "name": attrs.get("name", ""),
        })

    return _json_response({
        "query": text,
        "count": len(simplified),
        "products": simplified,
    })


def _handle_pdm_get_product(arguments: dict) -> list[TextContent]:
    product_id = arguments.get("product_id")
    if product_id is None:
        return _error_response("product_id is required")

    db_api = _get_db_api()

    # Get product definition
    pdf = db_api.products_api.get_product_definition(int(product_id))
    if pdf is None:
        return _error_response(f"Product with sys_id={product_id} not found.")

    result = _simplify_instance(pdf)

    # Get characteristics
    chars = db_api.products_api.get_product_characteristics(int(product_id))
    result["characteristics"] = []
    for ch in chars:
        ch_attrs = ch.get("attributes", {})
        result["characteristics"].append({
            "sys_id": ch.get("id"),
            "name": ch_attrs.get("name", ""),
            "value": ch_attrs.get("value", ""),
            "type": ch_attrs.get("property_type", ""),
        })

    return _json_response(result)


def _handle_pdm_get_bom(arguments: dict) -> list[TextContent]:
    product_id = arguments.get("product_id")
    if product_id is None:
        return _error_response("product_id is required")

    db_api = _get_db_api()
    bom_items = db_api.products_api.get_bom_structure(int(product_id))

    components = []
    for item in bom_items:
        attrs = item.get("attributes", {})
        related = attrs.get("related_product_definition", {})
        unit = attrs.get("unit_component", {})
        components.append({
            "bom_item_sys_id": item.get("id"),
            "child_product_sys_id": related.get("id") if isinstance(related, dict) else related,
            "quantity": attrs.get("value_component"),
            "unit_sys_id": unit.get("id") if isinstance(unit, dict) else unit,
        })

    return _json_response({
        "parent_product_id": product_id,
        "components_count": len(components),
        "components": components,
    })


def _handle_pdm_get_folders(arguments: dict) -> list[TextContent]:
    name_filter = arguments.get("name_filter")

    client = _get_client()
    filters = None
    if name_filter:
        filters = f'.name LIKE "{name_filter}"'

    folders = client.query_instances("apl_folder", filters=filters, size=200)

    simplified = []
    for f in folders:
        attrs = f.get("attributes", {})
        simplified.append({
            "sys_id": f.get("id"),
            "name": attrs.get("name", ""),
            "parent": attrs.get("parent", {}).get("id") if isinstance(attrs.get("parent"), dict) else attrs.get("parent"),
        })

    return _json_response({
        "count": len(simplified),
        "folders": simplified,
    })


def _handle_pdm_get_folder_contents(arguments: dict) -> list[TextContent]:
    folder_id = arguments.get("folder_id")
    if folder_id is None:
        return _error_response("folder_id is required")

    db_api = _get_db_api()
    result = db_api.folders_api.get_folder_with_content_types(int(folder_id))

    if result is None:
        return _error_response(f"Folder with sys_id={folder_id} not found.")
    return _json_response(result)


def _handle_pdm_get_documents(arguments: dict) -> list[TextContent]:
    item_id = arguments.get("item_id")
    if item_id is None:
        return _error_response("item_id is required")

    client = _get_client()
    query = (
        f"SELECT NO_CASE Ext_ FROM Ext_{{apl_document_reference"
        f"(.source = #{item_id})"
        f"}} END_SELECT"
    )
    result = client.query_apl(query)
    refs = result.get("instances", [])

    documents = []
    for ref in refs:
        attrs = ref.get("attributes", {})
        doc = attrs.get("assigned_document", {})
        documents.append({
            "ref_sys_id": ref.get("id"),
            "document_sys_id": doc.get("id") if isinstance(doc, dict) else doc,
            "role": attrs.get("role", ""),
        })

    return _json_response({
        "item_id": item_id,
        "documents_count": len(documents),
        "documents": documents,
    })


def _handle_pdm_get_characteristics(arguments: dict) -> list[TextContent]:
    product_id = arguments.get("product_id")
    if product_id is None:
        return _error_response("product_id is required")

    db_api = _get_db_api()
    chars = db_api.products_api.get_product_characteristics(int(product_id))

    result = []
    for ch in chars:
        ch_attrs = ch.get("attributes", {})
        result.append({
            "sys_id": ch.get("id"),
            "name": ch_attrs.get("name", ""),
            "value": ch_attrs.get("value", ""),
            "type": ch_attrs.get("property_type", ""),
        })

    return _json_response({
        "product_id": product_id,
        "count": len(result),
        "characteristics": result,
    })


def _handle_pdm_list_characteristic_types(arguments: dict) -> list[TextContent]:
    """Список типов характеристик (apl_characteristic)."""
    limit = arguments.get("limit", 500)
    db_api = _get_db_api()
    instances = db_api.characteristic_api.list_characteristics(limit=limit)

    result = []
    for inst in instances:
        attrs = inst.get("attributes", {})
        unit_ref = attrs.get("unit", {})
        result.append({
            "sys_id": inst.get("id"),
            "id": attrs.get("id", ""),
            "name": attrs.get("name", ""),
            "description": attrs.get("description", ""),
            "code": attrs.get("code", ""),
            "unit_sys_id": unit_ref.get("id") if isinstance(unit_ref, dict) else None,
        })

    return _json_response({
        "count": len(result),
        "characteristic_types": result,
    })


def _handle_pdm_get_characteristic_values(arguments: dict) -> list[TextContent]:
    """Значения характеристик (apl_characteristic_value) для заданного объекта."""
    item_id = arguments.get("item_id")
    if item_id is None:
        return _error_response("item_id is required")

    db_api = _get_db_api()
    instances = db_api.characteristic_api.get_values_for_item(int(item_id))

    result = []
    for inst in instances:
        parsed = db_api.characteristic_api._extract_display_value(inst)
        attrs = inst.get("attributes", {})
        char_ref = attrs.get("characteristic", {})
        result.append({
            "sys_id": inst.get("id"),
            "subtype": inst.get("type", ""),
            "characteristic_sys_id": char_ref.get("id") if isinstance(char_ref, dict) else None,
            "scope": parsed["scope"],
            "value": parsed["value"],
            "unit": parsed["unit"],
        })

    return _json_response({
        "item_id": item_id,
        "count": len(result),
        "characteristic_values": result,
    })


def _handle_pdm_find_by_code(arguments: dict) -> list[TextContent]:
    code = arguments.get("code", "")
    if not code:
        return _error_response("code is required")

    db_api = _get_db_api()
    pdf_id = db_api.products_api.find_product_version_by_code(code)

    if pdf_id is None:
        return _json_response({"code": code, "found": False, "sys_id": None})
    return _json_response({"code": code, "found": True, "sys_id": pdf_id})


def _handle_pdm_get_product_full_info(arguments: dict) -> list[TextContent]:
    product_id = arguments.get("product_id")
    if product_id is None:
        return _error_response("product_id is required")

    db_api = _get_db_api()
    result = db_api.products_api.get_product_full_info(int(product_id))
    if result is None:
        return _error_response(f"Product with sys_id={product_id} not found.")

    return _json_response(result)


# ==================== PDM handlers — Processes, Organizations, Resources ====================

def _handle_pdm_get_processes(arguments: dict) -> list[TextContent]:
    product_id = arguments.get("product_id")
    if product_id is None:
        return _error_response("product_id is required")

    client = _get_client()
    # Find processes linked to product via apl_applied_action
    query = (
        f"SELECT NO_CASE Ext_ FROM Ext_{{apl_applied_action"
        f"(.items = #{product_id})"
        f"}} END_SELECT"
    )
    result = client.query_apl(query, size=200)
    applied_actions = result.get("instances", [])

    processes = []
    for aa in applied_actions:
        attrs = aa.get("attributes", {})
        method = attrs.get("method", {})
        method_id = method.get("id") if isinstance(method, dict) else method
        processes.append({
            "applied_action_sys_id": aa.get("id"),
            "process_sys_id": method_id,
            "name": attrs.get("name", ""),
        })

    # Enrich with process details if we have method IDs
    method_ids = [p["process_sys_id"] for p in processes if p["process_sys_id"]]
    if method_ids:
        ids_str = ", ".join(f"#{mid}" for mid in method_ids)
        q2 = f"SELECT NO_CASE Ext_ FROM Ext_{{{ids_str}}} END_SELECT"
        r2 = client.query_apl(q2, size=200)
        method_map = {}
        for inst in r2.get("instances", []):
            method_map[inst.get("id")] = inst

        for p in processes:
            mid = p["process_sys_id"]
            if mid in method_map:
                m_attrs = method_map[mid].get("attributes", {})
                p["name"] = m_attrs.get("name", p["name"])
                p["type"] = method_map[mid].get("type", "")
                p["description"] = m_attrs.get("description", "")

    return _json_response({
        "product_id": product_id,
        "count": len(processes),
        "processes": processes,
    })


def _handle_pdm_get_process_hierarchy(arguments: dict) -> list[TextContent]:
    process_id = arguments.get("process_id")
    if process_id is None:
        return _error_response("process_id is required")

    client = _get_client()

    # Get the process itself
    process = client.get_instance(int(process_id))
    if process is None:
        return _error_response(f"Process with sys_id={process_id} not found.")

    proc_attrs = process.get("attributes", {})
    elements = proc_attrs.get("elements", [])

    # Collect child IDs
    child_ids = []
    if isinstance(elements, list):
        for el in elements:
            if isinstance(el, dict) and "id" in el:
                child_ids.append(el["id"])
            elif isinstance(el, (int, str)):
                child_ids.append(int(el))

    # Batch-fetch children
    children = []
    if child_ids:
        ids_str = ", ".join(f"#{cid}" for cid in child_ids)
        q = f"SELECT NO_CASE Ext_ FROM Ext_{{{ids_str}}} END_SELECT"
        r = client.query_apl(q, size=200)
        for inst in r.get("instances", []):
            i_attrs = inst.get("attributes", {})
            sub_elements = i_attrs.get("elements", [])
            children.append({
                "sys_id": inst.get("id"),
                "type": inst.get("type", ""),
                "name": i_attrs.get("name", ""),
                "description": i_attrs.get("description", ""),
                "has_children": bool(sub_elements),
                "children_count": len(sub_elements) if isinstance(sub_elements, list) else 0,
            })

    return _json_response({
        "process": {
            "sys_id": process.get("id"),
            "type": process.get("type", ""),
            "name": proc_attrs.get("name", ""),
            "description": proc_attrs.get("description", ""),
        },
        "children_count": len(children),
        "children": children,
    })


def _handle_pdm_get_process_details(arguments: dict) -> list[TextContent]:
    process_id = arguments.get("process_id")
    if process_id is None:
        return _error_response("process_id is required")

    client = _get_client()

    # Get the process
    process = client.get_instance(int(process_id))
    if process is None:
        return _error_response(f"Process with sys_id={process_id} not found.")

    result = _simplify_instance(process)

    # Get documents via apl_document_reference
    doc_query = (
        f"SELECT NO_CASE Ext_ FROM Ext_{{apl_document_reference"
        f"(.source = #{process_id})"
        f"}} END_SELECT"
    )
    doc_result = client.query_apl(doc_query)
    docs = []
    for ref in doc_result.get("instances", []):
        ref_attrs = ref.get("attributes", {})
        doc = ref_attrs.get("assigned_document", {})
        docs.append({
            "ref_sys_id": ref.get("id"),
            "document_sys_id": doc.get("id") if isinstance(doc, dict) else doc,
            "role": ref_attrs.get("role", ""),
        })
    result["documents"] = docs

    # Get resources (materials, norms)
    res_query = (
        f"SELECT NO_CASE Ext_ FROM Ext_{{apl_action_resource"
        f"(.of_action = #{process_id})"
        f"}} END_SELECT"
    )
    res_result = client.query_apl(res_query)
    resources = []
    for res in res_result.get("instances", []):
        res_attrs = res.get("attributes", {})
        res_type = res_attrs.get("type_of_resource", {})
        res_obj = res_attrs.get("object_of_resource", {})
        unit = res_attrs.get("unit_component", {})
        resources.append({
            "sys_id": res.get("id"),
            "type_sys_id": res_type.get("id") if isinstance(res_type, dict) else res_type,
            "type_name": res_type.get("name", "") if isinstance(res_type, dict) else "",
            "object_sys_id": res_obj.get("id") if isinstance(res_obj, dict) else res_obj,
            "value": res_attrs.get("value_component"),
            "unit_sys_id": unit.get("id") if isinstance(unit, dict) else unit,
        })
    result["resources"] = resources

    return _json_response(result)


def _handle_pdm_list_organizations(arguments: dict) -> list[TextContent]:
    name_filter = arguments.get("name_filter")
    limit = arguments.get("limit", 100)

    db_api = _get_db_api()
    filters = None
    if name_filter:
        filters = f'.name LIKE "*{name_filter}*"'

    orgs = db_api.orgs_api.list_organizations(filters=filters, limit=limit)

    simplified = []
    for org in orgs:
        attrs = org.get("attributes", {})
        simplified.append({
            "sys_id": org.get("id"),
            "id": attrs.get("id", ""),
            "name": attrs.get("name", ""),
            "description": attrs.get("description", ""),
        })

    return _json_response({
        "count": len(simplified),
        "organizations": simplified,
    })


def _handle_pdm_get_organization(arguments: dict) -> list[TextContent]:
    org_id = arguments.get("org_id")
    if org_id is None:
        return _error_response("org_id is required")

    db_api = _get_db_api()
    org = db_api.orgs_api.get_organization(int(org_id))

    if org is None:
        return _error_response(f"Organization with sys_id={org_id} not found.")
    return _json_response(_simplify_instance(org))


def _handle_pdm_get_process_resources(arguments: dict) -> list[TextContent]:
    process_id = arguments.get("process_id")
    if process_id is None:
        return _error_response("process_id is required")

    client = _get_client()
    query = (
        f"SELECT NO_CASE Ext_ FROM Ext_{{apl_action_resource"
        f"(.of_action = #{process_id})"
        f"}} END_SELECT"
    )
    result = client.query_apl(query)
    instances = result.get("instances", [])

    resources = []
    for res in instances:
        res_attrs = res.get("attributes", {})
        res_type = res_attrs.get("type_of_resource", {})
        res_obj = res_attrs.get("object_of_resource", {})
        unit = res_attrs.get("unit_component", {})
        resources.append({
            "sys_id": res.get("id"),
            "type_sys_id": res_type.get("id") if isinstance(res_type, dict) else res_type,
            "type_name": res_type.get("name", "") if isinstance(res_type, dict) else "",
            "object_sys_id": res_obj.get("id") if isinstance(res_obj, dict) else res_obj,
            "object_name": res_obj.get("name", "") if isinstance(res_obj, dict) else "",
            "value": res_attrs.get("value_component"),
            "unit_sys_id": unit.get("id") if isinstance(unit, dict) else unit,
            "unit_name": unit.get("name", "") if isinstance(unit, dict) else "",
        })

    return _json_response({
        "process_id": process_id,
        "count": len(resources),
        "resources": resources,
    })


def _handle_pdm_list_units(arguments: dict) -> list[TextContent]:
    limit = arguments.get("limit", 100)

    client = _get_client()
    units = client.query_instances("apl_unit", size=limit)

    simplified = []
    for u in units:
        attrs = u.get("attributes", {})
        simplified.append({
            "sys_id": u.get("id"),
            "id": attrs.get("id", ""),
            "name": attrs.get("name", ""),
        })

    return _json_response({
        "count": len(simplified),
        "units": simplified,
    })


# ==================== ILS — Logistic structure handlers ====================

def _handle_ils_find_final_products(arguments: dict) -> list[TextContent]:
    api = _get_ils_logstruct_api()
    result = api.find_final_products(
        search_text=arguments.get("search_text", ""),
        limit=arguments.get("limit", 50),
    )
    return _json_response(result)


def _handle_ils_get_logistic_structure(arguments: dict) -> list[TextContent]:
    component_id = arguments.get("component_id")
    if component_id is None:
        return _error_response("component_id is required")
    api = _get_ils_logstruct_api()
    result = api.get_logistic_structure(
        sys_id=int(component_id),
        max_depth=arguments.get("max_depth", 10),
    )
    return _json_response(result)


def _handle_ils_get_tasks(arguments: dict) -> list[TextContent]:
    component_id = arguments.get("component_id")
    if component_id is None:
        return _error_response("component_id is required")
    api = _get_ils_tasks_api()
    result = api.get_tasks(int(component_id))
    return _json_response(result)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

async def main():
    """Run the MCP server with stdio transport."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
        stream=sys.stderr,  # MCP uses stdout for protocol; logs go to stderr
    )
    logger.info("Starting PSS MCP server...")
    logger.info("PSS_SERVER=%s, PSS_DB=%s, PSS_USER=%s", PSS_SERVER, PSS_DB, PSS_USER)

    async with stdio_server() as (read, write):
        await server.run(read, write, server.create_initialization_options())


if __name__ == "__main__":
    asyncio.run(main())
