"""Command-line interface — wires the pieces into three subcommands.

    assurance-copilot review --control "ISMS-P 2.5.1" --evidence screenshot.png
    assurance-copilot eval [--ablation]
    assurance-copilot export-oscal --in eval/results/latest.json --out ar.json

`review` is the only path that calls the API (when actually invoked). `eval`
delegates to eval/run_eval.py; `export-oscal` is a pure offline transform.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

from . import config
from .models import Citation, Evidence, ReviewResult, Verdict

_IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp", ".gif", ".webp", ".pdf"}


def _load_evidence(path: str, control_id: str, ocr: str) -> Evidence:
    p = Path(path)
    if p.suffix.lower() in _IMAGE_EXTS:
        from .ocr.base import select_backend  # lazy: OCR deps only when needed

        res = select_backend(ocr).extract(str(p))
        return Evidence(control_id=control_id, text=res.text, source=p.name, ocr_backend=res.backend)
    return Evidence(control_id=control_id, text=p.read_text(encoding="utf-8"), source=p.name)


def _print_human(r: ReviewResult) -> None:
    print(f"Control:    {r.control_id}")
    print(f"Verdict:    {r.verdict.value}" + ("  [ESCALATED]" if r.escalated else ""))
    print(f"Confidence: {r.confidence:.2f}")
    if r.escalated and r.escalation_reason:
        print(f"Escalated:  {r.escalation_reason}")
    print(f"Reasoning:  {r.reasoning}")
    if r.citation.criterion_span:
        print(f"  control span:  {r.citation.criterion_span}")
    if r.citation.evidence_span:
        print(f"  evidence span: {r.citation.evidence_span}")
    if r.followup_question:
        print(f"Ask auditee: {r.followup_question}")


def cmd_review(args: argparse.Namespace) -> None:
    from .retrieval.local_retriever import LocalRetriever
    from .judgment.reviewer import EvidenceReviewer

    retriever = LocalRetriever()
    control = retriever.get_control(args.control)
    if control is None:
        known = ", ".join(c.id for c in retriever.all_controls())
        sys.exit(f"Unknown control {args.control!r}. Known: {known}")

    evidence = _load_evidence(args.evidence, control.id, args.ocr)
    result = EvidenceReviewer().review(control, evidence)
    if args.json:
        print(result.to_json())
    else:
        _print_human(result)


def cmd_eval(args: argparse.Namespace) -> None:
    script = config.REPO_ROOT / "eval" / "run_eval.py"
    raise SystemExit(subprocess.call([sys.executable, str(script), *args.rest]))


def _load_results(path: str) -> list[ReviewResult]:
    """Read eval results (latest.json dict or a jsonl) back into ReviewResults."""
    raw = Path(path).read_text(encoding="utf-8").strip()
    if raw.startswith("{"):
        records = json.loads(raw).get("records", [])
    else:
        records = [json.loads(line) for line in raw.splitlines() if line.strip()]

    out = []
    for r in records:
        verdict = r.get("predicted_verdict") or r.get("verdict") or "needs_human"
        out.append(
            ReviewResult(
                control_id=r["control_id"],
                verdict=Verdict(verdict),
                confidence=float(r.get("confidence", 0.0)),
                reasoning=str(r.get("reasoning", "")),
                citation=Citation(evidence_span=str(r.get("evidence_span", ""))),
                escalated=bool(r.get("escalated", False)),
                escalation_reason=str(r.get("escalation_reason") or ""),
                model=str(r.get("model", "")),
            )
        )
    return out


def cmd_export_oscal(args: argparse.Namespace) -> None:
    from .oscal import to_assessment_results, validate_against_schema

    results = _load_results(args.in_path)
    doc = to_assessment_results(results)
    Path(args.out).write_text(json.dumps(doc, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote {len(results)} finding(s) -> {args.out}")
    if args.schema:
        validate_against_schema(doc, args.schema)
        print(f"Validated against {args.schema}: OK")


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="assurance-copilot", description=__doc__)
    sub = p.add_subparsers(dest="command", required=True)

    r = sub.add_parser("review", help="judge one (control, evidence) pair")
    r.add_argument("--control", required=True, help='control id, e.g. "ISMS-P 2.5.1"')
    r.add_argument("--evidence", required=True, help="path to evidence (text or image)")
    r.add_argument("--ocr", default="auto", choices=["auto", "apple_vision", "tesseract"])
    r.add_argument("--json", action="store_true", help="emit JSON instead of a human summary")
    r.set_defaults(func=cmd_review)

    e = sub.add_parser("eval", help="run the eval harness (eval/run_eval.py)")
    e.add_argument("rest", nargs=argparse.REMAINDER, help="args forwarded to run_eval.py")
    e.set_defaults(func=cmd_eval)

    x = sub.add_parser("export-oscal", help="serialize eval results to OSCAL AR JSON")
    x.add_argument("--in", dest="in_path", required=True, help="eval results (latest.json or jsonl)")
    x.add_argument("--out", required=True, help="output OSCAL JSON path")
    x.add_argument("--schema", help="optional path to OSCAL AR schema to validate against")
    x.set_defaults(func=cmd_export_oscal)
    return p


def main(argv: list[str] | None = None) -> None:
    args = build_parser().parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
