"""The judgment layer: given a Control + Evidence, produce a draft ReviewResult.

This calls Claude via the official Anthropic SDK. Model defaults to
`claude-opus-4-8` (override with ASSURANCE_MODEL). Adaptive thinking is used
because the task is genuinely a judgment call, not a lookup.

Design note — why this is hand-written and not delegated to an off-the-shelf
RAG chatbot: retrieval is commoditised, but *audit judgment* (deciding whether
evidence meets a control, and when to defer to a human) is the actual product.
That layer lives here, in code we own and can evaluate.
"""

from __future__ import annotations

import json
import os
from typing import Optional

import anthropic

from ..models import Control, Evidence, ReviewResult, Verdict, Citation
from . import prompts
from .hitl import apply_hitl_policy

DEFAULT_MODEL = os.environ.get("ASSURANCE_MODEL", "claude-opus-4-8")


class EvidenceReviewer:
    def __init__(self, client: Optional[anthropic.Anthropic] = None,
                 model: str = DEFAULT_MODEL) -> None:
        # Zero-arg client resolves ANTHROPIC_API_KEY or an `ant auth login` profile.
        self.client = client or anthropic.Anthropic()
        self.model = model

    def review(self, control: Control, evidence: Evidence) -> ReviewResult:
        user_message = prompts.build_user_message(
            control_id=control.id,
            control_title=control.title,
            control_text=control.text,
            control_guidance=control.guidance,
            evidence_text=evidence.text,
        )

        response = self.client.messages.create(
            model=self.model,
            max_tokens=2000,
            thinking={"type": "adaptive"},
            system=prompts.SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_message}],
        )

        raw = _extract_text(response)
        result = _parse_result(raw, control_id=control.id, model=self.model)

        # HITL policy can override the verdict to NEEDS_HUMAN and annotate why.
        return apply_hitl_policy(result)


def _extract_text(response) -> str:
    """Concatenate text blocks, skipping thinking blocks (adaptive thinking)."""
    parts = []
    for block in response.content:
        if getattr(block, "type", None) == "text":
            parts.append(block.text)
    return "".join(parts).strip()


def _parse_result(raw: str, control_id: str, model: str) -> ReviewResult:
    """Parse the model's JSON. Robust to an accidental code fence."""
    text = raw
    if text.startswith("```"):
        text = text.strip("`")
        text = text.split("\n", 1)[1] if "\n" in text else text
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        # Fail closed: if we cannot parse a verdict, escalate to a human.
        return ReviewResult(
            control_id=control_id,
            verdict=Verdict.NEEDS_HUMAN,
            confidence=0.0,
            reasoning=f"Could not parse model output as JSON; escalating. Raw: {raw[:300]}",
            model=model,
            escalated=True,
            escalation_reason="unparseable_output",
        )

    try:
        verdict = Verdict(data["verdict"])
    except (KeyError, ValueError):
        verdict = Verdict.NEEDS_HUMAN

    return ReviewResult(
        control_id=control_id,
        verdict=verdict,
        confidence=float(data.get("confidence", 0.0)),
        reasoning=str(data.get("reasoning", "")),
        citation=Citation(
            criterion_span=str(data.get("criterion_span", "")),
            evidence_span=str(data.get("evidence_span", "")),
        ),
        followup_question=str(data.get("followup_question", "")),
        model=model,
    )
