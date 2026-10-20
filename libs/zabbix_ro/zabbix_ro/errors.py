"""zabbix_ro 예외.

호출하는 쪽은 `ZabbixRoError` 하나로 둘 다 잡을 수 있다.
"""


class ZabbixRoError(Exception):
    """zabbix_ro 의 모든 예외의 부모."""


class MethodNotAllowed(ZabbixRoError):
    """허용 목록 밖 메서드. 네트워크 요청을 보내기 **전에** 발생한다."""

    def __init__(self, method: object):
        # 문자열이 아닌 값이 와도 메시지를 만들 수 있게 repr 로 적는다
        super().__init__(
            f"허용되지 않은 Zabbix 메서드: {method!r} (읽기 전용 허용 목록 밖)"
        )
        self.method = method


class ZabbixError(ZabbixRoError):
    """설정 누락·연결 실패·타임아웃·HTTP 오류·JSON-RPC error 응답.

    `code`·`data` 는 JSON-RPC error 응답일 때만 채워진다.
    """

    def __init__(
        self, message: str, *, code: int | None = None, data: str | None = None
    ):
        super().__init__(message)
        self.code = code
        self.data = data
