"""ZABBIX_MOCK=true 일 때 쓰는 고정 응답.

`default` 시나리오: fixtures/ 는 `docs/zabbix/verification/api-probe-2026-10-14/` 의 실제 응답(Zabbix 7.0.31)
(result 부분)을 복사한 것이다. trigger.get 의 hosts 에는 host.get 의 `name` 을 보강했다(주기 수집기가 selectHosts 로 name 요청).
fixture 가 없는 허용 메서드는 빈 목록을 돌려준다.

`ZABBIX_MOCK_SCENARIO` 로 상황을 고른다 (기본 `default`, 지금 동작 그대로):

| 시나리오 | 상황 |
|---|---|
| `default` | 실서버 응답 그대로 (호스트 demo-host-01, 디스크 장애 1건) |
| `demo` | **mcp-zabbix 목과 같은 ID**: CPU 장애 30001(trigger 20001, host 10001 demo-host)이 진행 중, 디스크 장애 90002(trigger 23002, host 10602 MOCK-PC-02)는 해결됨, 호스트 3대(MOCK-PC-03 은 가용성 알 수 없음) |
| `quiet` | `demo` 의 호스트인데 문제가 없다 (problem.get·event.get 빈 목록) |
| `host_down` | `demo` 에서 demo-host 의 에이전트 가용성이 2(불가) |
| `empty` | `demo` 의 형식인데 목록 메서드가 전부 빈 목록 (호스트 0대) |
| `outage` | 모든 호출이 ZabbixError (Zabbix 연결 불가) |

여러 서비스가 목 모드에서 서로 다른 장애를 보여 주지 않도록 `demo` 는 mcp-zabbix 목과 ID 를 맞춘다.
"""

import copy
import json
from functools import cache
from pathlib import Path
from typing import Any

from zabbix_ro.errors import ZabbixError

_DIR = Path(__file__).parent / "fixtures"

SCENARIOS = ("default", "demo", "quiet", "host_down", "empty", "outage")
# demo 의 파일을 바탕으로 쓰고 아래 변형을 덧씌우는 시나리오
_DEMO_BASED = {"demo", "quiet", "host_down", "empty"}

# 요청 파라미터의 id 목록 → 레코드의 키 (값이 있을 때만 거른다)
_ID_FILTERS = {
    "eventids": "eventid",
    "triggerids": "triggerid",
    "hostids": "hostid",
    "itemids": "itemid",
    "objectids": "objectid",
}


@cache
def _load(name: str, folder: str) -> Any:
    path = _DIR / folder / f"{name}.json" if folder else _DIR / f"{name}.json"
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def _as_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, (list, tuple)):
        return [str(v) for v in value]
    return [str(value)]


def _apply_scenario(scenario: str, method: str, data: Any) -> Any:
    """demo 데이터에 시나리오별 변형을 덧씌운다 (data 는 이미 복사본)."""
    if not isinstance(data, list):
        return data  # apiinfo.version 은 문자열
    if scenario == "quiet" and method in ("problem.get", "event.get"):
        return []
    if scenario == "empty":
        return []
    if scenario == "host_down" and method == "host.get":
        for host in data:
            if host.get("hostid") == "10001":
                host["active_available"] = "2"
    return data


def mock_result(method: str, params: dict[str, Any], scenario: str = "default") -> Any:
    """허용 메서드에 대한 고정 응답. 호출자가 수정해도 원본이 바뀌지 않게 복사해서 준다."""
    if scenario == "outage":
        raise ZabbixError(f"Zabbix 연결 실패(목 시나리오 outage): {method}")
    folder = "scenarios/demo" if scenario in _DEMO_BASED else ""
    if method == "history.get":
        data = _load(f"history.get.type{params.get('history', 3)}", folder)
    else:
        data = _load(method, folder)
    if data is None:
        return []
    data = _apply_scenario(scenario, method, copy.deepcopy(data))
    if not isinstance(data, list):
        return data

    for param, key in _ID_FILTERS.items():
        wanted = _as_list(params.get(param))
        if wanted:
            data = [r for r in data if key not in r or str(r[key]) in wanted]
    limit = params.get("limit")
    if isinstance(limit, int) and limit >= 0:
        data = data[:limit]
    return data
