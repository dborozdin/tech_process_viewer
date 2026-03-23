"""
Persistent knowledge store for the ILS Report Agent.
Saves domain knowledge learned from user interactions to a JSON file,
and injects it into the system prompt on startup.
"""

import json
import logging
import os
from datetime import datetime

logger = logging.getLogger("ils.knowledge")


class KnowledgeStore:
    """File-backed store for agent domain knowledge."""

    def __init__(self, path: str):
        self.path = path
        self.entries: list[dict] = []
        self._load()

    def _load(self):
        if os.path.exists(self.path):
            try:
                with open(self.path, 'r', encoding='utf-8') as f:
                    self.entries = json.load(f)
                logger.info(f"Knowledge loaded: {len(self.entries)} entries from {self.path}")
            except (json.JSONDecodeError, OSError) as e:
                logger.warning(f"Failed to load knowledge: {e}")
                self.entries = []
        else:
            os.makedirs(os.path.dirname(self.path), exist_ok=True)
            self.entries = []
            self._save()

    def _save(self):
        try:
            with open(self.path, 'w', encoding='utf-8') as f:
                json.dump(self.entries, f, ensure_ascii=False, indent=2)
        except OSError as e:
            logger.error(f"Failed to save knowledge: {e}")

    def add(self, topic: str, content: str) -> dict:
        """Add a knowledge entry. Returns the saved entry."""
        entry = {
            "topic": topic,
            "content": content,
            "timestamp": datetime.now().isoformat(),
        }
        self.entries.append(entry)
        self._save()
        logger.info(f"Knowledge saved: {topic}")
        return entry

    def search(self, keyword: str) -> list[dict]:
        """Search entries by keyword in topic and content."""
        keyword_lower = keyword.lower()
        return [
            e for e in self.entries
            if keyword_lower in e['topic'].lower() or keyword_lower in e['content'].lower()
        ]

    def find_relevant(self, question: str) -> list[dict]:
        """Find knowledge entries relevant to a user question.

        Uses prefix-based matching (first 4 chars) to handle Russian
        word inflections: "финальные"→"фина" matches "финальное",
        "изделия"→"изде" matches "изделие".
        """
        words = [w.lower().strip('.,!?()"\':;') for w in question.split()]
        words = [w for w in words if len(w) >= 4]
        if not words:
            return []

        # Use first 4 chars as stem for matching (handles Russian inflections)
        stems = [w[:4] for w in words]

        scored = []
        for entry in self.entries:
            text = (entry['topic'] + ' ' + entry['content']).lower()
            hits = sum(1 for stem in stems if stem in text)
            if hits > 0:
                scored.append((hits, entry))

        scored.sort(key=lambda x: -x[0])
        return [e for _, e in scored]

    def format_relevant_for_message(self, question: str) -> str:
        """Format relevant knowledge entries as a prefix for the user message."""
        relevant = self.find_relevant(question)
        if not relevant:
            return ""
        lines = []
        for e in relevant:
            lines.append(f"- {e['topic']}: {e['content']}")
        return (
            "ВАЖНО! Перед выполнением запроса прочитай сохранённые знания.\n"
            "Используй ТОЧНЫЕ имена сущностей и атрибутов из этих записей, "
            "НЕ заменяй их на похожие или предполагаемые имена:\n\n"
            + "\n".join(lines)
            + "\n\nЗапрос пользователя: "
        )

    def format_for_prompt(self) -> str:
        """Format all entries for inclusion in the system prompt."""
        if not self.entries:
            return ""
        lines = []
        for e in self.entries:
            lines.append(f"- **{e['topic']}**: {e['content']}")
        return "\n".join(lines)
