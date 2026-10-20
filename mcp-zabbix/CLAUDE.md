# mcp-zabbix — Zabbix 읽기 전용 MCP 서버 (streamable HTTP `:8200/mcp`, 내부 전용)

> 한 줄 요약: mcp-zabbix 개발 규칙·도구 표. 먼저 루트 `CLAUDE.md`와 `docs/common-guidelines.md`, 이어서 `contracts/mcp-tools.md`.

## 역할 (등록 도구는 5개뿐)
- Python MCP SDK, `tools/list`·`tools/call`, 전송은 streamable HTTP(컨테이너 분리라 stdio 불가). Zabbix 호출은 **반드시 `libs/zabbix_ro`** 경유

| 도구 | 인자 | Zabbix 매핑 | 응답 핵심 |
|---|---|---|---|
| `zabbix_list_problems` | `severity_min?, hostid?, since?, limit?` | `problem.get`(recent, severities, selectTags, sortfield=eventid) + `trigger.get`(triggerids=objectid, selectHosts) | `[{eventid, objectid, name, severity, clock, host:{hostid,name}, tags[]}]` — `problem.get`은 호스트를 안 주므로 반드시 보강 |
| `zabbix_get_problem` | `eventid` | `event.get`(selectHosts, selectTags, select_acknowledges) + `trigger.get`(expandDescription, expandExpression, selectItems, selectFunctions) | `{eventid, name, severity, clock, r_clock?, acknowledged, hosts[], tags[], trigger:{triggerid, description, expression, items[{itemid, key_, name}]}}`. 없으면 `{ok:false, reason:"NOT_FOUND"}` |
| `zabbix_get_host` | `hostid` | `host.get` + `hostinterface.get` + `maintenance.get(hostids)` | `{hostid, host, name, available, interfaces[], groups[], in_maintenance}` |
| `zabbix_list_items` | `hostid, key_search?` | `item.get(output=[itemid,name,key_,lastvalue,lastclock,units,delay,value_type,state])` | 아이템마다 `lastclock, delay, stale` |
| `zabbix_get_history` | `itemid, time_from, time_till?, limit?` | `history.get(history=value_type, sortfield=clock)`; 24시간 초과 범위는 자동 `trend.get` | `{itemid, source:"history"/"trend", points[{clock, value}] ≤500, last_clock, stale}` |

- **공통 봉투**: 성공 `{ok:true, collected_at, data, truncated?}`(값별 `clock`), 실패 `{ok:false, reason: NO_PERMISSION | NOT_FOUND | ZABBIX_ERROR, collected_at}`. 예외·스택 트레이스를 호출자에게 그대로 넘기지 않는다. 목록 최대 100건·이력 최대 500점, 넘으면 자르고 `truncated:true`
- **오래된 값 판정**: `lastclock`(또는 마지막 점의 clock)이 `max(delay×3, 10분)`보다 과거면 `stale:true` + 마지막 수집 시각
- **미등록 보장**: 쓰기 도구는 등록하지 않는다. `contracts/mcp-tools.md`의 planned 7개(`zabbix_get_event_history`, `zabbix_list_triggers`, `zabbix_api_version`, `zabbix_get_trends`, `zabbix_list_hosts`, `zabbix_list_host_groups`, `zabbix_get_alert_settings`)도 구현 전에는 서버에 **등록하지 않는다**. `tools/list`에 `*_update_*`·`*_create_*` 없음
- `ZABBIX_MOCK=true`면 5개 도구가 fixture로 동작해 실 Zabbix 없이 소비자 E2E 테스트가 돈다
- `GET /healthz` 200

## 하지 않는 것
- 쓰기 메서드, `user.login`, 허용 목록 밖 메서드 — `zabbix_ro`가 막지만 여기서도 호출하지 않는다
- DB 접근, LLM 호출, 소비자(Agent 등) 호출
- 도메인 전용 아이템 키 하드코딩(키 선택은 호출자가 팩 `metrics.yaml`로 하고 `key_search` 인자로 넘긴다)
- 계약에 없는 도구 선구현(등록은 더더욱 금지)

## 계약
- 제공: `contracts/mcp-tools.md` (필수 5 상세, planned 7, 공통 봉투) — 이 repo가 원본, 변경은 계약 PR 먼저
- 소비: `libs/zabbix_ro`(허용 목록·Bearer 토큰·fixture)

## 환경 변수 (이름만, `.env.example` 참고)
`ZABBIX_URL`, `ZABBIX_API_TOKEN`, `ZABBIX_VERIFY_TLS`, `ZABBIX_MOCK`, `ZABBIX_MOCK_SCENARIO`, `INTERNAL_TOKEN`(선택), `MCP_ZABBIX_HOST`, `MCP_ZABBIX_PORT`

## 실행 (uv workspace, 루트에서)
- 로컬: `uv sync` → `uv run --package mcp-zabbix python -m mcp_zabbix` (`:8200/mcp`, `ZABBIX_MOCK=true`면 fixture)
- 확인: MCP 클라이언트로 `tools/list` → 이름 5개가 `contracts/mcp-tools.md`와 일치

## 테스트 (PR 머지 조건)
- `uv run ruff check . && uv run ruff format --check . && uv run pytest` (fixture 기반)
- 반드시 있어야 할 테스트: `delay 30s, lastclock 11분 전` → stale, `2분 전` → not stale / 150건 fixture → 100건 + `truncated:true` / Zabbix 5xx → `{ok:false, reason:"ZABBIX_ERROR"}` 스택 없음 / `tools/list`에 쓰기·planned 도구 없음 / 없는 eventid → `NOT_FOUND`
- 실연동: 토큰을 받은 뒤 5도구 실호출 1회씩(`python -m mcp_zabbix.live_check`), 결과를 `docs/zabbix/mcp-live-test.md` 형식으로 기록
