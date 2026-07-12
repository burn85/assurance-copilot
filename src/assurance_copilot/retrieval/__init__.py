"""Retrieval backends. LocalRetriever (MVP, no infra) and the optional MaxKB
RAG client share the same `retrieve(query, top_k) -> list[str]` shape."""

from .local_retriever import LocalRetriever

__all__ = ["LocalRetriever"]

# MaxKBRetriever is imported lazily via `from .maxkb_client import MaxKBRetriever`
# so the package has no hard dependency on a running MaxKB instance.
