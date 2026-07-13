"""Self-check for the mode-B legal-grounding helpers (no network).

Verifies: grounding is gated on the OC key, the control->statute seed resolves,
and verify_citations delegates to the injected client.
"""

from assurance_copilot.legal import (
    CONTROL_STATUTE_BASIS,
    grounding_enabled,
    statute_basis,
    verify_citations,
)
from assurance_copilot.legal.law_client import CitationCheck


def test_grounding_gated_on_key(monkeypatch):
    monkeypatch.delenv("LAW_OC", raising=False)
    assert grounding_enabled() is False
    assert grounding_enabled("some-oc") is True
    monkeypatch.setenv("LAW_OC", "env-oc")
    assert grounding_enabled() is True


def test_statute_basis_lookup():
    assert CONTROL_STATUTE_BASIS  # seeded
    assert statute_basis("ISMS-P 2.5.1") == "개인정보보호법 제29조"
    assert statute_basis("ISMS-P 9.9.9") == ""  # unseeded -> empty


def test_verify_citations_delegates():
    sentinel = CitationCheck(ok=False, summary="총 2건", raw="...")

    class FakeClient:
        def verify_citations(self, text):
            assert "제29조" in text
            return sentinel

    assert verify_citations("개인정보보호법 제29조", FakeClient()) is sentinel
