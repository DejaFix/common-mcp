# docs/zabbix — Zabbix 조사 결과, API 정리

> 한 줄 요약: Zabbix 조사 문서 색인과 공통 규칙(Bearer 토큰, 읽기 전용 역할). 먼저 core-metrics.md.

## 문서

| 파일 | 내용 |
|---|---|
| `core-metrics.md` | **먼저 볼 것.** CPU / MEM / DISK / Network 핵심 지표: Item key, 단위, 템플릿 장애 기준, API로 가져오는 순서 |
| `windows-agent-api.md` | 전체 명세: Windows 에이전트 설치·수집 검증(116개 key), Zabbix 7.0 조회 API 7개, 실서버 응답(12.0절) |
| `api-requests/` | 조회 API 요청 본문 예시 10개 (JSON-RPC) |
| `verification/` | 검증 결과: 패시브 key별 결과, 액티브 이벤트 로그 표본, 로컬 실서버 API 응답(`api-probe-2026-10-14/`) |
| `access.md` | 팀 Zabbix 접속 방식·`ZABBIX_URL` 형식·`.env` 주의점 (주소 값 없음) |
| `readonly-account.md` | 읽기 전용 계정 `dejafix-readonly` 역할·그룹·토큰 구성 (토큰 값 없음) |
| `mcp-live-test.md` | 팀 서버에서 mcp-zabbix 5도구 실호출 결과 |
| `incident-2026-10-16-db-stop.md` | 10/16 06:05 DB·서버 정지 사고 기록, 재발 방지 대책(안)·복구 순서·점검 3단계 |

데모 템플릿·트리거 정의와 적용 절차는 `infra/zabbix/demo/README.md`.

## 플랫폼 구성에서의 위치 (멘토 구성도 기준)

운영 Zabbix를 조회하는 서비스는 셋이다. 이 폴더의 조사는 셋 모두의 기반이다.

| 조회하는 서비스 | 쓰는 API | 참고 |
|---|---|---|
| Zabbix MCP (장애·서버·지표·알림 설정 조회, 쓰기 도구 없음) | problem/event/trigger.get, host.get, item/history.get | 알림 설정(action.get, mediatype.get)은 아직 미조사 |
| Backend (대시보드·리포트) | item.get → history.get, problem.get → trigger.get | `infra/zabbix/tools/dashboard/`가 같은 순서로 동작하는 시제품 |
| Scheduler (하루 한 번 지표·서버 사양 수집) | trend.get, item.get | trend는 숫자형만, 1시간 단위, 최대 2시간 지연, 정렬 없음 |

공통 규칙
- 인증은 `Authorization: Bearer <토큰>` 헤더. 본문 `auth`는 7.2에서 삭제됐다.
- 토큰 사용자는 읽기 전용 역할(API 허용 목록에 get 메서드만)로 만든다. 로컬에서 `user.get`이 차단되는 것을 확인했다.
- `history.get`은 value_type 하나씩만 조회한다(기본값 3).
- `problem.get`은 호스트를 주지 않는다 → `event.get`(`selectHosts`)이나 `trigger.get`(`selectHosts`)을 한 번 더 부른다.
- 지표 분류는 key 이름 대신 템플릿의 `component` 태그(cpu / memory / storage / network)로 조회할 수 있다(Windows 템플릿에서 확인, Linux는 미검증).
- 허용 메서드 13개(기획서 6-2): `apiinfo.version, problem.get, event.get, trigger.get, host.get, hostgroup.get, hostinterface.get, item.get, history.get, trend.get, maintenance.get, action.get, alert.get`. `user.login` 미사용.
- 토큰·비밀번호 **값은 어디에도 적지 않는다**(별도 안전 채널로만 전달).

## 아직 남겨야 닫히는 기록 (요구사항 수용 기준이 "`docs/zabbix/`에 기록"인 것)

| 기록 | 내용 | 근거 | 담당 | 상태 |
|---|---|---|---|---|
| `version.md` | 팀 VM의 OS·Zabbix 버전·설치 방식(apt / VM 내 Docker), `apiinfo.version` 응답 캡처 | FR-ZBX-001, G1 | Zabbix·MCP 담당 | 기록함(2026-10-16): Ubuntu 24.04.5·7.0.31·apt 설치·MariaDB 10.11·06:05 정지 사고(원인 미확정). 로컬 서버 응답은 `verification/api-probe-2026-10-14/` |
| `readonly-account.md` | `dejafix-readonly` 사용자·그룹·권한, API 토큰 발급 절차(값 제외), **`host.update` 호출 시 권한 오류 캡처** | FR-ZBX-004, NFR-SAFE-001 | Zabbix·MCP 담당 | 기록함(역할·그룹·사용자·토큰 구성). `host.update` 권한 오류 증빙 포함(2026-10-15) |
| `access.md` | 접속 방식(웹 80번 포트 `/zabbix`), `ZABBIX_URL` 형식, 방화벽 설정, 아침 점검 절차 결과 | FR-ZBX-006, G7 | Zabbix·MCP 담당 | 기록함(80번 포트, `ZABBIX_URL` 형식, `.env` 주의점). 주소 값은 적지 않음 |
| 실제 아이템 키 | 데모 PC agent 2 설치 결과, 템플릿 이름, cpu·mem·disk·net 키(인터페이스 이름 포함), 스왑 free 불일치 메모 | FR-ZBX-002·007, G2·G18 | 팀장 | **`core-metrics.md`·`windows-agent-api.md`로 충족**. `packs/it/metrics.yaml` 반영 완료(PR #41) |
| `demo-trigger.md` | 데모 템플릿 복제본(CPU 아이템 30초), 트리거 `avg(/<호스트>/system.cpu.util,1m)>85` High, 1회 발동 확인 시각 | FR-ZBX-003, G6 | 팀장 | 템플릿·트리거 정의는 **`infra/zabbix/demo/`로 대체**(PR #61, 로컬 7.0.31 가져오기 확인). 팀 서버 적용·주입 후 발동까지 **실측 104초**(2026-10-15 1회, 목표 90초, Issue #60·PR #119) |
| 자빅스 API 목록 | 노션 "자빅스 API 목록"(멘토 순서 ②)의 사본 또는 링크 | FR-INF-014 | 팀장·Zabbix·MCP 담당 | **`api-requests/`·`windows-agent-api.md`로 충족**. 노션 문서 링크만 추가 |
| `mcp-live-test.md` | 팀 VM 토큰 수령 후 MCP 5도구 실호출 결과(B3 DoD ③) | FR-MCP-002~006 | Zabbix·MCP 담당 | 기록함(2026-10-15 5/5 통과) |
