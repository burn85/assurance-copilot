"""Serialize ReviewResults to OSCAL Assessment Results v1.1.2 (JSON).

Scope is a deliberately minimal *valid* subset (BUILD-plan §8.4): the required
`metadata` / `import-ap` / `results` spine, plus one `observation` and one
`finding` per review. It is not a full OSCAL implementation — just enough to be
schema-valid and to interoperate.

Verdict -> finding status mapping:
  satisfied            -> "satisfied"
  gap/insufficient/... -> "not-satisfied"  (the specific verdict + any escalation
                                            reason go in the status remarks)

confidence and the escalation flag are carried as custom `props` under a private
namespace so they survive the round-trip without polluting the standard fields.
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone

from ..models import ReviewResult, Verdict

OSCAL_VERSION = "1.1.2"
_NS = "urn:assurance-copilot"  # namespace for non-standard props


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _observation(r: ReviewResult) -> dict:
    obs = {
        "uuid": str(uuid.uuid4()),
        "description": r.reasoning or f"Examined evidence for {r.control_id}.",
        "methods": ["EXAMINE"],
        "collected": _now(),
    }
    span = r.citation.evidence_span if r.citation else ""
    if span:
        obs["relevant-evidence"] = [{"description": f"Evidence span: {span}"}]
    return obs


def _finding(r: ReviewResult, observation_uuid: str) -> dict:
    satisfied = r.verdict == Verdict.SATISFIED
    status = {"state": "satisfied" if satisfied else "not-satisfied"}
    remarks = [] if satisfied else [f"verdict={r.verdict.value}"]
    if r.escalated:
        remarks.append(f"escalated: {r.escalation_reason or 'human review required'}")
    if remarks:
        status["remarks"] = "; ".join(remarks)
    return {
        "uuid": str(uuid.uuid4()),
        "title": r.control_id,
        "description": r.reasoning or f"Assessment of {r.control_id}.",
        "target": {
            "type": "objective-id",
            "target-id": r.control_id,
            "status": status,
        },
        "related-observations": [{"observation-uuid": observation_uuid}],
        "props": [
            {"ns": _NS, "name": "confidence", "value": f"{r.confidence:.2f}"},
            {"ns": _NS, "name": "escalated", "value": str(r.escalated).lower()},
        ],
    }


def to_assessment_results(
    results: list[ReviewResult],
    title: str = "Assurance Copilot — Assessment Results",
    version: str = "0.1.0",
) -> dict:
    """Build one OSCAL Assessment Results document from a batch of reviews."""
    observations, findings = [], []
    for r in results:
        obs = _observation(r)
        observations.append(obs)
        findings.append(_finding(r, obs["uuid"]))

    now = _now()
    result_block = {
        "uuid": str(uuid.uuid4()),
        "title": "Automated evidence review",
        "description": "Draft verdicts produced by the judgment layer.",
        "start": now,
        # required by the schema; we assess every control passed in.
        "reviewed-controls": {"control-selections": [{"include-all": {}}]},
        "observations": observations,
        "findings": findings,
    }
    return {
        "assessment-results": {
            "uuid": str(uuid.uuid4()),
            "metadata": {
                "title": title,
                "last-modified": now,
                "version": version,
                "oscal-version": OSCAL_VERSION,
            },
            # import-ap is required by the schema; we assess without a formal
            # assessment plan, so point at an empty reference.
            "import-ap": {"href": ""},
            "results": [result_block],
        }
    }


def dumps(results: list[ReviewResult], **kwargs) -> str:
    return json.dumps(to_assessment_results(results, **kwargs), ensure_ascii=False, indent=2)


def validate_against_schema(document: dict, schema_path: str) -> None:
    """Validate a document against the official OSCAL AR JSON schema.

    The ~130 KB NIST schema is not bundled — download the v1.1.2 copy:

        curl -sL -o oscal_ar.json \\
          https://github.com/usnistgov/OSCAL/releases/download/v1.1.2/oscal_assessment-results_schema.json

    NOTE: OSCAL's schema uses ECMA `\\p{...}` unicode-property escapes in its
    `pattern` keywords, which Python's `re` cannot compile. We relax those
    patterns to '.' before validating, so structure and required-field checks
    run but token character-class constraints are not enforced. For strict,
    pattern-exact validation use the official `oscal-cli`.

    Raises jsonschema.ValidationError if the document does not conform.
    """
    import re
    import jsonschema  # lazy: only needed when actually validating

    with open(schema_path, encoding="utf-8") as f:
        schema = json.load(f)

    def _relax(node):
        if isinstance(node, dict):
            return {
                k: (re.sub(r"\\p\{[^}]*\}", ".", v) if k == "pattern" and isinstance(v, str) else _relax(v))
                for k, v in node.items()
            }
        if isinstance(node, list):
            return [_relax(x) for x in node]
        return node

    validator = jsonschema.Draft7Validator(_relax(schema))
    errors = sorted(validator.iter_errors(document), key=lambda e: list(e.path))
    if errors:
        e = errors[0]
        raise jsonschema.ValidationError(
            f"{len(errors)} OSCAL schema error(s); first at {list(e.path)}: {e.message}"
        )
