# mcp-zabbix 5도구 실호출 확인

> 한 줄 요약: 실서버에서 mcp-zabbix 5도구를 한 번씩 호출해 확인하는 방법과 결과 기록(사례: 5/5 통과).

주소·토큰·호스트 이름은 적지 않는다. 환경 변수는 `.env`에서 터미널로 로드한다(`access.md` 참고).

## 실행
`uv run --package mcp-zabbix python -m mcp_zabbix.live_check` (읽기 전용 토큰, `ZABBIX_MOCK=false`)

## 결과 사례: 5/5 통과 (Zabbix 7.0.31)
| 도구 | 결과 | 요약 |
|---|---|---|
| `zabbix_list_problems` | OK | 5건(limit 5). 호스트는 `trigger.get`으로 보강 |
| `zabbix_get_problem` | OK | 트리거 아이템 1개 (`data.items` 필수 필드 확인) |
| `zabbix_get_host` | OK | 그룹 1개 |
| `zabbix_list_items` | OK | 100개(목록 상한), 그중 최신(stale 아님) 96개 |
| `zabbix_get_history` | OK | 최근 1시간 1점 (`data.points`) |

모두 조회 메서드(`problem/event/trigger/host/hostinterface/maintenance/item/history/trend.get`)만 사용하고 쓰기 호출은 없다.

## 확인할 것
- 실서버 응답에서도 공통 봉투 `{ok, collected_at, data, truncated}`이 계약(`contracts/mcp-tools.md`)대로 나온다.
- `zabbix_list_items`가 100건 상한에 걸리면 `truncated:true`로 표시되는지는 항목 수에 따라 다르다.
- `zabbix_get_history`는 `live_check`가 고른 아이템(첫 최신 아이템)의 최근 1시간에서 점을 돌려준다. 점 수가 적게 보이면 아이템 선택에 따른 것이다.

## 흔한 실패: 404
`.env`의 `ZABBIX_URL` 줄 뒤에 주석이 붙어 값이 길어지는 경우다. 주석을 윗줄로 옮기면 해결된다. 상세는 `access.md`.
