"""MaxKB-free control retriever — the MVP stand-in for the RAG backend.

Parses the markdown control catalog into `Control` objects so the review
pipeline (and the CLI) can run with no external infrastructure. Retrieval is a
naive keyword-overlap score, which is plenty for a small curated catalog.

# ponytail: naive substring keyword match, O(catalog) per query.
# Upgrade path: swap `retrieve()` for embeddings / the MaxKB client if the
# catalog grows past a few dozen controls.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Optional

from .. import config
from ..models import Control

_HEADING = re.compile(r"^##\s+(?P<id>.+?)\s+—\s+(?P<title>.+?)\s*$")


def _field(block: str, label: str) -> str:
    """Extract the text after a `- **Label:**` bullet within one control block."""
    m = re.search(rf"\*\*{label}:\*\*\s*(?P<val>.+?)\s*$", block, re.MULTILINE)
    return m.group("val").strip() if m else ""


def _parse_catalog(text: str) -> list[Control]:
    controls: list[Control] = []
    # Split so each chunk starts at a "## " heading.
    chunks = re.split(r"(?m)^(?=##\s)", text)
    for chunk in chunks:
        first_line, _, rest = chunk.partition("\n")
        m = _HEADING.match(first_line)
        if not m:
            continue
        controls.append(
            Control(
                id=m.group("id").strip(),
                title=m.group("title").strip(),
                text=_field(rest, "Requirement"),
                framework="ISMS-P",
                guidance=_field(rest, "Guidance"),
            )
        )
    return controls


def _tokens(s: str) -> list[str]:
    # Keep Korean/alphanumeric runs; drop punctuation. Crude but adequate.
    return [t for t in re.split(r"[^0-9A-Za-z가-힣]+", s.lower()) if len(t) > 1]


class LocalRetriever:
    def __init__(self, catalog_path: Optional[Path] = None) -> None:
        path = Path(catalog_path or config.CONTROLS_CATALOG)
        self._controls = _parse_catalog(path.read_text(encoding="utf-8"))
        self._by_id = {c.id: c for c in self._controls}

    def all_controls(self) -> list[Control]:
        return list(self._controls)

    def get_control(self, control_id: str) -> Optional[Control]:
        return self._by_id.get(control_id.strip())

    def retrieve(self, query: str, top_k: int = 3) -> list[str]:
        """Return the requirement spans of the top_k controls by keyword overlap."""
        q = set(_tokens(query))
        if not q:
            return []
        scored = []
        for c in self._controls:
            hay = set(_tokens(f"{c.id} {c.title} {c.text} {c.guidance}"))
            score = len(q & hay)
            if score:
                scored.append((score, c.text))
        scored.sort(key=lambda t: t[0], reverse=True)
        return [text for _, text in scored[:top_k]]


if __name__ == "__main__":
    r = LocalRetriever()
    controls = r.all_controls()
    assert len(controls) >= 5, f"expected >=5 controls, parsed {len(controls)}"
    c = r.get_control("ISMS-P 2.5.1")
    assert c is not None and "계정" in c.text, "get_control failed to parse requirement"
    assert c.guidance, "guidance not parsed"
    hits = r.retrieve("다중요소 인증 원격 접근", top_k=2)
    assert hits, "retrieve returned nothing for a relevant query"
    print(f"OK — parsed {len(controls)} controls; retrieve top hit:\n  {hits[0][:80]}...")
