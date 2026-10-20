# 팀 Zabbix 서버 버전·설치 방식 (T10, FR-ZBX-001)

> 한 줄 요약: 대상 Zabbix 서버의 버전·OS·설치 방식 확인 결과(7.0 LTS 기준).

> 서버 주소·토큰 값은 이 문서에 적지 않는다(`<서버 주소>`로 표기). 접속 방법은 `access.md`.
> 확인일: 2026-10-16 (Zabbix·MCP 담당). 서버 셸 출력(`lsb_release -a`·`apt list --installed`·`systemctl status`·`journalctl`·`apt history`·`df -h`·`uptime -s`·`last -x`)과 `apiinfo.version` 응답, 데모 PC 에이전트 로그에서 옮겼다. 각 행의 "근거" 칸에 출처를 적었고, 직접 못 본 칸은 `확인 못 함`으로 둔다.

## 확정 값
| 항목 | 값 | 근거 |
|---|---|---|
| Zabbix 서버·프론트 버전 | **7.0.31** | `apiinfo.version` 응답 `"result":"7.0.31"` (2026-10-16 확인) |
| OS | **Ubuntu 24.04.5 LTS (noble)**, 호스트 이름 `<zabbix-server-host>` | `lsb_release -a` |
| 설치 방식 | **apt 패키지(Zabbix 공식 저장소 `zabbix-release` 7.0-5, VM에 직접 설치).** Docker 아님 | `apt list --installed`, 서비스 유닛 `/usr/lib/systemd/system/zabbix-server.service` |
| 데이터베이스 | MariaDB 10.11.14 (PostgreSQL 없음) | `systemctl status mariadb`, `Unit postgresql.service could not be found` |
| 웹 서버 | Apache 2.4.58-1ubuntu8.17 (`apache2`) | `apt history`(2026-10-16 12:39 업그레이드 8.16 → 8.17) |
| 서버 자동 업그레이드 | `unattended-upgrade`가 실행된 기록이 있다(06:05:54·12:39). 타이머·`20auto-upgrades` 설정 파일은 직접 확인 못 함 | `apt history` |
| 에이전트(감시 PC) | Zabbix Agent 7.4.15(데모 PC `Heon-PC`) — 서버(7.0)보다 높은 버전. 같은 날 주입 시험에서 Problem이 정상 발생·해소됨 | 데모 PC의 에이전트 로그(`zabbix_agentd.log`), Zabbix Problems 화면 |
| 웹 경로·포트 | `http://<서버 주소>/zabbix`, **80번**. 트래퍼 10051 | `access.md` |

## `apiinfo.version` 응답 캡처 (토큰 불필요)
```json
{"jsonrpc":"2.0","result":"7.0.31","id":1}
```
요청: `POST http://<서버 주소>/zabbix/api_jsonrpc.php`, 본문 `{"jsonrpc":"2.0","method":"apiinfo.version","params":[],"id":1}`. 이 호출은 인증 없이 되고, 아침 점검과 `/api/health`의 Zabbix 판정(T31)에도 같은 방식이 쓰인다.

## 알아둘 점 (운영 기록 — 상세와 재발 방지 대책은 `incident-2026-10-16-db-stop.md`)
- **2026-10-16 06:05 KST에 MariaDB와 `zabbix-server`가 같은 초에 정지**했고, 낮 12시 이후(정확한 복구 시각은 확인 못 함) 수동으로 복구했다. 웹은 `Database error: No such file or directory`(DB 소켓 파일 없음), API는 `Internal error`를 냈다.
  - MariaDB 로그는 `Normal shutdown (initiated by: unknown)`이고 크래시가 아니었다. 디스크는 `df -h /var/lib` 기준 14% 사용(24GB 여유)이었고, 재부팅은 없었다(`uptime -s` 2026-10-14 16:19). 정지 시각 전후의 `last -x`에도 06:05 접속 기록이 없어 사람이 직접 멈춘 것은 아니다.
  - **유력한 원인: 새벽 자동 업그레이드.** `apt history`에 `unattended-upgrade`가 `systemd`·`udev`·`libsystemd0` 등 255.4-1ubuntu8.17 → 8.18 업그레이드를 **06:05:54에 끝냈고**(`End-Date`), 두 서비스는 그 1초 뒤(06:05:55)에 정지했다. 시각이 맞물리지만 업그레이드가 서비스를 멈춘 경로(패키지 설치 스크립트의 재시작)는 로그로 확인하지 못했다(`/var/log/unattended-upgrades/`에서 mariadb·zabbix·stop·restart 검색 결과 없음). 그래서 **원인은 미확정(유력)** 으로 둔다.
- **재발 방지(결정 필요, 서버 설정 변경이라 서버 관리자 몫):** 데모 전까지 `apt-daily-upgrade.timer`를 끄거나 `50unattended-upgrades`의 `Package-Blacklist`에 `mariadb-*`·`zabbix-*`를 넣는다. 데모 후 되돌린다.
- 복구 순서: `zabbix-server`가 `deactivating`에 걸려 있으면 `systemctl kill -s KILL zabbix-server` → `systemctl start mariadb` → `systemctl start zabbix-server`.

## 설치 패키지 (`apt list --installed | grep -E "zabbix|mariadb"`, 2026-10-16)
| 패키지 | 버전 |
|---|---|
| `zabbix-server-mysql` | 1:7.0.31-1+ubuntu24.04 |
| `zabbix-frontend-php`, `zabbix-apache-conf`, `zabbix-sql-scripts` | 1:7.0.31-1+ubuntu24.04 |
| `zabbix-agent`, `zabbix-get` | 1:7.0.31-1+ubuntu24.04 (서버 자신도 감시) |
| `zabbix-release` | 1:7.0-5+ubuntu24.04 (공식 저장소 설정) |
| `mariadb-server`, `mariadb-client` | 1:10.11.14-0ubuntu0.24.04.1 (`noble-updates`) |

## 아직 확인 못 한 것
- 업그레이드가 서비스를 멈춘 정확한 경로: `journalctl -b -u systemd-logind -u mariadb`나 `/var/log/apt/term.log`의 06:05 구간에서 확인할 수 있다. 확인되면 위 "유력한 원인"을 확정으로 고친다.
