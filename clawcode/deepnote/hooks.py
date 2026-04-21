from __future__ import annotations

from typing import Any

from .wiki_store import WikiStore


def build_session_start_orient_note(settings: Any) -> str:
    """Return an orient hint for SessionStart hook handlers."""
    try:
        cfg = getattr(settings, "deepnote", None)
        if not cfg or not bool(getattr(cfg, "enabled", False)) or not bool(getattr(cfg, "auto_orient", False)):
            return ""
        store = WikiStore.from_settings(settings)
        if not store.exists():
            return ""
        stats = store.get_stats()
        return (
            f"DeepNote active at {stats.get('root','')}, pages={stats.get('total_pages',0)}. "
            "Run wiki_orient before deepnote operations."
        )
    except Exception:
        return ""

