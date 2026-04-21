from __future__ import annotations

import json
import re
from typing import TYPE_CHECKING, Any

from ..wiki_store import WikiStore

if TYPE_CHECKING:
    from ...llm.tools.base import ToolCall, ToolContext

_WIKILINK_RE = re.compile(r"\[\[([^\]]+)\]\]")


class WikiLinkTool:
    def info(self):
        from ...llm.tools.base import ToolInfo

        return ToolInfo(
            name="wiki_link",
            description="Inspect and update DeepNote link graph for specific pages.",
            parameters={
                "type": "object",
                "properties": {
                    "action": {"type": "string", "enum": ["inspect", "refresh"]},
                    "page": {"type": "string", "description": "Page slug or path stem."},
                },
                "required": ["action", "page"],
            },
            required=["action", "page"],
        )

    async def run(self, call: ToolCall, context: ToolContext):
        from ...llm.tools.base import ToolResponse
        from ...config import get_settings

        args = call.get_input_dict()
        action = str(args.get("action", "")).strip().lower()
        page = str(args.get("page", "")).strip().lower()
        if not action or not page:
            return ToolResponse.error(json.dumps({"success": False, "error": "action and page are required"}, ensure_ascii=False))
        store = WikiStore.from_settings(get_settings())
        try:
            hit = None
            for p in store.iter_wiki_pages():
                if p.stem.lower() == page:
                    hit = p
                    break
            if hit is None:
                return ToolResponse.error(json.dumps({"success": False, "error": "page not found"}, ensure_ascii=False))

            if action == "refresh":
                text = hit.read_text(encoding="utf-8")
                links = [store.slugify(x) for x in _WIKILINK_RE.findall(text) if store.slugify(x)]
                store.graph.update_links(hit.stem, links)

            payload = {
                "success": True,
                "page": hit.stem,
                "outbound": store.graph.outbound(hit.stem),
                "inbound": store.graph.inbound(hit.stem),
            }
            return ToolResponse.text(json.dumps(payload, ensure_ascii=False))
        finally:
            store.close()


def create_wiki_link_tool(permissions: Any = None) -> WikiLinkTool:
    return WikiLinkTool()

