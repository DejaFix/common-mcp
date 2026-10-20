# Zabbix 서버 버전·설치 방식 기록

> 한 줄 요약: 대상 Zabbix 서버의 버전·OS·설치 방식을 기록하는 양식과 확인 명령(7.0 LTS 사례).

서버 주소·토큰 값은 적지 않는다(`<서버 주소>`). 접속 방법은 `access.md`. 직접 확인하지 못한 칸은 `확인 못 함`으로 둔다.

## 기록 양식 (사례 값)
| 항목 | 사례 | 확인 명령 |
|---|---|---|
| Zabbix 서버·프론트 버전 | 7.0.31 | `apiinfo.version` 응답 `"result":"7.0.31"` |
| OS | Ubuntu 24.04.5 LTS (noble) | `lsb_release -a` |
| 설치 방식 | apt 패키지(Zabbix 공식 저장소 `zabbix-release`, VM에 직접 설치). Docker 아님 | `apt list --installed`, 서비스 유닛 경로 |
| 데이터베이스 | MariaDB 10.11 (PostgreSQL 없음) | `systemctl status mariadb` |
| 웹 서버 | Apache 2.4 | `apt history` |
| 서버 자동 업그레이드 | `unattended-upgrade` 사용 여부, 타이머·`20auto-upgrades` 설정 | `systemctl list-timers 'apt-daily*'` |
| 에이전트 | 감시 대상의 에이전트 버전. 서버 버전보다 높으면 호환성 확인 | 에이전트 로그, Problems 화면 |
| 웹 경로·포트 | `http://<서버 주소>/zabbix`, 80번. 트래퍼 10051 | `access.md` |

## `apiinfo.version` 응답 캡처 (토큰 불필요)
```json
{"jsonrpc":"2.0","result":"7.0.31","id":1}
```
요청: `POST http://<서버 주소>/zabbix/api_jsonrpc.php`, 본문 `{"jsonrpc":"2.0","method":"apiinfo.version","params":[],"id":1}`. 인증 없이 호출되며, 아침 점검과 헬스체크의 Zabbix 판정에도 같은 방식을 쓴다.

## 설치 패키지 확인 (`apt list --installed | grep -E "zabbix|mariadb"`)
`zabbix-server-mysql`, `zabbix-frontend-php`, `zabbix-apache-conf`, `zabbix-sql-scripts`, `zabbix-agent`, `zabbix-get`(서버 자신도 감시), `zabbix-release`(공식 저장소 설정), `mariadb-server`·`mariadb-client`. 사례에서는 Zabbix 패키지가 모두 7.0.31이었다.

## 운영 메모
서버 정지 사고(자동 업그레이드가 유력 원인)와 복구·재발 방지는 `runbook-db-stop.md`. 서버 자동 업그레이드 설정은 서버 관리자가 확인한다.
