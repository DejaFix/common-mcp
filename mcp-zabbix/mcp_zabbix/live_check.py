"""실서버 점검 — mcp-zabbix 필수 5도구를 한 번씩 호출한다.

    uv run --package mcp-zabbix python -m mcp_zabbix.live_check

- `ZABBIX_URL`·`ZABBIX_API_TOKEN`·`ZABBIX_VERIFY_TLS` 환경 변수를 쓴다(`libs/zabbix_ro.from_env`).
  `.env`를 직접 읽지 않는다. 터미널에 환경 변수로 넣은 뒤 실행한다.
- 조회 도구만 부른다. 출력에는 주소·토큰·호스트 이름을 찍지 않고 도구별 결과(ok·건수·reason)만 낸다.
- 하나라도 실패하면 종료 코드 1.
"""

import sys
from typing import Any

from mcp_zabbix.tools import ZabbixCaller, ZabbixTools


def _row(tool: str, result: dict[str, Any], detail: str = "") -> tuple[str, bool, str]:
    if result.get("ok"):
        return tool, True, detail or "ok"
    return tool, False, f"{result.get('reason', 'ZABBIX_ERROR')}"


def run_check(client: ZabbixCaller) -> list[tuple[str, bool, str]]:
    """(도구, 성공 여부, 요약) 목록. 앞 도구 결과에서 다음 도구 인자를 고른다."""
    tools = ZabbixTools(client)
    rows: list[tuple[str, bool, str]] = []

    problems = tools.list_problems(limit=5)
    count = len(problems.get("data") or []) if problems.get("ok") else 0
    rows.append(_row("zabbix_list_problems", problems, f"{count}건"))

    # 장애가 없어도 호스트·아이템 도구는 시험할 수 있게 호스트를 따로 고른다
    eventid = hostid = None
    if count:
        first = problems["data"][0]
        eventid = first.get("eventid")
        hostid = (first.get("host") or {}).get("hostid")

    if eventid:
        problem = tools.get_problem(str(eventid))
        n_items = (
            len((problem.get("data") or {}).get("items") or [])
            if problem.get("ok")
            else 0
        )
        rows.append(_row("zabbix_get_problem", problem, f"트리거 아이템 {n_items}개"))
    else:
        rows.append(("zabbix_get_problem", True, "건너뜀(열린 장애 없음)"))

    if not hostid:
        try:
            hosts = client.call("host.get", {"output": ["hostid"], "limit": 1})
        except Exception:
            hosts = []
        hostid = hosts[0]["hostid"] if hosts else None

    itemid = None
    if hostid:
        host = tools.get_host(str(hostid))
        groups = (
            len((host.get("data") or {}).get("groups") or []) if host.get("ok") else 0
        )
        rows.append(_row("zabbix_get_host", host, f"그룹 {groups}개"))

        items = tools.list_items(str(hostid))
        listed = items.get("data") or [] if items.get("ok") else []
        fresh = [i for i in listed if not i.get("stale")]
        rows.append(
            _row("zabbix_list_items", items, f"{len(listed)}개 (최신 {len(fresh)}개)")
        )
        pick = (fresh or listed or [None])[0]
        itemid = pick.get("itemid") if pick else None
    else:
        rows.append(("zabbix_get_host", False, "호스트가 없음"))
        rows.append(("zabbix_list_items", False, "호스트가 없음"))

    if itemid:
        history = tools.get_history(str(itemid), time_from=_one_hour_ago())
        points = (
            len((history.get("data") or {}).get("points") or [])
            if history.get("ok")
            else 0
        )
        rows.append(_row("zabbix_get_history", history, f"{points}점"))
    else:
        rows.append(("zabbix_get_history", False, "아이템이 없음"))
    return rows


def _one_hour_ago() -> int:
    import time

    return int(time.time()) - 3600


def main() -> int:
    from zabbix_ro import from_env  # noqa: PLC0415 - 환경 변수가 필요한 실서버 전용

    client = from_env()
    if not getattr(client, "configured", True):
        print("ZABBIX_URL·ZABBIX_API_TOKEN 환경 변수가 비어 있습니다.")
        return 1
    rows = run_check(client)
    for tool, ok, detail in rows:
        print(f"[{'OK' if ok else 'FAIL'}] {tool}: {detail}")
    failed = [r for r in rows if not r[1]]
    print(f"결과: {len(rows) - len(failed)}/{len(rows)} 통과")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
