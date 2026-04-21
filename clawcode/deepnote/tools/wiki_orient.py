from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

from ..wiki_store import WikiStore

if TYPE_CHECKING:
    from ...llm.tools.base import ToolCall, ToolContext


class WikiOrientTool:
    def info(self):
        from ...llm.tools.base import ToolInfo

        return ToolInfo(
            name="wiki_orient",
            description="Load DeepNote orientation: SCHEMA.md, index.md and recent log.",
            parameters={
                "type": "object",
                "properties": {
                    "log_entries": {"type": "integer", "description": "How many recent log lines to include."},
                },
                "required": [],
            },
            required=[],
        )

    async def run(self, call: ToolCall, context: ToolContext):
        from ...llm.tools.base import ToolResponse
        from ...config import get_settings

        args = call.get_input_dict()
        log_entries = int(args.get("log_entries", 30) or 30)
        store = WikiStore.from_settings(get_settings())
        try:
            payload = {
                "success": True,
                "orient": store.get_orient_payload(log_entries=max(1, min(log_entries, 120))),
            }
            return ToolResponse.text(json.dumps(payload, ensure_ascii=False))
        finally:
            store.close()


def create_wiki_orient_tool(permissions: Any = None) -> WikiOrientTool:
    return WikiOrientTool()

