# mcp-zabbix — Zabbix 읽기 전용 MCP 서버 (streamable HTTP `:8200/mcp`, 내부 전용)

> 한 줄 요약: mcp-zabbix 개발 규칙·도구 표(원본 DejaFix 가이드, 참고용).


주담당 Zabbix·MCP 담당 · 부담당 DB·메일 담당.
먼저 읽을 것: 루트 `CLAUDE.md` → `docs/mvp-checklist.md` "mcp-zabbix" → `contracts/mcp-tools.md` → `libs/zabbix_ro/CLAUDE.md`.

## 역할 ([필수] — 등록 도구는 5개뿐)
- Python MCP SDK, `tools/list`·`tools/call`, 전송은 streamable HTTP(컨테이너 분리라 stdio 불가, D-08). Zabbix 호출은 **반드시 `libs/zabbix_ro`** 경유 (FR-MCP-001)

| 도구 | 인자 | Zabbix 매핑 | 응답 핵심 | 근거 |
|---|---|---|---|---|
| `zabbix_list_problems` | `severity_min?, hostid?, since?, limit?` | `problem.get`(recent, severities, selectTags, sortfield=eventid) + `trigger.get`(triggerids=objectid, selectHosts) | `[{eventid, objectid, name, severity, clock, host:{hostid,name}, tags[]}]` — `problem.get`은 호스트를 안 주므로 반드시 보강 | FR-MCP-002 |
| `zabbix_get_problem` | `eventid` | `event.get`(selectHosts, selectTags, select_acknowledges) + `trigger.get`(expandDescription, expandExpression, selectItems, selectFunctions) | `{eventid, name, severity, clock, r_clock?, acknowledged, hosts[], tags[], trigger:{triggerid, description, expression, items[{itemid, key_, name}]}}`. 없으면 `{ok:false, reason:"NOT_FOUND"}` | FR-MCP-003 |
| `zabbix_get_host` | `hostid` | `host.get` + `hostinterface.get` + `maintenance.get(hostids)` | `{hostid, host, name, available, interfaces[], groups[], in_maintenance}` | FR-MCP-004 |
| `zabbix_list_items` | `hostid, key_search?` | `item.get(output=[itemid,name,key_,lastvalue,lastclock,units,delay,value_type,state])` | 아이템마다 `lastclock, delay, stale` | FR-MCP-005 |
| `zabbix_get_history` | `itemid, time_from, time_till?, limit?` | `history.get(history=value_type, sortfield=clock)`; 24시간 초과 범위는 자동 `trend.get` | `{itemid, source:"history"/"trend", points[{clock, value}] ≤500, last_clock, stale}` | FR-MCP-006 |

- **공통 봉투**: 성공 `{ok:true, collected_at, data, truncated?}`(값별 `clock`), 실패 `{ok:false, reason: NO_PERMISSION | NOT_FOUND | ZABBIX_ERROR, collected_at}`. 예외·스택 트레이스를 LLM에 그대로 넘기지 않는다. 목록 최대 100건·이력 최대 500점, 넘으면 자르고 `truncated:true` (FR-MCP-007, NFR-PERF-007)
- **오래된 값 판정**: `lastclock`(또는 마지막 점의 clock)이 `max(delay×3, 10분)`보다 과거면 `stale:true` + 마지막 수집 시각 (FR-MCP-008, SAFE-09)
- **미등록 보장**: 쓰기 도구는 등록하지 않는다. `contracts/mcp-tools.md`의 planned 7개(`zabbix_get_event_history`, `zabbix_list_triggers`, `zabbix_api_version`, `zabbix_get_trends`, `zabbix_list_hosts`, `zabbix_list_host_groups`, `zabbix_get_alert_settings`)도 구현 전에는 서버에 **등록하지 않는다**(LLM이 없는 도구를 부르지 않게). `tools/list`에 `*_update_*`·`*_create_*` 없음 (FR-MCP-009, SAFE-03)
- `ZABBIX_MOCK=true`면 5개 도구가 fixture로 동작해 실 Zabbix 없이 Agent E2E 테스트가 돈다 (FR-MCP-010)
- `GET /healthz` 200 (FR-INF-002)

## 하지 않는 것 (기획서 3-2)
- 쓰기 메서드, `user.login`, 허용 목록(6-2) 밖 메서드 — `zabbix_ro`가 막지만 여기서도 호출하지 않는다
- DB 접근, LLM 호출, Agent·Backend 호출
- IT 전용 아이템 키 하드코딩(키 선택은 Agent가 팩 `metrics.yaml`로 하고 `key_search` 인자로 넘긴다)
- [선택]·[이후] 도구 선구현(등록은 더더욱 금지)

## 의존 계약
- 제공: `contracts/mcp-tools.md`(12개 — 필수 5 상세, 7 planned, 공통 봉투) — Zabbix·MCP 담당 소유, 소비자 Agent(팀장) 승인 필요
- 소비: `libs/zabbix_ro`(허용 목록·Bearer 토큰·fixture)

## 환경 변수 (이름만)
`ZABBIX_URL`, `ZABBIX_API_TOKEN`, `ZABBIX_VERIFY_TLS`, `ZABBIX_MOCK`, `INTERNAL_TOKEN`(선택)

## 실행 (uv workspace, 루트에서)
- 로컬: `uv sync` → `uv run --package mcp-zabbix python -m mcp_zabbix` (`:8200/mcp`, `ZABBIX_MOCK=true` 면 fixture, `MCP_ZABBIX_HOST`·`MCP_ZABBIX_PORT` 로 바인딩)
- 확인: MCP 클라이언트로 `tools/list` → 이름 5개가 `contracts/mcp-tools.md`와 일치
- compose: `docker compose -f infra/docker-compose.yml up -d mcp-zabbix` (호스트 포트 없음, `expose`만)

## 테스트 (PR 머지 조건)
- `uv run ruff check . && uv run ruff format --check . && uv run pytest` (fixture 기반)
- 반드시 있어야 할 테스트: SAFE-09 `delay 30s, lastclock 11분 전` → stale, `2분 전` → not stale / 150건 fixture → 100건 + `truncated:true` / Zabbix 5xx → `{ok:false, reason:"ZABBIX_ERROR"}` 스택 없음 / `tools/list`에 쓰기·planned 도구 없음 / 없는 eventid → `NOT_FOUND`
- 실연동(B3 DoD ③): 토큰을 받은 뒤 5도구 실호출 1회씩, 결과를 `docs/zabbix/`에 기록

## 작업 완료 체크
작업 단위는 `docs/work-order.md`의 T 번호(MCP: T08, T42~T45, T65 / Agent 접점: T47·T49). 끝나서 PR이 dev에 머지되면 노션 「DejaFix 작업 진행 현황」 현황표에서 그 행을 **`완료`로 체크**한다(사람이). 세션은 끝날 때 완료할 T 번호를 알려 준다.

## 데모 기준
Agent의 고정 수집 세트 4회 호출이 모두 `ok:true`로 돌아오고 `tool_calls`에 남아 EvidenceTrace 도구명이 전부 `zabbix_*`로 보인다.
