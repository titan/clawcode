"""DeepNote wiki subsystem.

DeepNote is a structured, persistent markdown knowledge base inspired by
Hermes llm-wiki, with additional guardrails and retrieval primitives.
"""

from .wiki_config import DeepNoteConfig, DeepNoteSearchConfig, DeepNoteValidationConfig, DeepNoteHistoryConfig
from .wiki_store import WikiStore

__all__ = [
    "DeepNoteConfig",
    "DeepNoteSearchConfig",
    "DeepNoteValidationConfig",
    "DeepNoteHistoryConfig",
    "WikiStore",
]

