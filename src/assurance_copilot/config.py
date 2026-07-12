"""Central paths and the model default. Kept intentionally tiny.

Only two modules need shared state — the local retriever (where is the control
catalog?) and the eval harness (where is the dataset / where do results go?).
Rather than duplicate path arithmetic in both, it lives here once.
"""

from __future__ import annotations

import os
from pathlib import Path

# src/assurance_copilot/config.py -> parents[2] == repo root
REPO_ROOT = Path(__file__).resolve().parents[2]

# Load .env (gitignored) so `python eval/run_eval.py` picks up ANTHROPIC_* (and a
# gateway ANTHROPIC_BASE_URL / ANTHROPIC_AUTH_TOKEN) without a manual `export`.
# Optional: a no-op if python-dotenv isn't installed.
try:
    from dotenv import load_dotenv

    load_dotenv(REPO_ROOT / ".env")
except ModuleNotFoundError:
    pass

# Mirrors the default in judgment/reviewer.py so the eval harness can report it.
MODEL = os.environ.get("ASSURANCE_MODEL", "claude-opus-4-8")

FRAMEWORKS_DIR = REPO_ROOT / "data" / "frameworks"
CONTROLS_CATALOG = FRAMEWORKS_DIR / "ismsp_controls.md"
EVAL_DATASET = REPO_ROOT / "eval" / "dataset" / "ismsp_samples.jsonl"
EVAL_RESULTS_DIR = REPO_ROOT / "eval" / "results"
