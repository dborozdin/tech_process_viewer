"""
2-step agent orchestrator.

Step 1: LLM selects the right MCP tool and calls it (with optional follow-up).
Step 2: LLM formats the JSON result as an HTML report.

Between requests, the agent remembers found objects (sys_id + label) so the
user can refer to them in follow-up questions without repeating searches.
"""

import json
import logging
import time
from typing import Generator

from ILS_reports_agent.agent.llm_client import LLMClient
from ILS_reports_agent.agent.tool_executor import ToolExecutor
from ILS_reports_agent.agent.prompts import STEP1_PROMPT, STEP2_PROMPT
from ILS_reports_agent.pss.mcp_bridge import MCPBridge

logger = logging.getLogger("ils.agent")

# Tools that search/list (may need a follow-up call with sys_id)
_SEARCH_TOOLS = {
    "ils_find_final_products", "pdm_search_products",
    "pdm_find_product_by_code", "pdm_list_organizations",
    "pdm_get_folders", "pdm_list_units",
    "pdm_list_characteristic_types", "schema_search",
    "schema_list_categories", "data_query",
}

# Keys to use as label when extracting objects from tool results
_LABEL_KEYS = ["name_rus", "name", "id", "designation", "code1", "lcn"]


class AgentStep:
    """One step in the agent pipeline."""

    def __init__(self, step_type: str, **kwargs):
        self.type = step_type
        self.data = kwargs
        self.timestamp = time.time()

    def to_dict(self) -> dict:
        return {"type": self.type, **self.data}


class Agent:
    """2-step ILS Report Agent with object memory."""

    def __init__(self, llm: LLMClient, executor: ToolExecutor,
                 mcp_bridge: MCPBridge, **_ignored):
        self.llm = llm
        self.executor = executor
        self.mcp_bridge = mcp_bridge
        # Memory: list of {sys_id, type, label, tool} found across requests
        self._memory: list[dict] = []

    def ask(self, question: str) -> Generator[AgentStep, None, None]:
        """Process user question in 2 steps: tool selection → HTML formatting."""
        tools = self.mcp_bridge.tools  # OpenAI format

        # ── Step 1: pick tool ──
        yield AgentStep("step", step=1, description="Выбор инструмента")

        system = STEP1_PROMPT
        if self._memory:
            system += "\n\nОбъекты в памяти (используй их sys_id если пользователь ссылается на них):\n"
            for m in self._memory:
                system += f"- {m['label']} (sys_id={m['sys_id']}, {m['type']})\n"

        messages = [
            {"role": "system", "content": system},
            {"role": "user", "content": question},
        ]

        try:
            response = self.llm.chat(messages, tools=tools)
        except Exception as e:
            logger.error("LLM step-1 error: %s", e, exc_info=True)
            yield AgentStep("error", message=f"Ошибка LLM: {e}")
            return

        usage = response.pop("usage", None)
        if usage:
            yield AgentStep("llm_usage", **usage)

        tool_calls = response.get("tool_calls")
        if not tool_calls:
            yield AgentStep("answer", content=response.get("content", ""))
            return

        # Execute tool(s)
        tool_results = []
        for tc in tool_calls:
            name = tc["function"]["name"]
            try:
                args = json.loads(tc["function"]["arguments"])
            except json.JSONDecodeError:
                args = {}
            yield AgentStep("tool_call", tool=name, arguments=args)
            result = self.executor.execute(name, args)
            yield AgentStep("tool_result", tool=name, result=result[:500])
            tool_results.append({"tool": name, "args": args, "result": result})

        # ── Extract objects to memory ──
        for tr in tool_results:
            new_items = self._extract_objects(tr["tool"], tr["result"])
            if new_items:
                self._memory.extend(new_items)
                # Keep memory bounded
                if len(self._memory) > 50:
                    self._memory = self._memory[-50:]
                labels = ", ".join(
                    f"{it['label']} (sys_id={it['sys_id']})" for it in new_items
                )
                yield AgentStep("memory", items=labels)

        # ── Follow-up: if first call was a search, allow one more tool call ──
        first_tool = tool_calls[0]["function"]["name"]
        if self._needs_followup(first_tool, tool_results):
            messages.append(response)
            for tc, tr in zip(tool_calls, tool_results):
                messages.append({
                    "role": "tool",
                    "tool_call_id": tc["id"],
                    "content": tr["result"],
                })

            try:
                response2 = self.llm.chat(messages, tools=tools)
            except Exception as e:
                logger.error("LLM follow-up error: %s", e, exc_info=True)
                yield AgentStep("error", message=f"Ошибка LLM (follow-up): {e}")
                return

            usage2 = response2.pop("usage", None)
            if usage2:
                yield AgentStep("llm_usage", **usage2)

            tool_calls2 = response2.get("tool_calls")
            if tool_calls2:
                for tc in tool_calls2:
                    name = tc["function"]["name"]
                    try:
                        args = json.loads(tc["function"]["arguments"])
                    except json.JSONDecodeError:
                        args = {}
                    yield AgentStep("tool_call", tool=name, arguments=args)
                    result = self.executor.execute(name, args)
                    yield AgentStep("tool_result", tool=name, result=result[:500])
                    tool_results.append({"tool": name, "args": args, "result": result})

                # Extract objects from follow-up results too
                for tr in tool_results[-len(tool_calls2):]:
                    new_items = self._extract_objects(tr["tool"], tr["result"])
                    if new_items:
                        self._memory.extend(new_items)
                        if len(self._memory) > 50:
                            self._memory = self._memory[-50:]
                        labels = ", ".join(
                            f"{it['label']} (sys_id={it['sys_id']})"
                            for it in new_items
                        )
                        yield AgentStep("memory", items=labels)

        # ── Step 2: format HTML ──
        yield AgentStep("step", step=2, description="Форматирование отчёта")

        last_result = tool_results[-1]
        user_content = (
            f"Запрос пользователя: {question}\n\n"
            f"Инструмент: {last_result['tool']}\n"
            f"Результат:\n{last_result['result']}"
        )

        format_messages = [
            {"role": "system", "content": STEP2_PROMPT},
            {"role": "user", "content": user_content},
        ]

        try:
            fmt_response = self.llm.chat(format_messages)
        except Exception as e:
            logger.error("LLM step-2 error: %s", e, exc_info=True)
            yield AgentStep("error", message=f"Ошибка форматирования: {e}")
            return

        usage3 = fmt_response.pop("usage", None)
        if usage3:
            yield AgentStep("llm_usage", **usage3)

        html = fmt_response.get("content", "")
        # Strip markdown code fences if LLM wraps HTML in ```html...```
        if html.strip().startswith("```"):
            lines = html.strip().splitlines()
            # Remove first line (```html) and last line (```)
            if lines[-1].strip() == "```":
                lines = lines[1:-1]
            else:
                lines = lines[1:]
            html = "\n".join(lines)
        yield AgentStep("answer", content=html)

    # ------------------------------------------------------------------
    # Memory extraction
    # ------------------------------------------------------------------

    def _extract_objects(self, tool_name: str, result_str: str) -> list[dict]:
        """Parse tool result JSON and extract objects with sys_id for memory."""
        try:
            data = json.loads(result_str)
        except (json.JSONDecodeError, ValueError):
            return []

        objects = []

        if isinstance(data, dict):
            # Single object with sys_id at top level
            if "sys_id" in data and not any(
                k in data for k in ("tree", "instances", "components",
                                     "processes", "organizations")
            ):
                label = self._make_label(data)
                if label:
                    objects.append({
                        "sys_id": data["sys_id"],
                        "type": data.get("type", tool_name),
                        "label": label,
                        "tool": tool_name,
                    })

            # root_component (from logistic structure)
            root = data.get("root_component")
            if isinstance(root, dict) and "sys_id" in root:
                label = self._make_label(root)
                if label:
                    objects.append({
                        "sys_id": root["sys_id"],
                        "type": "component",
                        "label": label,
                        "tool": tool_name,
                    })

            # Lists: components, instances, processes, organizations, etc.
            for list_key in ("components", "instances", "processes",
                             "organizations", "products", "items",
                             "folders", "documents", "resources",
                             "children", "units", "tasks"):
                items = data.get(list_key)
                if isinstance(items, list):
                    for item in items[:20]:  # cap to avoid flooding memory
                        if isinstance(item, dict) and "sys_id" in item:
                            label = self._make_label(item)
                            if label:
                                objects.append({
                                    "sys_id": item["sys_id"],
                                    "type": item.get("type", list_key),
                                    "label": label,
                                    "tool": tool_name,
                                })

            # Tree nodes (logistic structure): extract nested component
            tree = data.get("tree")
            if isinstance(tree, list):
                for node in tree[:30]:
                    comp = node.get("component") if isinstance(node, dict) else None
                    if isinstance(comp, dict) and "sys_id" in comp:
                        label = self._make_label(comp)
                        if label:
                            objects.append({
                                "sys_id": comp["sys_id"],
                                "type": "component",
                                "label": label,
                                "tool": tool_name,
                            })

        # Deduplicate by sys_id (keep latest)
        seen = set()
        unique = []
        for obj in reversed(objects):
            if obj["sys_id"] not in seen:
                seen.add(obj["sys_id"])
                unique.append(obj)
        unique.reverse()

        # Also deduplicate against existing memory
        existing_ids = {m["sys_id"] for m in self._memory}
        return [o for o in unique if o["sys_id"] not in existing_ids]

    @staticmethod
    def _make_label(obj: dict) -> str:
        """Build a human-readable label from object attributes."""
        parts = []
        for key in _LABEL_KEYS:
            val = obj.get(key)
            if val and isinstance(val, str) and val.strip():
                parts.append(val.strip())
                if len(parts) >= 2:
                    break
        return ", ".join(parts) if parts else ""

    def _needs_followup(self, first_tool: str, tool_results: list) -> bool:
        """Check if first tool was a search and we should allow a detail call."""
        name = first_tool.rsplit(":", 1)[-1] if ":" in first_tool else first_tool
        return name in _SEARCH_TOOLS

    # ------------------------------------------------------------------
    # Sync convenience & API compat
    # ------------------------------------------------------------------

    def ask_sync(self, question: str) -> dict:
        """Synchronous ask — returns final result dict."""
        steps = []
        answer = ""
        error = None
        for step in self.ask(question):
            steps.append(step.to_dict())
            if step.type == "answer":
                answer = step.data.get("content", "")
            elif step.type == "error":
                error = step.data.get("message", "Unknown error")
        return {"answer": answer, "steps": steps, "error": error}

    def clear_history(self):
        """Clear object memory."""
        self._memory.clear()
        logger.info("Agent memory cleared")

    @property
    def history_count(self) -> int:
        return len(self._memory)
