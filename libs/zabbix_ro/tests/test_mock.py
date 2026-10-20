"""ZABBIX_MOCK=true — 네트워크 없이 실서버(7.0.31) 응답 fixture 를 돌려준다 (FR-LIB-003)."""

import socket

import pytest

from zabbix_ro import from_env


@pytest.fixture
def client():
    return from_env({"ZABBIX_MOCK": "true"})


@pytest.fixture
def no_network(monkeypatch):
    def deny(*args, **kwargs):
        raise AssertionError("목 모드에서 네트워크를 쓰면 안 된다")

    monkeypatch.setattr(socket, "create_connection", deny)
    monkeypatch.setattr(socket.socket, "connect", deny)


def test_apiinfo_version(client, no_network):
    assert client.call("apiinfo.version") == "7.0.31"


def test_scheduler_problem_get_shape(client, no_network):
    """Scheduler(T36)가 부르는 problem.get 파라미터 그대로."""
    problems = client.call(
        "problem.get",
        {
            "output": "extend",
            "recent": True,
            "selectTags": "extend",
            "sortfield": ["eventid"],
            "sortorder": "DESC",
        },
    )
    assert problems and isinstance(problems, list)
    p = problems[0]
    for key in (
        "eventid",
        "objectid",
        "clock",
        "name",
        "severity",
        "r_eventid",
        "tags",
    ):
        assert key in p
    assert all(
        isinstance(v, str) for v in (p["eventid"], p["clock"], p["severity"])
    )  # Zabbix 는 숫자를 문자열로 준다


def test_scheduler_trigger_get_enriches_hosts(client, no_network):
    problem = client.call("problem.get", {})[0]
    triggers = client.call(
        "trigger.get",
        {
            "triggerids": [problem["objectid"]],
            "output": ["triggerid"],
            "selectHosts": ["hostid", "host", "name"],
        },
    )
    assert [t["triggerid"] for t in triggers] == [problem["objectid"]]
    host = triggers[0]["hosts"][0]
    assert host["hostid"] and host["host"] and host["name"]


def test_id_filters(client):
    all_triggers = client.call("trigger.get", {})
    assert len(all_triggers) > 1
    one = all_triggers[0]["triggerid"]
    assert [
        t["triggerid"] for t in client.call("trigger.get", {"triggerids": one})
    ] == [one]
    assert client.call("trigger.get", {"triggerids": ["does-not-exist"]}) == []
    hostid = client.call("host.get", {})[0]["hostid"]
    assert client.call("host.get", {"hostids": [hostid]})[0]["hostid"] == hostid


def test_limit(client):
    assert len(client.call("item.get", {"limit": 3})) == 3


def test_history_by_value_type(client):
    floats = client.call("history.get", {"history": 0})
    ints = client.call("history.get", {"history": 3})
    assert floats and ints
    assert client.call("history.get", {"history": 1}) == []


def test_methods_without_fixture_return_empty_list(client):
    for method in (
        "hostgroup.get",
        "hostinterface.get",
        "maintenance.get",
        "action.get",
        "alert.get",
    ):
        assert client.call(method, {}) == []


def test_results_are_copies(client):
    first = client.call("problem.get", {})
    first[0]["name"] = "changed"
    assert client.call("problem.get", {})[0]["name"] != "changed"
