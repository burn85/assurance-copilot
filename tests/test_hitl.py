"""Unit tests for the HITL routing policy. Pure logic — no network, no API key."""

from assurance_copilot.models import Citation, ReviewResult, Verdict
from assurance_copilot.judgment.hitl import (
    CONFIDENCE_ESCALATION_THRESHOLD,
    apply_hitl_policy,
)


def _result(verdict, confidence, evidence_span="some evidence span"):
    return ReviewResult(
        control_id="ISMS-P 2.5.1",
        verdict=verdict,
        confidence=confidence,
        reasoning="",
        citation=Citation(criterion_span="criterion", evidence_span=evidence_span),
    )


def test_needs_human_is_respected():
    r = apply_hitl_policy(_result(Verdict.NEEDS_HUMAN, 0.9))
    assert r.escalated
    assert r.escalation_reason  # a reason must be recorded


def test_low_confidence_satisfied_escalates():
    r = apply_hitl_policy(_result(Verdict.SATISFIED, CONFIDENCE_ESCALATION_THRESHOLD - 0.01))
    assert r.escalated


def test_low_confidence_gap_escalates():
    r = apply_hitl_policy(_result(Verdict.GAP, 0.1))
    assert r.escalated


def test_high_confidence_grounded_satisfied_not_escalated():
    r = apply_hitl_policy(_result(Verdict.SATISFIED, 0.95))
    assert not r.escalated


def test_satisfied_without_evidence_grounding_escalates():
    r = apply_hitl_policy(_result(Verdict.SATISFIED, 0.95, evidence_span=""))
    assert r.escalated
    assert r.escalation_reason == "satisfied_without_evidence_grounding"


def test_high_confidence_gap_not_escalated():
    r = apply_hitl_policy(_result(Verdict.GAP, 0.9))
    assert not r.escalated
