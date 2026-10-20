# 런북: Zabbix DB·서버 정지 사고 대응

> 한 줄 요약: Zabbix DB/서버가 멈췄을 때의 원인 후보, 복구 순서, 점검 3단계, 재발 방지 옵션. (Ubuntu + MariaDB + `zabbix-server` systemd 구성 기준)

서버 주소·토큰은 적지 않는다(`<서버 주소>`). 서버 설정 변경은 서버 관리자가 확인하고 실행한다. 재발 방지는 옵션이며 채택 여부는 각 팀이 정한다.

## 1. 증상
- 웹: `Database error: No such file or directory`, API: `Internal error`.
- `zabbix-server`가 `deactivating (stop-sigterm)`에서 멈춰 있고, `mariadb`는 `inactive`.
- 수집이 끊겨 MCP·백엔드의 실서버 호출이 `ZABBIX_ERROR`로 실패한다. 액티브 에이전트는 일부 버퍼링되지만 패시브 구간은 비는 값으로 남는다.

## 2. 원인 후보 (확인 순서)
1. **자동 업그레이드**: `unattended-upgrade`가 `systemd`·`udev`·`libsystemd0` 등을 올리면서 서비스를 재시작해 `mariadb`와 `zabbix-server`가 같은 초에 정지 요청(`Normal shutdown (initiated by: unknown)`)을 받고 다시 올라오지 않는 경우. 확인: `/var/log/apt/history.log`의 `End-Date`, `journalctl -b`, `/var/log/apt/term.log`.
2. 재부팅: `uptime -s`, `last -x`.
3. 디스크 가득 참: `df -h`.
4. 사람의 수동 정지: `last -x`의 SSH 접속 기록.

## 3. 복구 순서
`zabbix-server`가 `deactivating`에 걸려 있으면 먼저 정리하고 DB부터 올린다.
```bash
sudo systemctl kill -s KILL zabbix-server; sudo systemctl start mariadb
```
```bash
sudo systemctl start zabbix-server && sleep 5 && systemctl is-active mariadb zabbix-server
```
둘 다 `active`가 나오고 웹이 로그인 화면으로 돌아오면 복구된 것이다. 복구 뒤에는 4장의 2·3단계를 다시 한다.

## 4. 점검 3단계 (아침·중요 시연 직전)
1. **웹·API 응답** (토큰 불필요, `"result": "7.0.31"` 같은 버전 문자열이 나오면 정상):
   ```powershell
   Invoke-RestMethod -Uri $env:ZABBIX_URL -Method Post -ContentType 'application/json-rpc' -Body '{"jsonrpc":"2.0","method":"apiinfo.version","params":{},"id":1}'
   ```
2. **MCP 실호출 5도구**: `python -m mcp_zabbix.live_check` (5/5, 환경 변수로만 설정, 주소·토큰 출력 없음)
3. **수집 확인**: Zabbix Latest data에서 대상 호스트의 `CPU utilization`이 수집 주기(예: 30초)마다 갱신되는지 본다.

`apiinfo.version`이 `Internal error`를 내면 DB 문제이므로 3장으로 간다.

## 5. 재발 방지 옵션
| # | 옵션 | 효과 | 비용·주의 |
|---|---|---|---|
| 1 | 중요 시연·운영 기간 동안 자동 업그레이드 타이머 끄기 | 같은 원인의 재발을 가장 확실히 막는다 | 보안 패치가 미뤄진다. 끝나면 반드시 되돌린다 |
| 2 | 점검 3단계를 정기적으로(아침, 시연 직전) 실행 | 정지를 사용 전에 발견한다 | 사람이 직접 실행 |
| 3 | 복구 순서(3장)를 문서대로 따른다 | 복구 시간을 줄이고 `zabbix-server` 꼬임을 막는다 | — |
| 4 | 서버가 불안정하면 `ZABBIX_MOCK=true`로 전환 | 서버 상태에 묶이지 않는다 | 실데이터가 아니다 |

옵션 1 명령:
```bash
sudo systemctl disable --now apt-daily-upgrade.timer
```
확인: `systemctl list-timers 'apt-daily*' --no-pager`. 되돌리기:
```bash
sudo systemctl enable --now apt-daily-upgrade.timer
```
`Package-Blacklist`에 `mariadb-*`·`zabbix-*`를 넣는 방법은 원인이 `systemd` 패키지일 때 **막지 못할 수 있다**. 타이머를 끄는 쪽이 확실하다.

## 6. 사례 (한 건)
새벽 06:05경 자동 업그레이드(systemd 255.4-1ubuntu8.17 → 8.18)가 끝난 직후 MariaDB와 `zabbix-server`가 같은 초에 정지했고 아무도 다시 올리지 않아 약 6시간 수집이 비었다. 재부팅은 없었고 디스크는 14% 사용이었으며 사람의 SSH 접속 기록도 없었다. 서버 관리자가 낮에 수동 복구했고(정확한 시각은 확인 못 함) 복구 후 `apiinfo.version`은 7.0.31이었다. 유력한 원인은 자동 업그레이드이나 서비스를 멈춘 경로는 로그로 확인하지 못해 미확정이다.

## 7. 확인 못 한 것
- 업그레이드가 두 서비스를 멈춘 정확한 경로(`term.log`·`journalctl -b`).
- 타이머·`20auto-upgrades` 설정 파일의 값.
