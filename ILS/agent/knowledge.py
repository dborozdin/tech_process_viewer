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

    def format_for_prompt(self) -> str:
        """Format all entries for inclusion in the system prompt."""
        if not self.entries:
            return ""
        lines = []
        for e in self.entries:
            lines.append(f"- **{e['topic']}**: {e['content']}")
        return "\n".join(lines)
