# mcp-zabbix

> 한 줄 요약: Zabbix *.get을 MCP 도구 5개로 노출하는 읽기 전용 서버.

Zabbix `*.get` 메서드를 MCP 도구로 노출하는 읽기 전용 서버 (streamable HTTP `:8200/mcp`, 내부 전용). 금요일에는 도구 5개(`zabbix_list_problems`, `zabbix_get_problem`, `zabbix_get_host`, `zabbix_list_items`, `zabbix_get_history`)만 등록한다. 쓰기 도구는 없고, 결과는 공통 봉투로 정규화(크기 제한·오류 코드·오래된 값 판정)한다.

규칙·실행·테스트는 `CLAUDE.md`. 계약은 `contracts/mcp-tools.md`(제공).
