"""Zabbix 연결 점검 — `python -m zabbix_ro.probe` (T63 실연동 확인용, 읽기 전용).

`ZABBIX_URL`·`ZABBIX_API_TOKEN`·`ZABBIX_VERIFY_TLS`·`ZABBIX_MOCK` 를 **환경 변수에서만** 읽는다(.env 파일은 읽지 않는다).
허용 목록의 읽기 메서드를 각각 한 번씩 부르고 OK/FAIL 과 걸린 시간을 줄마다 찍는다. 하나라도 FAIL 이면 종료 코드 1.

- 토큰·URL 은 출력하지 않는다. 오류도 `ZabbixError` 메시지(토큰 없음)만 찍는다.
- 쓰기 메서드는 **실서버로 보내지 않는다.** 쓰기 차단은 네트워크 없는 검사로만 확인한다 — 허용 목록에 쓰기 메서드가 없는지,
  목 클라이언트가 거부하는지. (실서버 클라이언트로 부르면 허용 목록이 깨진 상태에서 운영 서버에 쓰기가 나갈 수 있다.)
  Zabbix 서버가 읽기 전용 계정의 쓰기를 거부하는지는 이 도구로 확인할 수 없다(T56 의 권한 오류 캡처로 한다).

예)  PowerShell:  $env:ZABBIX_URL="http://<주소>/api_jsonrpc.php"; $env:ZABBIX_API_TOKEN="<토큰>"; uv run python -m zabbix_ro.probe
"""

import sys
import time
from collections.abc import Callable, Mapping
from typing import Any

import httpx

from zabbix_ro import client as client_module
from zabbix_ro.client import ZabbixRoClient, from_env
from zabbix_ro.errors import MethodNotAllowed, ZabbixRoError

# (표시 이름, 메서드, 파라미터). 모두 결과를 1건으로 제한해 가볍게 부른다.
CHECKS: list[tuple[str, str, dict[str, Any]]] = [
    ("버전", "apiinfo.version", {}),
    ("호스트", "host.get", {"output": ["hostid", "name"], "limit": 1}),
    (
        "문제",
        "problem.get",
        {"output": ["eventid", "name", "severity"], "recent": True, "limit": 1},
    ),
    ("트리거", "trigger.get", {"output": ["triggerid", "description"], "limit": 1}),
    ("아이템", "item.get", {"output": ["itemid", "key_"], "limit": 1}),
]


# 허용 목록에 있으면 안 되는 쓰기·인증 메서드 표본
WRITE_SAMPLES = ("host.update", "item.create", "user.login", "problem.delete")


def _check_write_block() -> str | None:
    """실패 사유(없으면 None). 요청은 어디로도 나가지 않는다.

    1) 허용 목록에 쓰기 메서드가 없는지 (집합 검사)
    2) **목 클라이언트**(네트워크 없음)가 MethodNotAllowed 로 거부하는지
    """
    leaked = [m for m in WRITE_SAMPLES if m in client_module.ALLOWED_METHODS]
    if leaked:
        return f"허용 목록에 쓰기 메서드가 들어 있다: {', '.join(leaked)}"
    mock_client = from_env({"ZABBIX_MOCK": "true"})
    for method in WRITE_SAMPLES:
        try:
            mock_client.call(method, {})
        except MethodNotAllowed:
            continue
        return f"{method} 가 거부되지 않았다"
    return None


def _summary(method: str, result: Any) -> str:
    if method == "apiinfo.version":
        return str(result)
    return f"{len(result)}건" if isinstance(result, list) else type(result).__name__


def run(
    env: Mapping[str, str],
    *,
    transport: httpx.BaseTransport | None = None,
    out: Callable[[str], None] = print,
    clock: Callable[[], float] = time.monotonic,
) -> int:
    """점검을 돌리고 종료 코드(0 모두 OK, 1 하나라도 FAIL)를 돌려준다."""
    client: ZabbixRoClient = from_env(env, transport=transport)
    scenario = getattr(client, "mock_scenario", None)  # 목 시나리오가 있는 버전에서만
    mode = "실서버"
    if client.mock:
        mode = f"목 시나리오 {scenario}" if scenario else "목"
    out(f"모드: {mode} · TLS 검증 {'켜짐' if client.verify_tls else '꺼짐'}")
    failed = 0

    if not client.mock and not client.configured:
        # call() 이 정확한 사유(URL·토큰 누락, TLS 값 오타)를 말해 준다
        try:
            client.call("apiinfo.version", {})
        except ZabbixRoError as exc:
            out(f"[FAIL] 설정  {exc}")
        return 1

    for label, method, params in CHECKS:
        started = clock()
        try:
            result = client.call(method, params)
        except ZabbixRoError as exc:
            failed += 1
            out(f"[FAIL] {label:<4} {method:<16} {exc}")
            continue
        elapsed_ms = int((clock() - started) * 1000)
        out(
            f"[ OK ] {label:<4} {method:<16} {_summary(method, result)}  ({elapsed_ms} ms)"
        )

    # 쓰기 차단 확인은 **네트워크를 쓰지 않는 방식으로만** 한다. 실서버 클라이언트로 쓰기 메서드를 부르면
    # 허용 목록이 회귀로 깨진 상태에서 운영 Zabbix 에 쓰기 요청이 나갈 수 있다 (SAFE-02).
    write_failure = _check_write_block()
    if write_failure is None:
        out(
            "[ OK ] 쓰기 차단 허용 목록에 쓰기 메서드 없음, 요청 없이 거부됨(네트워크 미사용)"
        )
    else:
        failed += 1
        out(f"[FAIL] 쓰기 차단 {write_failure} — 즉시 알려 주세요")

    out(f"결과: {'모두 OK' if failed == 0 else f'FAIL {failed}건'}")
    return 0 if failed == 0 else 1


def main(argv: list[str] | None = None) -> int:
    import os

    return run(os.environ)


if __name__ == "__main__":
    sys.exit(main())
