"""
Agent orchestrator: the main loop that connects user questions,
LLM reasoning, tool execution, and report generation.
"""

import json
import logging
import os
import time
from typing import Generator

from ILS.agent.llm_client import LLMClient
from ILS.agent.tools import TOOLS
from ILS.agent.tool_executor import ToolExecutor
from ILS.agent.prompts import build_system_prompt, format_categories, FEW_SHOT_EXAMPLES
from ILS.agent.knowledge import KnowledgeStore
from ILS.pss.schema import Schema

logger = logging.getLogger("ils.agent")


class AgentStep:
    """Represents one step in the agent's reasoning process."""

    def __init__(self, step_type: str, **kwargs):
        self.type = step_type  # "tool_call", "tool_result", "api_calls", "clarification", "answer", "error"
        self.data = kwargs
        self.timestamp = time.time()

    def to_dict(self) -> dict:
        return {"type": self.type, **self.data}


class Agent:
    """ILS Report Agent orchestrator."""

    def __init__(self, llm: LLMClient, executor: ToolExecutor, schema: Schema,
                 knowledge: KnowledgeStore = None,
                 max_iterations: int = 15,
                 custom_instructions_path: str = None):
        self.llm = llm
        self.executor = executor
        self.schema = schema
        self.knowledge = knowledge
        self.max_iterations = max_iterations
        self.custom_instructions_path = custom_instructions_path

        # Build system prompt with categories, knowledge, and custom instructions
        self._rebuild_system_prompt()

        # Conversation state (persists between ask / continue_with_answer)
        self.messages: list = []
        self._pending_clarification = False
        self._pending_tool_call_id: str | None = None
        self._iteration = 0

    def _rebuild_system_prompt(self):
        """Rebuild system prompt to include latest knowledge and custom instructions."""
        categories = self.schema.get_categories()
        categories_text = format_categories(categories)
        knowledge_text = self.knowledge.format_for_prompt() if self.knowledge else ""
        custom = ""
        if self.custom_instructions_path and os.path.exists(self.custom_instructions_path):
            with open(self.custom_instructions_path, 'r', encoding='utf-8') as f:
                custom = f.read()
        self.system_prompt = build_system_prompt(categories_text, knowledge_text, custom)

    def ask(self, question: str) -> Generator[AgentStep, None, None]:
        """Start a new conversation turn.

        Yields AgentStep objects for each step:
        - tool_call: agent is calling a tool
        - tool_result: tool returned a result
        - api_calls: PSS REST API calls made during tool execution
        - clarification: agent asks user a clarifying question (stream ends here)
        - answer: final answer (may contain HTML)
        - error: something went wrong
        """
        self._rebuild_system_prompt()
        self.messages = [
            {"role": "system", "content": self.system_prompt},
        ]
        self.messages.extend(FEW_SHOT_EXAMPLES)
        self.messages.append({"role": "user", "content": question})
        self._pending_clarification = False
        self._pending_tool_call_id = None
        self._iteration = 0

        yield from self._run_loop()

    def continue_with_answer(self, answer: str) -> Generator[AgentStep, None, None]:
        """Continue after a clarification question was answered by the user."""
        if not self._pending_clarification:
            yield AgentStep("error", message="No pending clarification to answer.")
            return

        self.messages.append({
            "role": "tool",
            "tool_call_id": self._pending_tool_call_id,
            "content": json.dumps({"user_answer": answer}, ensure_ascii=False),
        })
        self._pending_clarification = False
        self._pending_tool_call_id = None

        yield from self._run_loop()

    def _run_loop(self) -> Generator[AgentStep, None, None]:
        """Core agent loop — shared between ask() and continue_with_answer()."""
        while self._iteration < self.max_iterations:
            self._iteration += 1
            logger.info(f"Agent iteration {self._iteration}/{self.max_iterations}")

            try:
                response = self.llm.chat(self.messages, tools=TOOLS)
            except Exception as e:
                logger.error(f"LLM error: {e}", exc_info=True)
                yield AgentStep("error", message=f"Ошибка LLM: {e}")
                return

            # Emit token usage info
            usage = response.pop("usage", None)
            if usage:
                yield AgentStep("llm_usage", **usage)

            tool_calls = response.get("tool_calls")

            if not tool_calls:
                # No tool calls — final answer
                content = response.get("content", "")
                if not content:
                    content = "Не удалось сформировать ответ."
                yield AgentStep("answer", content=content)
                return

            # Add assistant message with tool calls to history
            self.messages.append(response)

            # Separate ask_user from regular tools
            ask_user_tc = None
            regular_tcs = []
            for tc in tool_calls:
                if tc["function"]["name"] == "ask_user":
                    ask_user_tc = tc
                else:
                    regular_tcs.append(tc)

            # Execute regular tools first
            for tc in regular_tcs:
                func_name = tc["function"]["name"]
                try:
                    args = json.loads(tc["function"]["arguments"])
                except json.JSONDecodeError:
                    args = {}

                yield AgentStep("tool_call", tool=func_name, arguments=args)

                result = self.executor.execute(func_name, args)

                yield AgentStep("tool_result", tool=func_name, result=result[:500])

                # Flush PSS API debug log
                api_log = self.executor.pss.flush_log()
                if api_log:
                    yield AgentStep("api_calls", calls=api_log)

                self.messages.append({
                    "role": "tool",
                    "tool_call_id": tc["id"],
                    "content": result,
                })

            # Handle ask_user — pause and wait for user response
            if ask_user_tc:
                try:
                    args = json.loads(ask_user_tc["function"]["arguments"])
                except json.JSONDecodeError:
                    args = {}
                question_text = args.get("question", "Уточните ваш запрос.")
                yield AgentStep("tool_call", tool="ask_user", arguments=args)
                yield AgentStep("clarification", question=question_text)
                self._pending_clarification = True
                self._pending_tool_call_id = ask_user_tc["id"]
                return

        # Reached max iterations
        yield AgentStep("error",
                        message=f"Превышено максимальное количество итераций ({self.max_iterations}). "
                                "Попробуйте уточнить вопрос.")

    def ask_sync(self, question: str) -> dict:
        """Synchronous version of ask(). Returns final result dict.

        Note: does not support clarification flow (ask_user).

        Returns:
            {
                "answer": str,  # Final answer text (may contain HTML)
                "steps": list,  # List of step dicts
                "error": str | None,
            }
        """
        steps = []
        answer = ""
        error = None

        for step in self.ask(question):
            steps.append(step.to_dict())
            if step.type == "answer":
                answer = step.data.get("content", "")
            elif step.type == "error":
                error = step.data.get("message", "Unknown error")

        return {
            "answer": answer,
            "steps": steps,
            "error": error,
        }
