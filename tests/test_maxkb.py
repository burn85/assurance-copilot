"""MaxKB client checks — no live instance. urlopen is monkeypatched with canned
MaxKB JSON envelopes so the request flow, auth header, response parsing, and
error handling are exercised offline. The response shapes mirror those confirmed
against a running MaxKB v2 instance."""

import json

import pytest

from assurance_copilot.models import Control
from assurance_copilot.retrieval.maxkb_client import MaxKBError, MaxKBRetriever


class _Resp:
    def __init__(self, payload):
        self._b = json.dumps(payload).encode()

    def read(self):
        return self._b

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def _install(monkeypatch, dispatch, capture=None):
    def fake_urlopen(req, timeout=None):
        if capture is not None and req.data:
            capture[req.full_url] = json.loads(req.data.decode())
        return _Resp(dispatch(req.get_method(), req.full_url, req.headers))

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)


def test_retrieve_parses_hit_test(monkeypatch):
    headers_seen = {}

    def dispatch(method, url, headers):
        headers_seen.update(headers)
        if url.endswith("/user/login"):
            return {"code": 200, "data": {"token": "TOK"}}
        if url.endswith("/knowledge"):  # list
            return {"code": 200, "data": [{"id": "KID", "name": "assurance-ismsp"}]}
        if url.endswith("/hit_test"):
            return {"code": 200, "data": [
                {"content": "span A", "similarity": 0.9},
                {"content": "span B", "similarity": 0.7},
            ]}
        raise AssertionError(f"unexpected {method} {url}")

    captured = {}
    _install(monkeypatch, dispatch, capture=captured)
    r = MaxKBRetriever()
    assert r.retrieve("query", top_k=2) == ["span A", "span B"]
    assert headers_seen.get("Authorization") == "Bearer TOK"
    # the request body carries the confirmed hit_test field names + defaults
    ht = next(b for u, b in captured.items() if u.endswith("/hit_test"))
    assert ht == {"query_text": "query", "top_number": 2, "similarity": 0.3, "search_mode": "blend"}


def test_non_success_code_raises(monkeypatch):
    _install(monkeypatch, lambda m, u, h: {"code": 401, "message": "bad creds"})
    with pytest.raises(MaxKBError):
        MaxKBRetriever().login()


def test_http_error_body_is_surfaced(monkeypatch):
    # A 4xx with a JSON body must surface MaxKB's message, not "unreachable".
    import io
    import urllib.error

    def raising(req, timeout=None):
        raise urllib.error.HTTPError(
            req.full_url, 401, "Unauthorized", {},
            io.BytesIO(json.dumps({"code": 1002, "message": "illegal user"}).encode()),
        )

    monkeypatch.setattr("urllib.request.urlopen", raising)
    with pytest.raises(MaxKBError) as ei:
        MaxKBRetriever().login()
    assert "illegal user" in str(ei.value)
    assert "unreachable" not in str(ei.value)


def test_ensure_knowledge_creates_when_missing(monkeypatch):
    def dispatch(method, url, headers):
        if url.endswith("/user/login"):
            return {"code": 200, "data": {"token": "TOK"}}
        if url.endswith("/knowledge") and method == "GET":  # empty -> must create
            return {"code": 200, "data": []}
        if url.endswith("/model_list"):
            return {"code": 200, "data": {"model": [
                {"id": "EMB", "name": "maxkb-embedding", "model_name": "text2vec"},
            ]}}
        if url.endswith("/knowledge/base") and method == "POST":
            return {"code": 200, "data": {"id": "NEWKID"}}
        raise AssertionError(f"unexpected {method} {url}")

    captured = {}
    _install(monkeypatch, dispatch, capture=captured)
    assert MaxKBRetriever().ensure_knowledge() == "NEWKID"
    # create-knowledge body carries the confirmed field names
    base = next(b for u, b in captured.items() if u.endswith("/knowledge/base"))
    assert base["name"] == "assurance-ismsp"
    assert base["folder_id"] == "default"
    assert base["embedding_model_id"] == "EMB"


def test_sync_controls_posts_paragraphs(monkeypatch):
    def dispatch(method, url, headers):
        if url.endswith("/user/login"):
            return {"code": 200, "data": {"token": "TOK"}}
        if url.endswith("/knowledge") and method == "GET":
            return {"code": 200, "data": [{"id": "KID", "name": "assurance-ismsp"}]}
        if url.endswith("/document") and method == "POST":
            return {"code": 200, "data": {"id": "DOCID"}}
        raise AssertionError(f"unexpected {method} {url}")

    captured = {}
    _install(monkeypatch, dispatch, capture=captured)
    doc_id = MaxKBRetriever().sync_controls([
        Control(id="ISMS-P 2.5.1", title="Account mgmt", text="manage accounts"),
    ])
    assert doc_id == "DOCID"
    body = next(b for u, b in captured.items() if u.endswith("/document"))
    assert body["paragraphs"][0]["title"] == "ISMS-P 2.5.1"
    assert "manage accounts" in body["paragraphs"][0]["content"]
