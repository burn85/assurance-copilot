"""Legal grounding via korean-law-mcp (mode B, local stdio; MVP runs without it)."""

from .grounding import (
    CONTROL_STATUTE_BASIS,
    grounding_enabled,
    statute_basis,
    verify_citations,
)
from .law_client import CitationCheck, LawClient

__all__ = [
    "CONTROL_STATUTE_BASIS",
    "grounding_enabled",
    "statute_basis",
    "verify_citations",
    "CitationCheck",
    "LawClient",
]
