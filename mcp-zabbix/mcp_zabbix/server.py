"""Zabbix 읽기 전용 MCP 서버.

- streamable HTTP `/mcp`, `GET /healthz`. tools/list 에는 필수 5개만 등록한다(쓰기 도구 등록 차단).
- Zabbix 호출은 libs/zabbix_ro(`from_env().call`) 경유. `ZABBIX_MOCK=true` 면 fixture.
- 선택 `INTERNAL_TOKEN` 이 있으면 `/mcp` 요청에 `Authorization: Bearer <INTERNAL_TOKEN>` 을 요구한다.
"""

import hmac
import os
from typing import Any

from mcp.server.mcpserver import MCPServer
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from mcp_zabbix.fixtures import FakeZabbix
from mcp_zabbix.tools import ZabbixCaller, ZabbixTools

REQUIRED_TOOLS = (
    "zabbix_list_problems",
    "zabbix_get_problem",
    "zabbix_get_host",
    "zabbix_list_items",
    "zabbix_get_history",
)

_TRUE = {"1", "true", "yes", "on"}


def _mock_enabled() -> bool:
    return os.environ.get("ZABBIX_MOCK", "").strip().lower() in _TRUE


def make_client() -> tuple[ZabbixCaller, bool]:
    """(클라이언트, mock 여부). 실서버는 libs/zabbix_ro 만 쓴다."""
    if _mock_enabled():
        return FakeZabbix(), True
    from zabbix_ro import from_env  # noqa: PLC0415 - 목 모드에서는 필요 없다

    return from_env(), False


def build_server(client: ZabbixCaller, *, mock: bool = False) -> MCPServer:
    tools = ZabbixTools(client)
    server = MCPServer("mcp-zabbix")

    @server.tool(
        name="zabbix_list_problems",
        description="현재 문제(Problem) 목록. 호스트 이름을 포함한다. 최대 100건.",
    )
    def zabbix_list_problems(
        severity_min: int = 0,
        hostid: str | None = None,
        since: str | None = None,
        limit: int | None = None,
    ) -> dict[str, Any]:
        return tools.list_problems(severity_min, hostid, since, limit)

    @server.tool(
        name="zabbix_get_problem",
        description="이벤트 한 건과 트리거·트리거 아이템. 없으면 NOT_FOUND.",
    )
    def zabbix_get_problem(eventid: str) -> dict[str, Any]:
        return tools.get_problem(eventid)

    @server.tool(
        name="zabbix_get_host",
        description="호스트 한 대의 가용성·그룹·인터페이스 종류·유지보수 여부.",
    )
    def zabbix_get_host(hostid: str) -> dict[str, Any]:
        return tools.get_host(hostid)

    @server.tool(
        name="zabbix_list_items",
        description="호스트의 아이템 최신값. key_search 로 키를 부분 일치 검색. 항목마다 stale.",
    )
    def zabbix_list_items(hostid: str, key_search: str | None = None) -> dict[str, Any]:
        return tools.list_items(hostid, key_search)

    @server.tool(
        name="zabbix_get_history",
        description="아이템 이력(최대 500점). 24시간 초과 범위는 추세(trend)로 대체.",
    )
    def zabbix_get_history(
        itemid: str,
        time_from: str,
        time_till: str | None = None,
        limit: int | None = None,
    ) -> dict[str, Any]:
        return tools.get_history(itemid, time_from, time_till, limit)

    @server.custom_route("/healthz", methods=["GET"])
    async def healthz(_request: Request) -> Response:
        if mock:
            state = "mock"
        else:
            try:
                client.call("apiinfo.version", {})
                state = "ok"
            except Exception:
                state = "down"
        return JSONResponse({"ok": True, "zabbix": state})

    return server


class _InternalTokenGuard:
    """INTERNAL_TOKEN 이 있으면 /healthz 외 요청에 Bearer 토큰을 요구하는 ASGI 래퍼."""

    def __init__(self, app: Starlette, token: str):
        self._app = app
        self._token = token.encode()

    async def __call__(self, scope, receive, send):
        if scope["type"] == "http" and scope["path"] != "/healthz":
            headers = dict(scope.get("headers") or [])
            supplied = headers.get(b"authorization", b"")
            expected = b"Bearer " + self._token
            if not hmac.compare_digest(supplied, expected):
                response = JSONResponse(
                    {"ok": False, "reason": "UNAUTHORIZED"}, status_code=401
                )
                await response(scope, receive, send)
                return
        await self._app(scope, receive, send)


def build_app(client: ZabbixCaller | None = None, *, mock: bool | None = None):
    if client is None:
        client, mock = make_client()
    server = build_server(client, mock=bool(mock))
    app = server.streamable_http_app()
    token = os.environ.get("INTERNAL_TOKEN", "").strip()
    return _InternalTokenGuard(app, token) if token else app
