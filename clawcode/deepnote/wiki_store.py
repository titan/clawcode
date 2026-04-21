from __future__ import annotations

import json
import os
import re
import time
from pathlib import Path
from typing import Any

from .wiki_config import DeepNoteConfig
from .wiki_graph import WikiGraph
from .wiki_history import WikiHistory
from .wiki_search import WikiSearchIndex

_WIKILINK_RE = re.compile(r"\[\[([^\]]+)\]\]")

SCHEMA_TEMPLATE = """# DeepNote Schema

## Domain
General research knowledge base.

## Conventions
- File names: lowercase-hyphen markdown.
- Every wiki page includes YAML frontmatter.
- Use [[wikilinks]] for internal references.
- Update index.md and log.md for every significant change.

## Tag Taxonomy
- concept
- entity
- comparison
- query
"""

INDEX_TEMPLATE = """# DeepNote Index

> Content catalog for DeepNote.
> Last updated: TBD | Total pages: 0

## Entities

## Concepts

## Comparisons

## Queries
"""

LOG_TEMPLATE = """# DeepNote Log

> Append-only operational history.
"""


class WikiStore:
    """Structured markdown wiki storage backend."""

    def __init__(self, root_path: Path, config: DeepNoteConfig) -> None:
        self.root = root_path
        self.config = config
        self.meta = self.root / ".deepnote"
        self.graph = WikiGraph(self.meta / "graph.json")
        self.history = WikiHistory(self.meta / "history")
        self.search_index = WikiSearchIndex(self.meta / "index", vector_store=config.search.vector_store)
        self._init_layout()

    @classmethod
    def from_settings(cls, settings: Any) -> "WikiStore":
        cfg = getattr(settings, "deepnote", None) or DeepNoteConfig()
        root = Path(os.path.expandvars(os.path.expanduser(cfg.path))).resolve()
        return cls(root, cfg)

    def exists(self) -> bool:
        return self.root.exists() and (self.root / "SCHEMA.md").exists()

    def close(self) -> None:
        try:
            self.search_index.close()
        except Exception:
            pass

    def _init_layout(self) -> None:
        for d in [
            self.root,
            self.meta,
            self.root / "raw" / "articles",
            self.root / "raw" / "papers",
            self.root / "raw" / "transcripts",
            self.root / "raw" / "assets",
            self.root / "entities",
            self.root / "concepts",
            self.root / "comparisons",
            self.root / "queries",
            self.root / "_archive",
        ]:
            d.mkdir(parents=True, exist_ok=True)
        self._ensure_file(self.root / "SCHEMA.md", SCHEMA_TEMPLATE)
        self._ensure_file(self.root / "index.md", INDEX_TEMPLATE)
        self._ensure_file(self.root / "log.md", LOG_TEMPLATE)

    def _ensure_file(self, path: Path, content: str) -> None:
        if not path.exists():
            path.write_text(content, encoding="utf-8")

    def _append_log(self, action: str, subject: str, details: list[str] | None = None) -> None:
        details = details or []
        ts = time.strftime("%Y-%m-%d")
        lines = [f"\n## [{ts}] {action} | {subject}"]
        lines.extend([f"- {d}" for d in details])
        with (self.root / "log.md").open("a", encoding="utf-8") as f:
            f.write("\n".join(lines) + "\n")

    def read_schema(self) -> str:
        return (self.root / "SCHEMA.md").read_text(encoding="utf-8")

    def read_index(self) -> str:
        return (self.root / "index.md").read_text(encoding="utf-8")

    def read_log_tail(self, entries: int = 30) -> str:
        text = (self.root / "log.md").read_text(encoding="utf-8")
        return "\n".join(text.splitlines()[-max(1, entries):])

    def get_stats(self) -> dict[str, Any]:
        pages = list(self.iter_wiki_pages())
        return {
            "root": str(self.root),
            "total_pages": len(pages),
            "entities": len(list((self.root / "entities").glob("*.md"))),
            "concepts": len(list((self.root / "concepts").glob("*.md"))),
            "comparisons": len(list((self.root / "comparisons").glob("*.md"))),
            "queries": len(list((self.root / "queries").glob("*.md"))),
        }

    def get_orient_payload(self, log_entries: int = 30) -> dict[str, Any]:
        return {
            "schema": self.read_schema(),
            "index": self.read_index(),
            "recent_log": self.read_log_tail(log_entries),
            "stats": self.get_stats(),
        }

    def iter_wiki_pages(self):
        for folder in ("entities", "concepts", "comparisons", "queries"):
            yield from (self.root / folder).glob("*.md")

    def _extract_links(self, text: str) -> list[str]:
        links: list[str] = []
        for m in _WIKILINK_RE.findall(text):
            slug = self.slugify(m)
            if slug:
                links.append(slug)
        return sorted(set(links))

    @staticmethod
    def slugify(name: str) -> str:
        s = re.sub(r"[^a-zA-Z0-9\\-\\s_]", "", name).strip().lower()
        s = re.sub(r"[\\s_]+", "-", s)
        return s.strip("-")

    def write_page(self, section: str, title: str, body: str, tags: list[str] | None = None, sources: list[str] | None = None) -> Path:
        tags = tags or ["concept"]
        sources = sources or []
        slug = self.slugify(title) or "untitled"
        page = self.root / section / f"{slug}.md"
        now = time.strftime("%Y-%m-%d")
        frontmatter = (
            "---\n"
            f"title: {title}\n"
            f"created: {now}\n"
            f"updated: {now}\n"
            f"type: {section[:-1] if section.endswith('s') else section}\n"
            f"tags: {json.dumps(tags, ensure_ascii=False)}\n"
            f"sources: {json.dumps(sources, ensure_ascii=False)}\n"
            "---\n\n"
        )
        content = frontmatter + body.strip() + "\n"
        page.write_text(content, encoding="utf-8")
        links = self._extract_links(content)
        self.graph.update_links(slug, links)
        self.search_index.upsert_document(
            path=str(page.relative_to(self.root)),
            title=title,
            content=content,
            tags=tags,
        )
        self.history.commit(str(page.relative_to(self.root)), content, message="page upsert")
        self._append_log("update", title, [f"updated {page.relative_to(self.root)}"])
        self.rebuild_index_file()
        return page

    def save_raw_source(self, source_type: str, title: str, content: str) -> Path:
        source_type = source_type if source_type in {"articles", "papers", "transcripts"} else "articles"
        slug = self.slugify(title) or f"source-{int(time.time())}"
        path = self.root / "raw" / source_type / f"{slug}.md"
        path.write_text(content, encoding="utf-8")
        self._append_log("ingest", title, [f"saved raw source {path.relative_to(self.root)}"])
        return path

    def query(self, query: str, mode: str = "hybrid", limit: int = 10) -> list[dict[str, Any]]:
        mode = (mode or "hybrid").lower().strip()
        if mode == "keyword":
            rows = self.search_index.keyword_search(query, limit=limit)
        elif mode == "semantic":
            rows = self.search_index.semantic_search(query, limit=limit)
        else:
            k = self.search_index.keyword_search(query, limit=limit)
            s = self.search_index.semantic_search(query, limit=limit)
            by_path: dict[str, dict[str, Any]] = {}
            for r in k + s:
                p = str(r.get("path", ""))
                if not p:
                    continue
                by_path.setdefault(p, r)
            rows = list(by_path.values())[:limit]
        return rows

    def rebuild_index_file(self) -> None:
        sections = {
            "Entities": sorted((self.root / "entities").glob("*.md")),
            "Concepts": sorted((self.root / "concepts").glob("*.md")),
            "Comparisons": sorted((self.root / "comparisons").glob("*.md")),
            "Queries": sorted((self.root / "queries").glob("*.md")),
        }
        total = sum(len(v) for v in sections.values())
        now = time.strftime("%Y-%m-%d")
        lines = [
            "# DeepNote Index",
            "",
            "> Content catalog for DeepNote.",
            f"> Last updated: {now} | Total pages: {total}",
            "",
        ]
        for section, pages in sections.items():
            lines.append(f"## {section}")
            for p in pages:
                slug = p.stem
                lines.append(f"- [[{slug}]]")
            lines.append("")
        (self.root / "index.md").write_text("\n".join(lines).strip() + "\n", encoding="utf-8")

