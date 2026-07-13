"""MaxKB retrieval backend — the "bought" RAG half of the system (optional).

MaxKB (GPL-3.0) is referenced as an external service via docker-compose.maxkb.yml,
never bundled into this repo. It provides embedding-based retrieval over the
control catalog; the MVP runs on local_retriever without it.

`MaxKBRetriever.retrieve(query, top_k)` mirrors the local retriever's shape, so
the two are swappable. `sync_controls()` uploads the catalog as an embedded
knowledge base once.

Confirmed against MaxKB v2 (image 1panel/maxkb) running locally — not assumed:
  - API base            /admin/api
  - auth                POST user/login -> {data:{token}}; header "Bearer <token>"
  - workspace-scoped    /workspace/<ws>/knowledge/...
  - retrieval           POST .../knowledge/<id>/hit_test
                        {query_text, top_number, similarity, search_mode}
                        -> data: [{content, title, similarity, ...}]

ponytail: stdlib urllib, no new HTTP dependency — the surface is login + a few
JSON POSTs. Add httpx only if we need connection pooling or async.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from typing import Optional

from .. import config
from ..models import Control


class MaxKBError(RuntimeError):
    """A MaxKB API call returned a non-success code or was unreachable."""


class MaxKBRetriever:
    def __init__(
        self,
        base_url: Optional[str] = None,
        username: Optional[str] = None,
        password: Optional[str] = None,
        workspace: str = "default",
        knowledge_name: str = "assurance-ismsp",
        timeout: float = 60.0,
    ) -> None:
        base = (base_url or config.MAXKB_BASE_URL).rstrip("/")
        self.api = base + "/admin/api"
        self.username = username or os.environ.get("MAXKB_USERNAME", "admin")
        self.password = password or os.environ.get("MAXKB_PASSWORD", "MaxKB@123..")
        self.workspace = workspace
        self.knowledge_name = knowledge_name
        self.timeout = timeout
        self._token: Optional[str] = None

    # --- HTTP plumbing -------------------------------------------------------
    def _call(self, method: str, path: str, data: Optional[dict] = None, auth: bool = True) -> dict:
        body = json.dumps(data).encode() if data is not None else None
        req = urllib.request.Request(self.api + path, data=body, method=method)
        req.add_header("Content-Type", "application/json")
        if auth:
            req.add_header("AUTHORIZATION", "Bearer " + self._require_token())
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                payload = json.loads(resp.read().decode())
        except urllib.error.HTTPError as e:
            # Reached the server but got 4xx/5xx — MaxKB still returns a JSON
            # {code, message} body. Surface that, not a bogus "unreachable".
            # (HTTPError is a subclass of URLError, so it must be caught first.)
            try:
                payload = json.loads(e.read().decode())
            except Exception:
                raise MaxKBError(f"{method} {path} -> HTTP {e.code}") from e
        except urllib.error.URLError as e:
            raise MaxKBError(f"MaxKB unreachable at {self.api}: {e}") from e
        if payload.get("code") != 200:
            raise MaxKBError(f"{method} {path} -> {payload.get('code')}: {payload.get('message')}")
        return payload

    def _require_token(self) -> str:
        if self._token is None:
            self.login()
        return self._token  # type: ignore[return-value]

    # --- API ------------------------------------------------------------------
    def login(self) -> None:
        payload = self._call(
            "POST", "/user/login",
            data={"username": self.username, "password": self.password}, auth=False,
        )
        self._token = payload["data"]["token"]

    def _embedding_model_id(self) -> str:
        env = os.environ.get("MAXKB_EMBEDDING_MODEL_ID")
        if env:
            return env
        models = self._call("GET", f"/workspace/{self.workspace}/model_list")["data"]["model"]
        for m in models:
            if "embedding" in (m.get("name", "") + m.get("model_name", "")).lower():
                return m["id"]
        raise MaxKBError("No embedding model configured in MaxKB (see the UI / model_list).")

    def ensure_knowledge(self) -> str:
        """Return the knowledge-base id, creating it (empty) if it doesn't exist."""
        listing = self._call("GET", f"/workspace/{self.workspace}/knowledge")["data"]
        records = listing.get("records", listing) if isinstance(listing, dict) else listing
        for k in records or []:
            if k.get("name") == self.knowledge_name:
                return k["id"]
        created = self._call(
            "POST", f"/workspace/{self.workspace}/knowledge/base",
            data={
                "name": self.knowledge_name,
                "folder_id": "default",
                "desc": "ISMS-P control catalog (synced by assurance-copilot).",
                "embedding_model_id": self._embedding_model_id(),
            },
        )
        return created["data"]["id"]

    def sync_controls(self, controls: list[Control]) -> str:
        """Upload the catalog as one document, one paragraph per control.

        Returns the document id. Embedding is async on the MaxKB side but fast
        with the bundled local model; `retrieve()` returns nothing until it
        completes.
        """
        knowledge_id = self.ensure_knowledge()
        paragraphs = [
            {"content": f"[{c.id}] {c.title}\n{c.text}", "title": c.id}
            for c in controls
        ]
        doc = self._call(
            "POST", f"/workspace/{self.workspace}/knowledge/{knowledge_id}/document",
            data={"name": "ISMS-P access controls", "paragraphs": paragraphs},
        )
        return doc["data"]["id"]

    def retrieve(self, query: str, top_k: int = 3, similarity: float = 0.3,
                 search_mode: str = "blend") -> list[str]:
        """Return the criterion spans of the top_k most relevant controls."""
        knowledge_id = self.ensure_knowledge()
        payload = self._call(
            "POST", f"/workspace/{self.workspace}/knowledge/{knowledge_id}/hit_test",
            data={
                "query_text": query,
                "top_number": top_k,
                "similarity": similarity,
                "search_mode": search_mode,
            },
        )
        return [hit["content"] for hit in (payload.get("data") or [])]


if __name__ == "__main__":  # live self-check — needs MaxKB running (docker-compose.maxkb.yml)
    from .local_retriever import LocalRetriever

    r = MaxKBRetriever()
    r.sync_controls(LocalRetriever().all_controls())
    hits = r.retrieve("다중요소 인증 원격 접근", top_k=3, similarity=0.0, search_mode="embedding")
    assert hits, "MaxKB retrieve returned nothing (embedding may still be running)"
    print(f"OK — MaxKB retrieved {len(hits)} spans; top:\n  {hits[0][:80]}...")
