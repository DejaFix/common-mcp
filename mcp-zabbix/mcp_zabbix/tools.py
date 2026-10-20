"""필수 5도구 (contracts/mcp-tools.md 3장, FR-MCP-002~006).

Zabbix 는 `client.call(method, params)` 로만 부른다(libs/zabbix_ro 또는 fixture).
어떤 예외도 봉투(`ok:false`)로 바꿔 돌려주고 스택 트레이스·원문 오류는 넘기지 않는다.
키 선택은 하지 않는다: `key_search` 는 호출자(Agent)가 도메인 팩 metrics.yaml 로 정해 넘긴다.
"""

import logging
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any, Protocol

from mcp_zabbix import envelope
from mcp_zabbix.stale import is_stale, parse_time

log = logging.getLogger(__name__)

LIST_LIMIT = 100
HISTORY_LIMIT = 500
HISTORY_RANGE_SEC = 24 * 3600  # 넘으면 trend.get
_NUMERIC_VALUE_TYPES = {"0", "3"}  # float, unsigned (trend 는 숫자형만)


class ZabbixCaller(Protocol):
    def call(self, method: str, params: dict[str, Any] | None = None) -> Any: ...


class ToolFailure(Exception):
    """도구 안에서 봉투 실패로 바꿀 오류. message 는 사람용 한 줄."""

    def __init__(self, reason: str, message: str):
        super().__init__(message)
        self.reason = reason
        self.message = message


def _classify(exc: Exception) -> ToolFailure:
    if isinstance(exc, ToolFailure):
        return exc
    text = str(exc)
    log.warning("zabbix call failed: %s: %s", type(exc).__name__, text[:200])
    if "no permissions" in text.lower():
        return ToolFailure(envelope.NO_PERMISSION, "Zabbix 조회 권한이 없습니다.")
    return ToolFailure(envelope.ZABBIX_ERROR, "Zabbix 조회에 실패했습니다.")


def _clamp(limit: int | None, maximum: int) -> int:
    if limit is None or limit < 1:
        return maximum
    return min(limit, maximum)


def _time_arg(name: str, value: str | int | None) -> int | None:
    try:
        return parse_time(value)
    except ValueError as exc:
        raise ToolFailure(
            envelope.ZABBIX_ERROR, f"{name} 시각 형식이 올바르지 않습니다."
        ) from exc


class ZabbixTools:
    def __init__(
        self,
        client: ZabbixCaller,
        now: Callable[[], datetime] = lambda: datetime.now(UTC),
    ):
        self._client = client
        self._now = now

    # -- 공통 ---------------------------------------------------------
    def _run(self, fn: Callable[[datetime], tuple[Any, bool]]) -> dict[str, Any]:
        now = self._now()
        stamp = envelope.now_iso(now)
        try:
            data, truncated = fn(now)
        except Exception as exc:
            failure = _classify(exc)
            return envelope.fail(failure.reason, failure.message, collected_at=stamp)
        return envelope.ok(data, collected_at=stamp, truncated=truncated)

    def _call(self, method: str, params: dict[str, Any]) -> Any:
        return self._client.call(method, params)

    # -- 3-1 ----------------------------------------------------------
    def list_problems(
        self,
        severity_min: int = 0,
        hostid: str | None = None,
        since: str | int | None = None,
        limit: int | None = None,
    ) -> dict[str, Any]:
        def run(_now: datetime) -> tuple[Any, bool]:
            cap = _clamp(limit, LIST_LIMIT)
            low = max(0, min(int(severity_min), 5))
            params: dict[str, Any] = {
                "output": "extend",
                "recent": True,
                "severities": list(range(low, 6)),
                "selectTags": "extend",
                "sortfield": "eventid",
                "sortorder": "DESC",
                "limit": cap + 1,
            }
            if hostid:
                params["hostids"] = [str(hostid)]
            from_ts = _time_arg("since", since)
            if from_ts is not None:
                params["time_from"] = from_ts
            problems = self._call("problem.get", params) or []
            truncated = len(problems) > cap
            problems = problems[:cap]

            hosts_by_trigger: dict[str, dict[str, Any] | None] = {}
            trigger_ids = sorted({p["objectid"] for p in problems if p.get("objectid")})
            if trigger_ids:
                triggers = self._call(
                    "trigger.get",
                    {
                        "triggerids": trigger_ids,
                        "output": ["triggerid"],
                        "selectHosts": ["hostid", "name"],
                    },
                )
                for trig in triggers or []:
                    hosts = trig.get("hosts") or []
                    hosts_by_trigger[trig["triggerid"]] = hosts[0] if hosts else None

            rows = []
            for p in problems:
                host = hosts_by_trigger.get(p.get("objectid"))
                rows.append(
                    {
                        "eventid": p.get("eventid"),
                        "objectid": p.get("objectid"),
                        "name": p.get("name"),
                        "severity": p.get("severity"),
                        "clock": p.get("clock"),
                        "host": (
                            {"hostid": host.get("hostid"), "name": host.get("name")}
                            if host
                            else {"hostid": None, "name": None}
                        ),
                        "tags": p.get("tags") or [],
                    }
                )
            return rows, truncated

        return self._run(run)

    # -- 3-2 ----------------------------------------------------------
    def get_problem(self, eventid: str) -> dict[str, Any]:
        def run(_now: datetime) -> tuple[Any, bool]:
            events = self._call(
                "event.get",
                {
                    "eventids": [str(eventid)],
                    "output": "extend",
                    "selectHosts": ["hostid", "name"],
                    "selectTags": "extend",
                    "select_acknowledges": "extend",
                },
            )
            if not events:
                raise ToolFailure(envelope.NOT_FOUND, "해당 이벤트를 찾을 수 없습니다.")
            event = events[0]

            r_clock = "0"
            r_eventid = str(event.get("r_eventid") or "0")
            if r_eventid != "0":
                resolved = self._call(
                    "event.get", {"eventids": [r_eventid], "output": ["clock"]}
                )
                if resolved:
                    r_clock = str(resolved[0].get("clock", "0"))

            trigger: dict[str, Any] | None = None
            items: list[dict[str, Any]] = []
            if event.get("objectid"):
                triggers = self._call(
                    "trigger.get",
                    {
                        "triggerids": [event["objectid"]],
                        "output": ["triggerid", "description", "expression"],
                        "expandDescription": True,
                        "expandExpression": True,
                        "selectItems": [
                            "itemid",
                            "key_",
                            "name",
                            "value_type",
                            "units",
                        ],
                        "selectFunctions": "extend",
                    },
                )
                if triggers:
                    trig = triggers[0]
                    items = trig.get("items") or []
                    trigger = {
                        "triggerid": trig.get("triggerid"),
                        "description": trig.get("description"),
                        "expression": trig.get("expression"),
                        "items": items,
                    }

            data = {
                "eventid": event.get("eventid"),
                "name": event.get("name"),
                "severity": event.get("severity"),
                "clock": event.get("clock"),
                "r_clock": r_clock,
                "acknowledged": event.get("acknowledged"),
                "hosts": event.get("hosts") or [],
                "tags": event.get("tags") or [],
                "trigger": trigger,
                "items": items,
            }
            return data, False

        return self._run(run)

    # -- 3-3 ----------------------------------------------------------
    def get_host(self, hostid: str) -> dict[str, Any]:
        def run(now: datetime) -> tuple[Any, bool]:
            hosts = self._call(
                "host.get",
                {
                    "hostids": [str(hostid)],
                    "output": [
                        "hostid",
                        "host",
                        "name",
                        "status",
                        "active_available",
                        "maintenance_status",
                    ],
                    "selectHostGroups": ["groupid", "name"],
                },
            )
            if not hosts:
                raise ToolFailure(envelope.NOT_FOUND, "해당 호스트를 찾을 수 없습니다.")
            host = hosts[0]
            # ip·dns 는 넘기지 않는다(2-3). 종류·가용성만.
            interfaces = self._call(
                "hostinterface.get",
                {
                    "hostids": [str(hostid)],
                    "output": ["type", "main", "available", "error"],
                },
            )
            maintenances = self._call(
                "maintenance.get",
                {
                    "hostids": [str(hostid)],
                    "output": ["maintenanceid", "active_since", "active_till"],
                },
            )
            ts = now.timestamp()
            in_window = any(
                int(m.get("active_since", 0) or 0)
                <= ts
                <= int(m.get("active_till", 0) or 0)
                for m in maintenances or []
            )
            in_maintenance = str(host.get("maintenance_status")) == "1" or in_window
            data = {
                "hostid": host.get("hostid"),
                "host": host.get("host"),
                "name": host.get("name"),
                "available": host.get("active_available"),
                "interfaces": [
                    {
                        "type": i.get("type"),
                        "main": i.get("main"),
                        "available": i.get("available"),
                        "error": i.get("error", ""),
                    }
                    for i in interfaces or []
                ],
                "groups": host.get("hostgroups") or host.get("groups") or [],
                "in_maintenance": in_maintenance,
            }
            return data, False

        return self._run(run)

    # -- 3-4 ----------------------------------------------------------
    def list_items(self, hostid: str, key_search: str | None = None) -> dict[str, Any]:
        def run(now: datetime) -> tuple[Any, bool]:
            params: dict[str, Any] = {
                "hostids": [str(hostid)],
                "output": [
                    "itemid",
                    "name",
                    "key_",
                    "lastvalue",
                    "lastclock",
                    "units",
                    "delay",
                    "value_type",
                    "state",
                ],
                "filter": {"status": 0},
                "sortfield": "key_",
                "limit": LIST_LIMIT + 1,
            }
            if key_search:
                params["search"] = {"key_": key_search}
            items = self._call("item.get", params) or []
            truncated = len(items) > LIST_LIMIT
            rows = []
            for it in items[:LIST_LIMIT]:
                rows.append(
                    {
                        "itemid": it.get("itemid"),
                        "name": it.get("name"),
                        "key_": it.get("key_"),
                        "lastvalue": it.get("lastvalue"),
                        "lastclock": it.get("lastclock"),
                        "units": it.get("units"),
                        "delay": it.get("delay"),
                        "value_type": it.get("value_type"),
                        "state": it.get("state"),
                        "stale": is_stale(it.get("lastclock"), it.get("delay"), now),
                    }
                )
            return rows, truncated

        return self._run(run)

    # -- 3-5 ----------------------------------------------------------
    def get_history(
        self,
        itemid: str,
        time_from: str | int,
        time_till: str | int | None = None,
        limit: int | None = None,
    ) -> dict[str, Any]:
        def run(now: datetime) -> tuple[Any, bool]:
            cap = _clamp(limit, HISTORY_LIMIT)
            start = _time_arg("time_from", time_from)
            if start is None:
                raise ToolFailure(envelope.ZABBIX_ERROR, "time_from 이 필요합니다.")
            end = _time_arg("time_till", time_till)
            if end is None:
                end = int(now.timestamp())

            items = self._call(
                "item.get",
                {
                    "itemids": [str(itemid)],
                    "output": ["itemid", "value_type", "delay", "lastclock"],
                },
            )
            if not items:
                raise ToolFailure(envelope.NOT_FOUND, "해당 아이템을 찾을 수 없습니다.")
            item = items[0]
            value_type = str(item.get("value_type", "0"))

            use_trend = (
                end - start > HISTORY_RANGE_SEC and value_type in _NUMERIC_VALUE_TYPES
            )
            if use_trend:
                rows = self._call(
                    "trend.get",
                    {
                        "itemids": [str(itemid)],
                        "time_from": start,
                        "time_till": end,
                        "output": ["clock", "value_avg"],
                        "limit": cap + 1,
                    },
                )
                points_all = [
                    {"clock": r.get("clock"), "value": r.get("value_avg")}
                    for r in rows or []
                ]
                source = "trend"
            else:
                rows = self._call(
                    "history.get",
                    {
                        "history": int(value_type),
                        "itemids": [str(itemid)],
                        "time_from": start,
                        "time_till": end,
                        "output": "extend",
                        "sortfield": "clock",
                        "sortorder": "ASC",
                        "limit": cap + 1,
                    },
                )
                points_all = [
                    {"clock": r.get("clock"), "value": r.get("value")}
                    for r in rows or []
                ]
                source = "history"

            truncated = len(points_all) > cap
            points = points_all[:cap]
            last_clock = points[-1]["clock"] if points else item.get("lastclock")
            data = {
                "itemid": str(itemid),
                "source": source,
                "points": points,
                "last_clock": last_clock,
                "stale": is_stale(last_clock, item.get("delay"), now),
            }
            return data, truncated

        return self._run(run)
