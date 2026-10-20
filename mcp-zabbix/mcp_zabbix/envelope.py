"""공통 봉투 (contracts/mcp-tools.md 2장, IF-INT-MCP-001).

예외·스택 트레이스·Zabbix 원문 오류는 봉투에 넣지 않는다. message 는 한 줄 요약만.
"""

from datetime import UTC, datetime
from typing import Any

NO_PERMISSION = "NO_PERMISSION"
NOT_FOUND = "NOT_FOUND"
ZABBIX_ERROR = "ZABBIX_ERROR"


def now_iso(now: datetime | None = None) -> str:
    moment = (now or datetime.now(UTC)).astimezone(UTC)
    return moment.strftime("%Y-%m-%dT%H:%M:%SZ")


def ok(data: Any, *, collected_at: str, truncated: bool = False) -> dict[str, Any]:
    return {
        "ok": True,
        "collected_at": collected_at,
        "data": data,
        "truncated": truncated,
    }


def fail(reason: str, message: str, *, collected_at: str) -> dict[str, Any]:
    return {
        "ok": False,
        "collected_at": collected_at,
        "reason": reason,
        "message": message,
    }
