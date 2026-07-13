"""Structural self-check for the OSCAL serializer (offline, no schema download).

Verifies the required spine, the verdict->status mapping, and observation<->finding
link integrity. Full validation against the official NIST schema is a documented,
opt-in step (validate_against_schema); this keeps CI offline.
"""

from assurance_copilot.models import Citation, ReviewResult, Verdict
from assurance_copilot.oscal import to_assessment_results


def _results():
    return [
        ReviewResult(
            control_id="ISMS-P 2.5.1", verdict=Verdict.SATISFIED, confidence=0.9,
            reasoning="Approval, timely revocation, and reconciliation all evidenced.",
            citation=Citation(evidence_span="revocation ticket HR-2026-0512"),
        ),
        ReviewResult(
            control_id="ISMS-P 2.5.3", verdict=Verdict.GAP, confidence=0.85,
            reasoning="Terminated users' accounts remained active.",
            escalated=True, escalation_reason="model_requested_human",
        ),
    ]


def test_required_spine():
    ar = to_assessment_results(_results())["assessment-results"]
    assert ar["metadata"]["oscal-version"] == "1.1.2"
    assert "import-ap" in ar          # required by schema
    assert set(ar["metadata"]) >= {"title", "last-modified", "version", "oscal-version"}
    res = ar["results"][0]
    assert len(res["observations"]) == 2
    assert len(res["findings"]) == 2


def test_verdict_status_mapping_and_remarks():
    findings = to_assessment_results(_results())["assessment-results"]["results"][0]["findings"]
    by_control = {f["title"]: f for f in findings}
    assert by_control["ISMS-P 2.5.1"]["target"]["status"]["state"] == "satisfied"
    gap = by_control["ISMS-P 2.5.3"]["target"]["status"]
    assert gap["state"] == "not-satisfied"
    assert "verdict=gap" in gap["remarks"]
    assert "escalated" in gap["remarks"]


def test_findings_link_to_real_observations():
    res = to_assessment_results(_results())["assessment-results"]["results"][0]
    obs_uuids = {o["uuid"] for o in res["observations"]}
    for f in res["findings"]:
        linked = f["related-observations"][0]["observation-uuid"]
        assert linked in obs_uuids   # no dangling reference
        conf = next(p for p in f["props"] if p["name"] == "confidence")
        assert 0.0 <= float(conf["value"]) <= 1.0
