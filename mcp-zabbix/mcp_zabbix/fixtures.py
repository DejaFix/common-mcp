"""ZABBIX_MOCK=true 용 fixture 클라이언트.

실 Zabbix 없이 5도구가 같은 모양의 봉투를 돌려주게 하는 가짜 `call(method, params)`.
Zabbix 원본처럼 숫자도 전부 문자열이다(실측 api-probe-2026-10-14).
키는 packs/it/metrics.yaml 의 별칭 키를 흉내 낸 예시값일 뿐, 키 선택은 호출자가 한다.
"""

import time
from typing import Any

HOSTID = "10001"
HOST = {"hostid": HOSTID, "name": "demo-host"}
TRIGGERID = "20001"
EVENTID = "30001"
CPU_ITEMID = "40001"


def _items(now: int) -> list[dict[str, Any]]:
    def row(itemid, name, key, value, units, value_type="0", delay="1m", age=20):
        return {
            "itemid": itemid,
            "name": name,
            "key_": key,
            "lastvalue": value,
            "lastclock": str(now - age),
            "units": units,
            "delay": delay,
            "value_type": value_type,
            "state": "0",
            "status": "0",
        }

    return [
        row(CPU_ITEMID, "CPU utilization", "system.cpu.util", "96.1", "%", delay="30s"),
        row("40002", "Memory utilization", "vm.memory.util", "61.3", "%"),
        row(
            "40003",
            "C: Space utilization",
            "vfs.fs.dependent.size[C:,pused]",
            "72.4",
            "%",
        ),
        row(
            "40004",
            "Interface Ethernet: Bits received",
            'net.if.in["{GUID}"]',
            "1250000",
            "bps",
        ),
    ]


class FakeZabbix:
    """`ZabbixRoClient.call` 과 같은 모양. 조회 메서드만 안다."""

    def __init__(self, clock=time.time):
        self._clock = clock
        self.calls: list[tuple[str, dict[str, Any]]] = []

    def call(self, method: str, params: dict[str, Any] | None = None) -> Any:
        params = dict(params or {})
        self.calls.append((method, params))
        now = int(self._clock())
        handler = getattr(self, "_" + method.replace(".", "_"), None)
        if handler is None:
            raise RuntimeError(f"fixture 에 없는 메서드: {method}")
        return handler(params, now)

    def _problem_get(self, params, now):
        return [
            {
                "eventid": EVENTID,
                "objectid": TRIGGERID,
                "name": "Demo: CPU 1분 평균 85% 초과",
                "severity": "4",
                "clock": str(now - 120),
                "tags": [{"tag": "scope", "value": "performance"}],
            }
        ]

    def _trigger_get(self, params, now):
        trig = {
            "triggerid": TRIGGERID,
            "description": "Demo: CPU 1분 평균 85% 초과",
            "expression": "avg(/demo-host/system.cpu.util,1m)>85",
            "hosts": [HOST],
            "items": [
                {
                    "itemid": CPU_ITEMID,
                    "key_": "system.cpu.util",
                    "name": "CPU utilization",
                    "value_type": "0",
                    "units": "%",
                }
            ],
        }
        return [trig]

    def _event_get(self, params, now):
        ids = params.get("eventids") or []
        if EVENTID not in ids:
            return []
        return [
            {
                "eventid": EVENTID,
                "objectid": TRIGGERID,
                "name": "Demo: CPU 1분 평균 85% 초과",
                "severity": "4",
                "clock": str(now - 120),
                "r_eventid": "0",
                "acknowledged": "0",
                "hosts": [HOST],
                "tags": [{"tag": "scope", "value": "performance"}],
            }
        ]

    def _host_get(self, params, now):
        if HOSTID not in (params.get("hostids") or []):
            return []
        return [
            {
                "hostid": HOSTID,
                "host": "demo-host",
                "name": "demo-host",
                "status": "0",
                "active_available": "1",
                "maintenance_status": "0",
                "hostgroups": [{"groupid": "2", "name": "Windows servers"}],
            }
        ]

    def _hostinterface_get(self, params, now):
        return [{"type": "1", "main": "1", "available": "0", "error": ""}]

    def _maintenance_get(self, params, now):
        return []

    def _item_get(self, params, now):
        rows = _items(now)
        ids = params.get("itemids")
        if ids:
            rows = [r for r in rows if r["itemid"] in ids]
        host_ids = params.get("hostids")
        if host_ids and HOSTID not in host_ids:
            return []
        needle = (params.get("search") or {}).get("key_")
        if needle:
            rows = [r for r in rows if needle in r["key_"]]
        return rows

    def _history_get(self, params, now):
        start = int(params.get("time_from") or now - 600)
        end = int(params.get("time_till") or now)
        points = []
        t = max(start, end - 300)
        value = 88.4
        while t <= end and len(points) < int(params.get("limit") or 500):
            points.append(
                {
                    "itemid": params["itemids"][0],
                    "clock": str(t),
                    "value": f"{value:.1f}",
                    "ns": "0",
                }
            )
            t += 60
            value += 1.3
        return points

    def _trend_get(self, params, now):
        start = int(params.get("time_from"))
        return [
            {
                "itemid": params["itemids"][0],
                "clock": str(start + i * 3600),
                "value_avg": "55.0",
            }
            for i in range(3)
        ]
