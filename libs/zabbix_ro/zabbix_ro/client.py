"""읽기 전용 Zabbix JSON-RPC 클라이언트.

- 허용 목록 밖 메서드는 네트워크 요청 **전에** MethodNotAllowed.
- 인증은 `Authorization: Bearer <ZABBIX_API_TOKEN>`. `user.login`·본문 `auth` 필드는 쓰지 않는다.
- ZABBIX_MOCK=true 면 네트워크 없이 fixture 를 돌려준다.
"""

import itertools
import logging
import os
from collections.abc import Mapping
from typing import Any

import httpx

from zabbix_ro.errors import MethodNotAllowed, ZabbixError
from zabbix_ro.mock import SCENARIOS, mock_result

# httpx 는 INFO 로그에 요청 URL(=Zabbix 서버 주소)을 그대로 남긴다. 주소는 로그에 쓰지 않는다.
logging.getLogger("httpx").setLevel(logging.WARNING)

ALLOWED_METHODS = frozenset(
    {
        "apiinfo.version",
        "problem.get",
        "event.get",
        "trigger.get",
        "host.get",
        "hostgroup.get",
        "hostinterface.get",
        "item.get",
        "history.get",
        "trend.get",
        "maintenance.get",
        "action.get",
        "alert.get",
    }
)

# Zabbix 는 apiinfo.version 에 인증을 붙이면 오류를 낸다
_NO_AUTH_METHODS = frozenset({"apiinfo.version"})

_TRUE = {"1", "true", "yes", "on"}
_FALSE = {"0", "false", "no", "off"}
DEFAULT_TIMEOUT_SEC = 10.0


def _flag(value: str | None, default: bool = False) -> bool:
    if value is None or value.strip() == "":
        return default
    return value.strip().lower() in _TRUE


def _verify_tls_flag(value: str | None) -> tuple[bool, str | None]:
    """ZABBIX_VERIFY_TLS 를 (검증 여부, 설정 오류) 로 푼다.

    비어 있으면 검증을 켠다. 켜는 값·끄는 값으로 **명시된 것만** 인정하고, 오타 같은 모르는 값은
    검증을 켠 채로 두고 오류 메시지를 돌려준다 — 오타 하나로 TLS 검증이 조용히 꺼지면 안 된다.
    오류는 만들 때가 아니라 호출 때 ZabbixError 로 나간다 (from_env 는 항상 만들어진다).
    """
    if value is None or value.strip() == "":
        return True, None
    text = value.strip().lower()
    if text in _TRUE:
        return True, None
    if text in _FALSE:
        return False, None
    return True, (
        "ZABBIX_VERIFY_TLS 값을 알 수 없습니다 "
        "(true/false/1/0/yes/no/on/off 중 하나로 적으세요)"
    )


def _check_allowed(method: object) -> None:
    """허용 목록에 **정확히** 있는 str 만 통과시킨다.

    문자열이 아닌 값(list·dict·None·bytes)과 str 하위 클래스는 `in` 검사가 TypeError 를 내거나
    동등 비교를 속일 수 있어 먼저 거른다. 공백·대소문자가 다른 이름도 목록에 없으니 거부된다.
    """
    if type(method) is not str or method not in ALLOWED_METHODS:
        raise MethodNotAllowed(method)


class ZabbixRoClient:
    """`call(method, params)` 하나로 JSON-RPC `result` 를 돌려준다."""

    def __init__(
        self,
        url: str | None = None,
        token: str | None = None,
        *,
        verify_tls: bool = True,
        mock: bool = False,
        timeout: float = DEFAULT_TIMEOUT_SEC,
        transport: httpx.BaseTransport | None = None,
        config_error: str | None = None,
        mock_scenario: str = "default",
        scenario_error: str | None = None,
    ):
        self.url = url
        self.mock = mock
        self.mock_scenario = mock_scenario
        self.verify_tls = verify_tls
        self._token = token
        self._config_error = config_error
        self._scenario_error = scenario_error
        self._ids = itertools.count(1)
        self._http: httpx.Client | None = None
        # URL·토큰이 비어 있어도 만들기는 성공한다. 호출 시점에 ZabbixError 를 던져
        # 호출자(주기 폴링 등)가 그 주기를 오류로 기록하고 다음 주기에 다시 시도할 수 있게 한다.
        if not mock and url and token and not config_error:
            self._http = httpx.Client(
                verify=verify_tls, timeout=timeout, transport=transport
            )

    @property
    def configured(self) -> bool:
        """목 모드이거나 URL·토큰이 모두 있고 설정 오류가 없으면 True."""
        return self.mock or self._http is not None

    def call(self, method: str, params: Mapping[str, Any] | None = None) -> Any:
        _check_allowed(method)  # 요청 전에 막는다
        params = dict(params or {})
        if self.mock:
            if (
                self._scenario_error
            ):  # 오타가 조용히 default 로 바뀌지 않게 호출 때 알린다
                raise ZabbixError(self._scenario_error)
            return mock_result(method, params, self.mock_scenario)
        if self._config_error:
            raise ZabbixError(self._config_error)
        if not self.url:
            raise ZabbixError("ZABBIX_URL 이 비어 있습니다 (ZABBIX_MOCK=false)")
        if not self._token:
            raise ZabbixError("ZABBIX_API_TOKEN 이 비어 있습니다 (ZABBIX_MOCK=false)")
        return self._request(method, params)

    def _request(self, method: str, params: dict[str, Any]) -> Any:
        _check_allowed(method)  # call() 을 거치지 않고 불려도 막는다 (심층 방어)
        assert self._http is not None and self.url
        headers = {"Content-Type": "application/json-rpc"}
        if method not in _NO_AUTH_METHODS:
            headers["Authorization"] = f"Bearer {self._token}"
        body = {
            "jsonrpc": "2.0",
            "method": method,
            "params": params,
            "id": next(self._ids),
        }
        try:
            response = self._http.post(self.url, json=body, headers=headers)
        except httpx.TimeoutException as exc:
            raise ZabbixError(f"Zabbix 응답 시간 초과: {method}") from exc
        except httpx.HTTPError as exc:
            raise ZabbixError(
                f"Zabbix 연결 실패: {method} ({type(exc).__name__})"
            ) from exc

        if response.status_code != 200:
            raise ZabbixError(f"Zabbix HTTP {response.status_code}: {method}")
        try:
            payload = response.json()
        except ValueError as exc:
            raise ZabbixError(f"Zabbix 응답이 JSON 이 아닙니다: {method}") from exc

        if isinstance(payload, dict) and "error" in payload:
            err = payload["error"] or {}
            raise ZabbixError(
                f"Zabbix 오류: {err.get('message', '')} {err.get('data', '')}".strip(),
                code=err.get("code"),
                data=err.get("data"),
            )
        if not isinstance(payload, dict) or "result" not in payload:
            raise ZabbixError(f"Zabbix 응답에 result 가 없습니다: {method}")
        return payload["result"]

    def close(self) -> None:
        if self._http is not None:
            self._http.close()

    def __enter__(self) -> "ZabbixRoClient":
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()


def from_env(
    env: Mapping[str, str] | None = None,
    *,
    transport: httpx.BaseTransport | None = None,
) -> ZabbixRoClient:
    """ZABBIX_URL·ZABBIX_API_TOKEN·ZABBIX_VERIFY_TLS·ZABBIX_MOCK 로 클라이언트를 만든다.

    항상 만들어진다(예외 없음). 실서버 모드에서 URL·토큰이 비어 있으면 call() 이 요청 전에 ZabbixError 를 던진다.
    """
    env = os.environ if env is None else env
    verify_tls, config_error = _verify_tls_flag(env.get("ZABBIX_VERIFY_TLS"))
    scenario = (env.get("ZABBIX_MOCK_SCENARIO") or "").strip().lower() or "default"
    scenario_error = None
    if scenario not in SCENARIOS:
        scenario_error = (
            f"ZABBIX_MOCK_SCENARIO 값을 알 수 없습니다: {scenario!r} "
            f"({' / '.join(SCENARIOS)} 중 하나)"
        )
        scenario = "default"
    return ZabbixRoClient(
        url=env.get("ZABBIX_URL") or None,
        token=env.get("ZABBIX_API_TOKEN") or None,
        verify_tls=verify_tls,
        mock=_flag(env.get("ZABBIX_MOCK"), default=False),
        transport=transport,
        config_error=config_error,
        mock_scenario=scenario,
        scenario_error=scenario_error,
    )
