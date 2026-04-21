from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

from ..wiki_store import WikiStore

if TYPE_CHECKING:
    from ...llm.tools.base import ToolCall, ToolContext


class WikiHistoryTool:
    def info(self):
        from ...llm.tools.base import ToolInfo

        return ToolInfo(
            name="wiki_history",
            description="Inspect DeepNote page history commits.",
            parameters={
                "type": "object",
                "properties": {
                    "page": {"type": "string", "description": "Optional page path for filtering history."},
                    "limit": {"type": "integer", "description": "Maximum number of history rows."},
                },
                "required": [],
            },
            required=[],
        )

    async def run(self, call: ToolCall, context: ToolContext):
        from ...llm.tools.base import ToolResponse
        from ...config import get_settings

        args = call.get_input_dict()
        page = str(args.get("page", "") or "").strip() or None
        limit = int(args.get("limit", 30) or 30)
        limit = max(1, min(limit, 200))

        store = WikiStore.from_settings(get_settings())
        try:
            rows = store.history.list_commits(page_path=page, limit=limit)
            return ToolResponse.text(json.dumps({"success": True, "rows": rows}, ensure_ascii=False))
        finally:
            store.close()


def create_wiki_history_tool(permissions: Any = None) -> WikiHistoryTool:
    return WikiHistoryTool()

