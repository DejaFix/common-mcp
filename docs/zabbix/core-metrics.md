# 핵심 서버 리소스 지표: CPU / MEM / DISK / Network

> 한 줄 요약: CPU/MEM/DISK/Network 4분류 핵심 지표의 Item key·단위·장애 기준과 API 조회 순서.

- 작성: 2026-10-14 · 대상: Windows PC `demo-host-01`, Zabbix 7.0.31(로컬 Docker) + Agent 2 7.0.31, 템플릿 `Windows by Zabbix agent active`
- 목적: 상세 명세서(`windows-agent-api.md`)는 Windows에서 수집할 수 있는 것을 넓게 조사했다. 이 문서는 **일반적인 서버 리소스 관리에 필요한 4분류만** 추린 기준표다. 플랫폼 1차 구현은 이 표만 쓴다.
- 값은 2026-10-14 18:0x에 Zabbix API(`item.get`의 `lastvalue`)로 받은 실측값이다.

## 직접 확인하는 법

| 방법 | 실행 | 보이는 것 |
|---|---|---|
| **대시보드 (권장)** | `powershell -ExecutionPolicy Bypass -File infra\zabbix\tools\start_dashboard.ps1` → 브라우저 http://127.0.0.1:18090. 팀 서버를 바로 보려면 `-Remote <API URL>` (`infra/zabbix/README.md` "대시보드 보기") | CPU/MEM/DISK/NET 4칸: 현재 값, 최근 1시간 그래프와 템플릿 기준선, 보조 지표, 상태(정상/기준 초과/장애/값 없음), 열린 장애. 30초마다 갱신 |
| 점검 스크립트 | `powershell -ExecutionPolicy Bypass -File infra\zabbix\tools\check_zabbix.ps1` | 서버 컨테이너·에이전트·API·연결을 `[OK]/[FAIL]`로, 이어서 핵심 지표 최신 값 |
| Zabbix 웹 | 로컬 서버 http://127.0.0.1:18080 (Admin, 비밀번호는 `setup_local_server.py`의 `--secrets` 파일) 또는 팀 서버 웹 → Monitoring › Latest data / Problems | Zabbix 원래 화면 — 대시보드 값과 같은지 대조 |

데이터 경로: 이 PC → 수집용 Agent 2 7.0.31(사용자 모드, 127.0.0.1) → 로컬 Docker Zabbix 7.0.31 → API(읽기 전용 토큰) → 대시보드 서버(127.0.0.1:18090, 토큰은 브라우저로 안 보냄). 설치된 "Zabbix Agent" 7.0.31 서비스(구형 에이전트, 10050)는 팀 서버용이라 이 경로와 별개다.

## 한눈에

| 분류 | 1차 지표 (장애 판단) | 보조 지표 (원인 좁히기) | 템플릿 장애 기준 | 현재 값 |
|---|---|---|---|---|
| CPU | 사용률 % | 대기열 길이 | 5분 동안 계속 > 90 % | 17.7~21.8 %, 대기열 0 |
| MEM | 사용률 % | 페이지 파일 사용률 % | 5분 동안 계속 > 90 % | 48.7 % (8.3 / 17.1 GB) |
| DISK | 드라이브 사용률 % | 여유 바이트, 읽기/쓰기 지연 | 5분 동안 계속 > 80 % 경고 / > 90 % 평균 | **C: 92.1 % → 지금 장애 발생 중** |
| NET | 송수신 bps | 오류/s, 링크 상태 | 15분 평균 > 속도의 90 %, 오류 > 2/s, 링크 다운 | 수신 81 kbps, 송신 148 kbps, 오류 0 |

## 분류별 Item key

`value_type`: 0 = 실수, 3 = 정수. 단위는 Zabbix `item.units` 기준이다.

### CPU
| 지표 | Item key | 타입·단위 | 의미 | 템플릿 트리거 |
|---|---|---|---|---|
| 사용률 | `system.cpu.util` | 0, % | 1분 평균 CPU 사용률 | `min(...,5m) > 90` (경고) |
| 대기열 길이 | `perf_counter_en["\System\Processor Queue Length"]` | 0 | CPU를 기다리는 스레드 수 — 사용률보다 "밀림"을 직접 보여 줌 | `min(...,5m) − 코어×2 > 3` |

### MEM
| 지표 | Item key | 타입·단위 | 의미 | 템플릿 트리거 |
|---|---|---|---|---|
| 사용률 | `vm.memory.util` | 0, % | 서버 계산 항목 (사용 ÷ 전체) | `min(...,5m) > 90` (평균) |
| 사용 / 전체 | `vm.memory.size[used]`, `vm.memory.size[total]` | 3, B | 바이트 값 | — |
| 페이지 파일 사용률 | `perf_counter_en["\Paging file(_Total)\% Usage"]` | 0, % | 메모리가 부족해 디스크로 밀려난 정도 | 여유 < 20 % (경고) |

`system.swap.size[,free]`는 이 PC에서 0으로 틀리게 나와 쓰지 않는다(템플릿도 위 성능 카운터를 쓴다).

### DISK
| 지표 | Item key | 타입·단위 | 의미 | 템플릿 트리거 |
|---|---|---|---|---|
| 드라이브 사용률 | `vfs.fs.dependent.size[C:,pused]` | 0, % | 드라이브(C:, D: …)별 자동 생성 | `min(...,5m) > 80` 경고, `> 90` 평균 |
| 드라이브 여유 | `vfs.fs.dependent.size[C:,free]` | 3, B | 남은 바이트 → 증가 속도로 가득 찰 시각 추정 | — |
| 읽기/쓰기 지연 | `perf_counter_en["\PhysicalDisk(0 C:)\Avg. Disk sec/Read",60]`, `...sec/Write",60]` | 0, s | 디스크 응답 시간 (Linux의 IO Wait 대신) | `min(...,15m) > 0.02 s` |

디스크 지연 Item은 물리 디스크 탐색(1시간 주기)이 돈 뒤에 생긴다. 18:0x 기준 아직 없음.

### Network
| 지표 | Item key | 타입·단위 | 의미 | 템플릿 트리거 |
|---|---|---|---|---|
| 수신 / 송신 | `net.if.in["{#IFGUID}"]`, `net.if.out["{#IFGUID}"]` | 3, bps | 인터페이스별(GUID) 자동 생성, 서버가 bps로 변환 | 15분 평균 > 속도의 90 % |
| 오류 | `net.if.in["{#IFGUID}",errors]`, `net.if.out[...]` | 3, /s | 패킷 오류율 | `min(...,5m) > 2` |
| 링크 상태 | `net.if.status["{#IFGUID}"]` | 3 | 2 = 연결됨 | 연결 → 끊김으로 바뀌면 |

## 에이전트 자체 상태 (4분류 판단의 전제)
| 지표 | 확인 위치 | 의미 |
|---|---|---|
| 에이전트 연결 | `host.get`의 `active_available` (1 = 가용) | 값이 안 들어오면 4분류 모두 판단 불가 |
| 마지막 수신 시각 | `item.get`의 `lastclock` | 몇 분 넘게 멈추면 단절 의심 |

## 백엔드가 가져오는 방법

1. `item.get` — 호스트의 위 key만 골라 `itemid`, `value_type`, `units`, `lastvalue`, `lastclock` 확보 (최신 값은 이것만으로 충분).
2. `history.get` — 장애 시각 −60분 ~ +15분. **value_type별로 따로** 호출(CPU·MEM %·DISK %는 0, 바이트·bps는 3).
3. `trend.get` — 지난 7일 같은 시간대 평균·최대(평소 대비 비교).
4. `problem.get` → `trigger.get`(`selectItems`)으로 어느 지표 때문에 장애인지 연결.

예시 스크립트: `infra/zabbix/tools/core_metrics.py` (위 표의 key로 최신 값 출력).

## 이번 범위에서 뺀 것 (필요해지면 추가)
프로세스별 CPU·메모리, Windows 서비스 상태, 이벤트 로그, CPU 커널/인터럽트 시간, 컨텍스트 스위치, 메모리 풀·페이지 폴트, 디스크 큐·처리량, DNS·포트 점검. 근거와 실측은 `zabbix-windows-agent-api.md` 5~6절에 그대로 있다.
