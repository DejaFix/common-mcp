# infra/zabbix/demo — 데모 템플릿·트리거

> 한 줄 요약: CPU 부하 시연 장애를 빠르게(목표 120초 이내) 열리게 하는 Zabbix 템플릿·트리거 정의와 적용 절차 (시연용 예시, 바꿔 쓸 것).

`infra/scripts/inject-cpu.ps1`로 CPU를 올렸을 때 **빠르게 High 장애**가 열리게 하는 템플릿이다. 한 번의 실측은 **104초**였다(12코어 PC).

## 파일
| 파일 | 내용 |
|---|---|
| `demo-windows-active.yaml` | 템플릿 **`Demo Windows by Zabbix agent active`** (Zabbix 7.0 내보내기 형식) |

원본 `Windows by Zabbix agent active`(7.0.31 기본 템플릿)를 내보내 아래 두 가지만 바꿨다. 나머지 항목·LLD·트리거·그래프는 원본과 같고, uuid는 원본과 겹치지 않게 새로 만들었다.
1. `system.cpu.util` 수집 주기 **1m → 30s**
2. 트리거 추가: **`Demo: CPU 1분 평균 85% 초과`** — `avg(/Demo Windows by Zabbix agent active/system.cpu.util,1m)>85`, 심각도 **High**, 태그 `scope=performance`·`project=demo`. 평균이 85% 아래로 내려가면 자동 해소

원본 트리거 `Windows: High CPU utilization`(`min(...,5m)>90`, Warning)은 5분을 기다려야 해서 시연 시간 예산에 맞지 않는다.
- **원본 트리거는 이 템플릿에도 남아 있다.** 부하가 5분 넘게 이어지면 같은 호스트에 Problem이 2개(High + 원본 Warning) 뜰 수 있다. 주입은 `-Minutes 3` 이하로 하고, 1건으로 맞춰야 하면 시연 호스트에서 원본 트리거만 비활성화한다.
- 트리거 식은 템플릿 이름을 참조하므로 **호스트 이름과 무관**하다. 호스트 이름은 이 파일에 적지 않는다.
- 104초가 된 원인(추정): 수집 30초 간격이라 `avg(...,1m)` 창에 값이 2~3개뿐이고, Windows 에이전트의 `system.cpu.util`이 이미 1분 평균이라 이중 평균이 된다. 임계값 하향·`avg(...,#1)`은 오탐이 늘어 쓰지 않고 목표를 120초로 잡았다. 편차는 리허설에서 2~3회 더 재서 확인한다.

## 검증한 것 (로컬 개발 서버 7.0.31)
- `configuration.import` 성공, 템플릿 생성 확인: `system.cpu.util` delay `30s`, 트리거 priority `4`(High), 식 위와 동일
- 로컬 서버에서는 호스트에 연결하지 않아 **실제 발동(주입 → Problem)은 아래 4단계로 따로 확인**한다.

## 대상 서버에 적용 (관리자 권한 필요)
운영 Zabbix 쓰기 작업이므로 **애플리케이션이 아니라 사람이 웹 화면에서** 한다(애플리케이션은 조회만).
0. **버전 확인**: 이 YAML은 7.0 내보내기 형식이다. 서버 웹 하단 또는 `apiinfo.version`으로 **7.0 이상인지 먼저 확인**한다. 7.0 미만이면 가져오기가 실패하므로 멈춘다.
1. **가져오기**: Data collection → Templates → Import → 이 YAML 선택 → 기본 규칙(Create new) 그대로 Import
2. **호스트에 연결**: Data collection → Hosts → 시연 호스트 → Templates에서
   - 원본 `Windows by Zabbix agent active`는 **Unlink and clear** (Unlink만 하면 원본 항목이 호스트에 남아 같은 키가 충돌해 연결이 실패한다). **그 호스트의 기존 이력이 지워진다** — 보존할 이력이 있는 호스트면 적용하지 않는다
   - `Demo Windows by Zabbix agent active` 추가 → Update
   - 다른 호스트는 원본 템플릿을 그대로 둔다
3. **수집 확인**: Monitoring → Latest data에서 `CPU utilization` 값이 30초마다 갱신되는지
4. **발동 확인**(업무 시간 내): `powershell -ExecutionPolicy Bypass -File infra\scripts\inject-cpu.ps1 -Minutes 3` → Monitoring → Problems에 `Demo: CPU 1분 평균 85% 초과`(High)가 뜰 때까지 **걸린 시간을 잰다**(목표 120초) → `cleanup.ps1` 후 해소 확인

## 다시 만들 때
로컬 개발 서버에서 원본 템플릿을 `configuration.export`(yaml)로 내보내고 위 두 가지만 바꾼 뒤 uuid를 새로 만든다. 템플릿 이름이 들어간 곳(트리거·그래프 식의 `/템플릿/`, 그래프 항목의 `host:`)을 모두 바꿔야 가져오기가 된다(바꾸지 않으면 `Item with ID ... is not available`).
