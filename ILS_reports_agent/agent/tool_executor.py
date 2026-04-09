"""
Tool executor: routes all tool calls through MCP bridge.
"""

import json
import logging

from ILS_reports_agent.pss.mcp_bridge import MCPBridge

logger = logging.getLogger("ils.tools")


class ToolExecutor:
    """Executes tool calls via MCP bridge."""

    def __init__(self, mcp_bridge: MCPBridge, **_ignored):
        self.mcp = mcp_bridge

    def execute(self, tool_name: str, arguments: dict) -> str:
        """Execute a tool and return result as JSON string."""
        # Normalize: some LLMs add namespace prefixes like "pdm:pdm_search"
        if ":" in tool_name:
            tool_name = tool_name.rsplit(":", 1)[-1]

        logger.info("Executing tool: %s(%s)",
                     tool_name,
                     json.dumps(arguments, ensure_ascii=False)[:200])

        try:
            if tool_name in self.mcp.tool_names:
                return self._truncate(
                    tool_name, self.mcp.call_tool(tool_name, arguments))

            # Fuzzy match: LLMs sometimes invent similar names
            best = self._fuzzy_match(tool_name)
            if best:
                logger.warning("Fuzzy matched '%s' -> '%s'", tool_name, best)
                return self._truncate(
                    best, self.mcp.call_tool(best, arguments))

            return json.dumps({"error": f"Unknown tool: {tool_name}"},
                              ensure_ascii=False)

        except Exception as e:
            logger.error("Tool %s failed: %s", tool_name, e, exc_info=True)
            return json.dumps({"error": str(e)}, ensure_ascii=False)

    def _truncate(self, tool_name: str, result_str: str,
                  max_chars: int = 15000) -> str:
        """Truncate large results to fit LLM context."""
        if len(result_str) <= max_chars:
            return result_str
        logger.warning("Result for %s truncated: %d -> %d chars",
                       tool_name, len(result_str), max_chars)
        try:
            data = json.loads(result_str)
            if isinstance(data, dict) and "tree" in data:
                tree = data["tree"]
                data["tree"] = tree[:30]
                data["_truncated"] = True
                data["_total"] = len(tree)
                return json.dumps(data, ensure_ascii=False, default=str)
        except (json.JSONDecodeError, ValueError):
            pass
        return result_str[:max_chars] + '... (truncated)'

    def _fuzzy_match(self, tool_name: str) -> str | None:
        """Find closest MCP tool name by word overlap."""
        words = set(tool_name.lower().replace("-", "_").split("_"))
        best_name = None
        best_score = (0, 0)
        for name in self.mcp.tool_names:
            name_words = set(name.lower().replace("-", "_").split("_"))
            overlap = len(words & name_words)
            score = (overlap, len(name_words))
            if overlap >= 2 and score > best_score:
                best_score = score
                best_name = name
        return best_name
