# Evaluation

Runs the judgment layer over a small labelled dataset and reports the metrics
that matter for assurance review. All data is synthetic.

## Run

```bash
python eval/run_eval.py     # needs ANTHROPIC_API_KEY
```

Writes a per-sample breakdown and the summary metrics to
`eval/results/latest.json` (gitignored) and prints a table.

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

_To be filled in after a run (`eval/results/latest.json`)._

| Metric | Value |
|---|---|
| Samples | 18 |
| Verdict agreement | — |
| Gap recall | — |
| Escalation recall | — |
| Escalation precision | — |
| Mean confidence (correct / wrong) | — |

Numbers depend on the model (`ASSURANCE_MODEL`) and the dataset revision.
