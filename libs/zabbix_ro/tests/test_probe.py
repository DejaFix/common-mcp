"""python -m zabbix_ro.probe — 목·실서버(가짜 전송 계층) 점검 결과와 종료 코드, 비밀값 비노출, 쓰기 미호출."""

import json

import httpx
import pytest

from zabbix_ro.probe import CHECKS, run

URL = "http://zabbix.test/api_jsonrpc.php"
TOKEN = "test-token-not-real-0123456789"


def run_probe(env, transport=None):
    lines: list[str] = []
    code = run(env, transport=transport, out=lines.append)
    return code, "\n".join(lines)


def ok_transport(sent: list):
    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        sent.append(body["method"])
        result = "7.0.31" if body["method"] == "apiinfo.version" else [{"x": "1"}]
        return httpx.Response(200, json={"jsonrpc": "2.0", "result": result, "id": 1})

    return httpx.MockTransport(handler)


def test_mock_mode_all_ok():
    code, text = run_probe({"ZABBIX_MOCK": "true"})
    assert code == 0
    assert "모드: 목" in text
    assert text.count("[ OK ]") == len(CHECKS) + 1  # 조회 5개 + 쓰기 차단
    assert "결과: 모두 OK" in text


def test_real_mode_calls_only_the_five_read_methods_and_never_a_write():
    sent: list[str] = []
    env = {"ZABBIX_URL": URL, "ZABBIX_API_TOKEN": TOKEN, "ZABBIX_MOCK": "false"}
    code, text = run_probe(env, ok_transport(sent))
    assert code == 0
    assert sent == [
        method for _, method, _ in CHECKS
    ]  # host.update 는 요청이 나가지 않았다
    assert "7.0.31" in text
    assert "쓰기 차단" in text and "요청 없이" in text and "네트워크 미사용" in text
    assert TOKEN not in text and URL not in text  # 비밀값·주소는 출력하지 않는다


@pytest.mark.safety_regression
def test_probe_never_sends_a_write_even_if_the_allowlist_is_broken(monkeypatch):
    """허용 목록이 회귀로 깨져 host.update 가 들어 있어도, 점검 도구는 실서버로 쓰기 요청을 보내지 않고 FAIL 로 알린다 (SAFE-02)."""
    from zabbix_ro import client as client_module

    monkeypatch.setattr(
        client_module,
        "ALLOWED_METHODS",
        client_module.ALLOWED_METHODS | {"host.update", "user.login"},
    )
    sent: list[str] = []
    env = {"ZABBIX_URL": URL, "ZABBIX_API_TOKEN": TOKEN, "ZABBIX_MOCK": "false"}
    code, text = run_probe(env, ok_transport(sent))
    assert (
        "host.update" not in sent and "user.login" not in sent
    )  # 요청이 나가지 않았다
    assert sent == [method for _, method, _ in CHECKS]
    assert code == 1
    assert "[FAIL] 쓰기 차단" in text and "host.update" in text


@pytest.mark.safety_regression
def test_write_check_uses_no_network_at_all():
    """쓰기 차단 확인 함수는 transport 도 URL 도 없이 동작한다 — 어디로도 요청이 나갈 수 없다."""
    from zabbix_ro.probe import _check_write_block

    assert _check_write_block() is None


def test_a_failing_method_makes_exit_code_1_and_keeps_going():
    def handler(request: httpx.Request) -> httpx.Response:
        method = json.loads(request.content)["method"]
        if method == "trigger.get":
            return httpx.Response(
                200,
                json={
                    "jsonrpc": "2.0",
                    "error": {
                        "code": -32602,
                        "message": "Invalid params.",
                        "data": "No permissions.",
                    },
                    "id": 1,
                },
            )
        return httpx.Response(200, json={"jsonrpc": "2.0", "result": [], "id": 1})

    env = {"ZABBIX_URL": URL, "ZABBIX_API_TOKEN": TOKEN, "ZABBIX_MOCK": "false"}
    code, text = run_probe(env, httpx.MockTransport(handler))
    assert code == 1
    assert "[FAIL] 트리거" in text and "No permissions" in text
    assert "[ OK ] 아이템" in text  # 하나 실패해도 나머지를 계속 점검
    assert "FAIL 1건" in text
    assert TOKEN not in text


def test_connection_failure_is_reported_without_a_traceback():
    def boom(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("refused", request=request)

    env = {"ZABBIX_URL": URL, "ZABBIX_API_TOKEN": TOKEN, "ZABBIX_MOCK": "false"}
    code, text = run_probe(env, httpx.MockTransport(boom))
    assert code == 1
    assert text.count("[FAIL]") == len(CHECKS)
    assert "Traceback" not in text and TOKEN not in text


@pytest.mark.parametrize(
    "env,expected",
    [
        ({"ZABBIX_MOCK": "false"}, "ZABBIX_URL"),
        ({"ZABBIX_MOCK": "false", "ZABBIX_URL": URL}, "ZABBIX_API_TOKEN"),
    ],
)
def test_bad_config_explains_what_is_missing_and_exits_1(env, expected):
    code, text = run_probe(env)
    assert code == 1
    assert "[FAIL] 설정" in text and expected in text
    assert TOKEN not in text


def test_the_checks_use_only_allowed_read_methods():
    from zabbix_ro import ALLOWED_METHODS

    assert {method for _, method, _ in CHECKS} <= ALLOWED_METHODS
    assert all(m.endswith(".get") or m == "apiinfo.version" for _, m, _ in CHECKS)
