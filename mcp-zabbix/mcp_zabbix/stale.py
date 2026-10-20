"""오래된 값 판정과 시각 인자 해석 (FR-MCP-008, SAFE-09, contracts/mcp-tools.md 2-1·2-2)."""

import re
from datetime import UTC, datetime

MIN_STALE_SEC = 600  # max(delay×3, 10분)의 10분
_UNIT_SEC = {"s": 1, "m": 60, "h": 3600, "d": 86400, "w": 604800}
_DELAY_RE = re.compile(r"^(\d+)([smhdw]?)$")


def delay_seconds(delay: str | None) -> int | None:
    """`30s`·`1m`·`1h`·`60` 같은 수집 주기를 초로. 사용자 매크로 등 해석이 안 되면 None.

    `30s;50/1-7,00:00-24:00` 처럼 유연한 간격이 붙으면 첫 항목만 본다.
    """
    if delay is None:
        return None
    head = str(delay).split(";", 1)[0].strip()
    match = _DELAY_RE.match(head)
    if not match:
        return None
    return int(match.group(1)) * _UNIT_SEC.get(match.group(2) or "s", 1)


def stale_threshold_sec(delay: str | None) -> int:
    seconds = delay_seconds(delay)
    if seconds is None:
        return MIN_STALE_SEC
    return max(seconds * 3, MIN_STALE_SEC)


def is_stale(lastclock: str | int | None, delay: str | None, now: datetime) -> bool:
    """lastclock 이 0·없음이면 True. 그 밖에는 (now - lastclock) > max(delay×3, 600초)."""
    try:
        clock = int(lastclock) if lastclock is not None else 0
    except (TypeError, ValueError):
        return True
    if clock <= 0:
        return True
    return (now.timestamp() - clock) > stale_threshold_sec(delay)


def parse_time(value: str | int | None) -> int | None:
    """UTC ISO8601 문자열 또는 유닉스 초(정수·문자열) → 유닉스 초. 비어 있으면 None."""
    if value is None or (isinstance(value, str) and not value.strip()):
        return None
    if isinstance(value, int):
        return value
    text = str(value).strip()
    if text.lstrip("-").isdigit():
        return int(text)
    parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return int(parsed.timestamp())
