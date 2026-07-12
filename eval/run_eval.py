"""Eval harness — the reliability multiplier.

Runs the judgment layer over a small labelled dataset and reports the metrics
that actually matter for assurance work:

  1. Verdict agreement (overall) + a confusion matrix.
  2. Gap-detection recall — of the real gaps, how many did we catch (as gap OR
     needs_human)? A missed gap is the most dangerous error in an audit.
  3. HITL calibration — of the cases an expert flagged as needing human
     judgment, how many did we escalate? (precision/recall on escalation.)
  4. Mean confidence vs accuracy — a rough calibration read.

Usage: `python eval/run_eval.py`  (needs ANTHROPIC_API_KEY)
"""

from __future__ import annotations

import json
import pathlib
import sys
from datetime import datetime, timezone

# Make `assurance_copilot` importable whether or not the package is pip-installed.
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))

from assurance_copilot import config  # noqa: E402
from assurance_copilot.judgment.reviewer import EvidenceReviewer  # noqa: E402
from assurance_copilot.models import Control, Evidence, Verdict  # noqa: E402

VERDICTS = [v.value for v in Verdict]  # satisfied, gap, insufficient, needs_human


def load_dataset(path: pathlib.Path) -> list[dict]:
    if not path.exists():
        sys.exit(f"Dataset not found: {path}\nCreate it first (see eval/README.md).")
    samples = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("//"):
            samples.append(json.loads(line))
    return samples


def evaluate(samples: list[dict]) -> dict:
    reviewer = EvidenceReviewer()
    records = []
    for i, s in enumerate(samples, 1):
        c, e = s["control"], s["evidence"]
        control = Control(
            id=c["id"], title=c.get("title", ""), text=c["text"],
            framework=c.get("framework", "ISMS-P"), guidance=c.get("guidance", ""),
        )
        evidence = Evidence(control_id=c["id"], text=e["text"], source=e.get("source", ""))
        print(f"[{i}/{len(samples)}] reviewing {control.id} ...", flush=True)
        result = reviewer.review(control, evidence)
        records.append({
            "control_id": control.id,
            "expert_verdict": s["expert_verdict"],
            "predicted_verdict": result.verdict.value,
            "confidence": result.confidence,
            "escalated": result.escalated,
            "escalation_reason": result.escalation_reason,
            "reasoning": result.reasoning,
        })
    return {"records": records, "metrics": compute_metrics(records)}


def compute_metrics(records: list[dict]) -> dict:
    n = len(records)
    agree = sum(r["expert_verdict"] == r["predicted_verdict"] for r in records)

    # Confusion matrix[expert][predicted]
    cm = {a: {b: 0 for b in VERDICTS} for a in VERDICTS}
    for r in records:
        cm[r["expert_verdict"]][r["predicted_verdict"]] += 1

    # Gap-detection recall: a real gap is "caught" if predicted gap OR needs_human.
    gap_total = sum(r["expert_verdict"] == "gap" for r in records)
    gap_caught = sum(
        r["expert_verdict"] == "gap" and r["predicted_verdict"] in ("gap", "needs_human")
        for r in records
    )

    # HITL calibration: positive class = expert-labelled needs_human.
    nh_total = sum(r["expert_verdict"] == "needs_human" for r in records)
    escalated_total = sum(r["escalated"] for r in records)
    escalated_and_nh = sum(r["escalated"] and r["expert_verdict"] == "needs_human" for r in records)

    correct = [r for r in records if r["expert_verdict"] == r["predicted_verdict"]]
    wrong = [r for r in records if r["expert_verdict"] != r["predicted_verdict"]]

    def _mean(xs):
        return round(sum(xs) / len(xs), 3) if xs else None

    return {
        "n": n,
        "verdict_agreement": round(agree / n, 3) if n else None,
        "confusion_matrix": cm,
        "gap_recall": round(gap_caught / gap_total, 3) if gap_total else None,
        "gap_total": gap_total,
        "escalation_recall": round(escalated_and_nh / nh_total, 3) if nh_total else None,
        "escalation_precision": round(escalated_and_nh / escalated_total, 3) if escalated_total else None,
        "needs_human_total": nh_total,
        "mean_confidence": _mean([r["confidence"] for r in records]),
        "mean_confidence_correct": _mean([r["confidence"] for r in correct]),
        "mean_confidence_wrong": _mean([r["confidence"] for r in wrong]),
    }


def print_report(metrics: dict) -> None:
    m = metrics
    print("\n" + "=" * 60)
    print("EVAL RESULTS")
    print("=" * 60)
    print(f"Samples:            {m['n']}")
    print(f"Verdict agreement:  {_pct(m['verdict_agreement'])}")
    print(f"Gap recall:         {_pct(m['gap_recall'])}  (of {m['gap_total']} real gaps)")
    print(f"Escalation recall:  {_pct(m['escalation_recall'])}  (of {m['needs_human_total']} needs-human)")
    print(f"Escalation prec.:   {_pct(m['escalation_precision'])}")
    print(f"Mean confidence:    {m['mean_confidence']}  (correct {m['mean_confidence_correct']} / wrong {m['mean_confidence_wrong']})")

    print("\nConfusion matrix (rows = expert, cols = predicted):")
    header = "  expert\\pred  " + "".join(f"{v[:5]:>8}" for v in VERDICTS)
    print(header)
    for a in VERDICTS:
        row = "".join(f"{m['confusion_matrix'][a][b]:>8}" for b in VERDICTS)
        print(f"  {a:>11}  {row}")


def _pct(x) -> str:
    return "n/a" if x is None else f"{x * 100:.1f}%"


def main() -> None:
    samples = load_dataset(config.EVAL_DATASET)
    out = evaluate(samples)
    out["model"] = config.MODEL
    out["timestamp"] = datetime.now(timezone.utc).isoformat()

    config.EVAL_RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    result_path = config.EVAL_RESULTS_DIR / "latest.json"
    result_path.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")

    print_report(out["metrics"])
    print(f"\nModel: {out['model']}")
    print(f"Written: {result_path}")


if __name__ == "__main__":
    main()
