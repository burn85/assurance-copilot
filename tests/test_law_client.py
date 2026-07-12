"""Self-check for the stdio law client (no network).

Two layers: the pure result parser against the tool's real output shape, and a
full stdio round-trip against a fake MCP server (a tiny local script), so the
JSON-RPC handshake is exercised without hitting the network or Node.
"""

import sys

from assurance_copilot.legal.law_client import CitationCheck, LawClient

# Captured verbatim from a live korean-law-mcp verify_citations call.
REAL_HALLUCINATION = (
    "[HALLUCINATION_DETECTED] == 인용 검증 결과 ==\n"
    "총 2건 | ✓ 1 실존 | ✗ 1 오류 | ⚠ 0 확인필요\n\n"
    "✓ 개인정보 보호법 제29조(안전조치의무) 실존\n"
    "✗ 개인정보 보호법 제9999조 — [NOT_FOUND] 해당 조문 없음\n"
)


def test_parser_flags_hallucination():
    c = CitationCheck.from_tool_result(REAL_HALLUCINATION, is_error=True)
    assert c.ok is False


def test_parser_clean_citation():
    c = CitationCheck.from_tool_result(
        "총 1건 | ✓ 1 실존 | ✗ 0 오류\n✓ 개인정보보호법 제29조 실존", is_error=False
    )
    assert c.ok is True
    assert c.summary.startswith("총")


def test_parser_zero_citations_is_ok():
    c = CitationCheck.from_tool_result("인용된 조문이 없습니다.", is_error=False)
    assert c.ok is True


# A minimal MCP stdio server: answers initialize, then returns a canned
# verify_citations result keyed on whether the fabricated 제9999조 appears.
FAKE_SERVER = r'''
import sys, json
for line in sys.stdin:
    line = line.strip()
    if not line:
        continue
    try:
        msg = json.loads(line)
    except Exception:
        continue
    mid = msg.get("id")
    if mid is None:      # notification
        continue
    method = msg.get("method")
    if method == "initialize":
        result = {"protocolVersion": "2025-06-18", "capabilities": {"tools": {}},
                  "serverInfo": {"name": "fake", "version": "0"}}
    elif method == "tools/call":
        text = msg["params"]["arguments"].get("text", "")
        if "제9999조" in text:
            result = {"content": [{"type": "text",
                      "text": "[HALLUCINATION_DETECTED]\n총 1건 | ✓ 0 실존 | ✗ 1 오류\n✗ 제9999조 [NOT_FOUND]"}],
                      "isError": True}
        else:
            result = {"content": [{"type": "text",
                      "text": "총 1건 | ✓ 1 실존 | ✗ 0 오류\n✓ 개인정보보호법 제29조 실존"}]}
    else:
        result = {}
    sys.stdout.write(json.dumps({"jsonrpc": "2.0", "id": mid, "result": result}) + "\n")
    sys.stdout.flush()
'''


def test_stdio_roundtrip(tmp_path):
    server = tmp_path / "fake_server.py"
    server.write_text(FAKE_SERVER)
    with LawClient(command=[sys.executable, str(server)], oc="x", timeout=10) as law:
        good = law.verify_citations("개인정보보호법 제29조에 근거한다")
        bad = law.verify_citations("개인정보보호법 제9999조에 근거한다")
    assert good.ok is True
    assert good.summary.startswith("총")
    assert bad.ok is False
