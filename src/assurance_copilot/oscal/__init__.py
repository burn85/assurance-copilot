"""OSCAL export — ReviewResults to NIST Assessment Results (v1.1.2)."""

from .serializer import to_assessment_results, dumps, validate_against_schema

__all__ = ["to_assessment_results", "dumps", "validate_against_schema"]
