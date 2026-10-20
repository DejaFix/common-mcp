"""서버 수준 테스트 — tools/list 5개, 쓰기·planned 미등록(SAFE-03), /healthz, 내부 토큰."""

import asyncio
import json

from starlette.testclient import TestClient

from mcp_zabbix.fixtures import EVENTID, HOSTID, FakeZabbix
from mcp_zabbix.server import REQUIRED_TOOLS, build_app, build_server

# contracts/mcp-tools.md 4장: Agent 허용 12개 중 서버에 등록하지 않는 7개
PLANNED = {
    "zabbix_get_event_history",
    "zabbix_list_triggers",
    "zabbix_api_version",
    "zabbix_get_trends",
    "zabbix_list_hosts",
    "zabbix_list_host_groups",
    "zabbix_get_alert_settings",
}
WRITE_MARKERS = (
    "_create_",
    "_update_",
    "_delete_",
    "_ack",
    "_execute",
    "_run",
    "_set_",
)


def _names():
    server = build_server(FakeZabbix(), mock=True)
    return [t.name for t in asyncio.run(server.list_tools())]


def test_tools_list_is_exactly_the_five_required():
    names = _names()
    assert sorted(names) == sorted(REQUIRED_TOOLS)
    assert len(names) == 5


def test_no_write_or_planned_tools_registered():
    names = set(_names())
    assert not names & PLANNED
    for name in names:
        assert name.startswith("zabbix_")
        assert not any(marker in name for marker in WRITE_MARKERS)


def test_call_tool_returns_envelope_in_structured_content():
    server = build_server(FakeZabbix(), mock=True)
    result = asyncio.run(server.call_tool("zabbix_get_problem", {"eventid": EVENTID}))
    structured = result.structured_content
    assert structured["ok"] is True
    text = json.loads(result.content[0].text)
    assert text["data"]["eventid"] == EVENTID


def test_call_tool_not_found_is_envelope_not_exception():
    server = build_server(FakeZabbix(), mock=True)
    result = asyncio.run(server.call_tool("zabbix_get_host", {"hostid": "0"}))
    assert result.structured_content["reason"] == "NOT_FOUND"
    assert HOSTID  # fixture 호스트는 따로 있다


def test_healthz_mock():
    client = TestClient(build_app(FakeZabbix(), mock=True))
    response = client.get("/healthz")
    assert response.status_code == 200
    assert response.json() == {"ok": True, "zabbix": "mock"}


def test_healthz_down_when_zabbix_fails():
    class Broken:
        def call(self, method, params=None):
            raise RuntimeError("down")

    client = TestClient(build_app(Broken(), mock=False))
    assert client.get("/healthz").json() == {"ok": True, "zabbix": "down"}


def test_internal_token_required_when_set(monkeypatch):
    monkeypatch.setenv("INTERNAL_TOKEN", "t0ken")
    client = TestClient(build_app(FakeZabbix(), mock=True))
    assert client.get("/healthz").status_code == 200  # 헬스는 인증 없이
    assert client.post("/mcp", json={}).status_code == 401
    assert (
        client.post(
            "/mcp", json={}, headers={"Authorization": "Bearer wrong"}
        ).status_code
        == 401
    )
