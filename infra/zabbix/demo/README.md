# infra/zabbix/demo — 데모 템플릿·트리거 (T59, FR-ZBX-003·NFR-PERF-006)

> 한 줄 요약: 데모 CPU 장애를 120초 안에 열리게 하는 Zabbix 템플릿·트리거 정의와 적용 절차 (DejaFix 고유).

데모 장면 D-MAIN(`docs/demo/README.md`)에서 `infra/scripts/inject-cpu.ps1`로 CPU를 올렸을 때 **빠르게(목표 120초 이내, NFR-PERF-006·결정 016) High 장애**가 열리게 하는 템플릿이다. 팀 서버 1회 실측은 **104초**였다(2026-10-15, #60). 원래 목표 90초는 결정 016에서 120초로 고쳤다.

## 파일
| 파일 | 내용 |
|---|---|
| `dejafix-demo-windows-active.yaml` | 템플릿 **`DejaFix Demo Windows by Zabbix agent active`** (Zabbix 7.0 내보내기 형식) |

원본 `Windows by Zabbix agent active`(7.0.31 기본 템플릿)를 내보내 아래 두 가지만 바꿨다. 나머지 항목·LLD·트리거·그래프는 원본과 같고, uuid는 원본과 겹치지 않게 새로 만들었다.
1. `system.cpu.util` 수집 주기 **1m → 30s**
2. 트리거 추가: **`DejaFix demo: CPU 1분 평균 85% 초과`** — `avg(/DejaFix Demo Windows by Zabbix agent active/system.cpu.util,1m)>85`, 심각도 **High**, 태그 `scope=performance`·`dejafix=demo`. 평균이 85% 아래로 내려가면 자동 해소

원본 트리거 `Windows: High CPU utilization`(`min(...,5m)>90`, Warning)은 5분을 기다려야 해서 데모 시간 예산(트리거 120초, `docs/demo/README.md`)에 맞지 않는다.
- **원본 트리거는 이 템플릿에도 그대로 남아 있다.** 부하가 5분 넘게 이어지면 같은 호스트에 Problem이 2개(데모 High + 원본 Warning) 뜰 수 있다. 데모 주입은 `-Minutes 3` 이하로 하고, 장애 건수를 1건으로 맞춰야 하면 데모 호스트에서 원본 트리거만 비활성화한다(결정은 Zabbix·MCP 담당, 적용 전 Issue #60에 기록).

- 트리거 식은 템플릿 이름을 참조하므로 **호스트 이름과 무관**하다. 데모 호스트 이름은 `(TODO: 추후결정 — 후보: LAB-PC-DEMO)`(결정 008)이며 이 파일에 적지 않는다.
- **실측 104초**(2026-10-15, 1회, #60: 시작 21:54:10 → High 21:55:54 KST, 12코어 PC)로 목표 90초를 14초 넘겼다. 원인(추정): 수집 30초 간격이라 `avg(...,1m)` 창에 값이 2~3개뿐이고, Windows 에이전트의 `system.cpu.util`이 이미 1분 평균이라 이중 평균이 된다. **결정 016**(2026-10-16): 식·임계값은 그대로 두고 목표를 120초로 현실화했다(임계값 75~80% 하향·`avg(...,#1)`은 팀 PC 6대에 오탐이 늘어 기각). 편차 확인을 위해 리허설에서 2~3회 더 재고, 120초를 넘기면 결정 016의 재검토 조건을 따른다.

## 검증한 것 (2026-10-15, 로컬 개발 서버 7.0.31)
- `configuration.import` 성공, 템플릿 생성 확인: `system.cpu.util` delay `30s`, 데모 트리거 priority `4`(High), 식 위와 동일
- 로컬 서버에서는 **호스트에 연결하지 않았다**(기존 설정을 바꾸지 않기 위해). 그래서 **실제 발동(주입 → Problem)은 아직 확인하지 않았다** → 아래 4단계로 팀 서버에서 확인

## 팀 서버에 적용 (Zabbix·MCP 담당, 관리자 권한 필요)
운영 Zabbix 쓰기 작업이므로 **DejaFix 서비스(Backend·MCP·Scheduler)가 아니라 사람이 웹 화면에서** 한다(플랫폼은 조회만).
0. **버전 확인**: 이 YAML은 7.0 내보내기 형식이다(로컬 7.0.31에서만 확인). 팀 서버 웹 하단 또는 `apiinfo.version`으로 **7.0 이상인지 먼저 확인**한다. 7.0 미만이면 가져오기가 실패하므로 멈추고 Issue #60에 버전을 남긴다.
1. **가져오기**: Data collection → Templates → Import → 이 YAML 선택 → 기본 규칙(Create new) 그대로 Import
2. **데모 호스트에 연결**: Data collection → Hosts → 데모 호스트 → Templates에서
   - 원본 `Windows by Zabbix agent active`는 **Unlink and clear** (Unlink만 하면 원본 항목이 호스트에 남아 같은 키가 충돌해 연결이 실패한다). **그 호스트의 기존 이력이 지워진다** — 데모·리허설에 쓸 이력이 있는 호스트면 적용하지 말고 Issue #60에서 먼저 정한다
   - `DejaFix Demo Windows by Zabbix agent active` 추가 → Update
   - 데모 호스트 외 다른 호스트는 원본 템플릿을 그대로 둔다
3. **수집 확인**: Monitoring → Latest data에서 `CPU utilization` 값이 30초마다 갱신되는지
4. **발동 확인**(낮에만, 야간 금지): 데모 PC에서 `powershell -ExecutionPolicy Bypass -File infra\scripts\inject-cpu.ps1 -Minutes 3` → Monitoring → Problems에 `DejaFix demo: CPU 1분 평균 85% 초과`(High)가 뜰 때까지 **걸린 시간을 잰다**(목표 120초, 결정 016) → `cleanup.ps1` 후 해소 확인. 걸린 시간은 Issue #60 코멘트와 `docs/demo/rehearsal-log.md`

## 다시 만들 때
로컬 개발 서버에서 원본 템플릿을 `configuration.export`(yaml)로 내보내고 위 두 가지만 바꾼 뒤 uuid를 새로 만든다. 템플릿 이름이 들어간 곳(트리거·그래프 식의 `/템플릿/`, 그래프 항목의 `host:`)을 모두 바꿔야 가져오기가 된다(바꾸지 않으면 `Item with ID ... is not available`).
