"""CLI self-checks — offline paths only (no API calls).

Covers export-oscal (results -> valid OSCAL spine) and the unknown-control guard
in review, which must exit before any API call.
"""

import json

import pytest

from assurance_copilot import cli


def test_export_oscal_from_latest_json(tmp_path):
    latest = tmp_path / "latest.json"
    latest.write_text(json.dumps({"records": [
        {"control_id": "ISMS-P 2.5.1", "predicted_verdict": "satisfied", "confidence": 0.9, "reasoning": "ok", "escalated": False},
        {"control_id": "ISMS-P 2.5.3", "predicted_verdict": "gap", "confidence": 0.8, "reasoning": "x", "escalated": True, "escalation_reason": "model_requested_human"},
    ]}), encoding="utf-8")
    out = tmp_path / "ar.json"
    cli.main(["export-oscal", "--in", str(latest), "--out", str(out)])

    doc = json.loads(out.read_text(encoding="utf-8"))["assessment-results"]
    assert doc["metadata"]["oscal-version"] == "1.1.2"
    findings = doc["results"][0]["findings"]
    assert {f["title"] for f in findings} == {"ISMS-P 2.5.1", "ISMS-P 2.5.3"}


def test_review_unknown_control_exits(tmp_path):
    ev = tmp_path / "e.txt"
    ev.write_text("some evidence", encoding="utf-8")
    with pytest.raises(SystemExit):
        cli.main(["review", "--control", "NOPE-1.2.3", "--evidence", str(ev)])
