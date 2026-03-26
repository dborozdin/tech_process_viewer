"""
Tool executor: routes tool calls from the agent to PSS API and Schema.
"""

import json
import logging
import re
from typing import Any

from ILS_reports_agent.pss.api_client import PSSClient
from ILS_reports_agent.pss.schema import Schema
from ILS_reports_agent.agent.knowledge import KnowledgeStore
from api.pss_logstruct_api import LogStructAPI

logger = logging.getLogger("ils.tools")


class ToolExecutor:
    """Executes agent tool calls against PSS API and Schema."""

    def __init__(self, pss_client: PSSClient, schema: Schema,
                 knowledge: KnowledgeStore = None):
        self.pss = pss_client
        self.schema = schema
        self.knowledge = knowledge
        self.logstruct_api = LogStructAPI(pss_client)

    def execute(self, tool_name: str, arguments: dict) -> str:
        """Execute a tool and return result as JSON string.

        Args:
            tool_name: Name of the tool to execute.
            arguments: Tool arguments dict.

        Returns:
            JSON string with the tool result.
        """
        logger.info(f"Executing tool: {tool_name}({json.dumps(arguments, ensure_ascii=False)[:200]})")

        try:
            handler = getattr(self, f"_tool_{tool_name}", None)
            if handler is None:
                return json.dumps({"error": f"Unknown tool: {tool_name}"}, ensure_ascii=False)
            result = handler(**arguments)
            result_str = json.dumps(result, ensure_ascii=False, default=str)
            # Smart truncation for large results
            if len(result_str) > 25000:
                logger.warning(f"Tool {tool_name} result truncated from {len(result_str)} chars")
                if isinstance(result, dict) and "tree" in result:
                    # For tree results, truncate the tree array intelligently
                    truncated = {
                        **result,
                        "tree": result["tree"][:50],
                        "_truncated": True,
                        "_note": (f"Показано 50 из {len(result['tree'])} элементов. "
                                  "Уточните запрос или уменьшите max_depth."),
                    }
                    result_str = json.dumps(truncated, ensure_ascii=False, default=str)
                else:
                    result_str = result_str[:25000] + '... (truncated)'
            return result_str
        except Exception as e:
            logger.error(f"Tool {tool_name} failed: {e}", exc_info=True)
            return json.dumps({"error": str(e)}, ensure_ascii=False)

    # ------------------------------------------------------------------
    # Schema navigation tools
    # ------------------------------------------------------------------

    def _tool_list_entity_categories(self) -> list:
        categories = self.schema.get_categories()
        # Return compact summary
        return [
            {"section": c['name'], "entity_count": c['count'], "entities": c['entities'][:10]}
            for c in categories
        ]

    def _tool_search_entities(self, keyword: str) -> list:
        return self.schema.search_entities(keyword, limit=15)

    def _tool_get_entity_schema(self, entity_name: str) -> dict:
        result = self.schema.get_entity_schema(entity_name)
        if result is None:
            return {"error": f"Entity '{entity_name}' not found in schema"}
        return result

    def _tool_get_entity_description(self, entity_name: str) -> dict:
        desc = self.schema.get_entity_description(entity_name)
        if desc is None:
            return {"error": f"Entity '{entity_name}' not found"}
        return {"description": desc}

    def _tool_get_reverse_references(self, entity_name: str) -> dict:
        refs = self.schema.get_reverse_references(entity_name)
        if not refs:
            return {"entity": entity_name, "referenced_by": [], "count": 0}
        return {"entity": entity_name, "referenced_by": refs, "count": len(refs)}

    def _tool_save_knowledge(self, topic: str, content: str) -> dict:
        if self.knowledge is None:
            return {"error": "Knowledge store not configured"}
        entry = self.knowledge.add(topic, content)
        return {"saved": True, "topic": entry["topic"]}

    # ------------------------------------------------------------------
    # Data access tools
    # ------------------------------------------------------------------

    def _tool_count_instances(self, entity_type: str, filters: str = None) -> dict:
        if not self.pss.connected:
            return {"error": "Not connected to PSS database"}
        if filters:
            query = f"SELECT NO_CASE Ext_ FROM Ext_{{{entity_type}({filters})}} END_SELECT"
        else:
            query = f"SELECT NO_CASE Ext_ FROM Ext_{{{entity_type}}} END_SELECT"
        result = self.pss.query_apl(query, size=1, all_attrs=False)
        if result.get('error'):
            return {
                "error": f"Query syntax error: {result['error']}",
                "query": query,
                "hint": "Check APL filter syntax. Use .field = \"value\" for strings, "
                        ".field = value for numbers/booleans. "
                        "LIKE is not supported — use simple equality or omit the filter.",
            }
        return {"entity_type": entity_type, "count": result.get('count_all', 0)}

    def _tool_query_instances(self, entity_type: str, filters: str = None,
                              start: int = 0, size: int = 50) -> dict:
        if not self.pss.connected:
            return {"error": "Not connected to PSS database"}

        size = min(size, 200)  # Cap at 200

        # Build query and check for errors
        if filters:
            query = f"SELECT NO_CASE Ext_ FROM Ext_{{{entity_type}({filters})}} END_SELECT"
        else:
            query = f"SELECT NO_CASE Ext_ FROM Ext_{{{entity_type}}} END_SELECT"
        result = self.pss.query_apl(query, start=start, size=size)
        if result.get('error'):
            return {
                "error": f"Query syntax error: {result['error']}",
                "query": query,
                "hint": "Check APL filter syntax. Use .field = \"value\" for strings, "
                        ".field = value for numbers/booleans. "
                        "LIKE is not supported — use simple equality or omit the filter.",
            }
        instances = result.get('instances', [])

        # Simplify instance data for LLM context
        simplified = []
        for inst in instances:
            item = {"sys_id": inst.get("id"), "type": inst.get("type")}
            attrs = inst.get("attributes", {})
            # Flatten simple attributes, summarize references
            for k, v in attrs.items():
                if isinstance(v, dict) and 'id' in v:
                    item[k] = f"→#{v['id']} ({v.get('type', '')})"
                elif isinstance(v, list):
                    item[k] = f"[{len(v)} items]"
                else:
                    item[k] = v
            simplified.append(item)

        return {
            "entity_type": entity_type,
            "count": len(simplified),
            "instances": simplified,
        }

    def _tool_get_instance_by_id(self, sys_id: int, entity_type: str = None) -> dict:
        if not self.pss.connected:
            return {"error": "Not connected to PSS database"}

        instance = self.pss.get_instance(sys_id, entity_type)
        if instance is None:
            return {"error": f"Instance #{sys_id} not found"}

        # Simplify for LLM
        attrs = instance.get("attributes", {})
        result = {"sys_id": instance.get("id"), "type": instance.get("type")}
        for k, v in attrs.items():
            if isinstance(v, dict) and 'id' in v:
                result[k] = f"→#{v['id']} ({v.get('type', '')})"
            elif isinstance(v, list):
                items_preview = []
                for item in v[:5]:
                    if isinstance(item, dict) and 'id' in item:
                        items_preview.append(f"#{item['id']}")
                    else:
                        items_preview.append(str(item))
                suffix = f"... +{len(v)-5}" if len(v) > 5 else ""
                result[k] = f"[{', '.join(items_preview)}{suffix}]"
            else:
                result[k] = v

        return result

    def _tool_execute_apl_query(self, query: str, size: int = 100) -> dict:
        if not self.pss.connected:
            return {"error": "Not connected to PSS database"}

        # Security: only allow SELECT queries
        query_upper = query.strip().upper()
        if not query_upper.startswith("SELECT"):
            return {"error": "Only SELECT queries are allowed. Query must start with SELECT."}

        size = min(size, 500)
        result = self.pss.query_apl(query, size=size)
        if result.get('error'):
            return {
                "error": f"Query syntax error: {result['error']}",
                "query": query,
                "hint": "Check APL query syntax. Correct format: "
                        "SELECT NO_CASE Ext_ FROM Ext_{entity_type(.field = \"value\")} END_SELECT",
            }
        instances = result.get('instances', [])

        # Simplify
        simplified = []
        for inst in instances:
            item = {"sys_id": inst.get("id"), "type": inst.get("type")}
            attrs = inst.get("attributes", {})
            for k, v in attrs.items():
                if isinstance(v, dict) and 'id' in v:
                    item[k] = f"→#{v['id']} ({v.get('type', '')})"
                elif isinstance(v, list):
                    item[k] = f"[{len(v)} items]"
                else:
                    item[k] = v
            simplified.append(item)

        return {
            "count_all": result.get('count_all', 0),
            "returned": len(simplified),
            "instances": simplified,
        }

    # ------------------------------------------------------------------
    # High-level domain tools
    # ------------------------------------------------------------------

    def _tool_get_logistic_structure(self, component_designation: str = "",
                                     max_depth: int = 10,
                                     sys_id: int = None) -> dict:
        if not self.pss.connected:
            return {"error": "Not connected to PSS database"}
        if not component_designation and sys_id is None:
            return {"error": "Укажи component_designation или sys_id компонента"}
        return self.logstruct_api.get_logistic_structure(
            component_designation, max_depth=max_depth, sys_id=sys_id
        )

    # ------------------------------------------------------------------
    # Report formatting tool
    # ------------------------------------------------------------------

    def _tool_format_html_report(self, title: str, columns: list,
                                  rows: list, description: str = "") -> dict:
        """Generate an HTML report table."""
        html_parts = [
            '<div class="report">',
            f'<h2>{_escape(title)}</h2>',
        ]
        if description:
            html_parts.append(f'<p>{_escape(description)}</p>')

        html_parts.append('<table border="1" cellpadding="5" cellspacing="0" '
                          'style="border-collapse:collapse; width:100%">')

        # Header
        html_parts.append('<thead><tr>')
        for col in columns:
            html_parts.append(f'<th style="background:#f0f0f0">{_escape(str(col))}</th>')
        html_parts.append('</tr></thead>')

        # Rows
        html_parts.append('<tbody>')
        for row in rows:
            html_parts.append('<tr>')
            for cell in row:
                html_parts.append(f'<td>{_escape(str(cell))}</td>')
            html_parts.append('</tr>')
        html_parts.append('</tbody></table>')

        html_parts.append(f'<p><em>Всего записей: {len(rows)}</em></p>')
        html_parts.append('</div>')

        return {"html": "\n".join(html_parts)}


def _escape(text: str) -> str:
    """Escape HTML special characters."""
    return (text
            .replace('&', '&amp;')
            .replace('<', '&lt;')
            .replace('>', '&gt;')
            .replace('"', '&quot;'))
