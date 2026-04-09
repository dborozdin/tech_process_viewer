"""
Bridge to MCP server tools via direct import.

Instead of spawning MCP server as a subprocess (stdio transport has issues
on Windows), we import the server module directly and call its async
call_tool dispatcher via asyncio.run().
"""

import asyncio
import importlib
import json
import logging
import os
import sys
from typing import Any

logger = logging.getLogger("ils.mcp_bridge")

# Tools that the agent should NOT see (connection is managed by the app)
_EXCLUDED_TOOLS = {"connect", "connection_status"}


class MCPBridge:
    """Bridge to MCP server tools via direct import.

    Imports the MCP server module, reads its TOOLS list, and calls the
    async call_tool() dispatcher synchronously via asyncio.

    Usage::

        bridge = MCPBridge(
            pss_server="http://localhost:7239",
            pss_db="ils_lessons12",
            pss_user="Administrator",
        )
        bridge.start()
        tools = bridge.tools     # OpenAI function-calling format
        result = bridge.call_tool("pdm_search_products", {"text": "Двигатель"})
        bridge.stop()
    """

    def __init__(
        self,
        pss_server: str = "http://localhost:7239",
        pss_db: str = "ils_lessons12",
        pss_user: str = "Administrator",
        pss_password: str = "",
        project_root: str | None = None,
    ):
        self._pss_server = pss_server
        self._pss_db = pss_db
        self._pss_user = pss_user
        self._pss_password = pss_password
        self._project_root = project_root

        self._call_tool_fn = None  # async call_tool from server module
        self._mcp_tools: list = []
        self._openai_tools: list[dict] | None = None
        self._tool_name_set: set[str] | None = None

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def start(self) -> None:
        """Import MCP server module and read tool definitions."""
        # Ensure project root is on sys.path so mcp_server imports work
        if self._project_root and self._project_root not in sys.path:
            sys.path.insert(0, self._project_root)

        # Set env vars so MCP server module picks up our PSS config
        os.environ["PSS_SERVER"] = self._pss_server
        os.environ["PSS_DB"] = self._pss_db
        os.environ["PSS_USER"] = self._pss_user
        os.environ["PSS_PASSWORD"] = self._pss_password

        # Import (or reload) the MCP server module so it picks up
        # the current env vars for PSS_SERVER, PSS_DB, etc.
        if "mcp_server.server" in sys.modules:
            srv = importlib.reload(sys.modules["mcp_server.server"])
        else:
            import mcp_server.server as srv

        self._call_tool_fn = srv.call_tool
        # Filter out connection tools — the agent doesn't need them
        self._mcp_tools = [
            t for t in srv.TOOLS if t.name not in _EXCLUDED_TOOLS
        ]
        self._openai_tools = None
        self._tool_name_set = None

        # Pre-connect to PSS so tool calls don't fail on first use
        try:
            srv._get_client()
            logger.info("MCPBridge: PSS client connected")
        except Exception as e:
            logger.warning("MCPBridge: PSS pre-connect failed: %s", e)

        logger.info(
            "MCPBridge started (direct import), %d tools available",
            len(self._mcp_tools),
        )

    def stop(self) -> None:
        """Clean up."""
        self._call_tool_fn = None
        self._mcp_tools = []
        self._openai_tools = None
        self._tool_name_set = None
        logger.info("MCPBridge stopped")

    # ------------------------------------------------------------------
    # Tool access
    # ------------------------------------------------------------------

    @property
    def tools(self) -> list[dict]:
        """Return MCP tools in OpenAI function-calling format."""
        if self._openai_tools is None:
            self._openai_tools = [
                {
                    "type": "function",
                    "function": {
                        "name": t.name,
                        "description": t.description or "",
                        "parameters": t.inputSchema,
                    },
                }
                for t in self._mcp_tools
            ]
        return self._openai_tools

    @property
    def tool_names(self) -> set[str]:
        """Set of available MCP tool names."""
        if self._tool_name_set is None:
            self._tool_name_set = {t.name for t in self._mcp_tools}
        return self._tool_name_set

    def call_tool(self, name: str, arguments: dict[str, Any]) -> str:
        """Call an MCP tool synchronously. Returns result as JSON string."""
        if self._call_tool_fn is None:
            raise RuntimeError("MCPBridge not started")

        try:
            # call_tool is async — run it synchronously
            result_contents = asyncio.run(self._call_tool_fn(name, arguments))
        except Exception as e:
            logger.error("MCP tool %s failed: %s", name, e, exc_info=True)
            return json.dumps(
                {"error": f"Tool error: {e}"}, ensure_ascii=False
            )

        # Extract text from TextContent list
        texts = []
        for block in result_contents:
            if hasattr(block, "text"):
                texts.append(block.text)
        return "\n".join(texts) if texts else "{}"
