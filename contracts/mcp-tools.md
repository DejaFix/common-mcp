# mcp-tools.md — Agent ↔ mcp-zabbix·mcp-kb 도구 계약 (v0.2)

> 한 줄 요약: MCP 도구 계약 참고 사본(원본 DejaFix `contracts/`; mcp-kb 절은 이 저장소 범위 밖).

> 소유 Zabbix·MCP 담당 · 소비 팀장(Agent). 원본: 기획서 7-3, 요구사항 IF-INT-MCP-001~008·FR-MCP-001~010. 이 문서가 기획서보다 우선한다(루트 CLAUDE.md 0).
> 실측 근거: `docs/zabbix/verification/api-probe-2026-10-14/` (Zabbix 7.x, 템플릿 "Windows by Zabbix agent active").

## 1. 서버
- 전송: MCP **streamable HTTP** `http://mcp-zabbix:8200/mcp` (compose 내부 전용, 호스트 포트 공개 없음). 로컬 실행은 `http://localhost:8200/mcp`. Agent는 `MCP_ZABBIX_URL`로 받는다.
- `GET /healthz` → `{"ok": true, "zabbix": "ok" | "down" | "mock"}` (FR-INF-002). Zabbix가 죽어도 MCP 서버는 살아 있고 도구가 `ZABBIX_ERROR`를 돌려준다.
- 인증: 내부 토큰 `INTERNAL_TOKEN`은 [선택](NFR-SEC-003). 켜면 `Authorization: Bearer <INTERNAL_TOKEN>`.
- Zabbix 호출은 **전부 `libs/zabbix_ro` 경유**(허용 목록 밖 메서드는 요청 전 예외, SAFE-02). `ZABBIX_MOCK=true`면 5개 도구가 fixture로 같은 모양을 돌려준다(FR-MCP-010).
- `tools/list`에는 **필수 5개만** 등록한다. planned 7개(4장)는 구현 전 등록하지 않고, 쓰기 도구(`*_create_*`·`*_update_*`·`*_delete_*` 등)는 영원히 없다(SAFE-03). Agent는 4장 12개 이름을 명시 집합으로 검사하고 그 밖의 이름이 있으면 기동하지 않는다(FR-AG-010).

## 2. 공통 봉투 (IF-INT-MCP-001)
도구 결과는 MCP `tools/call` 응답의 `structuredContent`에 아래 JSON을 넣고, 같은 JSON 문자열을 `content[0].text`(type `text`)에도 넣는다.

```json
{"ok": true,  "collected_at": "2026-10-15T06:30:00Z", "data": <도구별>, "truncated": false}
{"ok": false, "collected_at": "2026-10-15T06:30:00Z", "reason": "NO_PERMISSION" | "NOT_FOUND" | "ZABBIX_ERROR", "message": "<사람용 한 줄>"}
```
- `collected_at`: MCP가 Zabbix 응답을 받은 시각, UTC ISO8601 `Z`.
- `truncated`: 목록 100건·이력 500점을 넘어 잘랐으면 `true`(없으면 `false`로 간주) (FR-MCP-007, NFR-PERF-007).
- 실패 시 예외·스택 트레이스·Zabbix 원문 오류를 그대로 넘기지 않는다. `message`는 한 줄 요약만.
- `reason` 규칙: Zabbix 권한 오류(`No permissions`) → `NO_PERMISSION` / 대상 없음(빈 결과로 판단되는 단건 조회) → `NOT_FOUND` / 연결 실패·타임아웃·그 밖의 오류 → `ZABBIX_ERROR`.
- Agent의 `unknown_reason` 변환은 `contracts/agent-api.md`와 같다: `NO_PERMISSION→NO_PERMISSION`, `NOT_FOUND→NO_DATA`, `ZABBIX_ERROR·타임아웃→TOOL_ERROR`, 빈 목록→`NO_DATA`, `stale:true→STALE`.

### 2-1. 값 형식 (#34 결정)
- **Zabbix가 준 필드는 원본 그대로(문자열)** 넘긴다: `eventid`·`itemid`·`hostid`·`triggerid`·`clock`·`r_clock`·`lastclock`·`lastvalue`·`value`·`severity`·`value_type`·`delay` 등. Zabbix API는 숫자도 문자열로 준다(실측 `item.get`·`history.get`). 소비자는 `int()`/`float()`로 바꿔 쓴다.
- **MCP가 계산해서 붙이는 필드만** JSON 타입을 쓴다: `stale`(bool)·`in_maintenance`(bool)·`truncated`(bool)·`source`(문자열)·`collected_at`(ISO8601).
- 시각 인자(`since`, `time_from`, `time_till`)는 **UTC ISO8601 문자열 또는 유닉스 초(정수·문자열)** 둘 다 받는다.

### 2-2. 오래된 값 판정 (FR-MCP-008, SAFE-09)
`stale = (now - lastclock) > max(delay초 × 3, 600초)`. `delay`는 `30s`·`1m`·`1h` 같은 문자열이라 MCP가 초로 바꾼다. 사용자 매크로(`{$...}`)라 해석이 안 되면 600초를 쓴다. `delay`가 `0`(종속 아이템 등)이면 `max(0, 600)`이라 600초다. `30s;50/1-7,00:00-24:00`처럼 유연한 간격이 붙으면 첫 항목(`30s`)만 본다. `lastclock`이 `"0"`이거나 없으면 `stale: true`.

### 2-3. 보내지 않는 값
- 호스트 인터페이스의 `ip`·`dns`는 넘기지 않는다(외부 LLM으로 사설 주소가 나가지 않게). 인터페이스는 종류·가용성만.
- 토큰·URL·비밀값은 어떤 응답에도 넣지 않는다.

## 3. 필수 도구 5개

### 3-1. `zabbix_list_problems` (IF-INT-MCP-002, FR-MCP-002)
- 인자: `severity_min?`(0~5, 기본 0), `hostid?`, `since?`, `limit?`(기본·최대 100)
- 매핑: `problem.get(recent=true, severities≥severity_min, hostids?, time_from=since?, selectTags=extend, sortfield=eventid, sortorder=DESC)` → `trigger.get(triggerids=objectid들, selectHosts=[hostid,name])`로 호스트 보강(**`problem.get`은 호스트를 주지 않는다** — 실측)
- `data`: 배열
```json
[{"eventid": "1234", "objectid": "23456", "name": "High CPU utilization (over 85% for 1m)", "severity": "4",
  "clock": "1792027170", "host": {"hostid": "10642", "name": "<데모 호스트>"}, "tags": [{"tag": "scope", "value": "performance"}]}]
```

### 3-2. `zabbix_get_problem` (IF-INT-MCP-003, FR-MCP-003)
- 인자: `eventid`(필수)
- 매핑: `event.get(eventids, selectHosts, selectTags, select_acknowledges)` + `trigger.get(triggerids=objectid, expandDescription=true, expandExpression=true, selectItems=[itemid,key_,name,value_type,units], selectFunctions)`. **트리거 아이템은 `problem.get`·`event.get`에 없으므로 `trigger.get(selectItems)`로 채운다.**
- 없으면 `{ok:false, reason:"NOT_FOUND"}`
- `data`: 객체. **`items`는 필수**(Agent 고정 수집이 트리거 아이템을 여기서 찾는다, #34). `trigger.items`와 같은 목록이다.
```json
{"eventid": "1234", "name": "High CPU utilization (over 85% for 1m)", "severity": "4", "clock": "1792027170", "r_clock": "0",
 "acknowledged": "0", "hosts": [{"hostid": "10642", "name": "<데모 호스트>"}], "tags": [],
 "trigger": {"triggerid": "23456", "description": "High CPU utilization (over 85% for 1m)",
             "expression": "avg(/<데모 호스트>/system.cpu.util,1m)>85",
             "items": [{"itemid": "45678", "key_": "system.cpu.util", "name": "CPU utilization", "value_type": "0", "units": "%"}]},
 "items": [{"itemid": "45678", "key_": "system.cpu.util", "name": "CPU utilization", "value_type": "0", "units": "%"}]}
```
- `r_clock`이 `"0"`이면 아직 해결되지 않음.

### 3-3. `zabbix_get_host` (IF-INT-MCP-004, FR-MCP-004)
- 인자: `hostid`(필수)
- 매핑: `host.get(hostids, selectHostGroups=[groupid,name], output=[hostid,host,name,status,active_available,maintenance_status])` + `hostinterface.get(hostids)` + `maintenance.get(hostids)`
- 없으면 `NOT_FOUND`
- Zabbix 7.x `host.get`은 그룹을 `hostgroups` 키로 준다. MCP는 이를 `groups`로 이름을 바꿔 돌려준다(Agent는 `groups`만 본다). 인터페이스는 실측 호스트처럼 빈 배열일 수 있다.
- `data`: 객체. `available`은 액티브 에이전트 가용성(`active_available`: 0 알 수 없음·1 사용 가능·2 사용 불가).
```json
{"hostid": "10642", "host": "<기술 이름>", "name": "<표시 이름>", "available": "1",
 "interfaces": [{"type": "1", "main": "1", "available": "0", "error": ""}],
 "groups": [{"groupid": "2", "name": "Windows servers"}], "in_maintenance": false}
```

### 3-4. `zabbix_list_items` (IF-INT-MCP-005, FR-MCP-005)
- 인자: `hostid`(필수), `key_search?`(`item.get`의 `search.key_`, 부분 일치)
- 매핑: `item.get(hostids, output=[itemid,name,key_,lastvalue,lastclock,units,delay,value_type,state], filter.status=0, search?, sortfield=key_)`. 최대 100건, 넘으면 `truncated`.
- `data`: 배열. **`stale`은 MCP가 2-2 규칙으로 계산해 항목마다 붙인다.** `state:"1"`(지원 안 됨)인 항목도 그대로 넘기고 소비자가 거른다.
```json
[{"itemid": "45678", "name": "CPU utilization", "key_": "system.cpu.util", "lastvalue": "96.1", "lastclock": "1792027170",
  "units": "%", "delay": "1m", "value_type": "0", "state": "0", "stale": false}]
```
- 참고(실측): 디스크는 `vfs.fs.dependent.size[C:,pused]`, 네트워크는 `net.if.in["{GUID}"]`처럼 키에 매개변수가 들어간다. 어떤 키를 쓸지는 `packs/<pack>/metrics.yaml`이 정하고 MCP는 키를 고르지 않는다(엔진 하드코딩 금지).

### 3-5. `zabbix_get_history` (IF-INT-MCP-006, FR-MCP-006)
- 인자: `itemid`(필수), `time_from`(필수), `time_till?`(기본 지금), `limit?`(기본·최대 500)
- 매핑: 먼저 `item.get(itemids, output=[value_type,delay,lastclock])`로 값 종류를 알아낸 뒤 `history.get(history=value_type, itemids, time_from, time_till, sortfield=clock, sortorder=ASC, limit)` — **`history.get`은 한 번에 값 종류 하나만 준다(실측)**. 범위가 24시간을 넘으면 `trend.get`(숫자 항목만, `value_avg`를 `value`로)
- `data`: 객체
```json
{"itemid": "45678", "source": "history", "points": [{"clock": "1792026870", "value": "88.4"}, {"clock": "1792026930", "value": "96.1"}],
 "last_clock": "1792026930", "stale": false}
```
- 점이 0개면 `ok:true`, `points: []`(소비자는 `NO_DATA`).
- **`data`는 배열이 아니라 객체다**(#34 결정 3). 오래된 값 판정에 필요한 `last_clock`·`stale`을 같이 주기 때문이다. 소비자는 점을 `data.points[]`에서 읽고 개수는 `len(data.points)`로 센다(`data` 자체의 길이가 아님).

## 4. 도구 이름 전체 (Agent 허용 명시 집합, 13개)
| 이름 | 등급 | 서버 등록 |
|---|---|---|
| `zabbix_list_problems`, `zabbix_get_problem`, `zabbix_get_host`, `zabbix_list_items`, `zabbix_get_history` | 필수 | **등록** |
| `zabbix_get_event_history`, `zabbix_list_triggers`, `zabbix_api_version` | 선택 (IF-INT-MCP-007) | 미등록 |
| `zabbix_get_trends`, `zabbix_list_hosts`, `zabbix_list_host_groups`, `zabbix_get_alert_settings` | 이후 (IF-INT-MCP-008) | 미등록 |
| `kb_search_knowledge` (서버 `mcp-kb`, 6장) | 이후 (FR-RAG-006, 결정 017) | `mcp-kb`에만 등록 |

planned 7개의 인자·응답은 기획서 7-3을 따르고, 구현할 때 이 문서에 상세를 추가하는 계약 PR을 먼저 올린다.

## 5. 확인 방법 (FR-MCP-009·010)
- `ZABBIX_MOCK=true`로 기동 → `tools/list` 이름이 정확히 3장 5개.
- 5개 도구를 fixture로 호출 → 위 예시와 같은 키를 가진 봉투.
- `lastclock`을 15분 전으로 둔 fixture 항목(`delay` 1m) → `stale: true`.
- 허용 목록 밖 메서드 요청 → 네트워크 전에 예외(`libs/zabbix_ro` 테스트).

## 6. mcp-kb — RAG 지식 검색 (v0.2, FR-RAG-006, 결정 017, 등급 [이후])
- 서버: 별도 MCP 서버 `mcp-kb`, streamable HTTP `http://mcp-kb:8300/mcp`(compose 내부 전용), 로컬 `http://localhost:8300/mcp`. Agent는 `MCP_KB_URL`로 받고, **비어 있으면 연결하지 않는다**(기존 동작 그대로).
- `GET /healthz` → `{"ok": true, "kb": "ok" | "empty" | "down", "documents": <int>, "chunks": <int>}`
- `tools/list`에는 `kb_search_knowledge` **하나만** 등록한다(쓰기 도구 없음, SAFE-03). Agent는 mcp-kb의 도구도 4장 명시 집합으로 검사한다.
- 데이터: `libs/kb`가 만든 `knowledge.db`를 **읽기 전용**으로 연다. 색인(쓰기)은 `python -m dejafix_kb index`만 한다.

### `kb_search_knowledge`
- 인자: `query`(필수, 문자열), `k`(선택, 1~5, 기본 5), `source_types`(선택, `incident_report`·`runbook`·`pack_action`·`resolution_note` 중 목록), `host_name`(선택, 장애 리포트만 거름), `exclude_source_ids`(선택, 예: 지금 장애 `incident:34`)
- 봉투: 2장과 같다. 실패 `reason`은 `KB_ERROR`(DB 없음·열기 실패) 하나 → Agent `unknown_reason`은 `TOOL_ERROR`. 결과가 비면 `ok:true`, `hits: []` → 소비자는 `NO_DATA`("관련 지식 없음")로 다룬다.
- `data`: 객체
```json
{"mode": "hybrid", "hits": [
  {"chunk_id": "kb_1a2b3c4d5e6f", "source_type": "incident_report", "source_id": "incident:32",
   "title": "장애 #32 DejaFix demo: CPU 1분 평균 85% 초과", "heading": "장애 #32 ...",
   "text": "<최대 600자>", "score": 0.0325, "cosine": 0.6944,
   "meta": {"incident_id": 32, "host_name": "TaeYoon-PC", "severity": 4}}]}
```
- `mode`: `hybrid`(임베딩 사용) 또는 `keyword`(임베딩 미설정·실패). 숫자 필드(`score`·`cosine`)는 MCP가 계산한 값이라 JSON 숫자다(2-1 예외 규칙과 같음).
- 근거: Agent는 이 호출 자체를 `tool_calls` 1행(`ev_...`)으로 남기고, 답변·리포트에서 인용하는 청크는 `chunk_id`(`kb_...`)로 밝힌다. 검색 결과는 **근거일 뿐 티어를 정하지 않는다**(티어는 `actions.yaml`, SAFE-06).
- 안전: `text`는 Agent가 `<data>` 블록으로 감싸 넣고 그 안의 지시를 따르지 않는다(NFR-RAG-001).

## 변경 이력
- v0 (2026-10-15): 필수 5도구 상세, 공통 봉투, 값 형식(원본 문자열 유지), `get_problem.data.items` 필수, 인터페이스 IP 제외. Issue #34·#28.
- v0.1 (2026-10-15): `get_history.data`가 객체임을 못박음(#34 결정 3), stale 규칙에 `delay` 0·유연한 간격 추가, `host.get` `hostgroups`→`groups` 매핑 명시. 구현은 PR #77과 일치. `docs/plan.md` 7-3은 동결 문서라 고치지 않고 계약이 우선한다(루트 CLAUDE.md 0).
- v0.2 (2026-10-16): `mcp-kb` 서버와 `kb_search_knowledge` 도구 추가(6장, 등급 [이후], 결정 017). 허용 명시 집합 12 → 13개. `MCP_KB_URL`이 비면 Agent는 연결하지 않음. mcp-zabbix 5도구는 변경 없음.
