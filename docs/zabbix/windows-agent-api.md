# Zabbix Windows Agent 2 · 수집 데이터 · API 연동 명세

> 한 줄 요약: Windows Agent 2 수집 항목과 Zabbix 7.0 조회 API 상세 명세(레퍼런스, 길어서 목차로 찾아 읽기).

- 작성: 2026-10-14 · 담당 범위: Windows PC에 Zabbix Agent 2 설치·수집 검증, Zabbix API 조사, 백엔드 연동 명세
- 기준 버전: Zabbix **7.0 LTS** (Agent 2 **7.0.31**, 2026-09-22 배포). API 문서는 7.0 기준, 7.2/7.4 차이는 따로 표시
- Zabbix 서버: **이 PC의 Docker에 Zabbix 7.0.31 로컬 서버를 올려 검증(2026-10-14 17:45~)** — `infra/zabbix/local-server`, 127.0.0.1 전용. 팀 공용 서버 정보는 아직 없음. 아래 "서버 필요" 표시 항목 중 로컬 서버로 확인한 것은 12.0절에 따로 적었다.

## 결론 먼저

| 항목 | 상태 |
|---|---|
| 설치 | 공식 Agent 2 7.0.31 압축본을 사용자 권한으로 설치해 실행 검증 완료(공식 SHA256 일치). **Windows 서비스 등록은 미완료** — 관리자 승인과 서버 주소가 필요하다. |
| 수집 검증 | 이 PC에서 Item key 116개 실측, 106개 성공. 실패 10개 중 9개는 "문서상 Windows 미지원"을 확인하려고 일부러 넣은 키, 1개는 한글 인터페이스 이름 문제. CPU·메모리·디스크·네트워크·서비스·프로세스 값은 같은 시점의 Windows 값과 교차 비교해 일치(차이 0~0.6%). |
| 이벤트 로그 | `eventlog[]`는 액티브 전용. 로컬 모의 수신기로 실제 에이전트 출력을 받아 Windows 이벤트 뷰어 원본과 **74/74건 일치** 확인. |
| 서버 연결 | **로컬 Docker 서버로 확인**: Agent 2 서비스(MSI, 액티브 전용, `SKIP=fw`) → `127.0.0.1:10051` 연결, 호스트 `active_available=1`, 실제 장애(C: 90% 초과) 감지. 팀 공용 서버 연결은 미검증. |
| API | 7개 get 메서드를 **로컬 실서버(7.0.31)에서 읽기 전용 토큰으로 호출해 확인**(12.0절, 응답 `docs/zabbix/verification/api-probe-2026-10-14/`). 허용 목록 밖 메서드(`user.get`)는 "No permissions"로 차단됨. |

백엔드가 꼭 알아야 할 다섯 가지:

1. 인증은 `Authorization: Bearer <API 토큰>` 헤더만 쓴다. 요청 본문의 `auth` 속성은 7.0에서 폐기 예정, **7.2에서 삭제**됐다.
2. `history.get`은 한 번에 **value_type 하나**만 조회한다(기본값 3 = 정수). 타입이 안 맞으면 오류 없이 빈 배열이 온다. Item의 `value_type`을 먼저 확인한다.
3. `trend.get`은 숫자형(0 float, 3 unsigned) Item의 **1시간 단위 min/avg/max**만 있다. 최대 2시간 늦게 생기고 정렬 파라미터가 없다.
4. `problem.get`은 호스트 정보를 주지 않는다. `objectid`(= triggerid)로 `trigger.get` 또는 `event.get`(`selectHosts`)을 다시 호출한다.
5. 응답의 숫자는 모두 **문자열**이다(`"clock": "1351090996"`, `"value": "0.085"`). `clock`은 Unix 초(UTC)다.

판정 표시: **[실측]** 이 PC에서 값 확인 · **[교차일치]** Windows 원본 값과 비교해 일치 · **[실측·미지원]** 이 PC에서 미지원 확인 · **[주의]** 실측값이 문서나 실제와 다름 · **[문서]** 문서·소스로만 확인 · **[서버 필요]** Zabbix 서버가 있어야 확인 가능

---

## 1. 작업 범위 및 시스템 구성

### 1.1 역할과 범위

- 이번 범위: Windows PC Agent 설치, 수집 가능한 데이터 검증, Zabbix API 조사, 백엔드 연동 명세
- 범위 밖: Zabbix 서버 설치(다른 팀원 담당), 프론트엔드, 플랫폼 코드 구현

### 1.2 구성: 수집과 조회는 서로 다른 단계

```
 [Windows PC]                    [Zabbix 서버 7.x]                         [DejaFix 백엔드 (FastAPI)]
  Zabbix Agent 2                  ┌───────────────────────────┐
   ├─ 액티브 체크 ──TCP 10051──▶  │ trapper (값 수신)          │
   │   (PC → 서버, 권장)           │ poller  (값 요청)          │        JSON-RPC 2.0 over HTTP(S)
   └─ 패시브 체크 ◀─TCP 10050──   │ DB: history / trends /     │ ◀── POST /api_jsonrpc.php ── Zabbix 어댑터
       (서버 → PC)                 │     events / problems      │      Authorization: Bearer <토큰>
                                   │ 프론트엔드(PHP) = API      │ ──▶ (선택) 웹훅으로 장애 이벤트 push
                                   └───────────────────────────┘
```

- **Agent → 서버**: Zabbix 자체 프로토콜(ZBXD 헤더 + JSON). 에이전트가 모은 값은 서버 DB에 저장된다.
- **백엔드 → 서버**: Zabbix API(JSON-RPC). 백엔드는 **에이전트에 직접 붙지 않는다**. 에이전트가 수집하지 않은 값은 API로도 나오지 않으므로, 분석에 필요한 데이터는 먼저 Zabbix Item으로 등록돼 있어야 한다.
- 플랫폼 7단계 중 사용처: 1단계 알람 수신(problem/event), 2단계 원인 분석(history/trend/trigger/event 이력), 6단계 결과 보고서(조치 전후 지표 = history).

### 1.3 1단계 조사 결과 (2026-10-14, 읽기 전용으로 조사)

| 항목 | 확인 값 |
|---|---|
| OS | Windows 10 Pro 22H2, 빌드 19045.6466, x64 |
| CPU / RAM | Intel i7-8700, 논리 프로세서 12개 / 15.9 GB(17,111,175,168 B) |
| 디스크 | C: NTFS 111.1 GB, 여유 약 9.1 GB(사용률 91.9%) — Windows 템플릿 기준이면 "디스크 공간 매우 부족(>90%)" 조건에 해당 |
| 네트워크 | Realtek PCIe GbE 1 Gbps, 연결 이름 `이더넷` |
| 언어 | UI 언어 en-US, 시스템 로캘 ko-KR → 성능 카운터 이름이 영어로 보임. 한글 UI PC에서는 `perf_counter`(현지어)와 `perf_counter_en`(영어)이 다르게 동작할 수 있어 **`perf_counter_en`을 기준으로** 쓴다. |
| 권한 | 계정은 Administrators 그룹 소속이지만 현재 셸은 비관리자 토큰(UAC 동의 프롬프트 방식) |
| 방화벽 | Domain/Private/Public 프로필 모두 켜짐 |
| 기존 Zabbix | 없음 — 서비스·프로세스·제거 프로그램 목록·설치 폴더·PATH·설정 파일·포트 10050/10051 모두 확인 |
| 서버 정보 | 저장소·환경 변수·hosts 파일에서 서버 주소를 찾지 못함 |
| 저장소 | `Documents/DejaFix`가 비어 있었음(git 아님). 이번 작업으로 `docs/`, `infra/zabbix/tools/`만 추가 |
| 개발 도구 | Python 3.11.17(conda `dev`), Git 2.55.0, curl 8.13.0, PowerShell 5.1 |

### 1.4 이번 작업 산출물

| 경로 | 내용 |
|---|---|
| `docs/zabbix/windows-agent-api.md` | 이 문서 |
| `docs/zabbix/verification/passive-items.md`, `.json` | 패시브 체크 116개 실측 결과(IP·프로세스 목록 등 개인 정보 제거본) |
| `docs/zabbix/verification/active-eventlog-sample.json` | 액티브 체크·이벤트 로그 실측 요약과 표본(메시지 본문 제거) |
| `docs/zabbix/api-requests/*.json` | 플랫폼이 보낼 API 요청 본문 10개(점검 스크립트 dry-run으로 생성) |
| `infra/zabbix/tools/verify_agent_items.py` | 에이전트에 패시브 질의를 보내 키별 결과를 기록 |
| `infra/zabbix/tools/mock_active_server.py` | 액티브 체크 검증용 로컬 모의 수신기(**Zabbix 서버 아님**) |
| `infra/zabbix/tools/zabbix_api_probe.py` | 서버 준비 후 7개 API를 읽기 전용으로 점검 |

에이전트 설치본은 저장소 밖 `C:\Users\403\zabbix-agent2\`에 있다(설치 파일, 압축 해제본, 로컬 검증 설정·로그·원본 결과).

---

## 2. Windows Agent 설치 절차

### 2.1 버전 선택

| 근거 | 내용 |
|---|---|
| 호환 규칙 [문서] | "Zabbix agent 2 must not be newer than 7.0"(7.0 서버 기준). **에이전트는 서버보다 높은 메이저 버전을 쓰면 안 된다.** 4.4 이후 에이전트 2는 7.0 서버와 호환. |
| 수명 [문서] | 7.0 LTS: 전체 지원 2027-06-30, 제한 지원 2029-06-30. 7.4: 8.0 LTS 출시까지. 8.0 LTS: 2026년 4분기 출시 예정(아직 미출시, CDN에 8.0 없음) |
| 최신 패치 [확인] | 7.0.31(2026-09-22), 7.4.15(2026-09-24) |
| 결정 | 서버 버전을 모르는 지금은 **7.0.31**이 가장 안전하다(7.0·7.2·7.4 서버 모두 호환). 서버가 7.4로 정해지면 같은 버전으로 올려도 된다. |

### 2.2 내려받은 파일과 무결성 확인 [실측]

| 파일 | 크기 | SHA256 (공식 다운로드 페이지 값과 일치) | 서명 |
|---|---|---|---|
| `zabbix_agent2-7.0.31-windows-amd64-openssl-static.zip` | 15,339,754 B | `4ed7f9f9071732c3339dcdc00e677624180623c01aeb37bcc0f138016796869e` | zip 안 exe는 Authenticode 서명 **없음** |
| `zabbix_agent2-7.0.31-windows-amd64-openssl.msi` | 18,415,616 B | `dd85c5448edf81bc1dae551d50bd486dfd9a226cf4a80db4f6945201de494fa9` | **Valid**, `CN=Zabbix SIA`(SSL.com 발급, 인증서 만료 2027-05-12) |

- 다운로드 경로: `https://cdn.zabbix.com/zabbix/binaries/stable/7.0/7.0.31/`
- 공식 체크섬은 `https://www.zabbix.com/download_agents` 페이지에 들어 있는 데이터에서 읽었다. CDN 폴더에는 체크섬 파일이 없다.
- `zabbix_agent2.exe -V` → `zabbix_agent2 Win64 (Zabbix) 7.0.31, Revision e7da53eea21`, go1.26.8, OpenSSL 3.5.1

### 2.3 이번에 한 설치: 압축본, 사용자 권한, 서비스 미등록 [실측]

관리자 권한과 서버 주소가 없어 서비스는 등록하지 않았다. 대신 같은 실행 파일을 콘솔 모드로 띄워 수집을 검증했고, 검증 뒤 프로세스를 종료했다(현재 실행 중인 Zabbix 프로세스 없음, 10050/10051 포트 해제 확인).

```powershell
# 1) 새 빈 폴더에 압축 해제 (원본 conf\zabbix_agent2.conf 는 수정하지 않음)
Expand-Archive C:\Users\403\zabbix-agent2\installer\zabbix_agent2-7.0.31-windows-amd64-openssl-static.zip `
               -DestinationPath C:\Users\403\zabbix-agent2\portable

# 2) 로컬 검증 전용 설정 (별도 파일, 루프백만 사용)
#    C:\Users\403\zabbix-agent2\local-test\zabbix_agent2.local-test.conf
$a = "C:\Users\403\zabbix-agent2\portable\bin\zabbix_agent2.exe"
$c = "C:\Users\403\zabbix-agent2\local-test\zabbix_agent2.local-test.conf"
& $a -c $c -T          # 설정 검증 → "Validation successful"
& $a -c $c -p          # 이 PC에서 아는 키를 모두 실행해 출력 (367줄)
& $a -c $c -f          # 콘솔(포그라운드) 실행 — 검증 동안만 띄움
& $a -c $c -R version  # 런타임 명령 (ControlSocket 파이프 사용) → 7.0.31
```

로컬 검증 설정의 핵심: `Server=127.0.0.1`, `ListenIP=127.0.0.1`(방화벽 개방 불필요), `ServerActive=127.0.0.1:10051`(모의 수신기), `LogFile=C:\Users\403\zabbix-agent2\local-test\logs\zabbix_agent2.log`, `ControlSocket=\\.\pipe\zabbix-agent2-localtest`.

### 2.4 서버 준비 후 할 설치 (관리자 권한 필요, 아직 실행 안 함)

**먼저 받아야 할 정보** (임의로 정하지 않는다):

| 정보 | 누구에게 | 쓰는 곳 |
|---|---|---|
| Zabbix 서버(또는 프록시) 주소·포트 | 서버 담당 팀원 | `SERVER`, `SERVERACTIVE` |
| 서버 버전 | 서버 담당 팀원 | 에이전트 버전 결정(서버 이하) |
| 이 PC를 Zabbix에 등록할 호스트 이름 | 서버 담당 팀원과 합의 | `HOSTNAME` — 서버에 등록된 이름과 **대소문자까지 같아야** 액티브 체크가 동작 |
| 패시브 체크 사용 여부 | 팀 결정 | 쓰면 이 PC 방화벽에 10050 인바운드를 **서버 IP로만** 허용해야 함 |
| 암호화(PSK) 사용 여부 | 팀 결정 | `TLSCONNECT/TLSACCEPT=psk` 등 |
| 관리자 승인 | PC 사용자 | MSI 설치·서비스 등록·방화벽 규칙 |

**권장: 액티브 전용 + MSI 설치** — 액티브 체크는 PC가 서버로 나가는 연결만 쓰므로 PC 방화벽에 들어오는 포트를 열 필요가 없다. 이벤트 로그(`eventlog[]`)도 액티브에서만 동작한다. Zabbix 쪽 템플릿은 `Windows by Zabbix agent active`를 쓴다.

```bat
:: 관리자 cmd에서 실행. <...> 는 받은 값으로 바꾼다. 로그는 %TEMP% 에 남는다.
msiexec.exe /l*v "%TEMP%\zabbix_agent2_install.log" /i "C:\Users\403\zabbix-agent2\installer\zabbix_agent2-7.0.31-windows-amd64-openssl.msi" /qn ^
 SERVER=<ZABBIX_SERVER> ^
 SERVERACTIVE=<ZABBIX_SERVER>:10051 ^
 HOSTNAME=<HOST_NAME_IN_ZABBIX> ^
 INSTALLFOLDER="C:\Program Files\Zabbix Agent 2" ^
 SKIP=fw ^
 ENABLEPATH=1
```

- `SKIP=fw` [문서]: 설치 프로그램이 Windows 방화벽 예외 규칙을 **자동으로 추가하지 않게** 한다. 액티브 전용이면 인바운드 규칙이 필요 없다.
- MSI 서비스 시작 유형 기본값은 지연된 자동 시작이다 [문서]. `STARTUPTYPE`, 설치 직후 시작을 막는 `DONOTSTART=1`(7.0.22 이상)도 있다.
- `SERVER`는 필수다 [문서]. 패시브를 쓰지 않아도 서버 주소를 넣어 둔다(액티브 전용으로 완전히 끄는 `STARTAGENTS=0` 설명은 문서상 zabbix_agentd 기준이라 Agent 2 적용 여부는 미확인).
- 기본 설치 폴더는 문서에 `C:\Program Files\Zabbix Agent`로 적혀 있고, Agent 2 플러그인 MSI 예시는 `C:\Program Files\Zabbix Agent 2`를 쓴다. 혼동을 피하려고 `INSTALLFOLDER`를 명시한다.
- 서비스 이름은 `Zabbix Agent 2` (추정 — 설치 후 `Get-Service *zabbix*`로 확인).

**패시브 체크도 쓸 때만** 방화벽 규칙을 서버 IP 하나로 좁혀 추가한다:

```powershell
New-NetFirewallRule -DisplayName "Zabbix Agent 2 passive (from Zabbix server only)" -Direction Inbound `
  -Protocol TCP -LocalPort 10050 -RemoteAddress <ZABBIX_SERVER_IP> `
  -Program "C:\Program Files\Zabbix Agent 2\zabbix_agent2.exe" -Action Allow
```

**대안: 압축본으로 서비스 등록** (MSI를 못 쓸 때) [문서]: 설정 파일을 exe와 같은 폴더에 두고 관리자 셸에서

```powershell
zabbix_agent2.exe -c "C:\Program Files\Zabbix Agent 2\zabbix_agent2.conf" -i   # 서비스 설치 (-S delayed 등으로 시작 유형 지정 가능)
zabbix_agent2.exe -c "C:\Program Files\Zabbix Agent 2\zabbix_agent2.conf" -s   # 서비스 시작
# 중지 -x, 제거 -d, 여러 인스턴스 -m
```

### 2.5 기존 설정 보존

- MSI로 업그레이드하면 기존 설정 파일 이름을 바꾸고 새 설정 파일을 만든다 [문서]. 설치 전 `zabbix_agent2.conf`를 백업하고, 필요하면 `CONF=` 템플릿 파일에 `[LogFile]`, `[Include]`, `[TLSConnect]` 같은 자리표시자를 넣어 기존 값을 이어받는다 [문서].
- 이번 작업에서는 압축본 원본 설정을 수정하지 않았고, 로컬 검증용 설정은 별도 파일로 만들었다.

---

## 3. 설정 파일의 주요 항목

배포본 `zabbix_agent2.conf`에서 실제로 켜져 있는 줄은 `Server=127.0.0.1`, `ServerActive=127.0.0.1`, `Hostname=Windows host`, `ControlSocket=\\.\pipe\agent.sock`, `Include=.\zabbix_agent2.d\plugins.d\*.conf` 다섯 줄뿐이다 [실측].

| 파라미터 | 의미 | 배포본 기본값 [실측] | 이번 로컬 검증 값 | 운영 권장 |
|---|---|---|---|---|
| `Server` | 패시브 요청을 허용할 서버/프록시 주소 | `127.0.0.1` | `127.0.0.1` | 팀 서버 주소 |
| `ListenIP` / `ListenPort` | 패시브 수신 주소·포트 | `0.0.0.0` / `10050`(주석) | `127.0.0.1` / `10050` | 패시브 안 쓰면 기본값 두고 방화벽 미개방 |
| `ServerActive` | 액티브 체크 목록을 받을 서버 `주소:포트` | `127.0.0.1` | `127.0.0.1:10051`(모의 수신기) | 팀 서버 `주소:10051` |
| `Hostname` | 서버에 등록된 호스트 이름(대소문자 구분) | `Windows host` | `dejafix-local-test` | 서버 등록명과 동일 |
| `HostMetadata` | 자동 등록용 메타데이터 | 없음 | 없음 | 자동 등록을 쓸 경우 예: `windows dejafix` |
| `LogType` / `LogFile` | 로그 | `file` / `c:\zabbix_agent2.log`(주석 = 기본값, **C:\ 루트라 관리자 권한 필요**) | 사용자 폴더 | MSI 기본값 사용 |
| `Timeout` | 항목 처리 제한 시간(초) | 3(주석) | 10 | WMI 쿼리가 많으면 늘림(프로세스 WMI 조회 351 ms 실측) |
| `RefreshActiveChecks` | 액티브 항목 목록 갱신 주기(초) | 120(주석) | 60 | 기본값 |
| `BufferSend` / `BufferSize` | 값 묶음 전송 주기 / 버퍼 크기 | 5 / 1000(주석) | 5 | 기본값 |
| `EnablePersistentBuffer` | 서버 단절 동안 값을 SQLite에 보관(Agent 2 전용) | 0(주석) | 0 | 네트워크 장애 분석을 위해 켜는 것 검토 |
| `HeartbeatFrequency` | 액티브 가용성 하트비트(초) | 비어 있음(주석) | 기본값 | 기본값 — 실측 60초마다 전송됨 |
| `ControlSocket` | `-R` 런타임 명령용 파이프 | `\\.\pipe\agent.sock` | 별도 파이프 이름 | 기본값 |
| `DenyKey` / `AllowKey` | 실행 허용/차단 키 | `DenyKey=system.run[*]`(주석 = 기본값) | 기본값 | **`system.run` 차단 유지**(원격 명령 실행 방지) |
| `TLSConnect` / `TLSAccept` | 서버와 암호화 | `unencrypted`(주석) | 기본값 | PSK 검토 — 미암호화 시 누구나 에이전트를 사칭해 액티브 항목 설정을 받아 갈 수 있다고 문서가 경고 |
| `Include` | 추가 설정 파일 | 플러그인 설정 폴더 | 절대 경로로 지정 | 기본값 |

---

## 4. 설치 및 연결 검증 방법

### 4.1 이번에 실행한 검증 [실측]

| 단계 | 명령 | 결과 |
|---|---|---|
| 설정 검증 | `zabbix_agent2.exe -c <conf> -T` | `Validation successful` |
| 키 목록 | `zabbix_agent2.exe -c <conf> -p` | 367줄. 수집기가 필요한 키(CPU·성능 카운터)는 이 모드에서 `ZBX_NODATA`, `eventlog`는 "not supported in test or single passive check mode" |
| 실행 | `zabbix_agent2.exe -c <conf> -f` (백그라운드) | 127.0.0.1:10050 수신 확인, 내장 플러그인 38개 로드(로그) |
| 패시브 질의 | `python infra/zabbix/tools/verify_agent_items.py --zabbix-get <zabbix_get.exe> --out <dir>` | 116개 중 106개 성공. 같은 키를 두 번 질의 — 1차는 수집기 등록, 65초 뒤 2차 값을 기록 |
| 액티브 수신 | `python infra/zabbix/tools/mock_active_server.py --items active-items.json --out received.jsonl` | 9개 항목, 값 175건 수신. 하트비트 60초 간격, 항목 목록 요청 60초 간격(증분 동기화 `config_revision`) |
| 교차 비교 | 같은 시점에 PowerShell/CIM 값과 비교 | 5.3절 표 |
| 런타임 명령 | `-R version`, `-R metrics` | `7.0.31`, 지원 메트릭 목록 361줄 |

### 4.2 서버 연결 후 체크리스트 [서버 필요]

```powershell
# (1) 서비스 상태
Get-Service *zabbix* | Format-List Name,DisplayName,Status,StartType
# (2) 에이전트 로그 (MSI 기본 로그 경로는 설치 후 conf 의 LogFile 로 확인)
Get-Content "C:\Program Files\Zabbix Agent 2\zabbix_agent2.log" -Tail 50
# (3) PC → 서버 액티브 포트
Test-NetConnection <ZABBIX_SERVER> -Port 10051
# (4) 서버 → PC 패시브 (패시브를 쓸 때만, 서버에서 실행)
zabbix_get -s <PC_IP> -k agent.ping          # → 1
# (5) 서버 쪽: 프론트엔드 호스트 목록의 가용성 아이콘, 또는 API
python infra/zabbix/tools/zabbix_api_probe.py --host <HOST_NAME_IN_ZABBIX>
#     host.get 의 active_available(1=가용) / interfaces[].available(1=가용), item.get 의 state(1=미지원)·error 확인
```

### 4.3 연결 실패 진단표

에이전트 로그 문구는 이번에 실제로 재현해서 얻은 것이다. 서버가 보내는 오류 문장 자체는 모의 수신기로 흉내 낸 부분이 있어 따로 표시했다.

| 증상(에이전트 로그·도구 출력) | 분류 | 확인 | 조치 |
|---|---|---|---|
| `cannot connect to [<서버>:10051]: ... actively refused it.` → `active check configuration update from host [<이름>] started to fail` → `sending of heartbeat message for [<이름>] started to fail` [실측] | 네트워크 / 방화벽 / 서버 미기동 | `Test-NetConnection <서버> -Port 10051`, 서버 프로세스·방화벽 | 서버 주소·포트, 경로상 방화벽 |
| `no active checks on server [<서버>:10051]: host [<이름>] not found` → `active checks on server started to fail` [실측 — 로컬 Zabbix 7.0.31 서버에서 같은 문구 확인: `host [demo-host-01] not found`] | 호스트 이름 / 서버 미등록 | conf의 `Hostname`과 서버 등록명 비교(대소문자) | 서버에 호스트 등록 또는 자동 등록 설정, `Hostname` 수정 |
| 에이전트: `connection from "127.0.0.1" rejected, allowed hosts: "127.0.0.2"` / zabbix_get: `cannot read from socket ... [0x00002745]` [실측] | 에이전트 설정(`Server`) | 서버가 실제로 접속하는 출발지 IP(NAT·프록시 경유 여부) | `Server`에 그 주소 추가 |
| zabbix_get 시간 초과, 에이전트 로그에 접속 기록 없음 (추정) | PC 방화벽 / 경로 | PC의 10050 인바운드 규칙, `ListenIP` | 서버 IP로만 좁힌 규칙 추가 또는 액티브 전용 |
| 프론트엔드에서 항목이 "Not supported", API `item.get` 의 `state=1`, `error` 문자열 [문서] | 키 문법 / OS 미지원 | 6절 표의 실측 결과 | 키 수정(예: `net.if.in`은 GUID 사용) |
| 에이전트 로그 `failed to read request from 127.0.0.1: EOF` [실측] | 정상 | `net.tcp.port[...,10050]`처럼 연결만 하고 끊는 점검이 남긴 흔적 | 조치 불필요 |
| TLS 관련 오류 (추정) | 암호화 설정 불일치 | 양쪽 `TLSConnect/TLSAccept`, PSK identity | 서버 호스트 설정과 맞춤 |

---

## 5. 실제 수집 가능한 모니터링 항목

### 5.1 범주별 요약 (이 PC, Agent 2 7.0.31)

| 범주 | 실측 성공 | 이 PC에서 안 되는 것 | 핵심 메모 |
|---|---|---|---|
| CPU | 사용률(전체·코어별), 사용자/커널/인터럽트/DPC 시간, 큐 길이, 컨텍스트 스위치, 코어 수 | `system.cpu.util[,user]`(Windows는 type=system만) | `system.cpu.load`는 Windows에서 큐 길이 기반이라 Linux load와 의미가 다르다 |
| 메모리 | 전체·사용·가용(바이트·%), 커밋(가상 메모리), 페이지 파일 사용률, 페이지/초, 풀 메모리 | `vm.memory.util`은 에이전트 키가 아님(템플릿의 계산 항목) | `system.swap.size[,free]`=0으로 **틀리게** 나옴 [주의] |
| 디스크 | 드라이브별 전체·사용·여유(바이트·%), 물리 디스크 읽기/쓰기 횟수·바이트·지연·큐·바쁨 | `vfs.fs.inode`, `vfs.dev.*` | 플랫폼 IT 팩 기본 지표 중 **Inode와 IO Wait는 Windows에 없다** → 디스크 지연·큐로 대체 |
| 네트워크 | 인터페이스 목록, 송수신 바이트·오류·드롭, 링크 상태·속도(WMI), TCP 포트·리슨·소켓 수, DNS | `net.if.in["이더넷"]`(한글 연결 이름) | GUID나 장치 설명 이름으로 지정 |
| 시스템 | 호스트 이름, OS 정보(JSON 포함), 아키텍처, 가동 시간, 시스템 시간, 로그인 사용자 수, 레지스트리 | `system.boottime` | 부팅 시각은 WMI `LastBootUpTime` |
| 서비스 | 서비스 탐색(271개), 상태·시작 유형·표시 이름, 멈춘 자동 시작 서비스 목록 | — | 서비스 **설명(description)의 한글이 깨짐** [주의] |
| 프로세스 | 전체·이름별 개수, 이름별 메모리·I/O·CPU 시간, 프로세스 요약 JSON, 프로세스별 CPU(WMI) | `proc.cpu.util`, `proc.mem` | 프로세스별 CPU%는 기본 템플릿에 없다 → 추가 수집 필요 |
| 이벤트 로그 | `eventlog[]`, `eventlog.count[]` (액티브) | 패시브 모드 | 기본 템플릿에 없다 → 별도 Item 필요 |

### 5.2 문서와 실측이 다른 점 [주의]

| 항목 | 문서 | 실측 | 영향 |
|---|---|---|---|
| `system.cpu.util[,,avg5]` | avg5/avg15는 Linux 등만 지원 | Windows에서 값이 나옴(11.498) | 문서와 달라 의존하지 않는다. 5분 평균은 서버 트리거 함수(`avg(...,5m)`)로 계산 |
| `system.swap.size[,free]` | 스왑 여유 바이트 | **0** (실제 페이지 파일 여유 약 2.9 GB) → `pfree`=0, `pused`=100 | 사용 금지. 템플릿처럼 `perf_counter_en["\Paging file(_Total)\% Usage"]` 사용 |
| `proc.get` `cputime_user` / `cputime_system` | 밀리초 | **초** (Get-Process 값과 소수점까지 일치: 3988.875 s) | CPU% 계산 시 단위 주의. `proc_info[...,utime]`은 문서대로 밀리초(3,988,865) |
| `proc.get` `vmsize` | virtual memory size | Windows **Private bytes(KB)** 와 정확히 일치 | 메모리 누수 판단에 쓰기 좋음 |
| `service.discovery` / `service.info[...,description]` | — | 한글 설명이 에이전트에서 이미 `�`로 깨진 채 전송됨(전송 바이트는 올바른 UTF-8) | 설명 대신 서비스 이름·표시 이름 사용 |
| 성능 카운터 첫 질의 | — | 새 `perf_counter_en` 키의 첫 응답은 빈 응답, 이후 정상 | 새 Item은 첫 1~2회 값이 없을 수 있음 |
| Application 로그 | — | 성능 카운터를 처음 조회할 때 `PerfNet 2004` 오류가 Application 로그에 기록됨(이번 검증 중 실제 발생) | AI가 이 이벤트를 장애 원인으로 오인하지 않게 잡음 목록에 넣는다 |

### 5.3 교차 검증: 같은 시점 Windows 값과 비교 [교차일치]

| Item key | 에이전트 값 | Windows 값 (출처) | 차이 |
|---|---|---|---|
| `vm.memory.size[total]` | 17,111,175,168 | 17,111,175,168 (Win32_ComputerSystem.TotalPhysicalMemory) | 0% |
| `vm.memory.size[available]` | 7,631,065,088 | 7,678,648,320 (FreePhysicalMemory×1024) | -0.62% (측정 순간 차이) |
| `vfs.fs.size[C:,total]` | 119,325,487,104 | 119,325,487,104 (Win32_LogicalDisk.Size) | 0% |
| `vfs.fs.size[C:,free]` | 9,713,381,376 | 9,713,381,376 (Win32_LogicalDisk.FreeSpace) | 0% |
| `system.uptime` | 265,797 | 265,797 (현재 − LastBootUpTime) | 0% |
| `system.cpu.num` | 12 | 12 (NumberOfLogicalProcessors) | 0% |
| `proc.num[]` | 210 | 209 (Get-Process) | +1 (질의 순간 차이) |
| `service.info[EventLog]` | 0(실행 중) | Running | 일치 |
| `system.swap.size[,total]` | 3,087,007,744 | 3,087,007,744 (Win32_PageFileUsage.AllocatedBaseSize) | 0% |
| `system.swap.size[,free]` | **0** | 2,905,604,096 | **-100%** [주의] |
| `perf_counter_en["\Paging file(_Total)\% Usage"]` | 5.887 | 5.88 (CurrentUsage/AllocatedBaseSize) | 0.1% |
| `net.if.in["{GUID}"]` / `net.if.out["{GUID}"]` | 8,094,710,456 / 888,728,855 | 8,094,707,066 / 888,727,182 (Get-NetAdapterStatistics) | 0.000% |
| `services[automatic,stopped]` | 6개 | 같은 6개 (Win32_Service) | 일치 |
| `proc.get[chrome.exe,,,summary]` | wkset 3,879,300 / vmsize 3,476,448 / cputime_user 3988.875 | WorkingSet64 합/1024, PrivateMemorySize64 합/1024, UserProcessorTime 합(초) | 일치 |

계산으로 본 일관성: `used`(9,190,973,440) + `available`(7,919,960,064) ≈ `total`(차이 0.0014%), `vm.vmemory.size[total]`(20,198,182,912) = 물리 메모리 + 페이지 파일, `vm.vmemory.size[pused]`(62.967) ≈ `\Memory\% Committed Bytes In Use`(62.966).

---

## 6. Item key 및 데이터 타입 목록

- 타입: Zabbix `value_type` — 0 float, 1 character, 2 log, 3 unsigned, 4 text. 템플릿 항목은 템플릿이 정한 타입을 따르며, 서버 연결 후 `item.get`의 `value_type`·`units`로 최종 확인한다.
- 기본 템플릿: 공식 `Windows by Zabbix agent` / `Windows by Zabbix agent active`(7.0) README 기준. 두 템플릿의 수집 항목은 같고 수집 방식(패시브/액티브)만 다르다.
- 실측 값은 2026-10-14 16:41~16:45 이 PC에서 받은 값이다. 전체 결과는 `docs/zabbix/verification/passive-items.md`.

### 6.1 가용성·시스템

| 데이터 | Item key | 타입·단위 | 의미 | Windows | 기본 템플릿 | 별도 설정 | 장애 분석 활용 | 검증 |
|---|---|---|---|---|---|---|---|---|
| 에이전트 응답 | `agent.ping` | 3, 항상 1 | 살아 있으면 1 | 지원 | 예 | — | `nodata(agent.ping,30m)`로 단절 감지(액티브 템플릿) | [실측] 1 |
| 액티브 가용성 | `zabbix[host,active_agent,available]` | 3, 0/1/2 | 하트비트 기반 서버 내부 항목 | 서버 측 | 예(액티브) | — | 에이전트·네트워크 단절 | [서버 필요] |
| 패시브 가용성 | `zabbix[host,agent,available]` | 3, 0/1/2 | 서버 폴링 결과 | 서버 측 | 예(패시브) | — | 위와 같음 | [서버 필요] |
| 에이전트 버전 | `agent.version` | 1 | | 지원 | 예 | — | 버전 불일치 확인 | [실측] 7.0.31 |
| 호스트 이름 | `system.hostname` | 1 | 기본 NetBIOS 이름 | 지원 | 예 | — | 호스트 식별, 이름 변경 감지 | [실측] demo-host-01 |
| OS 설명 | `system.uname` | 1 | OS·버전·아키텍처 | 지원 | 예 | — | 보고서 기본 정보 | [실측] `Windows demo-host-01 10.0.19045 Microsoft Windows 10 Pro x64` |
| OS 정보 | `system.sw.os` / `system.sw.os.get` | 1 / 4(JSON) | 버전·빌드·에디션 | 지원 | `sw.os`만 | `os.get`은 추가 | OS 업데이트 전후 비교 | [실측] build 19045.6466, 22H2 |
| 아키텍처 | `system.sw.arch` | 1 | | 지원 | 예 | — | | [실측] x64 |
| 가동 시간 | `system.uptime` | 3, 초 | 부팅 후 경과 | 지원 | 예(10분 미만이면 재시작 트리거) | — | 재부팅 감지·시점 계산 | [교차일치] |
| 부팅 시각 | `system.boottime` | — | | **미지원** | — | 대신 `wmi.get[root\cimv2,"select LastBootUpTime from Win32_OperatingSystem"]` | 재부팅 시각 | [실측·미지원] / WMI [실측] `20261011145408.503145+540` |
| 시스템 시간 | `system.localtime` | 3, Unix 초 | | 지원 | 예(`fuzzytime` 시간 동기 트리거) | — | 시간 어긋남 감지 | [실측] |
| 레지스트리 값 | `registry.data[key,name]` | 1/3/4 | | Windows 전용 | 아니요 | 추가 | 설정 확인용 | [실측] DisplayVersion=22H2 |

### 6.2 CPU

| 데이터 | Item key | 타입·단위 | 의미 | Windows | 기본 템플릿 | 별도 설정 | 장애 분석 활용 | 검증 |
|---|---|---|---|---|---|---|---|---|
| CPU 사용률 | `system.cpu.util` | 0, % | `Processor Time` 기반 1분 평균 | 지원(type=system만) | 예(5분 최소 >90% 경고) | — | CPU 과부하 감지의 1차 지표 | [실측] 10.95 |
| 코어별 사용률 | `system.cpu.util[N]` | 0, % | | 지원 | 아니요 | 추가 | 단일 스레드 병목(한 코어만 100%) | [실측] 코어0 24.27 |
| 유형별 사용률 | `system.cpu.util[,user]` | — | | **미지원**("Invalid second parameter.") | — | 아래 성능 카운터 사용 | | [실측·미지원] |
| 사용자/커널 시간 | `perf_counter_en["\Processor Information(_total)\% User Time"]`, `...% Privileged Time` | 0, % | 앱 코드 vs 커널 | 지원 | 예(커널 >30% 경고) | — | 앱 문제인지 드라이버·OS 문제인지 구분 | [실측] 1.43 / 2.74 |
| 인터럽트/DPC | `...% Interrupt Time`, `...% DPC Time` | 0, % | 하드웨어 인터럽트 처리 | 지원 | 예(인터럽트 >50%) | — | 높으면 하드웨어·드라이버 의심(템플릿 설명) | [실측] 0.52 / 0 |
| 큐 길이 | `perf_counter_en["\System\Processor Queue Length"]` | 0, 개 | CPU 대기 스레드 | 지원 | 예(5분 최소 − 코어×2 > 3) | — | 사용률보다 "밀림"을 직접 보여 줌 | [실측] 0 |
| CPU 부하 | `system.cpu.load[all,avg1]` | 0 | Windows는 큐 길이 기반 | 지원 | 아니요 | — | Linux load와 의미가 달라 비교 금지 | [실측] 0 |
| 컨텍스트 스위치 | `perf_counter_en["\System\Context Switches/sec"]` | 0, 회/초 | | 지원 | 예 | — | 과도한 스레드 전환 | [실측] 12,276 |
| 작업 관리자 기준 | `perf_counter_en["\Processor Information(_total)\% Processor Utility"]` | 0, % | Windows 8 이후 작업 관리자가 쓰는 값(문서) | 지원 | 아니요 | 추가 | 사용자가 보는 숫자와 맞출 때 | [실측] 5.84(같은 순간 Processor Time 2.99) |
| 논리 CPU 수 | `system.cpu.num` / `wmi.get[root/cimv2,"Select NumberOfLogicalProcessors from Win32_ComputerSystem"]` | 3 | | 지원 | WMI 쪽이 템플릿 | — | 큐 길이 기준 계산 | [교차일치] 12 |

### 6.3 메모리

| 데이터 | Item key | 타입·단위 | 의미 | Windows | 기본 템플릿 | 별도 설정 | 장애 분석 활용 | 검증 |
|---|---|---|---|---|---|---|---|---|
| 전체 | `vm.memory.size[total]` | 3, B | 물리 메모리 | 지원 | 예 | — | 사용률 분모 | [교차일치] |
| 사용 | `vm.memory.size[used]` | 3, B | 전체 − 가용 | 지원 | 예 | — | | [실측] |
| 가용 | `vm.memory.size[available]` | 3, B | | 지원 | 아니요 | 추가 | 메모리 부족 | [교차일치] |
| 사용률 | `vm.memory.size[pused]` | 0, % | | 지원 | 템플릿은 계산 항목 `vm.memory.util` (5분 최소 >90% 평균 심각도) | — | 1차 지표 | [실측] 53.72 |
| 템플릿 사용률 | `vm.memory.util` | 0, % | 서버 계산 항목 | 서버 계산 | 예 | — | | 에이전트 키 아님 [실측: Unknown metric] |
| 커밋(가상 메모리) | `vm.vmemory.size[pused]` 등 | 0 % / 3 B | 물리+페이지 파일 대비 커밋 | Windows 전용 | 아니요 | 추가 | 커밋 한도 근접 = 앱 메모리 할당 실패 위험 | [실측] 62.97 (성능 카운터와 일치) |
| 페이지 파일 사용률 | `perf_counter_en["\Paging file(_Total)\% Usage"]` | 0, % | | 지원 | 예(여유 <20% 경고) | — | 스왑 압박 | [교차일치] 5.89 |
| 페이지 파일 크기 | `system.swap.size[,total]` | 3, B | | 지원 | 예 | — | | [교차일치] |
| 페이지 파일 여유 | `system.swap.size[,free]` | — | | 값이 0으로 틀림 | — | **사용 금지** | | [주의] |
| 하드 페이지 폴트 | `perf_counter_en["\Memory\Pages/sec"]` | 0, 회/초 | | 지원 | 예(>1000 경고) | — | 메모리 부족으로 디스크 페이징 | [실측] 0 |
| 페이지 폴트 | `...\Memory\Page Faults/sec` | 0 | 소프트+하드 | 지원 | 예 | — | | [실측] 34,261 |
| 페이지 테이블 항목 | `...\Memory\Free System Page Table Entries` | 0 | | 지원 | 예(<5000 경고) | — | 누수 징후 | [실측] |
| 비페이징 풀 | `...\Memory\Pool Nonpaged Bytes` | 0, B | | 지원 | 예 | — | 드라이버 누수 징후 | [실측] 503,599,104 |
| 캐시 | `...\Memory\Cache Bytes` | 0, B | | 지원 | 예 | — | | [실측] |

### 6.4 디스크

| 데이터 | Item key | 타입·단위 | 의미 | Windows | 기본 템플릿 | 별도 설정 | 장애 분석 활용 | 검증 |
|---|---|---|---|---|---|---|---|---|
| 파일시스템 전체 정보 | `vfs.fs.get` | 4, JSON | 드라이브별 total/free/used/pfree/pused | 지원 | 예(마스터 항목) | — | 한 번에 모든 드라이브 | [실측] `C:` NTFS fixed, pused 91.86 |
| 드라이브 사용률 | `vfs.fs.dependent.size[{#FSNAME},pused]` | 0, % | 위 JSON에서 꺼낸 종속 항목 | 지원 | 예(>80% 경고, >90% 평균, 5분 최소) | — | 디스크 부족 1차 지표 | 템플릿 [서버 필요] / 같은 값 `vfs.fs.size[C:,pused]` [실측] 91.86 |
| 드라이브 용량 | `vfs.fs.size[C:,total\|used\|free\|pfree]` | 3 B / 0 % | | 지원 | 템플릿은 종속 항목 사용 | — | 증가 속도 → 가득 찰 시각 추정 | [교차일치] |
| 드라이브 탐색 | `vfs.fs.discovery` | JSON | `{#FSNAME}`, `{#FSTYPE}`, `{#FSDRIVETYPE}` | 지원 | 템플릿은 종속 탐색 | — | | [실측] |
| inode | `vfs.fs.inode[...]` | — | | **미지원** | — | — | IT 팩 "Inode" 지표는 Windows에 없음 | [실측·미지원] |
| 물리 디스크 탐색 | `perf_instance_en.discovery[PhysicalDisk]` | JSON | 인스턴스 `0 C:`, `_Total` | 지원 | 예(`_Total` 제외) | — | | [실측] |
| 읽기/쓰기 횟수 | `perf_counter_en["\PhysicalDisk(0 C:)\Disk Reads/sec",60]`, `Disk Writes/sec` | 0, 회/초 | 60초 평균 | 지원 | 예 | — | I/O 폭증 | [실측] 0.37 / 14.25 |
| 처리량 | `...Disk Read Bytes/sec`, `Disk Write Bytes/sec` | 0, B/초 | | 지원 | 아니요 | 추가 | 대량 쓰기(로그 폭증) | [실측] 9,562 / 195,959 |
| 디스크 바쁨 | `...% Idle Time` → 템플릿이 `100 − 값` | 0, % | | 지원 | 예(15분 최소 >95%) | — | 디스크 포화 | [실측] idle 99.42 |
| 응답 시간 | `...Avg. Disk sec/Read`, `Avg. Disk sec/Write` | 0, 초 | | 지원 | 예(15분 최소 >0.02초) | — | Linux IO Wait 대체 지표 | [실측] 0.000122 / 0.000201 |
| 큐 | `...Current Disk Queue Length`, `Avg. Disk Read/Write Queue Length` | 0 | | 지원 | 예 | — | 포화 | [실측] |
| 디스크 상태 | `wmi.getall[root\cimv2,"select Index,Model,Status,Size from Win32_DiskDrive"]` | 4, JSON | Status `OK` 등 | 지원 | 아니요 | 추가 | 하드웨어 이상 | [실측] Status OK |
| 블록 장치 I/O | `vfs.dev.read`, `vfs.dev.write`, `vfs.dev.discovery` | — | Linux 계열 키 | **미지원** | — | 위 성능 카운터 사용 | | [실측·미지원] |

### 6.5 네트워크

| 데이터 | Item key | 타입·단위 | 의미 | Windows | 기본 템플릿 | 별도 설정 | 장애 분석 활용 | 검증 |
|---|---|---|---|---|---|---|---|---|
| 물리 어댑터 정보 | `wmi.getall[root\cimv2,"select Name,Description,NetConnectionID,Speed,AdapterTypeId,NetConnectionStatus,GUID from win32_networkadapter where PhysicalAdapter=True and NetConnectionStatus>0"]` | 4, JSON | 속도·연결 상태·GUID | 지원 | 예(인터페이스 탐색·속도·상태의 원천) | — | 링크 다운, 속도 저하 | [실측] 어댑터 1개 |
| 인터페이스 목록 | `net.if.discovery` | JSON | `{#IFNAME}`, `{#IFGUID}` | 지원 | 템플릿은 WMI 결과로 대체 | 필터 필요 | WFP·QoS 필터 드라이버까지 9개가 나옴 | [실측] |
| 수신/송신 | `net.if.in["{#IFGUID}"]`, `net.if.out["{#IFGUID}"]` | 3, 누적 바이트 → 템플릿 전처리 "초당 변화 ×8" = bps | | 지원 | 예(15분 평균 > 속도의 90%) | — | 대역폭 포화 | [교차일치] |
| 오류/드롭 | `net.if.in["{#IFGUID}",errors]`, `...,dropped]`, out 동일 | 3, 누적 → 초당 변화 | | 지원 | 예(오류율 >2) | — | 케이블·드라이버 문제 | [실측] 오류 0, 수신 드롭 1,128 |
| 링크 상태 | `net.if.status["{#IFGUID}"]` (WMI 종속) | 3 | 2 = 연결됨 | 지원 | 예(Link down) | — | 네트워크 단절 | [서버 필요](원천 WMI는 [실측]) |
| 인터페이스 지정 방식 | `net.if.in["<장치 설명 이름>"]` / `net.if.in["이더넷"]` | | | 설명 이름 성공 / **한글 연결 이름 실패** | — | GUID 권장 | | [실측] |
| TCP 연결 | `net.tcp.port[<host>,<port>]` | 3, 1/0 | 연결 가능 여부 | 지원 | 아니요 | 추가 | 의존 서비스(DB 등) 도달성 | [실측] |
| 리슨 | `net.tcp.listen[<port>]` | 3, 1/0 | | 지원 | 아니요 | 추가 | 서비스 포트가 열렸는지 | [실측] |
| 소켓 수 | `net.tcp.socket.count[...]` | 3 | Windows는 Agent 2 64비트만 | 지원 | 아니요 | 추가 | 연결 폭증 | [실측] |
| DNS | `net.dns[,<name>,A,2,1]` | 3, 1/0 | | 지원 | 아니요 | 추가 | 이름 해석 장애 구분 | [실측] |

### 6.6 Windows 서비스·프로세스

| 데이터 | Item key | 타입·단위 | 의미 | Windows | 기본 템플릿 | 별도 설정 | 장애 분석 활용 | 검증 |
|---|---|---|---|---|---|---|---|---|
| 서비스 탐색 | `service.discovery` | JSON | 이름·표시 이름·상태·경로·계정·시작 유형 | Windows 전용 | 예(자동/지연 자동만 필터) | — | 감시 대상 자동 생성 | [실측] 271개, 설명 한글 깨짐 [주의] |
| 서비스 상태 | `service.info["{#SERVICE.NAME}",state]` | 3 | 0 실행, 1 일시 중지, 2 시작 중, 3 일시 중지 중, 4 계속 중, 5 중지 중, 6 중지, 7 알 수 없음, 255 없음 | Windows 전용 | 예(3회 연속 ≠0이면 평균) | — | 서비스 중지 감지 | [실측] EventLog 0, 없는 서비스 255 |
| 시작 유형 | `service.info[<name>,startup]` | 3 | 0 자동, 1 지연 자동, 2 수동, 3 사용 안 함 … | Windows 전용 | 아니요 | 추가 | "원래 자동인데 멈춤" 판단 | [실측] |
| 멈춘 자동 서비스 | `services[automatic,stopped]` | 4, 줄 목록(없으면 0) | | Windows 전용 | 아니요 | 추가 | 한 번에 전체 점검 | [교차일치] 6개 |
| 프로세스 수 | `proc.num[]`, `proc.num[<name>]` | 3 | Windows는 name·user 파라미터만 | 지원 | `proc.num[]`만 | — | 프로세스 폭증·특정 앱 미실행 | [교차일치] |
| 스레드 수 | `perf_counter_en["\System\Threads"]` | 0 | | 지원 | 예 | — | | [실측] 2,882 |
| 프로세스 요약 | `proc.get[,,,summary]` | 4, JSON | 이름별 개수·`wkset`(KB)·`vmsize`(Private KB)·`cputime_user/system`(초)·스레드·핸들·I/O | 지원(cmdline 미지원) | 아니요 | **추가 권장** | 두 시점 차분으로 프로세스별 CPU%·메모리 증가 계산 | [교차일치] 38개 이름 |
| 특정 프로세스 상세 | `proc_info[<name>,wkset\|utime\|io_read_b…,sum]` | 0 | wkset KB, utime ms | Windows 전용 | 아니요 | 추가 | 의심 프로세스 추적 | [실측] |
| 프로세스별 CPU 스냅샷 | `wmi.getall[root\cimv2,"select Name,IDProcess,PercentProcessorTime,WorkingSetPrivate from Win32_PerfFormattedData_PerfProc_Process where Name<>'_Total' and Name<>'Idle' and PercentProcessorTime>0"]` | 4, JSON | 그 순간 CPU를 쓰는 프로세스 | 지원 | 아니요 | 추가(조회 351 ms) | CPU 장애 때 "누가 쓰는가" | [실측] |
| 프로세스 CPU 카운터 | `perf_counter_en["\Process(<name>)\% Processor Time",60]` | 0, % | 같은 이름 여러 개면 `name#1`… 인스턴스 | 지원 | 아니요 | 추가 | 특정 앱 감시 | [실측] |
| 프로세스 CPU/메모리(Linux 키) | `proc.cpu.util`, `proc.mem` | — | | **미지원** | — | 위 방법 사용 | | [실측·미지원] |

### 6.7 이벤트 로그 (액티브 전용)

| 데이터 | Item key | 타입·단위 | 의미 | Windows | 기본 템플릿 | 별도 설정 | 장애 분석 활용 | 검증 |
|---|---|---|---|---|---|---|---|---|
| System 로그 | `eventlog[System,,"Warning\|Error\|Critical"]` | 2(log) | 메시지 + source, eventid, severity, 원본 시각 | Windows 전용, **액티브만** | **아니요** | **추가 필요** (Zabbix agent (active) 유형, 정보 유형 Log) | 서비스 비정상 종료·재부팅·디스크 오류 근거 | [실측] 74/74건 원본과 일치 |
| Application 로그 | `eventlog[Application,,"Error\|Critical"]` | 2 | | 위와 같음 | 아니요 | 추가 필요 | 앱 크래시 근거 | [실측] |
| 건수 | `eventlog.count[System,,"Warning\|Error\|Critical"]` | 3 | 주기당 새 줄 수 | 위와 같음 | 아니요 | 추가 | 오류 급증 감지(트리거로 쓰기 쉬움) | [실측] 첫 주기 74, 이후 0 |

- 심각도 숫자 [실측]: Windows 경고(Level 3) → `severity` 2, 오류(Level 2) → 4. 이벤트 ID·소스는 74건 모두 원본과 같음.
- `mode`를 `skip`으로 두면 새 Item이 과거 로그를 모두 보내지 않는다 [문서]. 이번 검증은 읽기 시작 위치(`lastlogsize` = 레코드 번호)를 최근 300개 앞으로 지정했다.
- 조건에 맞지 않는 레코드는 값 없이 읽기 위치만 갱신하는 데이터가 온다 [실측] — 수집 건수 계산 시 제외.
- 메시지 본문에 **사용자 계정명과 SID가 그대로** 들어 있다 [실측] → 9절 마스킹.
- 잡음 [실측]: 3.2일치 System 경고·오류 74건 중 68건(92%)이 `DistributedCOM 10016`, Application 오류 6건 중 5건이 `PerfNet 2004`(성능 카운터 조회 부작용). 분석 전에 잡음 목록으로 거른다.

---

## 7. Zabbix API 메서드와 요청 예시

> 이 절은 **[문서]** 7.0 공식 문서와 7.0 소스(`ui/include/classes/api/services/*.php`) 기준이다. 실서버 응답은 아직 없다. 요청 본문은 `infra/zabbix/tools/zabbix_api_probe.py --dry-run`이 만든 것과 같다(`docs/zabbix/api-requests/`).

### 7.1 공통 규칙

| 항목 | 내용 |
|---|---|
| 엔드포인트 | `POST https://<프론트엔드 주소>/api_jsonrpc.php` (프론트엔드가 `/zabbix` 아래면 `/zabbix/api_jsonrpc.php`) |
| 헤더 | `Content-Type: application/json-rpc`(또는 `application/json`), `Authorization: Bearer <토큰>` |
| 요청 | `{"jsonrpc":"2.0","method":"<메서드>","params":{...},"id":1}` — `id`가 없으면 알림으로 처리돼 응답이 없다 |
| 성공 응답 | `{"jsonrpc":"2.0","result":...,"id":1}` |
| 오류 응답 | `{"jsonrpc":"2.0","error":{"code":-32602,"message":"Invalid params.","data":"<자세한 이유>"},"id":1}` |
| 버전 확인 | `apiinfo.version` — **인증 없이** 호출해야 한다. API 버전 = Zabbix 버전 |
| 권한 | 7개 get 메서드는 모든 사용자 유형이 호출 가능하고, 사용자 역할에서 메서드 단위로 막을 수 있다. 결과는 그 사용자의 사용자 그룹이 읽기 권한을 가진 호스트 그룹 범위로 제한된다 |
| 공통 파라미터 | `output`(필드 목록 또는 `"extend"`), `filter`(정확히 일치), `search`(부분 일치), `limit`, `sortfield`, `sortorder`, `countOutput`, `preservekeys` |
| 값 형식 | 숫자·ID·시각이 모두 문자열. `clock`은 Unix 초(UTC), `ns`는 나노초 |
| 성능 | 필요한 필드만 `output`에 적는다(문서 권고). 시간 범위와 `limit`을 항상 준다 |

버전별 차이 (서버 버전 확인 후 적용):

| 변경 | 7.0 | 7.2 | 7.4 |
|---|---|---|---|
| 요청 본문 `auth` 속성 | 폐기 예정(동작) | **삭제** | 없음 |
| `Authorization: Bearer` 헤더 | 지원(7.0.7+ CORS, 7.0.11+ 헤더 대소문자 무관) | 지원 | 지원 |
| `host.get`/`trigger.get`의 `selectGroups` | 폐기 예정 → `selectHostGroups` | **삭제** | 없음 |
| `event.get`의 `select_acknowledges`, `select_alerts` | 폐기 예정 → `selectAcknowledges`, `selectAlerts` | **삭제** | 없음 |
| `item.get`의 `selectItemDiscovery`, `trigger.get`의 `selectTriggerDiscovery`, `host.get`의 `selectHostDiscovery`·`selectDiscoveries` | 사용 | 사용 | 폐기 예정 → `selectDiscoveryData`, `selectDiscoveryRules` |

→ 플랫폼 코드는 처음부터 Bearer 헤더, `selectHostGroups`, `selectAcknowledges`만 쓰면 7.0~7.4 모두 동작한다.

### 7.2 host.get — 어떤 PC를 감시하는가

- **용도**: 호스트 목록, 상태, 인터페이스 가용성, 호스트 그룹, 연결된 템플릿, 태그
- **권한**: 읽기 권한이 있는 호스트 그룹의 호스트만 반환
- **주요 파라미터**: `hostids`, `groupids`, `filter`(예: `{"host": ["<이름>"]}`), `search`, `templateids`, `monitored_hosts`, `selectInterfaces`, `selectHostGroups`, `selectParentTemplates`, `selectTags`, `selectInventory`, `selectItems`, `selectTriggers`, `limitSelects`, `sortfield`, `limit`
- **요청**:

```json
{"jsonrpc":"2.0","method":"host.get","id":2,"params":{
  "output":["hostid","host","name","status","active_available","maintenance_status"],
  "selectInterfaces":["interfaceid","type","main","useip","ip","dns","port","available","error"],
  "selectHostGroups":["groupid","name"],
  "selectParentTemplates":["templateid","name"],
  "selectTags":["tag","value"],
  "filter":{"host":["<HOST_NAME_IN_ZABBIX>"]},
  "sortfield":"host","limit":50}}
```

- **응답 구조** [문서]:

```json
{"jsonrpc":"2.0","id":2,"result":[{
  "hostid":"10084","host":"<기술 이름>","name":"<표시 이름>","status":"0",
  "active_available":"1","maintenance_status":"0",
  "interfaces":[{"interfaceid":"1","type":"1","main":"1","useip":"1","ip":"<ip>","dns":"","port":"10050","available":"1","error":""}],
  "hostgroups":[{"groupid":"2","name":"<그룹>"}],
  "parentTemplates":[{"templateid":"10081","name":"Windows by Zabbix agent active"}],
  "tags":[{"tag":"owner","value":"<담당>"}]}]}
```

- **조회 데이터**: `status` 0 감시 중 / 1 해제, `active_available`(7.0 호스트 속성) 0 알 수 없음 / 1 가용 / 2 불가, `interfaces[].available` 0/1/2와 `error`(패시브), `maintenance_status`
- **주의**: 인터페이스 `ip`는 민감 정보로 다룬다. 7.4부터 일부 select 파라미터 이름이 바뀐다(7.1 표).

### 7.3 item.get — 어떤 지표를 수집하는가

- **용도**: 호스트의 Item 목록, key, 타입, 단위, 보관 기간, 최근 값, 미지원 여부. `history.get` 호출 전 **`itemid`와 `value_type`을 얻는 단계**
- **주요 파라미터**: `hostids`, `itemids`, `triggerids`, `host`, `search`(예: `{"key_":"system.cpu"}`), `filter`(예: `{"key_":["system.cpu.util"]}`, `{"state":1}`), `monitored`, `with_triggers`, `selectHosts`, `selectTriggers`, `selectTags`, `selectPreprocessing`, `selectValueMap`, `sortfield`(itemid, name, key_, delay, history, trends, type, status)
- **요청**:

```json
{"jsonrpc":"2.0","method":"item.get","id":3,"params":{
  "output":["itemid","key_","name","type","value_type","units","delay","history","trends","status","state","error","lastclock","lastvalue"],
  "hostids":"<hostid>","sortfield":"key_"}}
```

- **응답 구조** [문서 예시 발췌]:

```json
{"itemid":"42269","type":"18","hostid":"10084","name":"CPU utilization","key_":"system.cpu.util",
 "delay":"0","history":"7d","trends":"365d","status":"0","value_type":"0","units":"%",
 "master_itemid":"42264","state":"0","error":"","lastclock":"0","lastns":"0","lastvalue":"0","prevvalue":"0"}
```

- **필드 의미**: `type` 0 Zabbix agent, 7 Zabbix agent (active), 15 계산, 18 종속 항목 … / `value_type` 0 float, 1 character, 2 log, 3 unsigned, 4 text, 5 binary / `status` 0 사용, 1 사용 안 함 / `state` 0 정상, **1 미지원**(`error`에 이유) / `history` 기본 31d, `trends` 기본 365d(숫자형만) / `flags` 0 일반, 4 탐색으로 생성
- **주의**: `lastvalue`·`lastclock`·`prevvalue`는 기본적으로 **최근 24시간 안의 값만** 보여 준다(관리 > 일반 > Max history display period). 템플릿이 탐색(LLD)으로 만든 Item(디스크·인터페이스·서비스)은 key에 실제 이름이 들어가므로 `search`로 찾는다(예: `vfs.fs.dependent.size[C:,pused]`).

### 7.4 history.get — 장애 전후의 원시 값

- **용도**: 수집된 값 하나하나(시계열). 장애 시각 ±N분의 CPU·메모리·디스크 변화, 이벤트 로그 본문
- **주요 파라미터** [문서·소스 확인]:

| 파라미터 | 타입 | 설명 |
|---|---|---|
| `history` | 정수 **하나** | 0 float, 1 character, 2 log, 3 unsigned(**기본값**), 4 text, 5 binary |
| `itemids` / `hostids` | ID/배열 | |
| `time_from` / `time_till` | Unix 초 | 이상/이하 |
| `sortfield` | `itemid`, `clock`, `ns` | |
| `sortorder`, `limit`, `output`, `countOutput`, `filter`, `search` | | log 타입은 `source`·`severity`·`logeventid` 필터 가능(소스 확인) |

- **요청** (float Item, 장애 1시간 전 ~ 15분 후):

```json
{"jsonrpc":"2.0","method":"history.get","id":4,"params":{
  "output":"extend","history":0,"itemids":["<cpu itemid>","<fs pused itemid>"],
  "time_from":<장애시각-3600>,"time_till":<장애시각+900>,
  "sortfield":"clock","sortorder":"ASC","limit":5000}}
```

- **응답 구조** [문서]:

```json
{"jsonrpc":"2.0","id":4,"result":[{"itemid":"23296","clock":"1351090996","value":"0.085","ns":"563157632"}]}
```

| value_type | 응답 필드 |
|---|---|
| 0 float / 3 unsigned / 1 character | `itemid`, `clock`, `ns`, `value` |
| 4 text | `id`, `itemid`, `clock`, `ns`, `value` |
| 2 log (이벤트 로그) | `id`, `itemid`, `clock`, `ns`, `value`(메시지), `source`, `severity`, `logeventid`(이벤트 ID), `timestamp`(원본 이벤트 시각) |

- **주의**
  - **value_type이 다른 Item을 한 번에 조회할 수 없다.** 타입별로 나눠 호출한다. 타입이 틀리면 오류 없이 빈 결과다(기본값 3이라 float Item을 `history` 없이 부르면 빈 배열).
  - 보관 기간(`item.history`, 기본 31d, 템플릿은 보통 더 짧게)이 지나면 하우스키퍼가 지운다. 보관 0이면 저장되지 않는다.
  - 값은 서버 전처리 **후** 값이다(예: 네트워크는 누적 바이트가 아니라 bps).
  - `limit` 없이 긴 기간을 부르면 응답이 커진다. 장애 분석은 ±1시간 정도로 자른다.

### 7.5 trend.get — 장기 추세(시간 단위 집계)

- **용도**: 1시간 단위 `min/avg/max/num`. "평소(지난 7일 같은 시간대)와 비교", 디스크 증가 추세
- **주요 파라미터** [문서]: `itemids`, `time_from`, `time_till`, `limit`, `output`, `countOutput` — **`sortfield`·`sortorder` 없음**
- **요청**:

```json
{"jsonrpc":"2.0","method":"trend.get","id":7,"params":{
  "output":["itemid","clock","num","value_min","value_avg","value_max"],
  "itemids":["<cpu itemid>","<mem itemid>"],"time_from":<now-604800>,"time_till":<now>,"limit":5000}}
```

- **응답 구조** [문서]: `{"itemid":"23715","clock":"1446199200","num":"60","value_min":"0.165","value_avg":"0.2168","value_max":"0.35"}` — `clock`은 그 시간의 시작(예: 04:00:00 = 04:00:00~04:59:59)
- **history와의 차이**

| | history.get | trend.get |
|---|---|---|
| 단위 | 수집된 값 하나하나 | 1시간 집계(min/avg/max/개수) |
| 대상 타입 | 0~5 모두, 한 번에 한 타입 | 숫자형(0, 3)만. 소스상 float·unsigned를 섞어 요청해도 내부에서 나눠 조회, 문자·로그 Item은 무시 |
| 보관 | 짧게(기본 31d) | 길게(기본 365d) |
| 지연 | 수집 즉시 | 서버가 시간이 바뀔 때 기록 → **최대 2시간** 뒤에 보임 |
| 정밀도 | 원값 | unsigned 평균은 정수로 반올림(예: 0과 1의 평균 = 0) |
| 정렬 | `sortfield` 있음 | 없음 → 백엔드에서 `clock`으로 정렬 |

### 7.6 problem.get — 지금 열려 있는 장애

- **용도**: 해결되지 않은 문제(+ 최근 해결된 문제). 플랫폼 1단계 "알람 수신"의 시작점
- **주요 파라미터** [문서·소스]: `eventids`, `hostids`, `groupids`, `objectids`(트리거 ID), `source`(기본 0 트리거), `object`(기본 0 트리거), `severities`, `acknowledged`, `suppressed`, `symptom`, `tags`/`evaltype`, `recent`, `eventid_from`/`eventid_till`, `time_from`/`time_till`, `selectAcknowledges`, `selectTags`, `selectSuppressionData`, `sortfield`(**eventid만**)
- `recent`: `true` = 미해결 + `ok_period`(관리 > 일반) 안에 해결된 것, `false`/생략 = 미해결만(소스: `r_eventid IS NULL`)
- **요청** (새 장애 폴링):

```json
{"jsonrpc":"2.0","method":"problem.get","id":8,"params":{
  "output":"extend","hostids":"<hostid>","eventid_from":"<마지막으로 본 eventid+1>",
  "selectTags":"extend","selectAcknowledges":["clock","message","action"],
  "sortfield":["eventid"],"sortorder":"ASC","limit":100}}
```

- **응답 구조** [문서]:

```json
{"eventid":"1245463","source":"0","object":"0","objectid":"15112","clock":"1472457242","ns":"209442442",
 "r_eventid":"1245468","r_clock":"1472457285","r_ns":"125644870","correlationid":"0","userid":"1",
 "name":"Zabbix agent on localhost is unreachable for 5 minutes","acknowledged":"1","severity":"3",
 "cause_eventid":"0","opdata":"","suppressed":"1",
 "acknowledges":[...],"suppression_data":[...],"tags":[{"tag":"test-tag","value":"test-value"}]}
```

- **필드**: `objectid` = 트리거 ID, `severity` 0 미분류 / 1 정보 / 2 경고 / 3 평균 / 4 높음 / 5 재해, `r_eventid` ≠ "0"이면 해결됨, `cause_eventid` ≠ "0"이면 다른 문제의 증상(symptom)
- **주의**: **호스트 정보가 없다** → 7.7/7.8로 보강. 오래전에 해결된 문제는 problem 테이블에 없으므로 `event.get`을 쓴다.

### 7.7 event.get — 발생·복구 이력

- **용도**: 기간 내 문제(value=1)·복구(value=0) 이벤트 이력, 같은 트리거의 반복 횟수, 호스트·트리거 정보까지 한 번에
- **주요 파라미터** [문서]: `eventids`, `hostids`, `objectids`, `source`, `object`, `value`, `severities`, `trigger_severities`, `time_from`/`time_till`, `problem_time_from`/`problem_time_till`(그 기간에 문제 상태였던 것), `eventid_from`/`eventid_till`, `selectHosts`, `selectRelatedObject`(트리거), `selectTags`, `selectAcknowledges`, `selectSuppressionData`, `sortfield`(eventid, objectid, clock), `groupBy`(objectid, 집계용)
- **요청**:

```json
{"jsonrpc":"2.0","method":"event.get","id":9,"params":{
  "output":["eventid","source","object","objectid","clock","value","severity","name","r_eventid","acknowledged"],
  "hostids":"<hostid>","source":0,"object":0,"value":[0,1],
  "time_from":<now-604800>,"time_till":<now>,
  "selectHosts":["hostid","host","name"],
  "selectRelatedObject":["triggerid","description","priority","value"],
  "selectTags":"extend","sortfield":["clock","eventid"],"sortorder":"DESC","limit":100}}
```

- **응답 구조** [문서 예시 발췌]:

```json
{"eventid":"4","source":"0","object":"0","objectid":"22395","clock":"1728657737","value":"1",
 "acknowledged":"1","ns":"460759366","name":"Load average is too high (per CPU load over 1.5 for 5m)",
 "severity":"3","r_eventid":"20","c_eventid":"0","correlationid":"0","userid":"0","cause_eventid":"0",
 "opdata":"Load averages(1m 5m 15m): (1.6328 3.0522 2.2515), # of CPUs: 2","suppressed":"0",
 "hosts":[{"hostid":"...","host":"...","name":"..."}],
 "relatedObject":{"triggerid":"22395","description":"...","priority":"3","value":"0"},"tags":[...]}
```

- **필드**: `source` 0 트리거 / 1 탐색 / 2 자동 등록 / 3 내부 / 4 서비스, `value`(트리거) 0 OK / 1 문제, `r_eventid` 복구 이벤트 ID
- **주의**: 하우스키퍼가 지우기 전까지는 삭제된 대상의 이벤트도 나올 수 있다. 7.2에서 `select_acknowledges`·`select_alerts` 삭제.

### 7.8 trigger.get — 장애 감지 규칙

- **용도**: 어떤 조건으로 장애를 판단하는지(식, 심각도), 트리거가 보는 Item, 현재 문제 상태. problem → **관련 Item** 역추적
- **주요 파라미터** [문서]: `triggerids`, `hostids`, `itemids`, `groupids`, `only_true`, `min_severity`, `monitored`, `active`, `skipDependent`, `lastChangeSince`/`lastChangeTill`, `filter`(예: `{"value":1}`), `expandDescription`, `expandExpression`, `expandComment`, `selectHosts`, `selectItems`, `selectFunctions`, `selectDependencies`, `selectLastEvent`, `selectTags`, `sortfield`(triggerid, description, status, priority, lastchange, hostname)
- **요청** (문제의 objectid로 보강):

```json
{"jsonrpc":"2.0","method":"trigger.get","id":10,"params":{
  "triggerids":"<problem.objectid>",
  "output":["triggerid","description","priority","value","status","state","lastchange","error","expression"],
  "expandDescription":true,"expandExpression":true,
  "selectItems":["itemid","key_","value_type","units"],
  "selectHosts":["hostid","host"],"selectTags":"extend"}}
```

- **응답 구조** [문서 예시 발췌]:

```json
{"triggerid":"14062","expression":"{13513}<10m","description":"{HOST.NAME} has been restarted (uptime < 10m)",
 "status":"0","value":"0","priority":"2","lastchange":"0","state":"0","flags":"0","recovery_mode":"0","manual_close":"0",
 "opdata":"","event_name":"","functions":[{"functionid":"13513","itemid":"24350","parameter":"$","function":"last"}]}
```

- **필드**: `value` 0 OK / 1 문제, `priority` = 심각도(0~5), `status` 0 사용 / 1 사용 안 함, `state` 0 최신 / 1 알 수 없음
- **주의**: `expandExpression` 없이 받으면 `{13513}` 같은 함수 ID로 나온다. 7.2에서 `selectGroups` 삭제.

### 7.9 인증 요청

```json
// 권장: API 토큰 (프론트엔드 Users > API tokens 에서 생성, 값은 생성 직후 한 번만 보임)
// → 모든 요청에 헤더 Authorization: Bearer <token>

// 대안: 로그인 세션 (끝나면 user.logout 필요, MFA 사용자 그룹이면 불가)
{"jsonrpc":"2.0","method":"user.login","params":{"username":"<user>","password":"<password>"},"id":1}
// → {"jsonrpc":"2.0","result":"<세션 토큰>","id":1}

// 버전 확인 (인증 없이)
{"jsonrpc":"2.0","method":"apiinfo.version","params":{},"id":1}
```

---

## 8. 실제 응답 또는 응답 구조 예시

### 8.1 Zabbix 서버 API 응답: 없음

팀 서버가 없어 실제 API 응답은 받지 못했다. 7절의 응답은 모두 **공식 문서 예시**다. 서버가 준비되면 아래 한 줄로 실제 응답을 받아 `probe_out/`에 저장한다(IP 자동 마스킹).

```powershell
$env:ZABBIX_API_URL = "https://<frontend>/api_jsonrpc.php"
$env:ZABBIX_API_TOKEN = "<read-only 사용자 토큰>"    # 파일·셸 기록에 남기지 않도록 세션 변수로만
python infra/zabbix/tools/zabbix_api_probe.py --host <HOST_NAME_IN_ZABBIX> --hours 6 --days 7 --out probe_out
```

점검 스크립트 자체 동작 확인 [실측, 모의 응답]: 문서 예시 모양으로 응답하는 로컬 가짜 엔드포인트에 붙여 10개 호출이 모두 끝나는 것, `apiinfo.version`만 인증 헤더 없이 보내고 나머지는 `Bearer` 헤더를 보내는 것, `history.get`을 value_type별(0/2/3)로 나눠 부르는 것, IP가 `<ipv4>`로 저장되는 것을 확인했다. 실제 Zabbix 응답이 아니다.

### 8.2 실제로 받은 에이전트 쪽 데이터 [실측]

패시브 체크 응답 (Zabbix 7.0 JSON 프로토콜, 원시 바이트로 확인):

```json
{"version":"7.0.31","variant":2,"data":[{"value":"[{\"name\":\"chrome.exe\",\"processes\":23,\"vmsize\":3476448,\"wkset\":3879300,\"cputime_user\":3988.875,\"cputime_system\":1758.25,\"threads\":528,\"page_faults\":65687281,\"handles\":10884,\"io_read_b\":47299408260,\"io_write_b\":18601563233,\"io_read_op\":7190780,\"io_write_op\":7654500,\"io_other_b\":1229608360,\"io_other_op\":10040910}]"}]}
```

액티브 체크: 에이전트 → 서버 요청(시작 시)

```json
{"request":"active checks","host":"dejafix-local-test","version":"7.0.31","variant":2,"config_revision":0,"ip":"127.0.0.1"}
```

액티브 체크: 에이전트가 보낸 값 (이벤트 로그 1건, 메시지 본문만 가림)

```json
{"id":1,"itemid":1000,"lastlogsize":1743,"value":"<이벤트 메시지 본문 생략: 원문에 사용자 계정명·SID가 포함됨>",
 "source":"Microsoft-Windows-DistributedCOM","eventid":10016,"severity":2,"timestamp":1791683162,
 "clock":1791963690,"ns":153205200}
```

액티브 체크: 숫자 값

```json
{"id":82,"itemid":1003,"value":"9.131499","clock":1791963693,"ns":2064200}
```

- 전송 헤더 플래그가 3(프로토콜+압축)이라 에이전트가 zlib 압축을 쓴다 [실측].
- 서버에 저장되면 `history.get(history=2)`에서 `eventid`는 `logeventid`, `timestamp`는 원본 이벤트 시각으로 대응된다(필드 이름 대응은 [문서] 기준).
- 전체 표본: `docs/zabbix/verification/active-eventlog-sample.json`

---

## 9. 인증 및 보안 주의사항

| 구분 | 규칙 |
|---|---|
| 인증 방식 | **API 토큰 + `Authorization: Bearer`**. 비밀번호를 코드에 두는 `user.login`은 쓰지 않는다(쓰면 반드시 `user.logout`). `auth` 본문 속성은 7.2에서 삭제 |
| 전용 사용자 | 사용자 유형 **User**, 프론트엔드 접근 없이 API만. 역할: "Access to API" 사용, "API methods"는 **허용 목록**으로 `host.get, item.get, history.get, trend.get, problem.get, event.get, trigger.get`만(와일드카드 가능). 사용자 그룹: 감시 대상 호스트 그룹에 **읽기(Read)** 권한만 |
| 토큰 | 만료일 설정, 토큰 값은 생성 직후 한 번만 보이므로 비밀 저장소·환경 변수에만 둔다. 노출되면 Regenerate(기존 값 즉시 무효) |
| 저장소 | 토큰·비밀번호·서버 IP·PSK를 문서·Git에 쓰지 않는다. `.env`는 `.gitignore`에. 요청 로그에 `Authorization` 헤더를 남기지 않는다 |
| 전송 | 프론트엔드는 HTTPS로(토큰이 헤더로 오감). 자체 서명 인증서는 실험실에서만 `--insecure` |
| 개인 정보 | 이벤트 로그 메시지(계정명·SID), 인터페이스 IP, 서비스 실행 계정, 프로세스 목록은 LLM 전송·보고서 저장 전에 가린다 |
| 에이전트 | `DenyKey=system.run[*]` 기본값 유지(원격 명령 금지). 방화벽은 열지 않거나(액티브 전용) 서버 IP 하나로만 연다. 서버↔에이전트 구간은 기본 평문이므로 PSK 암호화를 검토 |
| 플랫폼 안전 정책 | Zabbix 연동은 **조회 전용**(A 티어). `*.create/update/delete`, `script.execute`, `event.acknowledge`는 역할에서 막아 둔다 |

---

## 10. 장애 분석용 데이터 매핑

공통 원칙: 데이터로 확인되는 것은 **사실**, 데이터 사이를 잇는 설명은 **추정**으로 나눠 AI에 넘긴다. 예를 들어 CPU 사용률이 높다는 사실만으로 특정 프로세스를 원인으로 단정하지 않는다. 프로세스별 지표가 없으면 "추가 수집 필요"로 남긴다.

시간 범위 기본값: 상세 = 장애 시각 **−60분 ~ +15분** history, 기준선 = 직전 **7일** trend(같은 시간대), 재발 = 직전 **30일** event.

### 10.1 CPU 사용률 지속 상승

| 항목 | 내용 |
|---|---|
| 감지 | 템플릿 트리거 "High CPU utilization": `min(system.cpu.util,5m) > 90`(`{$CPU.UTIL.CRIT}`). 보조: 큐 길이 트리거, 커널 시간 >30%, 인터럽트 >50% |
| 조회 | `trigger.get`(objectid) → `item.get`(`system.cpu.util`, `% User Time`, `% Privileged Time`, `% Interrupt Time`, `% DPC Time`, `Processor Queue Length`, `Context Switches/sec`) → `history.get(history=0)` −60~+15분 → `trend.get` 7일 |
| 판단 시간 | 5분 이상 지속(템플릿 기준). 순간 최대값만으로 판단하지 않음 |
| AI에 더 필요한 것 | **프로세스별 CPU**(기본 템플릿에 없음 → `proc.get[,,,summary]`를 1분 주기로 추가해 `cputime` 차분, 또는 WMI 프로세스 스냅샷 Item), 같은 시각 이벤트 로그, 배포·작업 일정(Zabbix 밖) |
| 사실 | 사용률 값과 지속 시간, 사용자/커널 비율, 큐 길이, 평소(7일 같은 시간대) 대비 배수 |
| 추정 | "어떤 프로세스 때문" — 프로세스별 데이터가 있을 때만. 인터럽트·DPC가 높으면 하드웨어·드라이버 쪽(템플릿 설명 근거), 사용자 시간이 높으면 앱 쪽 |

### 10.2 메모리 부족·급증

| 항목 | 내용 |
|---|---|
| 감지 | 템플릿: `min(vm.memory.util,5m) > 90`, `Pages/sec` >1000, `Free System Page Table Entries` <5000, 페이지 파일 여유 <20% |
| 조회 | `vm.memory.size[used/available/pused]`, `vm.vmemory.size[pused]`(커밋), `Paging file % Usage`, `Pages/sec`, `Pool Nonpaged Bytes` history −60~+15분, trend 7일 |
| 판단 시간 | 5분 지속. 누수는 trend로 수 시간~수일 기울기 |
| AI에 더 필요한 것 | 프로세스별 `vmsize`(= Private KB, [실측])·`wkset` 변화 → `proc.get` summary 추가, 앱 오류 로그 |
| 사실 | 사용률·가용 바이트, 커밋 비율, 페이징 발생 여부, 증가 속도 |
| 추정 | 누수 여부(꾸준한 증가 기울기일 때), 원인 프로세스(프로세스별 데이터가 있을 때만), 비페이징 풀 증가 → 드라이버 쪽 |
| 주의 | `system.swap.size[,free]`는 0으로 틀리게 나온다[주의] — 쓰지 않는다 |

### 10.3 디스크 공간 부족 (플랫폼 IT 데모 장애와 같은 유형)

| 항목 | 내용 |
|---|---|
| 감지 | 템플릿: `min(vfs.fs.dependent.size[{#FSNAME},pused],5m)` > 90(평균) / > 80(경고) |
| 조회 | `vfs.fs.dependent.size[C:,pused/free/used/total]` history 6~24시간(증가 속도), trend 7~30일, `Disk Write Bytes/sec` history −60분 |
| 판단 시간 | 5분 지속(템플릿). 증가 속도는 최소 1~6시간 |
| AI에 더 필요한 것 | **어느 폴더가 커졌는가**(기본 수집 없음 → 로그·임시 폴더에 `vfs.dir.size[<경로>]` Item 추가 검토, 조회 비용 큼), 정리 가이드 문서 |
| 사실 | 현재 사용률·여유 바이트, 시간당 증가량, 쓰기 처리량 급증 여부 |
| 추정 | 가득 찰 예상 시각(선형 외삽), 원인(로그 폭증·업데이트 파일 등)은 폴더 크기 데이터가 있을 때만 |
| 참고 | 이 PC의 C:는 실측 91.86%로 이미 "매우 부족" 조건(>90%)에 해당 |

### 10.4 네트워크 연결 장애

| 항목 | 내용 |
|---|---|
| 감지 | 에이전트 단절: `zabbix[host,active_agent,available]=2`(5분), `nodata(agent.ping,30m)`(액티브 템플릿) / 패시브는 `zabbix[host,agent,available]=0`(3분). 링크: `net.if.status` 변화(Link down). 품질: 오류율 >2, 대역폭 >90% |
| 조회 | `host.get`(`active_available`, `interfaces.available/error`), `net.if.in/out[...,errors\|dropped]`, `net.if.status`, 대역폭 history −60분, `event.get` 같은 시간대 다른 호스트 문제 |
| 판단 시간 | 단절은 5~30분(템플릿 매크로), 오류율은 5분 |
| AI에 더 필요한 것 | 같은 네트워크의 다른 호스트 상태(동시 단절이면 네트워크 쪽), 서버 쪽 ICMP 핑 항목(서버 측 simple check, 별도 설정), 복구 후 `system.uptime`(재부팅이었는지), 의존 서비스 `net.tcp.port`·`net.dns` 항목 |
| 사실 | 마지막 값 수신 시각, 링크 상태 변화, 오류·드롭 증가 |
| 추정 | 원인 구분(PC 꺼짐 / 네트워크 / 에이전트 중지) — 에이전트 데이터만으로는 **구분할 수 없다**. 위 추가 데이터가 있어야 함 |
| 권장 | `EnablePersistentBuffer=1`이면 단절 동안의 값이 복구 후 들어와 원인 분석에 쓸 수 있다(문서) — 미검증 |

### 10.5 주요 Windows 서비스 중지

| 항목 | 내용 |
|---|---|
| 감지 | 템플릿: `min(service.info["{#SERVICE.NAME}",state],#3) <> 0`(3회 연속 실행 아님), 대상은 자동/지연 자동 시작 서비스 |
| 조회 | `service.info[...,state]` history(언제부터), `service.info[...,startup]`, `services[automatic,stopped]`, System 이벤트 로그 history(`history=2`) −30~+5분 |
| 판단 시간 | 3회 연속(수집 주기 × 3) |
| AI에 더 필요한 것 | 서비스 제어 관리자 이벤트(비정상 종료·재시작 기록) — **이벤트 로그 Item 추가 필요**, 해당 앱 로그, 서비스 의존 관계 |
| 사실 | 상태 코드(0 실행 … 6 중지, 255 없음)와 변경 시각, 시작 유형 |
| 추정 | 중지 이유(충돌·수동 중지·업데이트) — 이벤트 로그가 있을 때만 |
| 주의 | 평소에도 멈춰 있는 자동 시작 서비스가 있다(이 PC 6개: edgeupdate, MapsBroker, sppsvc 등 — 지연·트리거 시작형). 기준선에서 빼야 오탐이 없다 |

### 10.6 재부팅·이벤트 로그 이상

| 항목 | 내용 |
|---|---|
| 감지 | 템플릿: `last(system.uptime) < 10m`(재시작), 추가 Item: `eventlog.count[System,,"Error\|Critical"]` 급증, `eventlog[System,,"Critical"]` |
| 조회 | `system.uptime` history, WMI 부팅 시각, 이벤트 로그 history −30분~+10분(부팅 전후), `event.get` 30일(재발) |
| 판단 시간 | 재부팅 직후 10분, 로그 급증은 5~15분 창 |
| AI에 더 필요한 것 | 계획된 재시작인지(업데이트·사용자 종료 이벤트), 직전 리소스 상태(메모리·디스크 history) |
| 사실 | 재부팅 시각(가동 시간 초기화), 그 시각 앞뒤의 이벤트 ID·소스·심각도 |
| 추정 | 계획/비계획 여부와 원인 — 해당 이벤트 기록이 있어야 함 |
| 잡음 | `DistributedCOM 10016`(이 PC System 경고·오류의 92%), `PerfNet 2004`(성능 카운터 조회 부작용)는 기본 제외 목록에 둔다 [실측 근거] |

### 10.7 백엔드에 넘길 권장 데이터 구조

```json
{
  "incident": {
    "source": "zabbix", "source_event_id": "1245463", "trigger_id": "15112",
    "name": "Windows: FS [(C:)]: Space is critically low", "severity": 3, "severity_label": "average",
    "status": "problem", "started_at": "2026-10-14T07:41:33Z", "resolved_at": null,
    "host": {"zabbix_hostid": "10601", "host": "<HOST_NAME_IN_ZABBIX>", "groups": ["<그룹>"], "tags": {"owner": "<담당>"}},
    "trigger": {"expression": "min(/<host>/vfs.fs.dependent.size[C:,pused],5m)>90", "item_keys": ["vfs.fs.dependent.size[C:,pused]"]}
  },
  "metrics": [
    {"key": "vfs.fs.dependent.size[C:,pused]", "itemid": "50004", "value_type": 0, "units": "%",
     "window": {"from": "2026-10-14T06:41:33Z", "till": "2026-10-14T07:56:33Z"},
     "points": [["2026-10-14T07:40:00Z", 91.86]],
     "baseline_7d": {"avg": 85.2, "max": 88.0, "source": "trend.get"}}
  ],
  "logs": [
    {"time": "2026-10-14T07:31:37Z", "log": "System", "source": "Microsoft-Windows-DistributedCOM",
     "event_id": 10016, "severity": "warning", "message": "<마스킹된 본문>", "noise": true}
  ],
  "history": {"same_trigger_30d": 2, "other_open_problems_on_host": []},
  "facts": ["C: 사용률 91.86% (5분 이상 90% 초과)", "최근 6시간 증가 +0.4%p"],
  "missing_data": ["폴더별 크기 미수집 — 원인 폴더 특정 불가"]
}
```

- 값의 출처(`trend.get`, `history.get`)와 빠진 데이터(`missing_data`)를 같이 넘겨, AI가 없는 데이터를 추측으로 메우지 않게 한다.
- 시각은 Zabbix의 Unix 초를 UTC ISO 8601로 바꿔 저장하고, 화면 표시만 KST로 한다.

---

## 11. 백엔드 개발자가 참고할 연동 명세

### 11.1 연동 방식

| 방식 | 흐름 | 장점 | 단점 | 권장 |
|---|---|---|---|---|
| 폴링 | 10~30초마다 `problem.get(eventid_from=커서+1)` | 읽기 전용 토큰만 있으면 됨, Zabbix 설정 변경 없음 | 폴링 주기만큼 지연 | **MVP 기본**(30초 초동 리포트 목표 안에 들어옴) |
| 웹훅(push) | Zabbix 액션 + 웹훅 미디어 타입이 플랫폼 수신 API로 POST | 즉시 | Zabbix 서버 설정·플랫폼 공개 엔드포인트 필요 | 2단계(서버 담당과 협의, 미검증) |

### 11.2 처리 순서 (장애 1건)

```
1. 새 문제      problem.get {eventid_from: cursor+1, sortfield: eventid ASC}         → 커서 갱신
2. 트리거       trigger.get {triggerids: objectid, selectHosts, selectItems, selectTags,
                            expandDescription, expandExpression}
3. 호스트       host.get {hostids, selectInterfaces, selectHostGroups, selectTags}    (캐시 5분)
4. Item 목록    item.get {hostids, output: itemid/key_/value_type/units/history}      (호스트별 캐시 1시간, LLD 변화 대비)
5. 시계열       history.get × value_type별 {itemids, time_from: clock-3600, time_till: clock+900}
6. 기준선       trend.get {itemids(숫자형), time_from: now-7d}                        → 백엔드에서 clock 정렬
7. 로그         history.get {history: 2, itemids: eventlog Items, clock-1800 ~ clock+300} → 잡음 필터·마스킹
8. 재발         event.get {objectids: triggerid, value: 1, time_from: now-30d, countOutput 또는 limit}
9. 해결 추적    problem.get {eventids: 열린 것들, recent: true} → r_eventid != "0" 이면 해결
                (결과에 없으면 event.get {eventids} 로 확인)
```

### 11.3 어댑터 인터페이스 (제안, 구현은 백엔드 담당)

```python
class ZabbixClient:
    def __init__(self, url: str, token: str, timeout: float = 30): ...
    def call(self, method: str, params: dict | list, *, auth: bool = True): ...
        # 헤더 Authorization: Bearer, 응답 error → ZabbixApiError(code, message, data)

class ZabbixAdapter:                       # 팩 공통 '알람 수신 어댑터' 자리에 들어감
    def poll_problems(self, cursor: str) -> tuple[list[Incident], str]: ...
    def enrich(self, inc: Incident) -> IncidentContext: ...      # 11.2의 2~8
    def check_resolved(self, open_ids: list[str]) -> dict[str, str | None]: ...
```

### 11.4 구현 규칙

| 규칙 | 내용 |
|---|---|
| 형 변환 | `value_type` 0 → float, 3 → int, 1/4 → str, 2 → 로그 객체. `clock` → int → UTC datetime |
| history 분할 | itemid를 value_type별로 묶어 타입마다 한 번씩 호출 |
| trend 정렬 | 응답 순서 보장 없음 → `clock` 정렬 |
| 단위 | `item.units`를 같이 저장(%, B, bps). 네트워크 history는 이미 bps |
| 캐시 | itemid·value_type은 호스트별로 캐시, 탐색(LLD)으로 Item이 바뀔 수 있어 1시간마다 갱신 |
| 미지원 Item | `item.state == "1"`이면 분석 입력에서 빼고 `error`를 `missing_data`에 기록 |
| 오류 처리 | JSON-RPC `error`는 재시도하지 않고 기록(권한·파라미터 문제), 네트워크 오류·5xx만 지수 백오프 재시도 |
| 범위 제한 | 모든 history 호출에 `time_from/time_till`과 `limit` |
| 버전 확인 | 시작 시 `apiinfo.version`을 기록, 7.2 미만/이상에 따라 다른 코드 경로는 만들지 않는다(7.1 표의 공통 부분만 사용) |
| 읽기 전용 | `*.get`과 `apiinfo.version` 외 메서드 호출 금지 |

### 11.5 도메인 팩(IT 팩) 연결 제안

| Zabbix | IT 팩 | 비고 |
|---|---|---|
| 호스트(`hostid`, `host`) | `Node` | 객체 ID 예: `zabbix:10601` |
| 호스트 태그 `service=<서비스>`, `owner=<담당>` | `RUNS_ON`/`SUPPORTS`/`OWNS` 링크 | Zabbix 호스트에 태그를 미리 달아 두면 영향 범위 그래프와 바로 연결된다(서버 담당과 협의) |
| 트리거 심각도 0~5 | Incident 심각도 | 숫자 그대로 저장, 라벨은 화면에서 |
| Windows 서비스(`service.info`) | `Node`의 속성 또는 하위 구성 요소 | 업무 `Service`와 다른 개념이므로 같은 객체로 섞지 않는다 |
| IT 팩 기본 지표 Disk·메모리 | `vfs.fs.dependent.size[...]`, `vm.memory.util` | Windows에 Inode·IO Wait는 없음 → 디스크 지연(`Avg. Disk sec/*`)·큐로 대체 |

---

## 12. 테스트 결과와 미검증 항목

### 12.0 로컬 실서버 검증 (2026-10-14 17:45~17:52)

| 항목 | 결과 |
|---|---|
| 서버 | Docker Desktop 4.95.0(엔진 29.8.2) + `infra/zabbix/local-server` compose: zabbix-server-pgsql·web-nginx-pgsql `alpine-7.0.31`, postgres 16. `apiinfo.version` = 7.0.31. 첫 기동 직후 약 10초간 `Unable to select configuration.`(스키마 생성 중) |
| 에이전트 | MSI 7.0.31 서비스 `Zabbix Agent 2`(Running, Automatic), conf `Server=127.0.0.1`, `ServerActive=127.0.0.1:10051`, `Hostname=demo-host-01`, `ListenIP=127.0.0.1`, Zabbix 방화벽 규칙 0 |
| 서버 설정 | `infra/zabbix/local-server/setup_local_server.py`: 호스트 등록(그룹 DejaFix/Windows, 템플릿 Windows by Zabbix agent active, 인터페이스 없음), 이벤트 로그 Item 3개, 읽기 전용 역할(API 허용 목록 7개)·사용자 그룹(호스트 그룹 읽기)·사용자 `dejafix-api`·토큰, Admin 기본 비밀번호 변경. 비밀 값은 `C:\Users\403\host-setup\zabbix-secrets.json`(본인 계정만 읽기)에만 저장 |
| 연결 | 호스트 등록 전 에이전트 로그 `no active checks on server [127.0.0.1:10051]: host [demo-host-01] not found` → 등록 후 `active checks on server are active again`, `host.get` `active_available=1` |
| API 7개 | 읽기 전용 토큰으로 전부 성공(각 135~218 ms). item 51개(value_type 0:5, 1:2, 2:2, 3:14 중 핵심), history type0 4건·type3 11건, trend 0건(1시간 미만이라 정상), problem 1건, event 1건, trigger 19개 중 문제 1 |
| 감지된 장애 | `Windows: FS [(C:)]: Space is critically low (used > 90%, total 111.1GB)`, severity 3 — 에이전트 → 트리거 → problem.get까지 실제로 이어짐 |
| 권한 | 토큰으로 `user.get` 호출 → `No permissions to call "user.get".` (허용 목록 동작). 읽기 전용 사용자에게는 `parentTemplates`가 빈 배열(템플릿 그룹 권한 없음) — 템플릿 이름이 필요하면 템플릿 그룹 읽기 권한 추가 |
| 미지원 Item | `system.swap.free`(템플릿 계산 항목) `not enough data` — 데이터가 쌓이기 전 일시 상태 |

### 12.1 완료한 검증

| 검증 | 방법 | 결과 |
|---|---|---|
| 설치 파일 무결성 | 공식 SHA256 비교, Authenticode | zip·MSI 모두 일치, MSI 서명 Valid(Zabbix SIA), zip 안 exe는 서명 없음 |
| 설정 검증 | `-T` | 성공 |
| 패시브 수집 | 키 116개 × 2회 | 106개 성공, 미지원 확인 9개, 이름 문제 1개 |
| 교차 비교 | 같은 시점 CIM/PowerShell | 14개 항목 비교: 13개 일치, `system.swap.size[,free]` 1개 불일치 |
| 액티브 수집·이벤트 로그 | 모의 수신기 | 값 175건, System 74/74, Application 6(+기준 이후 1건 설명됨), 심각도 매핑 확인 |
| 실패 로그 재현 | 서버 없음 / 호스트 미등록 / 허용되지 않은 서버 | 4.3절 문구 확보 |
| 단위 확인 | Get-Process 비교 | `proc.get` CPU 시간 = 초, 메모리 = KB |
| 인코딩 | 원시 프로토콜 바이트 | 서비스 설명 한글은 에이전트 단계에서 깨짐 |
| API 문서·소스 | 7.0 문서 + `CHistory.php`·`CTrend.php`·`CProblem.php` | history 기본 타입 3·한 타입만, trend 숫자형만·정렬 없음, problem `recent` 조건 |
| API 점검 스크립트 | dry-run + 모의 JSON-RPC | 10개 호출 완료, Bearer 헤더, 타입별 분할, IP 마스킹 |

### 12.2 미검증·미완료 (다음 작업)

| 항목 | 이유 | 다음 할 일 |
|---|---|---|
| Windows 서비스 설치·상태 | 완료(로컬): `Zabbix Agent 2` Running·자동, 방화벽 규칙 0 | 팀 공용 서버가 정해지면 conf의 `Server`/`ServerActive`만 바꾸고 서비스 재시작 |
| 서버 연결(패시브·액티브) | 액티브는 로컬 서버로 확인, 패시브는 의도적으로 미사용 | 팀 서버에서 4.2절 체크리스트 |
| 템플릿 Item의 실제 `value_type`·`units`·보관 기간 | 서버에 템플릿을 연결해야 보임 | `zabbix_api_probe.py`의 `item.get` 결과로 6절 표 갱신 |
| 7개 API 실응답 | 로컬 서버로 확인(12.0절). trend는 1시간 이상 지나야 생김 | 2시간 뒤 `trend.get` 재확인 |
| TLS 오류 문구 | "host not found"는 실서버로 확인됨, TLS는 미사용 | PSK 도입 시 확인 |
| 웹훅 방식 | 서버 설정 필요 | 서버 담당과 협의 |
| `EnablePersistentBuffer` 동작 | 서버 단절 시나리오 필요 | 서버 연결 후 시험 |
| 한글 UI Windows에서 `perf_counter`(현지어) | 이 PC는 UI가 영어 | 한글 UI PC에서 `perf_counter_en` 정상 여부 확인 |
| 장시간 수집 부하 | 몇 분만 실행 | 서비스 설치 후 에이전트 CPU·메모리 확인 |

---

## 13. 공식 참고 문서 (2026-10-14 확인)

- 에이전트 다운로드·체크섬: https://www.zabbix.com/download_agents , https://cdn.zabbix.com/zabbix/binaries/stable/7.0/7.0.31/
- 수명 주기: https://www.zabbix.com/life_cycle_and_release_policy
- 버전 호환: https://www.zabbix.com/documentation/7.0/en/manual/appendix/compatibility
- MSI 설치: https://www.zabbix.com/documentation/7.0/en/manual/installation/install_from_packages/win_msi
- 압축본 설치·서비스 등록: https://www.zabbix.com/documentation/7.0/en/manual/appendix/install/windows_agent
- Agent 2 Windows 설정: https://www.zabbix.com/documentation/7.0/en/manual/appendix/config/zabbix_agent2_win
- Windows Item key: https://www.zabbix.com/documentation/7.0/en/manual/config/items/itemtypes/zabbix_agent/win_keys
- 공통 Item key: https://www.zabbix.com/documentation/7.0/en/manual/config/items/itemtypes/zabbix_agent
- `proc.get` 반환 필드: https://www.zabbix.com/documentation/7.0/en/manual/appendix/items/proc_get
- Windows `system.cpu.util`: https://www.zabbix.com/documentation/7.0/en/manual/appendix/items/system_cpu_util
- 패시브·액티브 프로토콜: https://www.zabbix.com/documentation/7.0/en/manual/appendix/items/activepassive
- 프로토콜 헤더: https://www.zabbix.com/documentation/7.0/en/manual/appendix/protocols/header_datalen
- 히스토리와 트렌드: https://www.zabbix.com/documentation/7.0/en/manual/config/items/history_and_trends
- 템플릿 README: https://raw.githubusercontent.com/zabbix/zabbix/release/7.0/templates/os/windows_agent/README.md , https://raw.githubusercontent.com/zabbix/zabbix/release/7.0/templates/os/windows_agent_active/README.md
- API 개요·인증: https://www.zabbix.com/documentation/7.0/en/manual/api
- API 메서드: https://www.zabbix.com/documentation/7.0/en/manual/api/reference/host/get , .../item/get , .../history/get , .../trend/get , .../problem/get , .../event/get , .../trigger/get (객체 정의는 같은 경로의 `/object`)
- 인증: .../api/reference/user/login , .../api/reference/token/generate , https://www.zabbix.com/documentation/7.0/en/manual/web_interface/frontend_sections/users/api_tokens
- 권한·역할: https://www.zabbix.com/documentation/7.0/en/manual/config/users_and_usergroups/permissions , https://www.zabbix.com/documentation/7.0/en/manual/web_interface/frontend_sections/users/user_roles
- API 변경 이력: https://www.zabbix.com/documentation/7.0/en/manual/api/changes , https://www.zabbix.com/documentation/7.2/en/manual/api/changes , https://www.zabbix.com/documentation/7.4/en/manual/api/changes
- API 소스(7.0): https://github.com/zabbix/zabbix/tree/release/7.0/ui/include/classes/api/services (`CHistory.php`, `CTrend.php`, `CProblem.php`)
