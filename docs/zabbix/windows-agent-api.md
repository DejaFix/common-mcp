# Zabbix Windows Agent 2 · 수집 데이터 · API 사용 명세

> 한 줄 요약: Windows Agent 2 설치·수집 검증 절차, 수집 항목(Item key), Zabbix 7.0 조회 API 7개의 사용법과 응답 예시. 길어서 목차로 찾아 읽는 레퍼런스.

- 기준 버전: Zabbix **7.0 LTS** (Agent 2 **7.0.31**). API 문서는 7.0 기준이고 7.2/7.4 차이는 7.1절에 표시한다.
- 표기: **[실측]** 직접 값 확인 · **[교차일치]** Windows 원본 값과 비교해 일치 · **[실측·미지원]** 미지원 확인 · **[주의]** 실측이 문서와 다름 · **[문서]** 공식 문서·소스로만 확인 · **[서버 필요]** Zabbix 서버가 있어야 확인 가능
- 검증 환경: Windows 10 x64(UI en-US) + Docker의 Zabbix 7.0.31 서버(로컬 전용). 아래 실측 값은 이 환경에서 얻은 예시다.

## 결론 먼저

| 항목 | 상태 |
|---|---|
| 설치 | 공식 Agent 2 7.0.31(MSI 또는 압축본) 설치·실행 검증, 공식 SHA256 일치 |
| 수집 검증 | Item key 116개 실측, 106개 성공. 실패 10개 중 9개는 "Windows 미지원"을 확인하려고 넣은 키, 1개는 한글 인터페이스 이름 문제. CPU·메모리·디스크·네트워크·서비스·프로세스 값은 같은 시점 Windows 값과 교차 비교해 일치(차이 0~0.6%) |
| 이벤트 로그 | `eventlog[]`는 액티브 전용. 모의 수신기로 받은 에이전트 출력이 Windows 이벤트 뷰어 원본과 74/74건 일치 |
| 서버 연결 | Agent 2 서비스(MSI, 액티브 전용) → `10051` 연결, 호스트 `active_available=1`, 실제 장애 트리거 감지까지 확인 |
| API | 7개 get 메서드를 읽기 전용 토큰으로 호출해 확인. 허용 목록 밖 메서드(`user.get`)는 "No permissions"로 차단 |

꼭 알아야 할 다섯 가지:

1. 인증은 `Authorization: Bearer <API 토큰>` 헤더만 쓴다. 요청 본문의 `auth`는 7.0에서 폐기 예정, **7.2에서 삭제**됐다.
2. `history.get`은 한 번에 **value_type 하나**만 조회한다(기본값 3 = 정수). 타입이 안 맞으면 오류 없이 빈 배열이 온다. Item의 `value_type`을 먼저 확인한다.
3. `trend.get`은 숫자형(0 float, 3 unsigned) Item의 **1시간 단위 min/avg/max**만 있다. 최대 2시간 늦게 생기고 정렬 파라미터가 없다.
4. `problem.get`은 호스트 정보를 주지 않는다. `objectid`(= triggerid)로 `trigger.get` 또는 `event.get`(`selectHosts`)을 다시 호출한다.
5. 응답의 숫자는 모두 **문자열**이다(`"clock": "1351090996"`, `"value": "0.085"`). `clock`은 Unix 초(UTC)다.

---

## 1. 구성: 수집과 조회는 서로 다른 단계

```
 [Windows PC]                    [Zabbix 서버 7.x]                         [조회 클라이언트]
  Zabbix Agent 2                  ┌───────────────────────────┐
   ├─ 액티브 체크 ──TCP 10051──▶  │ trapper (값 수신)          │
   │   (PC → 서버, 권장)           │ poller  (값 요청)          │        JSON-RPC 2.0 over HTTP(S)
   └─ 패시브 체크 ◀─TCP 10050──   │ DB: history / trends /     │ ◀── POST /api_jsonrpc.php ──
       (서버 → PC)                 │     events / problems      │      Authorization: Bearer <토큰>
                                   │ 프론트엔드(PHP) = API      │
                                   └───────────────────────────┘
```

- **Agent → 서버**: Zabbix 자체 프로토콜(ZBXD 헤더 + JSON). 값은 서버 DB에 저장된다.
- **클라이언트 → 서버**: Zabbix API(JSON-RPC). 클라이언트는 **에이전트에 직접 붙지 않는다**. 에이전트가 수집하지 않은 값은 API로도 나오지 않으므로 분석에 필요한 데이터는 먼저 Zabbix Item으로 등록돼 있어야 한다.

---

## 2. Windows Agent 설치 절차

### 2.1 버전 선택
- **에이전트는 서버보다 높은 메이저 버전을 쓰면 안 된다** [문서]. 4.4 이후 Agent 2는 7.0 서버와 호환.
- 7.0 LTS: 전체 지원 2027-06-30, 제한 지원 2029-06-30. 서버 버전을 모르면 **7.0.31**이 가장 안전하다(7.0·7.2·7.4 서버 모두 호환).

### 2.2 파일과 무결성 [실측]
| 파일 | 크기 | 서명 |
|---|---|---|
| `zabbix_agent2-7.0.31-windows-amd64-openssl-static.zip` | 15,339,754 B | zip 안 exe는 Authenticode 서명 없음 |
| `zabbix_agent2-7.0.31-windows-amd64-openssl.msi` | 18,415,616 B | Valid, `CN=Zabbix SIA` |

- 다운로드: `https://cdn.zabbix.com/zabbix/binaries/stable/7.0/7.0.31/`. 공식 SHA256은 `https://www.zabbix.com/download_agents` 페이지에 있다(CDN 폴더에는 체크섬 파일이 없음). `Get-FileHash <파일> -Algorithm SHA256`로 비교한다.
- `zabbix_agent2.exe -V` → `zabbix_agent2 Win64 (Zabbix) 7.0.31 ...`

### 2.3 서버 없이 로컬에서 수집만 검증 (관리자 권한 불필요) [실측]
압축본을 새 폴더에 풀고 **별도 검증용 설정**(원본 conf는 수정하지 않음)으로 콘솔 모드 실행한다.

```powershell
Expand-Archive <zip 경로> -DestinationPath <새 폴더>
$a = "<새 폴더>\bin\zabbix_agent2.exe"; $c = "<검증용 conf 경로>"
& $a -c $c -T          # 설정 검증 -> "Validation successful"
& $a -c $c -p          # 아는 키를 모두 실행해 출력 (367줄)
& $a -c $c -f          # 콘솔(포그라운드) 실행
& $a -c $c -R version  # 런타임 명령(ControlSocket 파이프) -> 7.0.31
```
검증용 설정 핵심: `Server=127.0.0.1`, `ListenIP=127.0.0.1`(방화벽 개방 불필요), `ServerActive=127.0.0.1:10051`, `LogFile`·`ControlSocket`은 사용자 폴더·별도 파이프 이름.

### 2.4 서버 연결용 설치 (관리자 권한 필요)

먼저 받을 정보(임의로 정하지 않는다):

| 정보 | 쓰는 곳 |
|---|---|
| Zabbix 서버(또는 프록시) 주소·포트, 서버 버전 | `SERVER`, `SERVERACTIVE`, 에이전트 버전(서버 이하) |
| Zabbix에 등록할 호스트 이름 | `HOSTNAME` — 서버 등록명과 **대소문자까지 같아야** 액티브 체크가 동작 |
| 패시브 체크 사용 여부 | 쓰면 10050 인바운드를 **서버 IP로만** 허용 |
| 암호화(PSK) 사용 여부 | `TLSCONNECT/TLSACCEPT=psk` 등 |

**권장: 액티브 전용 + MSI** — 액티브는 PC가 서버로 나가는 연결만 쓰므로 들어오는 포트를 열 필요가 없고, 이벤트 로그(`eventlog[]`)도 액티브에서만 동작한다. 템플릿은 `Windows by Zabbix agent active`.

```bat
:: 관리자 cmd. <...> 는 받은 값으로 바꾼다.
msiexec.exe /l*v "%TEMP%\zabbix_agent2_install.log" /i "<msi 경로>" /qn ^
 SERVER=<ZABBIX_SERVER> ^
 SERVERACTIVE=<ZABBIX_SERVER>:10051 ^
 HOSTNAME=<HOST_NAME_IN_ZABBIX> ^
 INSTALLFOLDER="C:\Program Files\Zabbix Agent 2" ^
 SKIP=fw ^
 ENABLEPATH=1
```
- `SKIP=fw` [문서]: 방화벽 예외 규칙을 자동 추가하지 않는다. 액티브 전용이면 인바운드 규칙이 필요 없다.
- 서비스 시작 유형 기본은 지연된 자동 시작이다 [문서]. `STARTUPTYPE`, 설치 직후 시작을 막는 `DONOTSTART=1`(7.0.22+)도 있다. `SERVER`는 필수이므로 패시브를 안 써도 넣는다.
- 서비스 이름은 `Zabbix Agent 2`(설치 후 `Get-Service *zabbix*`로 확인).

**패시브도 쓸 때만** 방화벽 규칙을 서버 IP 하나로 좁혀 추가한다:
```powershell
New-NetFirewallRule -DisplayName "Zabbix Agent 2 passive (from Zabbix server only)" -Direction Inbound `
  -Protocol TCP -LocalPort 10050 -RemoteAddress <ZABBIX_SERVER_IP> `
  -Program "C:\Program Files\Zabbix Agent 2\zabbix_agent2.exe" -Action Allow
```

**대안: 압축본으로 서비스 등록** [문서] (설정 파일을 exe와 같은 폴더에 두고 관리자 셸에서):
```powershell
zabbix_agent2.exe -c "<conf 경로>" -i   # 서비스 설치 (-S delayed 등으로 시작 유형 지정)
zabbix_agent2.exe -c "<conf 경로>" -s   # 시작 (중지 -x, 제거 -d, 여러 인스턴스 -m)
```
**업그레이드 시** MSI는 기존 설정 파일 이름을 바꾸고 새 파일을 만든다 [문서]. 설치 전 `zabbix_agent2.conf`를 백업하고, 필요하면 `CONF=` 템플릿에 `[LogFile]`, `[Include]`, `[TLSConnect]` 자리표시자를 넣어 기존 값을 이어받는다.

---

## 3. 설정 파일의 주요 항목

배포본 `zabbix_agent2.conf`에서 켜져 있는 줄은 `Server=127.0.0.1`, `ServerActive=127.0.0.1`, `Hostname=Windows host`, `ControlSocket=\\.\pipe\agent.sock`, `Include=.\zabbix_agent2.d\plugins.d\*.conf` 다섯 줄뿐이다 [실측].

| 파라미터 | 의미 | 배포본 기본값 [실측] | 운영 권장 |
|---|---|---|---|
| `Server` | 패시브 요청을 허용할 서버/프록시 주소 | `127.0.0.1` | 팀 서버 주소 |
| `ListenIP` / `ListenPort` | 패시브 수신 주소·포트 | `0.0.0.0` / `10050`(주석) | 패시브 안 쓰면 기본값 두고 방화벽 미개방 |
| `ServerActive` | 액티브 체크 목록을 받을 서버 `주소:포트` | `127.0.0.1` | 팀 서버 `주소:10051` |
| `Hostname` | 서버에 등록된 호스트 이름(대소문자 구분) | `Windows host` | 서버 등록명과 동일 |
| `LogType` / `LogFile` | 로그 | `file` / `c:\zabbix_agent2.log`(주석 = 기본값, **C:\ 루트라 관리자 권한 필요**) | MSI 기본값 사용 |
| `Timeout` | 항목 처리 제한 시간(초) | 3(주석) | WMI 쿼리가 많으면 늘림(프로세스 WMI 조회 약 351 ms) |
| `EnablePersistentBuffer` | 서버 단절 동안 값을 SQLite에 보관(Agent 2 전용) | 0(주석) | 네트워크 장애 분석을 위해 켜는 것 검토 |
| `HeartbeatFrequency` | 액티브 가용성 하트비트(초) | 비어 있음(주석) | 기본값(60초마다 전송) |
| `DenyKey` / `AllowKey` | 실행 허용/차단 키 | `DenyKey=system.run[*]`(주석 = 기본값) | **`system.run` 차단 유지**(원격 명령 실행 방지) |
| `TLSConnect` / `TLSAccept` | 서버와 암호화 | `unencrypted`(주석) | PSK 검토 — 미암호화 시 누구나 에이전트를 사칭해 액티브 항목 설정을 받아 갈 수 있다고 문서가 경고 |
---

## 4. 설치 및 연결 검증 방법

### 4.1 서버 없이 한 검증 [실측]
`-T` 설정 검증(`Validation successful`), `-p` 키 출력(367줄, 수집기가 필요한 키는 `ZBX_NODATA`, `eventlog`는 패시브 모드 미지원), `-f` 실행(127.0.0.1:10050 수신, 플러그인 38개 로드), `zabbix_get -s 127.0.0.1 -k <key>`를 키마다 두 번(1차는 수집기 등록, 약 65초 뒤 2차 값 기록) 질의해 116개 중 106개 성공, 모의 수신기(Zabbix 서버 아님)로 액티브 값 175건 수신(하트비트·항목 목록 요청 60초 간격), `-R version`·`-R metrics`로 런타임 명령 확인. 같은 시점 PowerShell/CIM 값과의 비교는 5.3절.

### 4.2 서버 연결 후 체크리스트 [서버 필요]
```powershell
Get-Service *zabbix* | Format-List Name,DisplayName,Status,StartType        # (1) 서비스 상태
Get-Content "C:\Program Files\Zabbix Agent 2\zabbix_agent2.log" -Tail 50   # (2) 로그 (경로는 conf의 LogFile)
Test-NetConnection <ZABBIX_SERVER> -Port 10051                               # (3) PC -> 서버 액티브 포트
zabbix_get -s <PC_IP> -k agent.ping                                          # (4) 서버 -> PC 패시브(쓸 때만, 서버에서 실행) -> 1
uv run python -m zabbix_ro.probe                                             # (5) API 점검(읽기 전용, 환경 변수 ZABBIX_URL·ZABBIX_API_TOKEN)
```
(5) 후 `host.get`의 `active_available`(1=가용)·`interfaces[].available`(1=가용), `item.get`의 `state`(1=미지원)·`error`를 확인한다.

### 4.3 연결 실패 진단표
에이전트 로그 문구는 실제 재현으로 얻었다(서버 측 오류 문장 일부는 모의 수신기로 흉내 냄).

| 증상(에이전트 로그·도구 출력) | 분류 | 확인 | 조치 |
|---|---|---|---|
| `cannot connect to [<서버>:10051]: ... actively refused it.` → `active check configuration update ... started to fail` → `sending of heartbeat message ... started to fail` [실측] | 네트워크 / 방화벽 / 서버 미기동 | `Test-NetConnection <서버> -Port 10051`, 서버 프로세스·방화벽 | 서버 주소·포트, 경로상 방화벽 |
| `no active checks on server [<서버>:10051]: host [<이름>] not found` → `active checks on server started to fail` [실측, Zabbix 7.0.31 서버에서 같은 문구 확인] | 호스트 이름 / 서버 미등록 | conf의 `Hostname`과 서버 등록명 비교(대소문자) | 서버에 호스트 등록 또는 자동 등록 설정, `Hostname` 수정 |
| 에이전트 `connection from "127.0.0.1" rejected, allowed hosts: "127.0.0.2"` / zabbix_get `cannot read from socket ... [0x00002745]` [실측] | 에이전트 설정(`Server`) | 서버가 실제 접속하는 출발지 IP(NAT·프록시) | `Server`에 그 주소 추가 |
| zabbix_get 시간 초과, 에이전트 로그에 접속 기록 없음 (추정) | PC 방화벽 / 경로 | PC의 10050 인바운드 규칙, `ListenIP` | 서버 IP로만 좁힌 규칙 추가 또는 액티브 전용 |
| 프론트엔드 "Not supported", `item.get`의 `state=1`과 `error` [문서] | 키 문법 / OS 미지원 | 6절 표 | 키 수정(예: `net.if.in`은 GUID 사용) |
| `failed to read request from 127.0.0.1: EOF` [실측] | 정상 | `net.tcp.port[...,10050]`처럼 연결만 하고 끊는 점검의 흔적 | 조치 불필요 |
| TLS 관련 오류 (추정) | 암호화 설정 불일치 | 양쪽 `TLSConnect/TLSAccept`, PSK identity | 서버 호스트 설정과 맞춤 |

---

## 5. 실제 수집 가능한 모니터링 항목

### 5.1 범주별 요약 (Agent 2 7.0.31)

| 범주 | 실측 성공 | 이 PC에서 안 되는 것 | 핵심 메모 |
|---|---|---|---|
| CPU | 사용률(전체·코어별), 사용자/커널/인터럽트/DPC 시간, 큐 길이, 컨텍스트 스위치, 코어 수 | `system.cpu.util[,user]`(Windows는 type=system만) | `system.cpu.load`는 Windows에서 큐 길이 기반이라 Linux load와 의미가 다르다 |
| 메모리 | 전체·사용·가용(바이트·%), 커밋(가상 메모리), 페이지 파일 사용률, 페이지/초, 풀 메모리 | `vm.memory.util`은 에이전트 키가 아님(템플릿의 계산 항목) | `system.swap.size[,free]`=0으로 **틀리게** 나옴 [주의] |
| 디스크 | 드라이브별 전체·사용·여유(바이트·%), 물리 디스크 읽기/쓰기 횟수·바이트·지연·큐·바쁨 | `vfs.fs.inode`, `vfs.dev.*` | IT 기본 지표 중 **Inode와 IO Wait는 Windows에 없다** → 디스크 지연·큐로 대체 |
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
| Application 로그 | — | 성능 카운터를 처음 조회할 때 `PerfNet 2004` 오류가 Application 로그에 기록됨 | 장애 원인으로 오인하지 않게 잡음 목록에 넣는다 |

### 5.3 교차 검증: 같은 시점 Windows 값과 비교 [교차일치]
| Item key | 에이전트 값 | Windows 값 (출처) | 차이 |
|---|---|---|---|
| `vm.memory.size[total]` | 17,111,175,168 | 17,111,175,168 (Win32_ComputerSystem) | 0% |
| `vm.memory.size[available]` | 7,631,065,088 | 7,678,648,320 (FreePhysicalMemory×1024) | -0.62% (측정 순간 차이) |
| `system.uptime` / `system.cpu.num` | 265,797 / 12 | 265,797 / 12 | 0% |
| `system.swap.size[,free]` | **0** | 2,905,604,096 | **-100%** [주의] |

14개 항목 비교에서 13개 일치, `system.swap.size[,free]` 1개 불일치. 일관성: `used + available ≈ total`(차이 0.0014%), `vm.vmemory.size[total]` = 물리 메모리 + 페이지 파일.

---

## 6. Item key 및 데이터 타입 목록

- 타입: Zabbix `value_type` — 0 float, 1 character, 2 log, 3 unsigned, 4 text. 서버 연결 후 `item.get`의 `value_type`·`units`로 최종 확인한다.
- 기본 템플릿: 공식 `Windows by Zabbix agent` / `... active`(7.0). 수집 항목은 같고 수집 방식(패시브/액티브)만 다르다.
- 마지막 열은 검증 상태다. 개별 실측값은 `docs/zabbix/verification/passive-items.md`에 있다.

### 6.1 가용성·시스템

| 데이터 | Item key | 타입·단위 | Windows | 기본 템플릿 | 별도 설정 | 검증 |
|---|---|---|---|---|---|---|
| 에이전트 응답 | `agent.ping` | 3, 항상 1 | 지원 | 예 | — | [실측] |
| 호스트 이름 | `system.hostname` | 1 | 지원 | 예 | — | [실측] |
| OS 설명 | `system.uname` | 1 | 지원 | 예 | — | [실측] |
| 가동 시간 | `system.uptime` | 3, 초 | 지원 | 예(10분 미만이면 재시작 트리거) | — | [교차일치] |
| 부팅 시각 | `system.boottime` | — | **미지원** | — | 대신 `wmi.get[root\cimv2,"select LastBootUpTime from Win32_OperatingSystem"]` | [실측·미지원] [실측] |

### 6.2 CPU

| 데이터 | Item key | 타입·단위 | Windows | 기본 템플릿 | 별도 설정 | 검증 |
|---|---|---|---|---|---|---|
| CPU 사용률 | `system.cpu.util` | 0, % | 지원(type=system만) | 예(5분 최소 >90% 경고) | — | [실측] |
| 코어별 사용률 | `system.cpu.util[N]` | 0, % | 지원 | 아니요 | 추가 | [실측] |
| 유형별 사용률 | `system.cpu.util[,user]` | — | **미지원**("Invalid second parameter.") | — | 아래 성능 카운터 사용 | [실측·미지원] |
| 사용자/커널 시간 | `perf_counter_en["\Processor Information(_total)\% User Time"]`, `...% Privileged Time` | 0, % | 지원 | 예(커널 >30% 경고) | — | [실측] |
| 인터럽트/DPC | `...% Interrupt Time`, `...% DPC Time` | 0, % | 지원 | 예(인터럽트 >50%) | — | [실측] |
| 큐 길이 | `perf_counter_en["\System\Processor Queue Length"]` | 0, 개 | 지원 | 예(5분 최소 − 코어×2 > 3) | — | [실측] |
| 논리 CPU 수 | `system.cpu.num` / `wmi.get[root/cimv2,"Select NumberOfLogicalProcessors from Win32_ComputerSystem"]` | 3 | 지원 | WMI 쪽이 템플릿 | — | [교차일치] |

### 6.3 메모리

| 데이터 | Item key | 타입·단위 | Windows | 기본 템플릿 | 별도 설정 | 검증 |
|---|---|---|---|---|---|---|
| 전체 | `vm.memory.size[total]` | 3, B | 지원 | 예 | — | [교차일치] |
| 사용률 | `vm.memory.size[pused]` | 0, % | 지원 | 템플릿은 계산 항목 `vm.memory.util` (5분 최소 >90% 평균 심각도) | — | [실측] |
| 커밋(가상 메모리) | `vm.vmemory.size[pused]` 등 | 0 % / 3 B | Windows 전용 | 아니요 | 추가 | [실측] |
| 페이지 파일 사용률 | `perf_counter_en["\Paging file(_Total)\% Usage"]` | 0, % | 지원 | 예(여유 <20% 경고) | — | [교차일치] |
| 페이지 파일 여유 | `system.swap.size[,free]` | — | 값이 0으로 틀림 | — | **사용 금지** | [주의] |

### 6.4 디스크

| 데이터 | Item key | 타입·단위 | Windows | 기본 템플릿 | 별도 설정 | 검증 |
|---|---|---|---|---|---|---|
| 파일시스템 전체 정보 | `vfs.fs.get` | 4, JSON | 지원 | 예(마스터 항목) | — | [실측] |
| 드라이브 사용률 | `vfs.fs.dependent.size[{#FSNAME},pused]` | 0, % | 지원 | 예(>80% 경고, >90% 평균, 5분 최소) | — | [서버 필요] [C:,pused] [실측] |
| 읽기/쓰기 횟수 | `perf_counter_en["\PhysicalDisk(0 C:)\Disk Reads/sec",60]`, `Disk Writes/sec` | 0, 회/초 | 지원 | 예 | — | [실측] |
| 디스크 바쁨 | `...% Idle Time` → 템플릿이 `100 − 값` | 0, % | 지원 | 예(15분 최소 >95%) | — | [실측] |
| 응답 시간 | `...Avg. Disk sec/Read`, `Avg. Disk sec/Write` | 0, 초 | 지원 | 예(15분 최소 >0.02초) | — | [실측] |

### 6.5 네트워크

| 데이터 | Item key | 타입·단위 | Windows | 기본 템플릿 | 별도 설정 | 검증 |
|---|---|---|---|---|---|---|
| 물리 어댑터 정보 | `wmi.getall[root\cimv2,"select Name,Description,NetConnectionID,Speed,AdapterTypeId,NetConnectionStatus,GUID from win32_networkadapter where PhysicalAdapter=True and NetConnectionStatus>0"]` | 4, JSON | 지원 | 예(인터페이스 탐색·속도·상태의 원천) | — | [실측] |
| 수신/송신 | `net.if.in["{#IFGUID}"]`, `net.if.out["{#IFGUID}"]` | 3, 누적 바이트 → 템플릿 전처리 "초당 변화 ×8" = bps | 지원 | 예(15분 평균 > 속도의 90%) | — | [교차일치] |
| 링크 상태 | `net.if.status["{#IFGUID}"]` (WMI 종속) | 3 | 지원 | 예(Link down) | — | [서버 필요] [실측] |
| 인터페이스 지정 방식 | `net.if.in["<장치 설명 이름>"]` / `net.if.in["이더넷"]` | | 설명 이름 성공 / **한글 연결 이름 실패** | — | GUID 권장 | [실측] |
| TCP 연결 | `net.tcp.port[<host>,<port>]` | 3, 1/0 | 지원 | 아니요 | 추가 | [실측] |

### 6.6 Windows 서비스·프로세스

| 데이터 | Item key | 타입·단위 | Windows | 기본 템플릿 | 별도 설정 | 검증 |
|---|---|---|---|---|---|---|
| 서비스 탐색 | `service.discovery` | JSON | Windows 전용 | 예(자동/지연 자동만 필터) | — | [실측] [주의] |
| 서비스 상태 | `service.info["{#SERVICE.NAME}",state]` | 3 | Windows 전용 | 예(3회 연속 ≠0이면 평균) | — | [실측] |
| 시작 유형 | `service.info[<name>,startup]` | 3 | Windows 전용 | 아니요 | 추가 | [실측] |
| 멈춘 자동 서비스 | `services[automatic,stopped]` | 4, 줄 목록(없으면 0) | Windows 전용 | 아니요 | 추가 | [교차일치] |
| 프로세스 수 | `proc.num[]`, `proc.num[<name>]` | 3 | 지원 | `proc.num[]`만 | — | [교차일치] |
| 프로세스 요약 | `proc.get[,,,summary]` | 4, JSON | 지원(cmdline 미지원) | 아니요 | **추가 권장** | [교차일치] |
| 특정 프로세스 상세 | `proc_info[<name>,wkset\|utime\|io_read_b…,sum]` | 0 | Windows 전용 | 아니요 | 추가 | [실측] |
| 프로세스별 CPU 스냅샷 | `wmi.getall[root\cimv2,"select Name,IDProcess,PercentProcessorTime,WorkingSetPrivate from Win32_PerfFormattedData_PerfProc_Process where Name<>'_Total' and Name<>'Idle' and PercentProcessorTime>0"]` | 4, JSON | 지원 | 아니요 | 추가(조회 351 ms) | [실측] |

### 6.7 이벤트 로그 (액티브 전용)

| 데이터 | Item key | 타입·단위 | Windows | 기본 템플릿 | 별도 설정 | 검증 |
|---|---|---|---|---|---|---|
| System 로그 | `eventlog[System,,"Warning\|Error\|Critical"]` | 2(log) | Windows 전용, **액티브만** | **아니요** | **추가 필요** (Zabbix agent (active) 유형, 정보 유형 Log) | [실측] |
| Application 로그 | `eventlog[Application,,"Error\|Critical"]` | 2 | 위와 같음 | 아니요 | 추가 필요 | [실측] |
| 건수 | `eventlog.count[System,,"Warning\|Error\|Critical"]` | 3 | 위와 같음 | 아니요 | 추가 | [실측] |

- 심각도 숫자 [실측]: Windows 경고(Level 3) → `severity` 2, 오류(Level 2) → 4. 이벤트 ID·소스는 74건 모두 원본과 같음.
- `mode`를 `skip`으로 두면 새 Item이 과거 로그를 모두 보내지 않는다 [문서]. 이번 검증은 읽기 시작 위치(`lastlogsize` = 레코드 번호)를 최근 300개 앞으로 지정했다.
- 조건에 맞지 않는 레코드는 값 없이 읽기 위치만 갱신하는 데이터가 온다 [실측] — 수집 건수 계산 시 제외.
- 메시지 본문에 **사용자 계정명과 SID가 그대로** 들어 있다 [실측] → 9절 마스킹.
- 잡음 [실측]: 3.2일치 System 경고·오류 74건 중 68건(92%)이 `DistributedCOM 10016`, Application 오류 6건 중 5건이 `PerfNet 2004`(성능 카운터 조회 부작용). 분석 전에 잡음 목록으로 거른다.

---

## 7. Zabbix API 메서드와 요청 예시

> 이 절은 7.0 공식 문서와 7.0 소스(`ui/include/classes/api/services/*.php`) 기준이다. 요청 본문 10개는 `docs/zabbix/api-requests/`에 있다.

### 7.1 공통 규칙

| 항목 | 내용 |
|---|---|
| 엔드포인트 | `POST https://<프론트엔드 주소>/api_jsonrpc.php` (프론트엔드가 `/zabbix` 아래면 `/zabbix/api_jsonrpc.php`) |
| 헤더 | `Content-Type: application/json-rpc`(또는 `application/json`), `Authorization: Bearer <토큰>` |
| 요청 | `{"jsonrpc":"2.0","method":"<메서드>","params":{...},"id":1}` — `id`가 없으면 알림으로 처리돼 응답이 없다 |
| 성공 응답 | `{"jsonrpc":"2.0","result":...,"id":1}` |
| 오류 응답 | `{"jsonrpc":"2.0","error":{"code":-32602,"message":"Invalid params.","data":"<이유>"},"id":1}` |
| 버전 확인 | `apiinfo.version` — **인증 없이** 호출. API 버전 = Zabbix 버전 |
| 공통 파라미터 | `output`(필드 목록 또는 `"extend"`), `filter`(정확히 일치), `search`(부분 일치), `limit`, `sortfield`, `sortorder`, `countOutput`, `preservekeys` |
| 값 형식 | 숫자·ID·시각이 모두 문자열. `clock`은 Unix 초(UTC), `ns`는 나노초 |
| 성능 | 필요한 필드만 `output`에 적고 시간 범위와 `limit`을 항상 준다 |

버전별 차이:

| 변경 | 7.0 | 7.2 | 7.4 |
|---|---|---|---|
| 요청 본문 `auth` | 폐기 예정(동작) | **삭제** | 없음 |
| `Authorization: Bearer` 헤더 | 지원(7.0.7+ CORS, 7.0.11+ 헤더 대소문자 무관) | 지원 | 지원 |
| `host.get`/`trigger.get`의 `selectGroups` | 폐기 예정 → `selectHostGroups` | **삭제** | 없음 |
| `event.get`의 `select_acknowledges`, `select_alerts` | 폐기 예정 → `selectAcknowledges`, `selectAlerts` | **삭제** | 없음 |
| `item.get`의 `selectItemDiscovery` 등 | 사용 | 사용 | 폐기 예정 → `selectDiscoveryData` 등 |

→ 처음부터 Bearer 헤더, `selectHostGroups`, `selectAcknowledges`만 쓰면 7.0~7.4 모두 동작한다.

### 7.2 host.get — 어떤 호스트를 감시하는가
- 용도: 호스트 목록, 상태, 인터페이스 가용성, 호스트 그룹, 연결된 템플릿, 태그. 읽기 권한이 있는 호스트 그룹의 호스트만 반환.
- 주요 파라미터: `hostids`, `groupids`, `filter`, `search`, `selectInterfaces`, `selectHostGroups`, `selectParentTemplates`, `selectTags`, `limit` (전체 목록은 공식 문서).

```json
{"jsonrpc":"2.0","method":"host.get","id":2,"params":{
  "output":["hostid","host","name","status","active_available","maintenance_status"],
  "selectInterfaces":["interfaceid","type","main","useip","ip","dns","port","available","error"],
  "selectHostGroups":["groupid","name"],"selectParentTemplates":["templateid","name"],"selectTags":["tag","value"],
  "filter":{"host":["<HOST_NAME_IN_ZABBIX>"]},"sortfield":"host","limit":50}}
```
응답 구조 [문서]:
```json
{"jsonrpc":"2.0","id":2,"result":[{
  "hostid":"10084","host":"<기술 이름>","name":"<표시 이름>","status":"0","active_available":"1","maintenance_status":"0",
  "interfaces":[{"interfaceid":"1","type":"1","main":"1","useip":"1","ip":"<ip>","dns":"","port":"10050","available":"1","error":""}],
  "hostgroups":[{"groupid":"2","name":"<그룹>"}],
  "parentTemplates":[{"templateid":"10081","name":"Windows by Zabbix agent active"}],
  "tags":[{"tag":"owner","value":"<담당>"}]}]}
```
- 필드: `status` 0 감시 중 / 1 해제, `active_available` 0 알 수 없음 / 1 가용 / 2 불가, `interfaces[].available`·`error`(패시브), `maintenance_status`.
- 주의: 인터페이스 `ip`는 민감 정보로 다룬다. 읽기 전용 사용자는 템플릿 그룹 권한이 없으면 `parentTemplates`가 빈 배열이다.

### 7.3 item.get — 어떤 지표를 수집하는가
- 용도: Item 목록, key, 타입, 단위, 보관 기간, 최근 값, 미지원 여부. `history.get` 전에 **`itemid`와 `value_type`을 얻는 단계**.
- 주요 파라미터: `hostids`, `itemids`, `search`(예: `{"key_":"system.cpu"}`), `filter`(예: `{"state":1}`), `monitored`, `selectHosts`, `selectTriggers`, `sortfield`(itemid, name, key_ 등).

```json
{"jsonrpc":"2.0","method":"item.get","id":3,"params":{
  "output":["itemid","key_","name","type","value_type","units","delay","history","trends","status","state","error","lastclock","lastvalue"],
  "hostids":"<hostid>","sortfield":"key_"}}
```
응답 예 [문서 발췌]:
```json
{"itemid":"42269","type":"18","hostid":"10084","name":"CPU utilization","key_":"system.cpu.util",
 "delay":"0","history":"7d","trends":"365d","status":"0","value_type":"0","units":"%",
 "master_itemid":"42264","state":"0","error":"","lastclock":"0","lastns":"0","lastvalue":"0","prevvalue":"0"}
```
- 필드: `type` 0 Zabbix agent, 7 Zabbix agent (active), 15 계산, 18 종속 항목 / `value_type` 0 float, 1 character, 2 log, 3 unsigned, 4 text, 5 binary / `status` 0 사용, 1 사용 안 함 / `state` 0 정상, **1 미지원**(`error`에 이유) / `history` 기본 31d, `trends` 기본 365d(숫자형만).
- 주의: `lastvalue`·`lastclock`·`prevvalue`는 기본적으로 **최근 24시간 안의 값만** 보여 준다(관리 > 일반 > Max history display period). 탐색(LLD)으로 만든 Item(디스크·인터페이스·서비스)은 key에 실제 이름이 들어가므로 `search`로 찾는다(예: `vfs.fs.dependent.size[C:,pused]`).

### 7.4 history.get — 장애 전후의 원시 값
- 용도: 수집된 값 하나하나(시계열). 장애 시각 ±N분의 CPU·메모리·디스크 변화, 이벤트 로그 본문.
- 파라미터: `history`(정수 **하나**: 0 float, 1 character, 2 log, 3 unsigned **기본값**, 4 text, 5 binary), `itemids`/`hostids`, `time_from`/`time_till`(Unix 초), `sortfield`(`itemid`, `clock`, `ns`), `sortorder`, `limit`, `output`, `countOutput`, `filter`, `search`(log 타입은 `source`·`severity`·`logeventid` 필터 가능).

```json
{"jsonrpc":"2.0","method":"history.get","id":4,"params":{
  "output":"extend","history":0,"itemids":["<cpu itemid>","<fs pused itemid>"],
  "time_from":<장애시각-3600>,"time_till":<장애시각+900>,
  "sortfield":"clock","sortorder":"ASC","limit":5000}}
```
응답 [문서]: `{"jsonrpc":"2.0","id":4,"result":[{"itemid":"23296","clock":"1351090996","value":"0.085","ns":"563157632"}]}`

| value_type | 응답 필드 |
|---|---|
| 0 float / 3 unsigned / 1 character | `itemid`, `clock`, `ns`, `value` |
| 4 text | `id`, `itemid`, `clock`, `ns`, `value` |
| 2 log (이벤트 로그) | `id`, `itemid`, `clock`, `ns`, `value`(메시지), `source`, `severity`, `logeventid`(이벤트 ID), `timestamp`(원본 이벤트 시각) |

- 주의: **value_type이 다른 Item을 한 번에 조회할 수 없다**(타입별로 나눠 호출, 타입이 틀리면 오류 없이 빈 결과). 보관 기간(기본 31d)이 지나면 하우스키퍼가 지운다. 값은 서버 전처리 **후** 값이다(네트워크는 누적 바이트가 아니라 bps). `limit` 없이 긴 기간을 부르면 응답이 커지므로 장애 분석은 ±1시간 정도로 자른다.

### 7.5 trend.get — 장기 추세(시간 단위 집계)
- 용도: 1시간 단위 `min/avg/max/num`. 평소(지난 7일 같은 시간대) 비교, 디스크 증가 추세.
- 파라미터 [문서]: `itemids`, `time_from`, `time_till`, `limit`, `output`, `countOutput` — **`sortfield`·`sortorder` 없음**.

```json
{"jsonrpc":"2.0","method":"trend.get","id":7,"params":{
  "output":["itemid","clock","num","value_min","value_avg","value_max"],
  "itemids":["<cpu itemid>","<mem itemid>"],"time_from":<now-604800>,"time_till":<now>,"limit":5000}}
```
응답 [문서]: `{"itemid":"23715","clock":"1446199200","num":"60","value_min":"0.165","value_avg":"0.2168","value_max":"0.35"}` — `clock`은 그 시간의 시작.

| | history.get | trend.get |
|---|---|---|
| 단위 | 값 하나하나 | 1시간 집계(min/avg/max/개수) |
| 대상 타입 | 0~5, 한 번에 한 타입 | 숫자형(0, 3)만. 문자·로그 Item은 무시 |
| 보관 | 짧게(기본 31d) | 길게(기본 365d) |
| 지연 | 수집 즉시 | **최대 2시간** 뒤에 보임 |
| 정밀도 | 원값 | unsigned 평균은 정수 반올림 |
| 정렬 | `sortfield` 있음 | 없음 → 클라이언트에서 `clock` 정렬 |

### 7.6 problem.get — 지금 열려 있는 장애
- 용도: 해결되지 않은 문제(+ 최근 해결된 문제). 알람 수신의 시작점.
- 주요 파라미터: `hostids`, `objectids`(트리거 ID), `severities`, `recent`, `eventid_from`/`eventid_till`, `time_from`/`time_till`, `selectAcknowledges`, `selectTags`, `sortfield`(**eventid만**)
- `recent`: `true` = 미해결 + `ok_period` 안에 해결된 것, 생략 = 미해결만.

```json
{"jsonrpc":"2.0","method":"problem.get","id":8,"params":{
  "output":"extend","hostids":"<hostid>","eventid_from":"<마지막으로 본 eventid+1>",
  "selectTags":"extend","selectAcknowledges":["clock","message","action"],
  "sortfield":["eventid"],"sortorder":"ASC","limit":100}}
```
응답 [문서]:
```json
{"eventid":"1245463","source":"0","object":"0","objectid":"15112","clock":"1472457242","ns":"209442442",
 "r_eventid":"1245468","r_clock":"1472457285","r_ns":"125644870","correlationid":"0","userid":"1",
 "name":"Zabbix agent on localhost is unreachable for 5 minutes","acknowledged":"1","severity":"3",
 "cause_eventid":"0","opdata":"","suppressed":"1",
 "acknowledges":[...],"suppression_data":[...],"tags":[{"tag":"test-tag","value":"test-value"}]}
```
- 필드: `objectid` = 트리거 ID, `severity` 0 미분류 / 1 정보 / 2 경고 / 3 평균 / 4 높음 / 5 재해, `r_eventid` ≠ "0"이면 해결됨, `cause_eventid` ≠ "0"이면 다른 문제의 증상.
- 주의: **호스트 정보가 없다** → 7.7/7.8로 보강. 오래전에 해결된 문제는 problem 테이블에 없으므로 `event.get`을 쓴다.

### 7.7 event.get — 발생·복구 이력
- 용도: 기간 내 문제(value=1)·복구(value=0) 이벤트 이력, 같은 트리거의 반복 횟수, 호스트·트리거 정보.
- 주요 파라미터: `hostids`, `objectids`, `value`, `time_from`/`time_till`, `problem_time_from`/`problem_time_till`, `selectHosts`, `selectRelatedObject`, `selectTags`, `sortfield`(eventid, objectid, clock)

```json
{"jsonrpc":"2.0","method":"event.get","id":9,"params":{
  "output":["eventid","source","object","objectid","clock","value","severity","name","r_eventid","acknowledged"],
  "hostids":"<hostid>","source":0,"object":0,"value":[0,1],
  "time_from":<now-604800>,"time_till":<now>,
  "selectHosts":["hostid","host","name"],
  "selectRelatedObject":["triggerid","description","priority","value"],
  "selectTags":"extend","sortfield":["clock","eventid"],"sortorder":"DESC","limit":100}}
```
- 필드: `source` 0 트리거 / 1 탐색 / 2 자동 등록 / 3 내부 / 4 서비스, `value`(트리거) 0 OK / 1 문제, `r_eventid` 복구 이벤트 ID. 하우스키퍼가 지우기 전까지는 삭제된 대상의 이벤트도 나올 수 있다.

### 7.8 trigger.get — 장애 감지 규칙
- 용도: 장애 판단 조건(식, 심각도), 트리거가 보는 Item, 현재 문제 상태. problem → **관련 Item** 역추적.
- 주요 파라미터: `triggerids`, `hostids`, `itemids`, `only_true`, `min_severity`, `filter`(예: `{"value":1}`), `expandDescription`, `expandExpression`, `selectHosts`, `selectItems`, `selectFunctions`, `selectTags`

```json
{"jsonrpc":"2.0","method":"trigger.get","id":10,"params":{
  "triggerids":"<problem.objectid>",
  "output":["triggerid","description","priority","value","status","state","lastchange","error","expression"],
  "expandDescription":true,"expandExpression":true,
  "selectItems":["itemid","key_","value_type","units"],"selectHosts":["hostid","host"],"selectTags":"extend"}}
```
- 필드: `value` 0 OK / 1 문제, `priority` = 심각도(0~5), `status` 0 사용 / 1 사용 안 함, `state` 0 최신 / 1 알 수 없음. `expandExpression` 없이 받으면 `{13513}` 같은 함수 ID로 나온다.

### 7.9 인증
- 권장: API 토큰(프론트엔드 Users > API tokens에서 생성, 값은 생성 직후 한 번만 보임). 모든 요청에 `Authorization: Bearer <token>`.
- 대안: `user.login`(세션, 끝나면 `user.logout` 필요, MFA 사용자 그룹이면 불가). **읽기 전용 클라이언트에서는 쓰지 않는다.**
- 버전 확인: `{"jsonrpc":"2.0","method":"apiinfo.version","params":{},"id":1}` (인증 없이).

---

## 8. 실제로 받은 데이터 예시 [실측]

패시브 체크 응답 (Zabbix 7.0 JSON 프로토콜, 원시 바이트로 확인):
```json
{"version":"7.0.31","variant":2,"data":[{"value":"[{\"name\":\"chrome.exe\",\"processes\":23,\"vmsize\":3476448,\"wkset\":3879300,\"cputime_user\":3988.875,\"threads\":528,...}]"}]}
```
액티브 체크: 에이전트 → 서버 요청(시작 시)
```json
{"request":"active checks","host":"<HOST_NAME_IN_ZABBIX>","version":"7.0.31","variant":2,"config_revision":0,"ip":"127.0.0.1"}
```
액티브 체크: 이벤트 로그 1건 (본문 생략)
```json
{"id":1,"itemid":1000,"lastlogsize":1743,"value":"<이벤트 메시지 본문 생략: 원문에 사용자 계정명·SID가 포함됨>",
 "source":"Microsoft-Windows-DistributedCOM","eventid":10016,"severity":2,"timestamp":1791683162,
 "clock":1791963690,"ns":153205200}
```
액티브 체크: 숫자 값
```json
{"id":82,"itemid":1003,"value":"9.131499","clock":1791963693,"ns":2064200}
```
- 전송 헤더 플래그가 3(프로토콜+압축)이라 에이전트가 zlib 압축을 쓴다.
- 서버에 저장되면 `history.get(history=2)`에서 `eventid`는 `logeventid`, `timestamp`는 원본 이벤트 시각으로 대응된다 [문서].
- 7절의 `[문서]` 응답은 공식 문서 예시이고, 실서버 호출은 7개 모두 읽기 전용 토큰으로 성공했다(12절). 요청 본문 전체는 `docs/zabbix/api-requests/`.

---

## 9. 인증 및 보안 주의사항

| 구분 | 규칙 |
|---|---|
| 인증 방식 | **API 토큰 + `Authorization: Bearer`**. 비밀번호를 코드에 두는 `user.login`은 쓰지 않는다(쓰면 반드시 `user.logout`). `auth` 본문 속성은 7.2에서 삭제 |
| 전용 사용자 | 사용자 유형 **User**, 프론트엔드 접근 없이 API만. 역할: "Access to API" 사용, "API methods"는 **허용 목록**으로 `host.get, item.get, history.get, trend.get, problem.get, event.get, trigger.get`만. 사용자 그룹: 감시 대상 호스트 그룹에 **읽기(Read)** 권한만. 절차는 `readonly-account.md` |
| 토큰 | 만료일 설정, 값은 생성 직후 한 번만 보이므로 비밀 저장소·환경 변수에만 둔다. 노출되면 Regenerate(기존 값 즉시 무효) |
| 저장소 | 토큰·비밀번호·서버 IP·PSK를 문서·Git에 쓰지 않는다. `.env`는 `.gitignore`에. 요청 로그에 `Authorization` 헤더를 남기지 않는다 |
| 전송 | 프론트엔드는 HTTPS로. 자체 서명 인증서는 실험실에서만 `--insecure` |
| 개인 정보 | 이벤트 로그 메시지(계정명·SID), 인터페이스 IP, 서비스 실행 계정, 프로세스 목록은 외부(LLM 등) 전송·저장 전에 가린다 |
| 에이전트 | `DenyKey=system.run[*]` 기본값 유지(원격 명령 금지). 방화벽은 열지 않거나(액티브 전용) 서버 IP 하나로만 연다. 서버↔에이전트 구간은 기본 평문이므로 PSK 검토 |
| 클라이언트 정책 | 조회 전용. `*.create/update/delete`, `script.execute`, `event.acknowledge`는 역할에서 막아 둔다 |

---

## 10. 장애 유형별 조회 매핑

원칙: 데이터로 확인되는 것은 **사실**, 사이를 잇는 설명은 **추정**으로 나눈다. 데이터가 없으면 "추가 수집 필요"로 남긴다. 기본 시간 범위: 상세 = 장애 시각 **−60분 ~ +15분** history, 기준선 = 직전 **7일** trend(같은 시간대), 재발 = 직전 **30일** event.

| 유형 | 템플릿 감지 | 조회 | 추가로 필요한 데이터 | 추정은 이때만 |
|---|---|---|---|---|
| CPU 지속 상승 | `min(system.cpu.util,5m) > 90`, 큐 길이, 커널 >30%, 인터럽트 >50% | `trigger.get` → `item.get`(`system.cpu.util`, `% User/Privileged/Interrupt/DPC Time`, `Processor Queue Length`, `Context Switches/sec`) → `history.get(0)` → `trend.get` 7일 | **프로세스별 CPU**(기본 템플릿에 없음 → `proc.get[,,,summary]` 1분 주기로 `cputime` 차분, 또는 WMI 스냅샷 Item), 같은 시각 이벤트 로그 | 원인 프로세스는 프로세스별 데이터가 있을 때만. 인터럽트·DPC 높음 → 하드웨어·드라이버, 사용자 시간 높음 → 앱 |
| 메모리 부족·급증 | `min(vm.memory.util,5m) > 90`, `Pages/sec` >1000, `Free System Page Table Entries` <5000, 페이지 파일 여유 <20% | `vm.memory.size[used/available/pused]`, `vm.vmemory.size[pused]`, `Paging file % Usage`, `Pages/sec`, `Pool Nonpaged Bytes` history, trend 7일 | 프로세스별 `vmsize`(= Private KB)·`wkset` 변화(`proc.get` summary), 앱 오류 로그 | 누수는 꾸준한 증가 기울기일 때, 원인 프로세스는 프로세스별 데이터가 있을 때만. `system.swap.size[,free]`는 쓰지 않는다 |
| 디스크 공간 부족 | `min(vfs.fs.dependent.size[{#FSNAME},pused],5m)` >90(평균) / >80(경고) | `vfs.fs.dependent.size[C:,pused/free/used/total]` history 6~24시간, trend 7~30일, `Disk Write Bytes/sec` | **어느 폴더가 커졌는가**(기본 수집 없음 → 로그·임시 폴더에 `vfs.dir.size[<경로>]` 검토, 조회 비용 큼) | 가득 찰 시각은 선형 외삽, 원인(로그 폭증 등)은 폴더 크기 데이터가 있을 때만 |
| 네트워크 단절 | `zabbix[host,active_agent,available]=2`(5분), `nodata(agent.ping,30m)`; 패시브 `zabbix[host,agent,available]=0`(3분); Link down; 오류율 >2; 대역폭 >90% | `host.get`(`active_available`, `interfaces.available/error`), `net.if.in/out[...,errors\|dropped]`, `net.if.status`, `event.get` 같은 시간대 다른 호스트 문제 | 같은 네트워크 다른 호스트 상태, 서버 측 ICMP 핑 항목, 복구 후 `system.uptime`, 의존 서비스 `net.tcp.port`·`net.dns` | PC 꺼짐 / 네트워크 / 에이전트 중지는 에이전트 데이터만으로 **구분할 수 없다**. `EnablePersistentBuffer=1`이면 단절 동안 값이 복구 후 들어옴(미검증) |
| 서비스 중지 | `min(service.info["{#SERVICE.NAME}",state],#3) <> 0`(3회 연속) | `service.info[...,state/startup]` history, `services[automatic,stopped]`, System 이벤트 로그 history(`history=2`) −30~+5분 | 서비스 제어 관리자 이벤트(**이벤트 로그 Item 추가 필요**), 앱 로그, 의존 관계 | 중지 이유는 이벤트 로그가 있을 때만. 평소에도 멈춰 있는 자동 시작 서비스(지연·트리거 시작형)는 기준선에서 뺀다 |
| 재부팅·이벤트 로그 이상 | `last(system.uptime) < 10m`; 추가 Item `eventlog.count[System,,"Error\|Critical"]` 급증 | `system.uptime` history, WMI 부팅 시각, 이벤트 로그 −30분~+10분, `event.get` 30일 | 계획된 재시작 여부(업데이트·사용자 종료 이벤트), 직전 리소스 history | 계획/비계획과 원인은 해당 이벤트 기록이 있을 때만. 잡음 `DistributedCOM 10016`, `PerfNet 2004`는 기본 제외 |

---

## 11. 연동 구현 참고

- **연동 방식**: 폴링(10~30초마다 `problem.get(eventid_from=커서+1)`)이 기본이다. 읽기 전용 토큰만 있으면 되고 Zabbix 설정 변경이 없다. 웹훅(push)은 Zabbix 액션·미디어 타입 설정과 수신 엔드포인트가 필요하다(미검증).
- **처리 순서 (장애 1건)**
```
1. 새 문제      problem.get {eventid_from: cursor+1, sortfield: eventid ASC}         -> 커서 갱신
2. 트리거       trigger.get {triggerids: objectid, selectHosts, selectItems, selectTags, expandDescription, expandExpression}
3. 호스트       host.get {hostids, selectInterfaces, selectHostGroups, selectTags}    (캐시 5분)
4. Item 목록    item.get {hostids, output: itemid/key_/value_type/units/history}      (호스트별 캐시 1시간, LLD 변화 대비)
5. 시계열       history.get x value_type별 {itemids, time_from: clock-3600, time_till: clock+900}
6. 기준선       trend.get {itemids(숫자형), time_from: now-7d}                        -> clock 정렬
7. 로그         history.get {history: 2, itemids: eventlog Items, clock-1800 ~ clock+300} -> 잡음 필터·마스킹
8. 재발         event.get {objectids: triggerid, value: 1, time_from: now-30d, countOutput 또는 limit}
9. 해결 추적    problem.get {eventids: 열린 것들, recent: true} -> r_eventid != "0" 이면 해결 (없으면 event.get {eventids})
```
- **구현 규칙**

| 규칙 | 내용 |
|---|---|
| 형 변환 | `value_type` 0 → float, 3 → int, 1/4 → str, 2 → 로그 객체. `clock` → int → UTC datetime |
| history 분할 | itemid를 value_type별로 묶어 타입마다 한 번씩 호출 |
| trend 정렬 | 응답 순서 보장 없음 → `clock` 정렬 |
| 단위 | `item.units`를 같이 저장(%, B, bps). 네트워크 history는 이미 bps |
| 캐시 | itemid·value_type은 호스트별로 캐시하되 LLD로 바뀔 수 있어 1시간마다 갱신 |
| 미지원 Item | `item.state == "1"`이면 분석 입력에서 빼고 `error`를 "빠진 데이터"에 기록 |
| 오류 처리 | JSON-RPC `error`는 재시도하지 않고 기록(권한·파라미터), 네트워크 오류·5xx만 지수 백오프 재시도 |
| 범위 제한 | 모든 history 호출에 `time_from/time_till`과 `limit` |
| 버전 확인 | 시작 시 `apiinfo.version`을 기록, 버전별 코드 경로는 만들지 않는다(7.1 표의 공통 부분만 사용) |
| 읽기 전용 | `*.get`과 `apiinfo.version` 외 메서드 호출 금지 |

- 값의 출처(`trend.get`, `history.get`)와 빠진 데이터를 같이 넘겨, 소비자가 없는 데이터를 추측으로 메우지 않게 한다. 시각은 Unix 초를 UTC ISO 8601로 바꿔 저장하고 표시할 때만 현지 시각으로 바꾼다.

---

## 12. 검증 결과와 남은 항목

### 12.1 로컬 서버 검증 결과
| 항목 | 결과 |
|---|---|
| 서버 | Docker의 `zabbix-server-pgsql`·`web-nginx-pgsql` `alpine-7.0.31` + postgres 16. `apiinfo.version` = 7.0.31. 첫 기동 직후 약 10초간 `Unable to select configuration.`(스키마 생성 중) |
| 에이전트 | MSI 7.0.31 서비스 `Zabbix Agent 2`(Running, Automatic), `Server=127.0.0.1`, `ServerActive=127.0.0.1:10051`, `ListenIP=127.0.0.1`, 방화벽 규칙 0 |
| API 7개 | 읽기 전용 토큰으로 전부 성공(각 135~218 ms). item 51개, history type0 4건·type3 11건, trend 0건(1시간 미만이라 정상), problem 1건, event 1건, trigger 19개 중 문제 1 |
| 감지된 장애 | `Windows: FS [(C:)]: Space is critically low (used > 90%, total 111.1GB)`, severity 3 — 에이전트 → 트리거 → problem.get까지 실제로 이어짐 |
| 기타 | 읽기 전용 토큰으로 `user.get` 호출 시 `No permissions`(허용 목록 동작), 설치 파일 SHA256·서명 일치, 키 116개 × 2회 패시브 수집, 교차 비교 14개 중 13개 일치, 액티브 이벤트 로그 74/74 일치, `proc.get` CPU 시간 = 초·메모리 = KB, 서비스 설명 한글은 에이전트 단계에서 깨짐 |

### 12.2 미검증·남은 항목
| 항목 | 이유 | 다음 할 일 |
|---|---|---|
| 공용 서버 연결 | 로컬 서버로만 확인, 패시브는 의도적으로 미사용 | conf의 `Server`/`ServerActive`만 바꾸고 서비스 재시작, 4.2절 체크리스트 |
| 템플릿 Item의 실제 `value_type`·`units`·보관 기간 | 서버에 템플릿을 연결해야 보임 | `item.get` 결과로 6절 표 갱신 |
| `trend.get` | 1시간 이상 지나야 생김 | 2시간 뒤 재확인 |
| TLS 오류 문구 | TLS 미사용 | PSK 도입 시 확인 |
| 웹훅 방식, `EnablePersistentBuffer` | 서버 설정·단절 시나리오 필요 | 서버 연결 후 시험 |
| 한글 UI Windows의 `perf_counter`(현지어) | 검증 PC UI가 영어 | 한글 UI PC에서 `perf_counter_en` 정상 여부 확인 |
| 장시간 수집 부하 | 몇 분만 실행 | 서비스 설치 후 에이전트 CPU·메모리 확인 |

---

## 13. 공식 참고 문서 (7.0)

- 에이전트 다운로드·체크섬: https://www.zabbix.com/download_agents , https://cdn.zabbix.com/zabbix/binaries/stable/7.0/7.0.31/
- 버전 호환·수명: https://www.zabbix.com/documentation/7.0/en/manual/appendix/compatibility , https://www.zabbix.com/life_cycle_and_release_policy
- 설치: https://www.zabbix.com/documentation/7.0/en/manual/installation/install_from_packages/win_msi , .../appendix/install/windows_agent
- Agent 2 Windows 설정: https://www.zabbix.com/documentation/7.0/en/manual/appendix/config/zabbix_agent2_win
- Windows Item key: https://www.zabbix.com/documentation/7.0/en/manual/config/items/itemtypes/zabbix_agent/win_keys , `proc.get`: .../appendix/items/proc_get
- 패시브·액티브 프로토콜: https://www.zabbix.com/documentation/7.0/en/manual/appendix/items/activepassive
- 템플릿 README: https://raw.githubusercontent.com/zabbix/zabbix/release/7.0/templates/os/windows_agent_active/README.md
- API 개요·인증: https://www.zabbix.com/documentation/7.0/en/manual/api , 메서드: .../api/reference/(host|item|history|trend|problem|event|trigger)/get
- 권한·역할·토큰: .../manual/config/users_and_usergroups/permissions , .../web_interface/frontend_sections/users/user_roles , .../users/api_tokens
- API 변경 이력: .../manual/api/changes (7.0 / 7.2 / 7.4)
- API 소스(7.0): https://github.com/zabbix/zabbix/tree/release/7.0/ui/include/classes/api/services (`CHistory.php`, `CTrend.php`, `CProblem.php`)
