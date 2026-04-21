from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

from ..wiki_store import WikiStore

if TYPE_CHECKING:
    from ...llm.tools.base import ToolCall, ToolContext


class WikiQueryTool:
    def info(self):
        from ...llm.tools.base import ToolInfo

        return ToolInfo(
            name="wiki_query",
            description="Query DeepNote wiki using keyword, semantic, or hybrid retrieval.",
            parameters={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Natural language or keyword query."},
                    "mode": {"type": "string", "enum": ["keyword", "semantic", "hybrid"]},
                    "limit": {"type": "integer", "description": "Maximum result count (default 10)."},
                },
                "required": ["query"],
            },
            required=["query"],
        )

    async def run(self, call: ToolCall, context: ToolContext):
        from ...llm.tools.base import ToolResponse
        from ...config import get_settings

        args = call.get_input_dict()
        query = str(args.get("query", "")).strip()
        if not query:
            return ToolResponse.error(json.dumps({"success": False, "error": "query is required"}, ensure_ascii=False))
        mode = str(args.get("mode", "hybrid") or "hybrid").strip().lower()
        limit = int(args.get("limit", 10) or 10)
        limit = max(1, min(limit, 50))

        store = WikiStore.from_settings(get_settings())
        try:
            results = store.query(query=query, mode=mode, limit=limit)
            return ToolResponse.text(json.dumps({"success": True, "query": query, "mode": mode, "results": results}, ensure_ascii=False))
        finally:
            store.close()


def create_wiki_query_tool(permissions: Any = None) -> WikiQueryTool:
    return WikiQueryTool()

