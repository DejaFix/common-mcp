# 핵심 서버 리소스 지표: CPU / MEM / DISK / Network

> 한 줄 요약: CPU/MEM/DISK/Network 4분류 핵심 지표의 Item key·단위·장애 기준과 API 조회 순서(Windows + Zabbix Agent 2, 템플릿 `Windows by Zabbix agent active` 기준).

`windows-agent-api.md`는 Windows에서 수집할 수 있는 것을 넓게 조사한 명세다. 이 문서는 일반적인 서버 리소스 관리에 필요한 **4분류만** 추린 기준표다. 검증 환경은 Zabbix 7.0.31 + Agent 2 7.0.31이다. 지표 별칭은 `packs/it/metrics.yaml`에 둔다.

## 직접 확인하는 법
- Zabbix 웹: Monitoring › Latest data / Problems 에서 호스트의 아래 key 값을 본다.
- 연결 점검: `uv run python -m zabbix_ro.probe` (읽기 전용, 환경 변수 `ZABBIX_URL`·`ZABBIX_API_TOKEN`). MCP 5도구 점검은 `python -m mcp_zabbix.live_check`.

## 한눈에

| 분류 | 1차 지표 (장애 판단) | 보조 지표 (원인 좁히기) | 템플릿 장애 기준 |
|---|---|---|---|
| CPU | 사용률 % | 대기열 길이 | 5분 동안 계속 > 90 % |
| MEM | 사용률 % | 페이지 파일 사용률 % | 5분 동안 계속 > 90 % |
| DISK | 드라이브 사용률 % | 여유 바이트, 읽기/쓰기 지연 | 5분 동안 계속 > 80 % 경고 / > 90 % 평균 |
| NET | 송수신 bps | 오류/s, 링크 상태 | 15분 평균 > 속도의 90 %, 오류 > 2/s, 링크 다운 |

## 분류별 Item key

`value_type`: 0 = 실수, 3 = 정수. 단위는 Zabbix `item.units` 기준이다.

### CPU
| 지표 | Item key | 타입·단위 | 의미 | 템플릿 트리거 |
|---|---|---|---|---|
| 사용률 | `system.cpu.util` | 0, % | 1분 평균 CPU 사용률 | `min(...,5m) > 90` (경고) |
| 대기열 길이 | `perf_counter_en["\System\Processor Queue Length"]` | 0 | CPU를 기다리는 스레드 수. 사용률보다 "밀림"을 직접 보여 줌 | `min(...,5m) − 코어×2 > 3` |

### MEM
| 지표 | Item key | 타입·단위 | 의미 | 템플릿 트리거 |
|---|---|---|---|---|
| 사용률 | `vm.memory.util` | 0, % | 서버 계산 항목 (사용 ÷ 전체) | `min(...,5m) > 90` (평균) |
| 사용 / 전체 | `vm.memory.size[used]`, `vm.memory.size[total]` | 3, B | 바이트 값 | — |
| 페이지 파일 사용률 | `perf_counter_en["\Paging file(_Total)\% Usage"]` | 0, % | 메모리가 부족해 디스크로 밀려난 정도 | 여유 < 20 % (경고) |

`system.swap.size[,free]`는 검증 PC에서 0으로 틀리게 나와 쓰지 않는다(템플릿도 위 성능 카운터를 쓴다).

### DISK
| 지표 | Item key | 타입·단위 | 의미 | 템플릿 트리거 |
|---|---|---|---|---|
| 드라이브 사용률 | `vfs.fs.dependent.size[C:,pused]` | 0, % | 드라이브(C:, D: …)별 자동 생성 | `min(...,5m) > 80` 경고, `> 90` 평균 |
| 드라이브 여유 | `vfs.fs.dependent.size[C:,free]` | 3, B | 남은 바이트. 증가 속도로 가득 찰 시각 추정 | — |
| 읽기/쓰기 지연 | `perf_counter_en["\PhysicalDisk(0 C:)\Avg. Disk sec/Read",60]`, `...sec/Write",60]` | 0, s | 디스크 응답 시간 (Linux의 IO Wait 대신) | `min(...,15m) > 0.02 s` |

디스크 지연 Item은 물리 디스크 탐색(1시간 주기)이 돈 뒤에 생긴다.

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

## API 조회 순서

1. `item.get`: 호스트의 위 key만 골라 `itemid`, `value_type`, `units`, `lastvalue`, `lastclock` 확보 (최신 값은 이것만으로 충분).
2. `history.get`: 장애 시각 −60분 ~ +15분. **value_type별로 따로** 호출(CPU·MEM %·DISK %는 0, 바이트·bps는 3).
3. `trend.get`: 지난 7일 같은 시간대 평균·최대(평소 대비 비교).
4. `problem.get` → `trigger.get`(`selectItems`)으로 어느 지표 때문에 장애인지 연결.

## 이 범위에서 뺀 것 (필요해지면 추가)
프로세스별 CPU·메모리, Windows 서비스 상태, 이벤트 로그, CPU 커널/인터럽트 시간, 컨텍스트 스위치, 메모리 풀·페이지 폴트, 디스크 큐·처리량, DNS·포트 점검. 근거와 실측은 `windows-agent-api.md`에 있다.
