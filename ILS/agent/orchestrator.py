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
from ILS.agent.prompts import (build_system_prompt, format_categories,
                                FEW_SHOT_EXAMPLES, FEW_SHOT_EXAMPLES_HIGH_LEVEL)
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

        # Cross-turn conversation history (Q&A summaries for context continuity)
        self._conversation_history: list[dict] = []  # [{question, answer}]
        self._max_history_turns = 3  # keep last N turns

    def _rebuild_system_prompt(self):
        """Rebuild system prompt to include latest knowledge and custom instructions."""
        categories = self.schema.get_categories()
        categories_text = format_categories(categories)
        knowledge_text = self.knowledge.format_for_prompt() if self.knowledge else ""
        custom = ""
        if self.custom_instructions_path and os.path.exists(self.custom_instructions_path):
            with open(self.custom_instructions_path, 'r', encoding='utf-8') as f:
                custom = f.read()
        self.system_prompt = build_system_prompt(
            categories_text, knowledge_text, custom, high_level_available=True
        )

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
        self.messages.extend(FEW_SHOT_EXAMPLES_HIGH_LEVEL)
        self.messages.extend(FEW_SHOT_EXAMPLES)

        # Inject previous conversation turns as context
        for turn in self._conversation_history:
            self.messages.append({"role": "user", "content": turn["question"]})
            self.messages.append({"role": "assistant", "content": turn["answer"]})

        # Inject relevant knowledge directly into the user message
        knowledge_prefix = ""
        if self.knowledge:
            knowledge_prefix = self.knowledge.format_relevant_for_message(question)
        self._current_question = question
        self.messages.append({"role": "user", "content": knowledge_prefix + question})
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

            yield AgentStep("llm_thinking",
                            iteration=self._iteration,
                            max_iterations=self.max_iterations)

            # Emit LLM request debug info (full messages for debugging)
            debug_messages = []
            for m in self.messages:
                role = m.get("role", "?")
                if role == "system":
                    debug_messages.append({"role": "system", "content": m.get("content", "")})
                elif role == "user":
                    debug_messages.append({"role": "user", "content": m.get("content", "")})
                elif role == "assistant":
                    tc = m.get("tool_calls")
                    if tc:
                        calls = [f"{c['function']['name']}({c['function']['arguments']})" for c in tc]
                        debug_messages.append({"role": "assistant", "content": f"[tool_calls: {', '.join(calls)}]"})
                    else:
                        debug_messages.append({"role": "assistant", "content": m.get("content") or ""})
                elif role == "tool":
                    debug_messages.append({"role": "tool", "content": m.get("content", "")})
            yield AgentStep("llm_request", messages=debug_messages)

            try:
                response = self.llm.chat(self.messages, tools=TOOLS)
            except Exception as e:
                logger.error(f"LLM error: {e}", exc_info=True)
                yield AgentStep("error", message=f"Ошибка LLM: {e}")
                return

            # Emit LLM response debug info
            resp_debug = {"content": (response.get("content") or "")[:500]}
            if response.get("tool_calls"):
                resp_debug["tool_calls"] = [
                    {"name": tc["function"]["name"],
                     "arguments": tc["function"]["arguments"][:200]}
                    for tc in response["tool_calls"]
                ]
            yield AgentStep("llm_response", **resp_debug)

            # Emit token usage info (with rate limit data if available)
            usage = response.pop("usage", None)
            rate_limit = response.pop("rate_limit", None)
            if usage:
                usage_data = {**usage}
                if rate_limit:
                    usage_data["rate_limit"] = rate_limit
                yield AgentStep("llm_usage", **usage_data)

            tool_calls = response.get("tool_calls")

            if not tool_calls:
                # No tool calls — final answer
                content = response.get("content", "")
                if not content:
                    content = "Не удалось сформировать ответ."

                # Save Q&A to conversation history for cross-turn context
                if hasattr(self, '_current_question') and self._current_question:
                    self._conversation_history.append({
                        "question": self._current_question,
                        "answer": content[:2000],  # truncate long HTML reports
                    })
                    if len(self._conversation_history) > self._max_history_turns:
                        self._conversation_history = self._conversation_history[-self._max_history_turns:]

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

    def clear_history(self):
        """Clear conversation history (start fresh context)."""
        self._conversation_history = []
        logger.info("Conversation history cleared")

    @property
    def history_count(self) -> int:
        """Number of previous turns in conversation history."""
        return len(self._conversation_history)

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
