# Assurance Copilot

A **judgment layer** for audit evidence review. Given a control requirement and
the evidence submitted to demonstrate it, the tool produces a *draft* verdict —
does this evidence satisfy the control? — grounds that verdict in quoted source
spans, and routes the genuine judgment calls to a human reviewer.

> This is a demo project, not a production system. Sample evidence and the
> evaluation labels are entirely synthetic. See [Limitations](#limitations).

## The problem

Reviewing audit evidence is slow and judgment-heavy. For every control, an
auditor collects artifacts — policies, screenshots, configuration exports,
tickets — and has to decide whether they actually demonstrate the control, or
merely look like they do. Much of that is pattern-matching that a machine can
draft. But a meaningful share hinges on *auditor judgment*: materiality,
sampling adequacy, whether a compensating control is good enough. Getting that
split right — draft the routine, escalate the judgment — is the point.

## What it does

For a `(control, evidence)` pair it returns:

- a **verdict**: `satisfied` · `gap` · `insufficient` · `needs_human`
- a self-reported **confidence**
- **reasoning** in an auditor's voice
- a **citation**: the span of the control and the span of the evidence it relied on
- an **escalation flag** when the case should go to a human

`needs_human` is a first-class outcome, not a failure — being able to say "this
needs auditor judgment" is as valuable as a confident pass or fail.

## Build vs. buy

Retrieval is commoditised — plenty of tools will search a knowledge base well.
The hard, valuable part is the **judgment**: deciding whether evidence meets a
control and when to defer to a human. So this project *buys* retrieval (behind a
pluggable interface) and *builds* the judgment layer, the human-in-the-loop
policy, and the evaluation harness — the parts that are the actual product.

## Architecture

| Layer | Role | Build or buy |
|---|---|---|
| Retrieval | find the relevant control text | **buy** — pluggable (local keyword retriever for the MVP; RAG backend as a roadmap option) |
| Judgment | draft the verdict + grounding | **build** — Claude with adaptive thinking; prompts encode the auditor's mindset |
| HITL policy | decide what a human must review | **build** — explicit, testable escalation rules |
| Evaluation | measure agreement, gap recall, escalation calibration | **build** — the reliability multiplier |

On-device OCR for image evidence and legal-text grounding are **roadmap** items
behind their own interfaces, not all wired up yet.
[OSCAL](https://pages.nist.gov/OSCAL/) assessment-results export is implemented
(see below). Full design rationale is in [ARCHITECTURE.md](ARCHITECTURE.md).

## Human-in-the-loop design

The cost of a wrong "satisfied" is asymmetric — it can let a real gap through an
audit. So the escalation policy (in [`hitl.py`](src/assurance_copilot/judgment/hitl.py))
is deliberately conservative and lives in code, not in the prompt, so it is
testable and shows up as a metric. A draft is escalated to a human when:

- the model itself asks for a human;
- a `satisfied`/`gap` verdict is below a confidence threshold; or
- a `satisfied` verdict has no evidence grounding.

## Explainability

Every verdict quotes the span of the control it was judged against and the span
of the evidence it relied on. A verdict you can't trace isn't useful to an
auditor.

## Evaluation

The harness runs the judgment layer over a small labelled dataset and reports:

- **Verdict agreement** with expert labels (+ confusion matrix)
- **Gap-detection recall** — of the real gaps, how many were caught (a missed
  gap is the most dangerous error)
- **HITL calibration** — of the cases an expert flagged as needing human
  judgment, how many were escalated (precision/recall)
- **Confidence vs. accuracy** — a rough calibration read

On 18 synthetic samples with `claude-opus-4-8`:

| Metric | Value |
|---|---|
| Verdict agreement | 83.3% (15/18) |
| Gap recall | 100.0% (5/5) |
| Escalation recall / precision | 75.0% / 100.0% |
| Mean confidence (correct / wrong) | 0.845 / 0.673 |

An ablation (`--ablation`) isolates the HITL policy's contribution from the
model's own judgment. On this set the delta is zero — the deterministic policy
never fired beyond the model's own `needs_human` calls, an honest null result
that the harness makes visible rather than hides. Method, confusion matrix, and
the ablation are in [`eval/README.md`](eval/README.md).

## Quickstart

```bash
pip install -e ".[dev]"      # or: pip install -r requirements.txt
cp .env.example .env         # add your ANTHROPIC_API_KEY

pytest tests/                # unit tests — no API key needed
python eval/run_eval.py      # runs the eval (needs ANTHROPIC_API_KEY)
```

After `pip install -e .` the CLI is available:

```bash
assurance-copilot review --control "ISMS-P 2.5.1" --evidence evidence.txt
assurance-copilot eval --ablation
assurance-copilot export-oscal --in eval/results/latest.json --out ar.json
```

The model defaults to `claude-opus-4-8`; override with `ASSURANCE_MODEL`.

## Limitations

- **Demo, not production.** No auth, no persistence, no scale hardening.
- **Synthetic data only.** The sample evidence and expert labels are fabricated
  for demonstration; no real audit data is used.
- **Small evaluation set.** A few dozen cases — indicative, not statistically robust.
- **Self-reported confidence.** The model's confidence is not independently calibrated.
- **Paraphrased controls.** Control texts are short summaries for demo use, not
  official normative texts.
- **Roadmap components** (on-device OCR, RAG backend, OSCAL export, legal
  grounding) are interfaces-first and not all implemented.

## License

MIT — see [LICENSE](LICENSE). A RAG backend option (MaxKB, GPL-3.0) is referenced
as an external service and is **not** bundled with this repository.
