# Architecture

This document describes how Assurance Copilot is put together and why the
boundaries fall where they do. It is a demo system; see
[Limitations](README.md#limitations) for what it deliberately does not do.

## Design principle: buy retrieval, build judgment

Searching a knowledge base is a solved, commoditised problem. The hard,
valuable part of audit-evidence review is the **judgment** — deciding whether a
piece of evidence actually satisfies a control, grounding that decision in the
source text, and recognising when the call belongs to a human. So the system
programs to interfaces at the commodity boundaries (retrieval, OCR) and spends
its own code on the judgment layer, the human-in-the-loop policy, and the
evaluation harness that measures them.

## Data flow

```
                 control catalog (markdown / RAG)
                          │
                          ▼
  evidence file ──▶ [ OCR backend ]──▶ Evidence ─┐
   (image/pdf)      (on-device or               │
                     Tesseract)                 ▼
                                        [ Judgment layer ]
  control id ──▶ [ retriever ] ──▶ Control ──▶  Claude (adaptive thinking)
                                                 │  emits JSON verdict
                                                 ▼
                                        [ parse → ReviewResult ]
                                                 │
                                                 ▼
                                        [ HITL policy ]  ── escalate? ──▶ human
                                                 │
                                                 ▼
                                          ReviewResult
                                          ├──▶ human-readable / JSON (CLI)
                                          └──▶ OSCAL Assessment Results (export)

  eval harness: runs the judgment layer over a labelled dataset and scores it.
```

## Components

| Component | Module | Buy / build | Notes |
|---|---|---|---|
| Retrieval | `retrieval/local_retriever.py` | **buy** (interface) | MVP uses a keyword retriever over a markdown catalog; a RAG backend is a drop-in behind the same shape. |
| OCR | `ocr/` | **buy** (interface) | Pluggable: on-device Apple Vision (private, zero-token) or Tesseract (portable fallback). |
| Judgment | `judgment/reviewer.py`, `prompts.py` | **build** | Claude via the official SDK, adaptive thinking; the prompt encodes the auditor's mindset and the verdict contract. |
| HITL policy | `judgment/hitl.py` | **build** | Deterministic, testable escalation rules that run after the model. |
| Legal grounding | `legal/` | **buy** (tool) + **build** (verify loop) | Opt-in: cite the governing statute, then verify it against a national-law MCP tool over local stdio. |
| OSCAL export | `oscal/serializer.py` | **build** | Results → NIST Assessment Results v1.1.2. |
| Evaluation | `eval/run_eval.py` | **build** | Metrics + ablation; the reliability multiplier. |
| CLI | `cli.py` | **build** | `review`, `eval`, `export-oscal`. |

## Judgment layer

`EvidenceReviewer.review(control, evidence)` builds a task-specific prompt and
calls Claude with adaptive thinking — the task is a judgment call, not a lookup.
The model returns a JSON object (verdict, confidence, reasoning, and the control
and evidence spans it relied on). Only text blocks are read from the response;
thinking blocks are skipped. If the output cannot be parsed, the result *fails
closed* — it becomes `needs_human` rather than a guessed verdict.

The four verdicts are `satisfied`, `gap`, `insufficient`, and `needs_human`.
`needs_human` is a first-class outcome: being able to say "this requires auditor
judgment" is as valuable as a confident pass or fail.

## Human-in-the-loop policy

Escalation lives in code, not in the prompt, so it is deterministic, unit-tested,
and measurable in the eval. A draft is escalated when:

1. the model itself asks for a human;
2. a `satisfied`/`gap` verdict falls below a confidence threshold; or
3. a `satisfied` verdict has no evidence grounding.

The rules are deliberately conservative because the risk is asymmetric: a wrong
`satisfied` can let a real gap pass an audit, which is far costlier than an
unnecessary escalation. The eval's ablation mode (`--ablation`) isolates how
much this policy changes outcomes versus the raw model, so its value is a
measured number rather than an assumption.

## Explainability

Every verdict carries a `Citation` — the span of the control it was judged
against and the span of the evidence it relied on. A verdict an auditor cannot
trace back to the source is not useful.

## OSCAL export

`oscal/serializer.py` maps a batch of `ReviewResult`s to a minimal valid subset
of OSCAL Assessment Results v1.1.2: the `metadata` / `import-ap` / `results`
spine, one `observation` and one `finding` per review, with `satisfied` →
`"satisfied"` and every other verdict → `"not-satisfied"` (the specific verdict
and any escalation reason go in the status remarks). Confidence and the
escalation flag ride along as custom `props`.

Validation caveat: the official OSCAL JSON schema uses ECMA `\p{...}`
unicode-property escapes in its `pattern` keywords, which Python's `re` cannot
compile. `validate_against_schema` relaxes those patterns before validating, so
structural and required-field checks run but token character-class constraints
are not enforced. For strict, pattern-exact validation, use the official
`oscal-cli`.

## Legal grounding

Controls in a privacy/security framework are rooted in real statutes. When
grounding is enabled, `legal/` closes a verify loop around the verdict:

1. **Cite** — the reviewer tells the model which statute family the control
   derives from (a control→statute seed in `grounding.py`) and asks it to cite
   the specific article in its reasoning.
2. **Verify** — the cited article is checked against the national statute
   database through the [`korean-law-mcp`](https://github.com/chrisryugj/korean-law-mcp)
   tool. A fabricated article number is caught and the draft is escalated
   (`unverified_legal_citation`), regardless of confidence.

The verification runs through a **local stdio MCP client** (`legal/law_client.py`
spawns the tool as a subprocess and calls it over JSON-RPC), not the Anthropic
MCP connector. The connector would be the more "agentic" wiring, but the beta
is not available on every API endpoint, whereas the local client works
anywhere: the law lookups happen client-side and only the resulting text is
fed to the model. It also makes the behaviour deterministic and unit-testable
(the JSON-RPC handshake is exercised against a fake server, no network).

The eval exposes this as a **citation-validity** metric under an opt-in
`--ground` flag (see `eval/README.md`); the default run makes no law lookups.
Grounding is gated on a free national-statute API key (`LAW_OC`) and Node.js —
the MVP stands without either. Injecting the full article *text* into the
prompt (the client exposes `get_law_text`) is a supported follow-on, not yet
wired into the default loop.

## Evaluation

The harness runs the judgment layer over a small labelled dataset and reports
verdict agreement (+ confusion matrix), gap-detection recall, HITL escalation
precision/recall, and a confidence-vs-accuracy read. Results and the ablation
are in [`eval/README.md`](eval/README.md).

## What is not wired up

On-device OCR requires the platform binary; a production RAG backend,
persistence, and auth are all out of scope for this demo. Legal grounding is
implemented but opt-in (needs Node.js and a statute-API key). These sit behind
interfaces so they can be added or enabled without reshaping the core.
