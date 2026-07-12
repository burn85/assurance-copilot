"""Human-in-the-loop routing policy.

The model self-reports a verdict and confidence; this layer decides — with
explicit, auditable rules — when a draft must be escalated to a human auditor
regardless of what the model said. Keeping this in code (not in the prompt)
means the escalation behaviour is testable and tunable, and shows up in the
eval as a measurable "did we escalate the right cases?" metric.

Why this matters for assurance specifically: the cost of a wrong "satisfied" is
asymmetric — it can let a real gap through an audit. So the policy is
deliberately conservative around low-confidence passes.
"""

from __future__ import annotations

from ..models import ReviewResult, Verdict

# Below this confidence, a machine "satisfied"/"gap" is not trusted on its own.
CONFIDENCE_ESCALATION_THRESHOLD = 0.70


def apply_hitl_policy(result: ReviewResult) -> ReviewResult:
    # 1. The model itself asked for a human — respect it.
    if result.verdict == Verdict.NEEDS_HUMAN:
        result.escalated = True
        result.escalation_reason = result.escalation_reason or "model_requested_human"
        return result

    # 2. A low-confidence pass or fail is escalated (asymmetric-risk guardrail).
    if result.verdict in (Verdict.SATISFIED, Verdict.GAP):
        if result.confidence < CONFIDENCE_ESCALATION_THRESHOLD:
            result.escalated = True
            result.escalation_reason = (
                f"confidence {result.confidence:.2f} < {CONFIDENCE_ESCALATION_THRESHOLD:.2f}"
            )
            return result

    # 3. Missing grounding on a "satisfied" verdict is not acceptable.
    if result.verdict == Verdict.SATISFIED and not result.citation.evidence_span:
        result.escalated = True
        result.escalation_reason = "satisfied_without_evidence_grounding"
        return result

    result.escalated = False
    return result
