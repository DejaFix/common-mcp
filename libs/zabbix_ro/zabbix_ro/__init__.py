"""읽기 전용 Zabbix 클라이언트 (여러 서비스 공용)

import zabbix_ro
client = zabbix_ro.from_env()                  # ZABBIX_URL·ZABBIX_API_TOKEN·ZABBIX_VERIFY_TLS·ZABBIX_MOCK
problems = client.call("problem.get", {...})   # JSON-RPC result 를 그대로 돌려준다
"""

from zabbix_ro.client import ALLOWED_METHODS, ZabbixRoClient, from_env
from zabbix_ro.errors import MethodNotAllowed, ZabbixError, ZabbixRoError
from zabbix_ro.mock import SCENARIOS

__all__ = [
    "ALLOWED_METHODS",
    "MethodNotAllowed",
    "SCENARIOS",
    "ZabbixError",
    "ZabbixRoClient",
    "ZabbixRoError",
    "from_env",
]
