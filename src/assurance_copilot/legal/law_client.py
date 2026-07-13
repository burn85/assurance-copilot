"""Local korean-law-mcp client over stdio (mode B) — gateway-independent.

Why mode B rather than the Anthropic MCP connector (mode A): our API gateway
rejects the connector (`tool type 'mcp_toolset' is not supported for this
model`). Mode B spawns the MCP server as a local subprocess and calls its tools
client-side, so the law lookups never traverse the gateway — only the resulting
text is fed into the normal `messages.create` call. Deterministic and testable.

Needs Node.js (`npx korean-law-mcp`) and a free 법제처 Open API key (env LAW_OC).
Without the key the server errors on real lookups, so callers gate on
`legal.grounding.grounding_enabled()` before constructing a client.

ponytail: raw JSON-RPC over stdio instead of pulling in the `mcp` SDK — the
handshake is three messages and we only need one tool call per review. Add the
SDK if we ever need streaming, cancellation, or resource subscriptions.
"""

from __future__ import annotations

import json
import os
import select
import subprocess
import time
from dataclasses import dataclass

DEFAULT_COMMAND = ["npx", "-y", "korean-law-mcp"]
_PROTOCOL = "2025-06-18"


@dataclass
class CitationCheck:
    """Result of verifying the statute citations in a piece of text."""

    ok: bool          # True = no fabricated/incorrect statute citation detected
    summary: str      # one-line human summary (the tool's "총 N건 ..." line)
    raw: str          # full tool text, for the audit trail

    @classmethod
    def from_tool_result(cls, text: str, is_error: bool) -> "CitationCheck":
        # verify_citations flags fabricated statutes with [HALLUCINATION_DETECTED]
        # and sets isError=True; each bad citation gets its own line starting '✗'.
        # (The summary line "총 N건 | ... | ✗ 0 오류" also contains '✗', so match on
        # a line *start*, not a bare substring.) A clean check has none of these.
        bad = (
            is_error
            or "[HALLUCINATION_DETECTED]" in text
            or any(ln.lstrip().startswith("✗") for ln in text.splitlines())
        )
        summary = next(
            (ln.strip() for ln in text.splitlines() if ln.strip().startswith("총 ")),
            "",
        )
        return cls(ok=not bad, summary=summary or text[:80], raw=text)


class LawClient:
    """Context-managed stdio MCP client for korean-law-mcp.

    Spawns the server and completes the initialize handshake on __enter__;
    terminates the process on __exit__. Use as::

        with LawClient() as law:
            check = law.verify_citations("... 개인정보보호법 제29조 ...")
    """

    def __init__(self, command: list[str] | None = None, oc: str | None = None,
                 timeout: float = 60.0) -> None:
        self.command = command or DEFAULT_COMMAND
        self.oc = oc if oc is not None else os.environ.get("LAW_OC", "")
        self.timeout = timeout
        self.proc: subprocess.Popen | None = None
        self._id = 0

    def __enter__(self) -> "LawClient":
        env = {**os.environ, "LAW_OC": self.oc, "OC": self.oc}
        self.proc = subprocess.Popen(
            self.command, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL, text=True, bufsize=1, env=env,
        )
        # First run may download the npm package — allow extra time.
        self._request(
            "initialize",
            {"protocolVersion": _PROTOCOL, "capabilities": {},
             "clientInfo": {"name": "assurance-copilot", "version": "0"}},
            deadline_extra=90.0,
        )
        self._notify("notifications/initialized")
        return self

    def __exit__(self, *exc) -> None:
        if self.proc:
            self.proc.terminate()
            try:
                self.proc.wait(timeout=5)
            except Exception:
                self.proc.kill()

    # --- JSON-RPC plumbing (newline-delimited, MCP stdio transport) ----------
    def _send(self, obj: dict) -> None:
        assert self.proc and self.proc.stdin
        self.proc.stdin.write(json.dumps(obj) + "\n")
        self.proc.stdin.flush()

    def _notify(self, method: str, params: dict | None = None) -> None:
        self._send({"jsonrpc": "2.0", "method": method, "params": params or {}})

    def _request(self, method: str, params: dict, deadline_extra: float = 0.0) -> dict:
        assert self.proc and self.proc.stdout
        self._id += 1
        rid = self._id
        self._send({"jsonrpc": "2.0", "id": rid, "method": method, "params": params})
        deadline = time.time() + self.timeout + deadline_extra
        while time.time() < deadline:
            ready, _, _ = select.select([self.proc.stdout], [], [], deadline - time.time())
            if not ready:
                continue
            line = self.proc.stdout.readline()
            if not line:
                break
            try:
                msg = json.loads(line)
            except json.JSONDecodeError:
                continue  # skip any non-JSON log line
            if msg.get("id") == rid:
                return msg
        raise TimeoutError(f"korean-law-mcp: no response to {method} within {self.timeout}s")

    def call_tool(self, name: str, arguments: dict) -> tuple[str, bool]:
        """Call an MCP tool. Returns (concatenated text content, is_error)."""
        msg = self._request("tools/call", {"name": name, "arguments": arguments})
        if "error" in msg:
            raise RuntimeError(f"korean-law-mcp {name}: {msg['error']}")
        result = msg.get("result", {})
        text = "".join(
            b.get("text", "") for b in result.get("content", []) if b.get("type") == "text"
        )
        return text, bool(result.get("isError"))

    # --- convenience wrappers -------------------------------------------------
    def verify_citations(self, text: str) -> CitationCheck:
        out, is_error = self.call_tool(
            "legal_analysis", {"mode": "verify_citations", "text": text}
        )
        return CitationCheck.from_tool_result(out, is_error)

    def search_law(self, query: str) -> str:
        out, _ = self.call_tool("search_law", {"query": query})
        return out

    def get_law_text(self, *, mst: str | None = None, law_id: str | None = None,
                     jo: str | None = None) -> str:
        args: dict = {}
        if mst:
            args["mst"] = mst
        if law_id:
            args["lawId"] = law_id
        if jo:
            args["jo"] = jo
        out, _ = self.call_tool("get_law_text", args)
        return out


if __name__ == "__main__":  # live self-check — needs LAW_OC + Node.
    if not os.environ.get("LAW_OC"):
        raise SystemExit("set LAW_OC to run the live self-check")
    sample = "본 통제는 개인정보보호법 제29조에 근거하며 제9999조에도 해당한다."
    with LawClient() as law:
        check = law.verify_citations(sample)
    assert not check.ok, "expected the fabricated 제9999조 to be flagged"
    print("OK — caught hallucinated citation:", check.summary)
