"""
MCP server for Claude Code integration with PSS database.

Exposes PSS data model browsing and querying capabilities via
the Model Context Protocol (stdio transport).

Environment variables:
    PSS_SERVER   — PSS REST API base URL (default: http://localhost:7239)
    PSS_DB       — Database name (default: ils_lessons12)
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

from ILS_reports_agent.pss.api_client import PSSClient
from ILS_reports_agent.pss.schema import get_schema

logger = logging.getLogger("mcp.pss")

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

PSS_SERVER = os.environ.get("PSS_SERVER", "http://localhost:7239")
PSS_DB = os.environ.get("PSS_DB", "ils_lessons12")
PSS_USER = os.environ.get("PSS_USER", "Administrator")
PSS_PASSWORD = os.environ.get("PSS_PASSWORD", "")

# Schema file paths (relative to express_api/)
_EXPRESS_API_ROOT = os.path.dirname(_PROJECT_ROOT)
DICT_FILE_PATH = os.path.join(_EXPRESS_API_ROOT, "doc", "apl_pss_a.dict")
HTML_SCHEMA_PATH = os.path.join(_PROJECT_ROOT, "db_schema_doc", "apl_pss_a_1419_data.htm")

# ---------------------------------------------------------------------------
# Globals
# ---------------------------------------------------------------------------

_client: PSSClient | None = None
_schema = None

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


def _json_response(data) -> list[TextContent]:
    """Wrap data as MCP TextContent JSON response."""
    return [TextContent(type="text", text=json.dumps(data, ensure_ascii=False, indent=2))]


def _error_response(message: str) -> list[TextContent]:
    """Return an error response."""
    return [TextContent(type="text", text=json.dumps({"error": message}, ensure_ascii=False))]


# ---------------------------------------------------------------------------
# Tool definitions
# ---------------------------------------------------------------------------

TOOLS = [
    Tool(
        name="list_entity_categories",
        description=(
            "Просмотр категорий данных PSS. Возвращает разделы схемы данных "
            "с перечнем типов сущностей в каждом разделе."
        ),
        inputSchema={
            "type": "object",
            "properties": {},
            "required": [],
        },
    ),
    Tool(
        name="search_entities",
        description=(
            "Поиск типов сущностей по ключевому слову. Ищет по имени, описанию, "
            "разделу и атрибутам. Возвращает список совпадений с оценкой релевантности."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "keyword": {
                    "type": "string",
                    "description": "Ключевое слово для поиска (на русском или английском)",
                },
            },
            "required": ["keyword"],
        },
    ),
    Tool(
        name="get_entity_schema",
        description=(
            "Получить схему сущности: атрибуты, типы данных, связи с другими сущностями. "
            "Включает унаследованные атрибуты и обратные ссылки."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "entity_name": {
                    "type": "string",
                    "description": "Имя типа сущности (например, 'product_version')",
                },
            },
            "required": ["entity_name"],
        },
    ),
    Tool(
        name="get_entity_description",
        description=(
            "Получить описание сущности на русском языке: назначение, атрибуты, связи."
        ),
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
    Tool(
        name="query_instances",
        description=(
            "Запросить экземпляры сущности из базы данных с опциональными фильтрами APL. "
            "Пример фильтра: '.name LIKE \"деталь*\"'"
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "entity_type": {
                    "type": "string",
                    "description": "Имя типа сущности (например, 'organization')",
                },
                "filters": {
                    "type": "string",
                    "description": "APL-условие фильтрации (опционально). Пример: '.name LIKE \"test*\"'",
                },
                "limit": {
                    "type": "integer",
                    "description": "Максимальное количество результатов (по умолчанию 50, макс. 200)",
                    "default": 50,
                },
            },
            "required": ["entity_type"],
        },
    ),
    Tool(
        name="get_instance",
        description=(
            "Получить один экземпляр сущности по его системному идентификатору (sys_id)."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "sys_id": {
                    "type": "integer",
                    "description": "Системный идентификатор экземпляра",
                },
            },
            "required": ["sys_id"],
        },
    ),
    Tool(
        name="execute_apl_query",
        description=(
            "Выполнить APL-запрос SELECT к базе данных PSS. "
            "Только SELECT-запросы; модификация данных запрещена."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "APL SELECT-запрос. Пример: SELECT NO_CASE Ext_ FROM Ext_{organization} END_SELECT",
                },
            },
            "required": ["query"],
        },
    ),
    Tool(
        name="get_folder_tree",
        description=(
            "Получить иерархию папок (folder_version) из базы PSS. "
            "Возвращает дерево вложенных папок начиная от корня."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "root": {
                    "type": "string",
                    "description": "Имя или фильтр корневой папки (опционально). Если не указано, возвращает все корневые папки.",
                },
            },
            "required": [],
        },
    ),
    Tool(
        name="get_product_tree",
        description=(
            "Получить дерево входимости изделия (BOM). "
            "Возвращает иерархическую структуру компонентов изделия."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "product_id": {
                    "type": "integer",
                    "description": "sys_id версии изделия (product_version)",
                },
            },
            "required": ["product_id"],
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
        if name == "list_entity_categories":
            return _handle_list_categories()
        elif name == "search_entities":
            return _handle_search_entities(arguments)
        elif name == "get_entity_schema":
            return _handle_get_entity_schema(arguments)
        elif name == "get_entity_description":
            return _handle_get_entity_description(arguments)
        elif name == "query_instances":
            return _handle_query_instances(arguments)
        elif name == "get_instance":
            return _handle_get_instance(arguments)
        elif name == "execute_apl_query":
            return _handle_execute_apl_query(arguments)
        elif name == "get_folder_tree":
            return _handle_get_folder_tree(arguments)
        elif name == "get_product_tree":
            return _handle_get_product_tree(arguments)
        else:
            return _error_response(f"Unknown tool: {name}")
    except ConnectionError as e:
        return _error_response(f"PSS connection error: {e}")
    except Exception as e:
        logger.exception("Tool %s failed", name)
        return _error_response(f"Tool execution error: {e}")


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
        return _error_response(f"Entity '{entity_name}' not found. Use search_entities to find the correct name.")
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
        "instances": instances,
    })


def _handle_get_instance(arguments: dict) -> list[TextContent]:
    sys_id = arguments.get("sys_id")
    if sys_id is None:
        return _error_response("sys_id is required")

    client = _get_client()
    instance = client.get_instance(int(sys_id))

    if instance is None:
        return _error_response(f"Instance with sys_id={sys_id} not found.")
    return _json_response(instance)


def _handle_execute_apl_query(arguments: dict) -> list[TextContent]:
    query = arguments.get("query", "").strip()
    if not query:
        return _error_response("query is required")

    # Validate: only SELECT queries allowed
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

    return _json_response({
        "count_all": result.get("count_all", 0),
        "returned": len(result.get("instances", [])),
        "instances": result.get("instances", []),
    })


def _handle_get_folder_tree(arguments: dict) -> list[TextContent]:
    root_filter = arguments.get("root")

    client = _get_client()

    # Query folder_version entities
    filters = None
    if root_filter:
        filters = f'.name LIKE "{root_filter}*"'

    folders = client.query_instances("folder_version", filters=filters, size=200)

    return _json_response({
        "count": len(folders),
        "folders": folders,
    })


def _handle_get_product_tree(arguments: dict) -> list[TextContent]:
    product_id = arguments.get("product_id")
    if product_id is None:
        return _error_response("product_id is required")

    client = _get_client()

    # Get root product
    root = client.get_instance(int(product_id))
    if root is None:
        return _error_response(f"Product with sys_id={product_id} not found.")

    # Build BOM tree by querying product_structure for this product
    query = (
        f"SELECT NO_CASE Ext_ FROM Ext_{{product_structure"
        f"(.parent_product_version = #{product_id})"
        f"}} END_SELECT"
    )
    result = client.query_apl(query, size=200)
    children = result.get("instances", [])

    return _json_response({
        "root": root,
        "children_count": len(children),
        "children": children,
    })


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
