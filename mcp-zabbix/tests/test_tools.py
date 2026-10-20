"""필수 5도구 단위 테스트 — fixture/가짜 클라이언트 기반 (실 Zabbix 불필요)."""

from datetime import UTC, datetime

from mcp_zabbix.fixtures import CPU_ITEMID, EVENTID, HOSTID, FakeZabbix
from mcp_zabbix.stale import delay_seconds, is_stale, parse_time
from mcp_zabbix.tools import ZabbixTools

NOW = datetime(2026, 10, 15, 6, 30, 0, tzinfo=UTC)


def make_tools(client=None):
    return ZabbixTools(client or FakeZabbix(clock=NOW.timestamp), now=lambda: NOW)


class StubClient:
    def __init__(self, responses=None, error=None):
        self.responses = responses or {}
        self.error = error
        self.calls = []

    def call(self, method, params=None):
        self.calls.append((method, params))
        if self.error:
            raise self.error
        value = self.responses.get(method, [])
        return value(params) if callable(value) else value


# -- 오래된 값 -------------------------------------------------
def test_stale_delay_30s_lastclock_11min_ago_is_stale():
    assert is_stale(str(int(NOW.timestamp()) - 11 * 60), "30s", NOW) is True


def test_stale_delay_30s_lastclock_2min_ago_is_fresh():
    assert is_stale(str(int(NOW.timestamp()) - 2 * 60), "30s", NOW) is False


def test_stale_long_delay_uses_three_times_delay():
    # delay 1h → 3시간까지는 최신. 2시간 전은 최신, 4시간 전은 오래됨
    assert is_stale(str(int(NOW.timestamp()) - 2 * 3600), "1h", NOW) is False
    assert is_stale(str(int(NOW.timestamp()) - 4 * 3600), "1h", NOW) is True


def test_stale_zero_or_missing_lastclock_is_stale():
    assert is_stale("0", "1m", NOW) is True
    assert is_stale(None, "1m", NOW) is True


def test_delay_macro_and_custom_interval():
    assert delay_seconds("{$AGENT.TIMEOUT}") is None
    assert delay_seconds("30s;50/1-7,00:00-24:00") == 30
    assert delay_seconds("0") == 0
    # 해석 불가·0 이어도 최소 10분 규칙
    assert is_stale(str(int(NOW.timestamp()) - 5 * 60), "{$X}", NOW) is False
    assert is_stale(str(int(NOW.timestamp()) - 5 * 60), "0", NOW) is False


def test_parse_time_accepts_iso_and_epoch():
    assert parse_time("2026-10-15T06:30:00Z") == int(NOW.timestamp())
    assert parse_time("1792027170") == 1792027170
    assert parse_time(1792027170) == 1792027170
    assert parse_time(None) is None


# -- 5도구 (fixture) -----------------------------------------------------
def test_list_problems_adds_host_from_trigger():
    result = make_tools().list_problems()
    assert result["ok"] is True
    assert result["collected_at"] == "2026-10-15T06:30:00Z"
    row = result["data"][0]
    assert row["host"] == {"hostid": HOSTID, "name": "demo-host"}
    assert row["severity"] == "4"  # Zabbix 원본 문자열 유지


def test_list_problems_truncates_to_100():
    problems = [{"eventid": str(i), "objectid": "1", "name": "p"} for i in range(150)]
    client = StubClient({"problem.get": problems, "trigger.get": []})
    result = make_tools(client).list_problems()
    assert len(result["data"]) == 100
    assert result["truncated"] is True
    assert result["data"][0]["host"] == {"hostid": None, "name": None}


def test_get_problem_has_items_and_trigger():
    result = make_tools().get_problem(EVENTID)
    assert result["ok"] is True
    data = result["data"]
    assert data["items"] == data["trigger"]["items"]
    assert data["items"][0]["itemid"] == CPU_ITEMID
    assert data["r_clock"] == "0"


def test_get_problem_not_found():
    result = make_tools().get_problem("999")
    assert result == {
        "ok": False,
        "collected_at": "2026-10-15T06:30:00Z",
        "reason": "NOT_FOUND",
        "message": result["message"],
    }


def test_get_host_excludes_ip_and_dns():
    result = make_tools().get_host(HOSTID)
    assert result["ok"] is True
    data = result["data"]
    assert data["groups"] == [{"groupid": "2", "name": "Windows servers"}]
    assert data["in_maintenance"] is False
    for iface in data["interfaces"]:
        assert "ip" not in iface and "dns" not in iface


def test_get_host_not_found():
    assert make_tools().get_host("1")["reason"] == "NOT_FOUND"


def test_list_items_marks_stale_per_item():
    client = StubClient(
        {
            "item.get": [
                {
                    "itemid": "1",
                    "key_": "a",
                    "delay": "30s",
                    "lastclock": str(int(NOW.timestamp()) - 11 * 60),
                },
                {
                    "itemid": "2",
                    "key_": "b",
                    "delay": "30s",
                    "lastclock": str(int(NOW.timestamp()) - 60),
                },
            ]
        }
    )
    rows = make_tools(client).list_items(HOSTID)["data"]
    assert [r["stale"] for r in rows] == [True, False]


def test_list_items_key_search_passes_through():
    result = make_tools().list_items(HOSTID, key_search="cpu")
    assert [r["key_"] for r in result["data"]] == ["system.cpu.util"]


def test_list_items_truncates_to_100():
    items = [
        {"itemid": str(i), "key_": f"k{i}", "delay": "1m", "lastclock": "0"}
        for i in range(150)
    ]
    result = make_tools(StubClient({"item.get": items})).list_items(HOSTID)
    assert len(result["data"]) == 100 and result["truncated"] is True


def test_get_history_returns_points_from_history():
    start = int(NOW.timestamp()) - 600
    result = make_tools().get_history(CPU_ITEMID, str(start))
    assert result["ok"] is True
    data = result["data"]
    assert data["source"] == "history"
    assert data["points"] and set(data["points"][0]) == {"clock", "value"}
    assert data["stale"] is False


def test_get_history_over_24h_uses_trend():
    start = int(NOW.timestamp()) - 3 * 86400
    data = make_tools().get_history(CPU_ITEMID, start)["data"]
    assert data["source"] == "trend"


def test_get_history_empty_points_is_ok_not_error():
    client = StubClient(
        {
            "item.get": [
                {"itemid": "1", "value_type": "0", "delay": "1m", "lastclock": "0"}
            ],
            "history.get": [],
        }
    )
    result = make_tools(client).get_history("1", "2026-10-15T06:00:00Z")
    assert result["ok"] is True
    assert result["data"]["points"] == []
    assert result["data"]["stale"] is True


def test_get_history_caps_points_at_500():
    rows = [{"clock": str(i), "value": "1"} for i in range(600)]
    client = StubClient(
        {
            "item.get": [
                {"itemid": "1", "value_type": "0", "delay": "1m", "lastclock": "599"}
            ],
            "history.get": rows,
        }
    )
    result = make_tools(client).get_history("1", 0, 100)
    assert len(result["data"]["points"]) == 500
    assert result["truncated"] is True


def test_get_history_bad_time_is_zabbix_error():
    assert make_tools().get_history(CPU_ITEMID, "어제")["reason"] == "ZABBIX_ERROR"


# -- 오류 봉투: 스택·원문 오류 없음 -------------------------------------------
def test_zabbix_5xx_becomes_zabbix_error_without_stack():
    secret = "Zabbix HTTP 502: https://internal.example/api_jsonrpc.php token=abc"
    result = make_tools(StubClient(error=RuntimeError(secret))).list_problems()
    assert result["ok"] is False
    assert result["reason"] == "ZABBIX_ERROR"
    text = str(result)
    assert (
        "Traceback" not in text
        and "token=abc" not in text
        and "internal.example" not in text
    )


def test_permission_error_maps_to_no_permission():
    result = make_tools(
        StubClient(error=RuntimeError("No permissions to referred object"))
    ).get_host("1")
    assert result["reason"] == "NO_PERMISSION"
