"""Legal grounding via korean-law-mcp (mode B, local stdio).

Why: ISMS-P access-control criteria are rooted in real statutes (the Personal
Information Protection Act — 개인정보보호법). When grounding is enabled the
reviewer (1) tells the model which statute family the control derives from and
asks it to cite the specific article, then (2) verifies that citation against
the 법제처 database via `verify_citations` — a fabricated article number is
flagged and escalated. The verification runs client-side (see law_client), so
it is independent of the API gateway.

The MVP stands without this: if `LAW_OC` is unset, `grounding_enabled()` is
False and the reviewer runs its normal, ungrounded path.

Scope note: this grounds and *verifies* the citation. Injecting the full
article text (get_law_text) into the prompt is a supported follow-on — the
client exposes it — but is not wired into the default review loop yet.
"""

from __future__ import annotations

import os

from .law_client import CitationCheck, LawClient

# Statute basis for each seeded control. Access-control criteria (2.5.x / 2.6.x)
# share the safety-measures duty of the Personal Information Protection Act
# (개인정보보호법 제29조).
# ponytail: article-level refinement per control is a domain-review task; this
# seed maps the family to its shared statutory basis, which is accurate enough
# to ground a verdict and to exercise verify_citations.
CONTROL_STATUTE_BASIS = {
    "ISMS-P 2.5.1": "개인정보보호법 제29조",
    "ISMS-P 2.5.3": "개인정보보호법 제29조",
    "ISMS-P 2.5.4": "개인정보보호법 제29조",
    "ISMS-P 2.5.5": "개인정보보호법 제29조",
    "ISMS-P 2.5.6": "개인정보보호법 제29조",
    "ISMS-P 2.6.1": "개인정보보호법 제29조",
    "ISMS-P 2.6.2": "개인정보보호법 제29조",
}


def grounding_enabled(oc: str | None = None) -> bool:
    """True when a 법제처 OC key is available (env LAW_OC or explicit arg)."""
    return bool(oc or os.environ.get("LAW_OC"))


def statute_basis(control_id: str) -> str:
    """The statute this control derives from, or '' if unseeded."""
    return CONTROL_STATUTE_BASIS.get(control_id, "")


def verify_citations(text: str, client: LawClient) -> CitationCheck:
    """Verify any statute citations in `text` against the 법제처 database."""
    return client.verify_citations(text)
