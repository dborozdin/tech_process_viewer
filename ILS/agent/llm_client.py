"""
LLM client using OpenAI-compatible API.
Works with OpenRouter, Groq, Ollama, OpenAI, and any compatible provider.
"""

import logging
import time

from openai import OpenAI, RateLimitError
from httpx import Timeout

logger = logging.getLogger("ils.llm")


class LLMClient:
    """Wrapper around OpenAI-compatible chat completions with tool use."""

    def __init__(self, base_url: str, api_key: str, model: str,
                 temperature: float = 0.1, max_tokens: int = 4096,
                 timeout: float = 120):
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens

        self.client = OpenAI(
            base_url=base_url,
            api_key=api_key or "not-needed",  # Some providers require non-empty key
            timeout=Timeout(timeout, connect=15),
        )
        logger.info(f"LLM client initialized: {base_url}, model={model}, timeout={timeout}s")

    def chat(self, messages: list, tools: list = None) -> dict:
        """Send chat completion request with optional tools.

        Args:
            messages: List of message dicts (role, content, tool_calls, etc.)
            tools: List of tool definitions (OpenAI format).

        Returns:
            The assistant message dict from the response, containing either
            'content' (text reply) or 'tool_calls' (list of tool call requests).
        """
        kwargs = {
            "model": self.model,
            "messages": messages,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
        }
        if tools:
            kwargs["tools"] = tools
            kwargs["tool_choice"] = "auto"

        logger.debug(f"LLM request: {len(messages)} messages, {len(tools or [])} tools")

        # Retry on rate limit (429) with exponential backoff
        max_retries = 3
        for attempt in range(max_retries + 1):
            try:
                response = self.client.chat.completions.create(**kwargs)
                break
            except RateLimitError as e:
                if attempt == max_retries:
                    raise
                wait = 2 ** attempt * 5  # 5s, 10s, 20s
                logger.warning(f"Rate limited (429), retry {attempt + 1}/{max_retries} in {wait}s")
                time.sleep(wait)

        message = response.choices[0].message

        # Extract token usage
        usage = None
        if response.usage:
            usage = {
                "prompt_tokens": response.usage.prompt_tokens,
                "completion_tokens": response.usage.completion_tokens,
                "total_tokens": response.usage.total_tokens,
            }

        # Convert to plain dict for serialization
        result = {"role": "assistant", "content": message.content, "usage": usage}
        if message.tool_calls:
            result["tool_calls"] = [
                {
                    "id": tc.id,
                    "type": "function",
                    "function": {
                        "name": tc.function.name,
                        "arguments": tc.function.arguments,
                    },
                }
                for tc in message.tool_calls
            ]

        logger.debug(f"LLM response: content={'yes' if message.content else 'no'}, "
                      f"tool_calls={len(message.tool_calls or [])}")

        return result
