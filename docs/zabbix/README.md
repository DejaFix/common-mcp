# docs/zabbix — Zabbix 조사 결과, API 정리

> 한 줄 요약: Zabbix 조사 문서 색인과 공통 규칙(Bearer 토큰, 읽기 전용 역할). 먼저 core-metrics.md.

## 문서

| 파일 | 내용 |
|---|---|
| `core-metrics.md` | **먼저 볼 것.** CPU / MEM / DISK / Network 핵심 지표: Item key, 단위, 템플릿 장애 기준, API 조회 순서 |
| `windows-agent-api.md` | Windows Agent 2 설치·수집 검증 절차, Item key 목록, 조회 API 7개 사용법과 응답 예시 |
| `api-requests/` | 조회 API 요청 본문 예시 10개 (JSON-RPC) |
| `verification/` | 검증 결과: 패시브 key별 결과 |
| `access.md` | Zabbix 접속 형식(`ZABBIX_URL`, Bearer 토큰)과 `.env` 주의점 (주소 값 없음) |
| `version.md` | 대상 서버의 버전·OS·설치 방식을 기록하는 양식과 사례 |
| `readonly-account.md` | 읽기 전용 역할·사용자 그룹·API 토큰 구성 절차와 쓰기 거부 증빙 (토큰 값 없음) |
| `mcp-live-test.md` | 실서버에서 mcp-zabbix 5도구를 호출해 확인하는 방법과 기록 양식 |
| `runbook-db-stop.md` | Zabbix DB·서버 정지 사고 대응 런북 |

## 공통 규칙
- 인증은 `Authorization: Bearer <토큰>` 헤더. 본문 `auth`는 7.2에서 삭제됐다.
- 토큰 사용자는 읽기 전용 역할(API 허용 목록에 get 메서드만)로 만든다. 허용 목록 밖 메서드(`user.get` 등)가 차단되는 것을 확인한다.
- `history.get`은 value_type 하나씩만 조회한다(기본값 3).
- `problem.get`은 호스트를 주지 않는다 → `event.get`(`selectHosts`)이나 `trigger.get`(`selectHosts`)을 한 번 더 부른다.
- 지표 분류는 key 이름 대신 템플릿의 `component` 태그(cpu / memory / storage / network)로 조회할 수 있다(Windows 템플릿에서 확인, Linux는 미검증).
- 허용 메서드 13개: `apiinfo.version, problem.get, event.get, trigger.get, host.get, hostgroup.get, hostinterface.get, item.get, history.get, trend.get, maintenance.get, action.get, alert.get`. `user.login` 미사용.
- 토큰·비밀번호 **값은 어디에도 적지 않는다**(별도 안전 채널로만 전달).

## 조회 클라이언트별 쓰는 API 예
| 클라이언트 | 쓰는 API | 참고 |
|---|---|---|
| MCP 서버(읽기 전용 도구) | problem/event/trigger.get, host.get, item/history.get | 알림 설정(action.get, mediatype.get)은 미조사 |
| 대시보드·리포트 | item.get → history.get, problem.get → trigger.get | |
| 주기 수집기 | trend.get, item.get | trend는 숫자형만, 1시간 단위, 최대 2시간 지연, 정렬 없음 |
