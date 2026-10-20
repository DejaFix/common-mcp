# mcp-zabbix 5도구 실호출 기록 (T65, B3 DoD ③)

> 한 줄 요약: 실서버에서 mcp-zabbix 5도구를 호출해 통과한 기록과 실행 방법.

> 확인일: 2026-10-15, 팀 Zabbix 7.0.31, `dejafix-readonly` 토큰. 주소·토큰·호스트 이름은 적지 않는다.
> 실행: `uv run --package mcp-zabbix python -m mcp_zabbix.live_check` (PR #95). 환경 변수는 `.env`에서 터미널로 로드(`access.md` 참고).

## 결과: 5/5 통과
| 도구 | 결과 | 요약 |
|---|---|---|
| `zabbix_list_problems` | OK | 5건(limit 5). 호스트는 `trigger.get`으로 보강 |
| `zabbix_get_problem` | OK | 트리거 아이템 1개 (`data.items` 필수 필드 확인) |
| `zabbix_get_host` | OK | 그룹 1개 |
| `zabbix_list_items` | OK | 100개(목록 상한), 그중 최신(stale 아님) 96개 |
| `zabbix_get_history` | OK | 최근 1시간 1점 (`data.points`) |

모두 조회 메서드(`problem/event/trigger/host/hostinterface/maintenance/item/history/trend.get`)만 사용하고, 쓰기 호출은 없다.

## 확인한 것
- 실서버 응답에서도 공통 봉투 `{ok, collected_at, data, truncated}`이 계약(`contracts/mcp-tools.md` v0.1)대로 나온다.
- `zabbix_list_items`가 100개를 돌려주고 그중 4개가 `stale`이었다. 상한(100건)에 걸려 `truncated:true`로 표시되는지는 항목 수에 따라 다르며 이번 호출의 `truncated` 값은 기록하지 않았다.
- `zabbix_get_history`는 `live_check`가 고른 아이템의 최근 1시간에서 1점을 돌려줬다. 점 수가 적게 보이면 아이템 선택(첫 최신 아이템)에 따른 것으로, 이상 여부는 판단하지 않았다.

## 첫 실행에서 실패한 이유 (404)
`.env`의 `ZABBIX_URL` 줄 뒤에 주석이 붙어 값 길이가 203이었다. 주석을 윗줄로 옮기거나 로드 명령에서 주석을 버리니 44자로 줄고 5/5가 통과했다. 상세는 `access.md`.

## 다음
- `host.update` 권한 오류 캡처(`readonly-account.md`).
- Agent(T66)가 MCP를 거쳐 실서버 수치를 쓰는 E2E는 `LLM_FAKE=true` 1건 + 키 없는 fallback 1건으로 별도 확인한다.
