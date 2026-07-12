# Evaluation

Runs the judgment layer over a small labelled dataset and reports the metrics
that matter for assurance review. All data is synthetic.

## Run

```bash
python eval/run_eval.py                # needs ANTHROPIC_API_KEY
python eval/run_eval.py --ablation     # no API — recomputes from latest.json
```

Writes a per-sample breakdown and the summary metrics to
`eval/results/latest.json` (gitignored) and prints a table. `--ablation` reuses
that saved run to compare the raw model against the model + HITL policy (below).

## Dataset

`dataset/ismsp_samples.jsonl` — one JSON object per line:

```json
{
  "control":  {"id": "...", "title": "...", "text": "...", "guidance": "...", "framework": "ISMS-P"},
  "evidence": {"text": "...", "source": "..."},
  "expert_verdict": "satisfied | gap | insufficient | needs_human",
  "notes": "why this is the correct label"
}
```

The `expert_verdict` is the human label the model is scored against; `notes`
records the labelling rationale.

## Metrics

- **Verdict agreement** — exact match between predicted and expert verdict, plus
  a 4×4 confusion matrix.
- **Gap recall** — of samples labelled `gap`, the fraction the model caught as
  `gap` or `needs_human`. A missed gap (predicted `satisfied`/`insufficient`) is
  the most costly error.
- **Escalation recall / precision** — treating `needs_human` labels as the
  positive class: recall = escalated among needs-human; precision = needs-human
  among escalated.
- **Mean confidence** — overall, and split by correct vs. wrong predictions.

## Results

Run on `claude-opus-4-8`, 18 synthetic samples.

| Metric | Value |
|---|---|
| Samples | 18 |
| Verdict agreement | 83.3% (15/18) |
| Gap recall | 100.0% (5/5 real gaps caught) |
| Escalation recall | 75.0% (3/4 needs-human) |
| Escalation precision | 100.0% |
| Mean confidence (correct / wrong) | 0.817 (0.845 / 0.673) |

Confusion matrix (rows = expert label, cols = predicted):

| expert ↓ / pred → | satisfied | gap | insufficient | needs_human |
|---|---|---|---|---|
| **satisfied** | 4 | 0 | 2 | 0 |
| **gap** | 0 | 5 | 0 | 0 |
| **insufficient** | 0 | 0 | 3 | 0 |
| **needs_human** | 0 | 1 | 0 | 3 |

The three misses lean the safe way: 2 `satisfied` cases were judged the stricter
`insufficient` (the model asked for more evidence than the expert required), and
1 `needs_human` case was decided as `gap`. Wrong predictions carry lower mean
confidence (0.673) than correct ones (0.845), so confidence is a usable signal.

### Ablation — does the HITL policy add anything?

`--ablation` recomputes two views from the same run: **(A)** the raw model
verdict, and **(B)** the verdict after the HITL policy (an escalated case counts
as `needs_human`). The delta is what the policy contributes beyond the model.

| Metric | A raw | B +HITL | Δ |
|---|---|---|---|
| Verdict agreement | 83.3% | 83.3% | +0.0pp |
| Gap recall | 100.0% | 100.0% | +0.0pp |
| Escalation recall | 75.0% | 75.0% | +0.0pp |

On this dataset the delta is **zero**: the deterministic policy never fired
beyond the model's own `needs_human` calls. The two errors it might have caught
were low-confidence `insufficient` predictions (outside the policy's
satisfied/gap scope), and the missed `needs_human` was a *confident* wrong `gap`
(no confidence rule can catch a confidently-wrong verdict). This is an honest
null result — the policy is a safety floor whose value shows up on harder,
overconfident inputs, not a lift on this particular set.

Numbers depend on the model (`ASSURANCE_MODEL`) and the dataset revision.
