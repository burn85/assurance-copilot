"""Self-check for the eval ablation view (A raw vs B +HITL).

No API calls: exercises the pure record-transform + metric recompute so a
broken _hitl_view or a mis-counted agreement fails loudly.
"""

import pathlib
import sys

_ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT / "eval"))
sys.path.insert(0, str(_ROOT / "src"))

from run_eval import _hitl_view, _policy_only_escalations, compute_metrics  # noqa: E402


def _rec(expert, pred, escalated):
    return {
        "expert_verdict": expert,
        "predicted_verdict": pred,
        "confidence": 0.5,
        "escalated": escalated,
        "escalation_reason": "test" if escalated else None,
    }


def test_hitl_view_forces_needs_human_and_leaves_original_intact():
    recs = [_rec("needs_human", "gap", True)]
    viewed = _hitl_view(recs)
    assert viewed[0]["predicted_verdict"] == "needs_human"
    assert recs[0]["predicted_verdict"] == "gap"  # input not mutated


def test_policy_recovers_escalated_case_expert_wanted_reviewed():
    # Model called it gap (wrongly); policy escalated; expert wanted needs_human.
    recs = [
        _rec("needs_human", "gap", True),        # A wrong, B correct
        _rec("satisfied", "satisfied", False),   # correct in both
    ]
    a = compute_metrics(recs)
    b = compute_metrics(_hitl_view(recs))
    assert a["verdict_agreement"] == 0.5
    assert b["verdict_agreement"] == 1.0


def test_policy_only_escalations_excludes_model_self_flags():
    recs = [
        _rec("needs_human", "needs_human", True),  # model self-flagged -> not policy-only
        _rec("satisfied", "satisfied", True),      # policy-only escalation
        _rec("gap", "gap", False),
    ]
    only = _policy_only_escalations(recs)
    assert len(only) == 1
    assert only[0]["predicted_verdict"] == "satisfied"
