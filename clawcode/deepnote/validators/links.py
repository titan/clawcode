from __future__ import annotations

import re
from pathlib import Path

_WIKILINK_RE = re.compile(r"\[\[([^\]]+)\]\]")


def _slug(s: str) -> str:
    s = re.sub(r"[^a-zA-Z0-9\-\s_]", "", s).strip().lower()
    s = re.sub(r"[\s_]+", "-", s)
    return s.strip("-")


def validate_links(page_path: Path, wiki_root: Path, min_outbound: int = 2) -> list[str]:
    text = page_path.read_text(encoding="utf-8")
    links = [_slug(x) for x in _WIKILINK_RE.findall(text) if _slug(x)]
    errs: list[str] = []
    if len(set(links)) < max(0, min_outbound):
        errs.append(f"outbound links below minimum ({len(set(links))} < {min_outbound})")

    known = {p.stem for folder in ("entities", "concepts", "comparisons", "queries") for p in (wiki_root / folder).glob("*.md")}
    broken = sorted({l for l in links if l not in known})
    for b in broken:
        errs.append(f"broken wikilink: [[{b}]]")
    return errs

