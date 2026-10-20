"""ZABBIX_MOCK_SCENARIO — 시나리오별 응답과, mcp-zabbix 목과 ID 가 맞는지 (데모 대체 경로의 화면 일관성)."""

import pytest

from zabbix_ro import SCENARIOS, MethodNotAllowed, ZabbixError, from_env
from zabbix_ro.client import ALLOWED_METHODS


def client(scenario: str | None = None):
    env = {"ZABBIX_MOCK": "true"}
    if scenario is not None:
        env["ZABBIX_MOCK_SCENARIO"] = scenario
    return from_env(env)


def ids(rows, key):
    return [r[key] for r in rows]


def test_the_six_scenarios():
    assert SCENARIOS == ("default", "demo", "quiet", "host_down", "empty", "outage")


@pytest.mark.parametrize("value", [None, "", "  ", "default", "DEFAULT"])
def test_default_scenario_is_the_current_behaviour(value):
    problems = client(value).call("problem.get", {})
    assert ids(problems, "eventid") == ["27"]  # 실서버 응답 그대로
    assert client(value).call("apiinfo.version", {}) == "7.0.31"


@pytest.mark.parametrize("value", ["ghost", "Demo2", "demo "])
def test_unknown_scenario_fails_at_call_not_at_creation(value):
    """오타가 조용히 default 로 바뀌면 데모 데이터가 달라진다. 만들 때는 예외 없이, 호출 때 오류."""
    c = client(value.strip() if value == "demo " else value)
    if value == "demo ":
        assert c.call("problem.get", {})  # 앞뒤 공백은 허용(알려진 값)
        return
    with pytest.raises(ZabbixError, match="ZABBIX_MOCK_SCENARIO"):
        c.call("problem.get", {})


@pytest.mark.safety_regression
@pytest.mark.parametrize("scenario", SCENARIOS)
def test_every_scenario_still_blocks_write_methods(scenario):
    for method in ("host.update", "user.login", "problem.delete", "event.acknowledge"):
        with pytest.raises(MethodNotAllowed):
            client(scenario).call(method, {})


@pytest.mark.safety_regression
def test_allowlist_wins_over_a_bad_scenario_name():
    with pytest.raises(MethodNotAllowed):
        client("ghost").call("host.update", {})


def test_scenario_name_is_ignored_in_real_mode():
    """실서버 모드에서는 시나리오가 쓰이지 않는다 (오타가 있어도 실서버 호출에 영향 없음)."""
    c = from_env({"ZABBIX_MOCK": "false", "ZABBIX_MOCK_SCENARIO": "ghost"})
    assert c.mock is False
    with pytest.raises(ZabbixError, match="ZABBIX_URL"):
        c.call("problem.get", {})


# ---------------------------------------------------------------- demo


def test_demo_matches_the_mcp_zabbix_mock():
    fx = pytest.importorskip("mcp_zabbix.fixtures")
    c = client("demo")
    problem = next(p for p in c.call("problem.get", {}) if p["eventid"] == fx.EVENTID)
    assert problem["objectid"] == fx.TRIGGERID
    trigger = c.call("trigger.get", {"triggerids": [fx.TRIGGERID]})[0]
    host = trigger["hosts"][0]
    assert {
        k: host[k] for k in fx.HOST
    } == fx.HOST  # hostid·name 이 같다 (host 키는 Zabbix 원본에만 더 있다)
    cpu = next(
        i
        for i in c.call("item.get", {"hostids": [fx.HOSTID]})
        if i["itemid"] == fx.CPU_ITEMID
    )
    assert cpu["key_"] == "system.cpu.util"
    assert c.call("host.get", {"hostids": [fx.HOSTID]})[0]["name"] == fx.HOST["name"]


def test_demo_has_one_active_one_resolved_and_one_unknown_host():
    c = client("demo")
    problems = {p["eventid"]: p for p in c.call("problem.get", {})}
    assert problems["30001"]["r_eventid"] == "0"  # 진행 중
    assert problems["90002"]["r_eventid"] != "0"  # 해결됨
    hosts = {h["hostid"]: h for h in c.call("host.get", {})}
    assert {h: v["active_available"] for h, v in hosts.items()} == {
        "10001": "1",
        "10602": "1",
        "10603": "0",
    }


def test_demo_event_history_and_items_are_filterable():
    c = client("demo")
    assert ids(c.call("event.get", {"eventids": ["30001"]}), "eventid") == ["30001"]
    assert ids(c.call("item.get", {"hostids": ["10602"]}), "itemid") == ["40012"]
    cpu = c.call("history.get", {"history": 0, "itemids": ["40001"]})
    assert [p["itemid"] for p in cpu] == ["40001"] * 5
    assert [float(p["value"]) for p in cpu] == sorted(float(p["value"]) for p in cpu)
    assert c.call("history.get", {"history": 3, "itemids": ["40004"]})
    assert c.call("hostgroup.get", {}) == []  # fixture 없는 메서드는 빈 목록


def test_demo_results_are_copies():
    c = client("demo")
    c.call("host.get", {})[0]["name"] = "changed"
    assert c.call("host.get", {})[0]["name"] == "demo-host"


# ---------------------------------------------------------------- 나머지 시나리오


def test_quiet_has_hosts_but_no_problems():
    c = client("quiet")
    assert c.call("problem.get", {}) == []
    assert c.call("event.get", {}) == []
    hosts = c.call("host.get", {})
    assert len(hosts) == 3
    assert c.call("apiinfo.version", {}) == "7.0.31"


def test_host_down_only_changes_demo_host_availability():
    hosts = {
        h["hostid"]: h["active_available"]
        for h in client("host_down").call("host.get", {})
    }
    assert hosts == {"10001": "2", "10602": "1", "10603": "0"}
    assert ids(client("host_down").call("problem.get", {}), "eventid") == [
        "30001",
        "90002",
    ]
    # demo 자체는 바뀌지 않는다
    assert {
        h["hostid"]: h["active_available"] for h in client("demo").call("host.get", {})
    }["10001"] == "1"


def test_empty_returns_empty_lists_but_a_version():
    c = client("empty")
    for method in ("problem.get", "trigger.get", "event.get", "host.get", "item.get"):
        assert c.call(method, {}) == [], method
    assert c.call("history.get", {"history": 0}) == []
    assert c.call("apiinfo.version", {}) == "7.0.31"


@pytest.mark.parametrize("method", sorted(ALLOWED_METHODS))
def test_outage_fails_every_allowed_method(method):
    with pytest.raises(ZabbixError, match="outage"):
        client("outage").call(method, {})
