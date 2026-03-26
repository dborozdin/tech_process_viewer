"""
Mock LLM client: запись и воспроизведение LLM-сессий.

LLMRecorder  — обёртка над реальным LLMClient, записывает все chat()-вызовы и tool-результаты.
MockLLMClient — воспроизводит записанные сессии без обращения к LLM API и PSS API.
"""

import json
import os
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


class LLMRecorder:
    """Обёртка над реальным LLMClient: проксирует chat() и записывает ответы + tool-результаты."""

    def __init__(self, real_client, recordings_dir: str):
        self.real_client = real_client
        self.recordings_dir = recordings_dir
        self._current_session = []
        self._pending_tool_results = {}  # tool_call_id -> result
        os.makedirs(recordings_dir, exist_ok=True)

    @property
    def model(self):
        return self.real_client.model

    def chat(self, messages: list, tools: list = None) -> dict:
        response = self.real_client.chat(messages, tools)

        # Собрать tool-результаты от предыдущего шага (если были)
        tool_results = self._pending_tool_results if self._pending_tool_results else None
        self._pending_tool_results = {}

        entry = {
            "call_index": len(self._current_session),
            "response": response,
        }
        if tool_results:
            entry["tool_results"] = tool_results

        self._current_session.append(entry)
        return response

    def record_tool_result(self, tool_call_id: str, tool_name: str, result: str):
        """Записать результат выполнения tool (вызывается из оркестратора)."""
        self._pending_tool_results[tool_call_id] = {
            "tool_name": tool_name,
            "result": result,
        }

    def save_session(self, question: str):
        """Сохранить записанную сессию в JSON-файл."""
        if not self._current_session:
            return

        # Сохранить последние tool_results (если сессия завершилась после tool-вызовов)
        if self._pending_tool_results:
            if self._current_session:
                last = self._current_session[-1]
                if "tool_results" not in last:
                    last["tool_results"] = {}
                last["tool_results"].update(self._pending_tool_results)
            self._pending_tool_results = {}

        provider = getattr(self.real_client, '_provider', None) or "unknown"
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_model = self.model.replace("/", "_").replace(":", "_")
        filename = f"{safe_model}_{ts}.json"
        filepath = os.path.join(self.recordings_dir, filename)

        data = {
            "model": self.model,
            "provider": provider,
            "user_question": question,
            "timestamp": datetime.now().isoformat(),
            "calls": self._current_session,
        }

        try:
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2, default=str)
            logger.info(f"Session recorded: {filename} ({len(self._current_session)} calls)")
        except OSError as e:
            logger.error(f"Failed to save recording: {e}")

        self._current_session = []

    def reset_session(self):
        """Сбросить текущую запись (без сохранения)."""
        self._current_session = []
        self._pending_tool_results = {}


class MockLLMClient:
    """Воспроизводит записанные LLM-сессии. Реализует интерфейс chat()."""

    def __init__(self, recordings_dir: str, model_label: str = "mock-replay"):
        self.recordings_dir = recordings_dir
        self.model = model_label
        self._sessions = {}  # {question: {"calls": [...], "model": str, ...}}
        self._current_calls = []  # полные записи (с tool_results)
        self._current_replay = []  # только LLM-ответы
        self._call_index = 0
        self._load_recordings()

    def _load_recordings(self):
        """Загрузить записи из директории, фильтруя по модели если задана."""
        self._sessions = {}
        if not os.path.isdir(self.recordings_dir):
            logger.warning(f"Recordings dir not found: {self.recordings_dir}")
            return

        filter_model = self.model if self.model != "mock-replay" else None

        for fname in os.listdir(self.recordings_dir):
            if not fname.endswith(".json"):
                continue
            fpath = os.path.join(self.recordings_dir, fname)
            try:
                with open(fpath, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if filter_model and data.get("model") != filter_model:
                    continue
                question = data.get("user_question", "")
                if question:
                    self._sessions[question] = data
                    logger.debug(f"Loaded recording: {fname} -> '{question[:60]}'")
            except (json.JSONDecodeError, OSError) as e:
                logger.warning(f"Failed to load recording {fname}: {e}")

        logger.info(f"MockLLMClient: loaded {len(self._sessions)} sessions"
                     f"{f' for model {filter_model}' if filter_model else ''}")

    def _select_session(self, question: str):
        """Найти подходящую запись: сначала точное совпадение, потом подстрока."""
        session = None

        # Точное совпадение
        if question in self._sessions:
            session = self._sessions[question]
            logger.info(f"Mock: exact match for '{question[:60]}'")

        # Подстрочное совпадение
        if not session:
            q_lower = question.lower()
            for key, s in self._sessions.items():
                if q_lower in key.lower() or key.lower() in q_lower:
                    session = s
                    logger.info(f"Mock: substring match '{question[:40]}' -> '{key[:40]}'")
                    break

        if session:
            calls = session.get("calls", [])
            self._current_calls = calls
            self._current_replay = [c["response"] for c in calls]
        else:
            self._current_calls = []
            self._current_replay = []
            logger.warning(f"Mock: no matching recording for '{question[:60]}'")

        self._call_index = 0

    def chat(self, messages: list, tools: list = None) -> dict:
        # При первом вызове в сессии — найти подходящую запись
        if self._call_index == 0:
            question = self._extract_user_question(messages)
            self._select_session(question)

        if self._call_index < len(self._current_replay):
            response = self._current_replay[self._call_index]
            self._call_index += 1
            logger.info(f"Mock: replaying call {self._call_index}/{len(self._current_replay)}")
            return response

        # Записи закончились — заглушка
        return {
            "role": "assistant",
            "content": "\u26a0\ufe0f Записанный сценарий завершён. Для этого вопроса нет (больше) записанных шагов.",
            "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
            "rate_limit": None,
        }

    def get_tool_result(self, tool_call_id: str) -> str | None:
        """Получить записанный результат tool-вызова (для полного replay без PSS).

        Ищет в следующем call-entry (т.к. tool_results записываются перед следующим chat).
        """
        # tool_results для call N хранятся в call N+1 (перед следующим chat)
        next_idx = self._call_index  # _call_index уже инкрементирован после chat()
        if next_idx < len(self._current_calls):
            tr = self._current_calls[next_idx].get("tool_results", {})
            if tool_call_id in tr:
                return tr[tool_call_id]["result"]

        # Также проверим текущий call (на случай если формат другой)
        prev_idx = self._call_index - 1
        if 0 <= prev_idx < len(self._current_calls):
            tr = self._current_calls[prev_idx].get("tool_results", {})
            if tool_call_id in tr:
                return tr[tool_call_id]["result"]

        return None

    def reset_session(self):
        """Сброс текущего воспроизведения (для нового вопроса)."""
        self._current_calls = []
        self._current_replay = []
        self._call_index = 0

    @staticmethod
    def _extract_user_question(messages: list) -> str:
        """Извлечь последний вопрос пользователя из истории сообщений."""
        for m in reversed(messages):
            if m.get("role") == "user" and m.get("content"):
                content = m["content"]
                if "Запрос пользователя:" in content:
                    return content.split("Запрос пользователя:")[-1].strip()
                return content
        return ""

    @classmethod
    def list_sessions(cls, recordings_dir: str) -> list:
        """Получить список всех записанных сессий (для API)."""
        sessions = []
        if not os.path.isdir(recordings_dir):
            return sessions

        for fname in sorted(os.listdir(recordings_dir)):
            if not fname.endswith(".json"):
                continue
            fpath = os.path.join(recordings_dir, fname)
            try:
                with open(fpath, "r", encoding="utf-8") as f:
                    data = json.load(f)
                sessions.append({
                    "file": fname,
                    "model": data.get("model", "unknown"),
                    "provider": data.get("provider", "unknown"),
                    "question": data.get("user_question", ""),
                    "steps": len(data.get("calls", [])),
                    "timestamp": data.get("timestamp", ""),
                })
            except (json.JSONDecodeError, OSError):
                continue
        return sessions

    @classmethod
    def list_models(cls, recordings_dir: str) -> list:
        """Получить уникальные модели из записей (для dropdown)."""
        models = set()
        for s in cls.list_sessions(recordings_dir):
            models.add(s["model"])
        return sorted(models)
