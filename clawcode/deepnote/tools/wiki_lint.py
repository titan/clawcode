from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

from ..validators.frontmatter import validate_frontmatter
from ..validators.links import validate_links
from ..validators.schema import validate_schema_compliance
from ..wiki_store import WikiStore

if TYPE_CHECKING:
    from ...llm.tools.base import ToolCall, ToolContext


class WikiLintTool:
    def info(self):
        from ...llm.tools.base import ToolInfo

        return ToolInfo(
            name="wiki_lint",
            description="Lint DeepNote wiki for frontmatter/schema/link issues.",
            parameters={
                "type": "object",
                "properties": {
                    "checks": {"type": "array", "items": {"type": "string"}},
                },
                "required": [],
            },
            required=[],
        )

    async def run(self, call: ToolCall, context: ToolContext):
        from ...llm.tools.base import ToolResponse
        from ...config import get_settings

        store = WikiStore.from_settings(get_settings())
        try:
            schema_path = store.root / "SCHEMA.md"
            issues: list[dict[str, Any]] = []
            for page in store.iter_wiki_pages():
                text = page.read_text(encoding="utf-8")
                errs: list[str] = []
                errs.extend(validate_frontmatter(text))
                errs.extend(validate_links(page, store.root, min_outbound=store.config.validation.min_outbound_links))
                errs.extend(validate_schema_compliance(text, schema_path))
                if errs:
                    issues.append({"page": str(page.relative_to(store.root)), "issues": errs})
            payload = {"success": True, "issue_count": len(issues), "issues": issues}
            return ToolResponse.text(json.dumps(payload, ensure_ascii=False))
        finally:
            store.close()


def create_wiki_lint_tool(permissions: Any = None) -> WikiLintTool:
    return WikiLintTool()

