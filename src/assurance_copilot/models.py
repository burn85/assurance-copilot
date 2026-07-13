"""Core data models for Assurance Copilot.

These types are deliberately small and framework-agnostic. A `Control` is one
requirement from an assurance framework (ISMS-P criterion, SOC 2 TSC point of
focus, ...). `Evidence` is whatever the auditee submitted to demonstrate the
control is met. A `ReviewResult` is the copilot's *draft* judgment — always
reviewable by a human.
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Optional
import json


class Verdict(str, Enum):
    """The copilot's assessment of whether evidence satisfies a control.

    NEEDS_HUMAN is a first-class outcome, not a failure mode: in assurance work
    the ability to say "this requires auditor judgment" is as valuable as a
    confident pass/fail. See judgment/hitl.py for the routing rules.
    """

    SATISFIED = "satisfied"          # evidence adequately demonstrates the control
    GAP = "gap"                      # evidence shows the control is not met
    INSUFFICIENT = "insufficient"    # evidence is unrelated / incomplete; ask for more
    NEEDS_HUMAN = "needs_human"      # judgment call — escalate to the auditor


@dataclass
class Control:
    id: str                          # e.g. "ISMS-P 2.5.1"
    title: str
    text: str                        # the normative requirement text
    framework: str = "ISMS-P"
    guidance: str = ""               # optional interpretive guidance / points of focus


@dataclass
class Evidence:
    control_id: str
    text: str                        # extracted/OCR'd text of the submitted evidence
    source: str = ""                 # filename or descriptor
    ocr_backend: str = ""            # which OCR backend produced `text` (provenance)


@dataclass
class Citation:
    """Grounds a verdict in specific source text — the explainability contract."""

    criterion_span: str = ""         # quoted text from the control it was judged against
    evidence_span: str = ""          # quoted text from the evidence it relied on


@dataclass
class ReviewResult:
    control_id: str
    verdict: Verdict
    confidence: float                # 0.0–1.0, self-reported by the model
    reasoning: str
    citation: Citation = field(default_factory=Citation)
    followup_question: str = ""      # what to ask the auditee when evidence is thin
    model: str = ""
    escalated: bool = False          # set True by the HITL layer when routed to a human
    escalation_reason: str = ""
    citation_valid: Optional[bool] = None  # legal-grounding check; None if not run

    def to_json(self) -> str:
        d = asdict(self)
        d["verdict"] = self.verdict.value
        return json.dumps(d, ensure_ascii=False, indent=2)
