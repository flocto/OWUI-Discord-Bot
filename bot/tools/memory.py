import json
import os
from datetime import datetime, timezone
from pathlib import Path

from ..log import logger
from ..types import Memory

MEMORIES_PATH = Path(os.getenv("MEMORIES_PATH", "/app/memories/memories.json"))


def _load() -> list[Memory]:
    if not MEMORIES_PATH.exists():
        return []
    return json.loads(MEMORIES_PATH.read_text())


def _save(memories: list[Memory]) -> None:
    MEMORIES_PATH.parent.mkdir(parents=True, exist_ok=True)
    MEMORIES_PATH.write_text(json.dumps(memories, indent=2))


def add_memory(content: str) -> str:
    """Store a memory for future reference. Call this when something important
    about the user or conversation should be retained across future sessions —
    such as their name, preferences, ongoing projects, or facts they've shared.

    Args:
        content: The information to remember.

    Returns:
        str: Confirmation message.
    """
    logger.info(f"Adding memory: {content}")
    memories = _load()
    memories.append({
        "content": content,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })
    _save(memories)
    return f"Stored: {content}"


def forget_memory(query: str) -> str:
    """Remove stored memories that match a keyword or phrase. Use this to
    correct outdated information or remove something that no longer applies.
    Call recall_memories first if you need to confirm what exists before
    deleting.

    Args:
        query: Keyword or phrase to match against memory content
               (case-insensitive). All matching memories are removed.

    Returns:
        str: Description of what was removed, or a message indicating no
             matches were found.
    """
    memories = _load()
    matching = [m for m in memories if query.lower() in m["content"].lower()]
    if not matching:
        logger.info(f"forget_memory: no matches for '{query}'")
        return f"No memories matched '{query}'."
    kept = [m for m in memories if query.lower() not in m["content"].lower()]
    _save(kept)
    removed_lines = "\n".join(f"  - {m['content']}" for m in matching)
    logger.info(f"Forgot {len(matching)} memory/memories matching '{query}':\n{removed_lines}")
    return f"Removed {len(matching)} memory/memories:\n{removed_lines}"


def recall_memories(query: str = "") -> str:
    """Retrieve previously stored memories. Call this when you need context
    from past conversations, when the user references something they may have
    told you before, or at the start of a conversation to orient yourself.

    Args:
        query: Optional keyword filter — only returns memories whose content
               contains this string (case-insensitive). Leave empty to retrieve
               all stored memories.

    Returns:
        str: Newline-separated list of matching memories with timestamps, or a
             message indicating none were found.
    """
    logger.info(f"Recalling memories with query: '{query}'")
    memories = _load()
    if query:
        memories = [m for m in memories if query.lower() in m["content"].lower()]
    if not memories:
        return "No memories found."
    return "\n".join(f"[{m['timestamp']}] {m['content']}" for m in memories)
