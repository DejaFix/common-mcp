"""live_check 의 흐름만 fixture 로 확인한다(실서버 호출 없음)."""

from mcp_zabbix.fixtures import FakeZabbix
from mcp_zabbix.live_check import run_check


def test_run_check_passes_all_five_tools_with_fixture():
    rows = run_check(FakeZabbix())
    assert [r[0] for r in rows] == [
        "zabbix_list_problems",
        "zabbix_get_problem",
        "zabbix_get_host",
        "zabbix_list_items",
        "zabbix_get_history",
    ]
    assert all(ok for _, ok, _ in rows), rows


def test_run_check_reports_failure_without_secrets():
    class Broken:
        def call(self, method, params=None):
            raise RuntimeError("HTTP 401 https://secret.example token=abc")

    rows = run_check(Broken())
    assert any(not ok for _, ok, _ in rows)
    text = str(rows)
    assert "secret.example" not in text and "token=abc" not in text
