# 사고 기록과 재발 방지 대책 — 팀 Zabbix DB·서버 정지 (2026-10-16)

> 한 줄 요약: Zabbix DB·서버 정지 사고 기록과 재발 방지 대책(운영 교훈용).

> 서버 주소·토큰은 적지 않는다(`<서버 주소>`). 사실은 서버 셸 출력과 웹·API 응답에서만 옮겼고, 직접 못 본 것은 `확인 못 함`으로 둔다. 서버 설정 변경은 **서버 관리자(Zabbix·MCP 담당)가 결정·실행**한다. 이 문서는 대책 안이고 결정이 아니다.

## 1. 무슨 일이 있었나
| 시각(KST) | 일 | 근거 |
|---|---|---|
| 06:05:54 | `unattended-upgrade`가 `systemd`·`udev`·`libsystemd0` 등 255.4-1ubuntu8.17 → 8.18 업그레이드를 끝냄 | `apt history` `End-Date` |
| 06:05:55 | `mariadb`와 `zabbix-server`가 같은 초에 정지 요청(`Normal shutdown (initiated by: unknown)`) | `journalctl` |
| 06:05:56 | MariaDB 정지 완료. 이후 아무도 다시 올리지 않음 | `systemctl status` |
| 이후 | 웹은 `Database error: No such file or directory`, API는 `Internal error`. `zabbix-server`는 `deactivating (stop-sigterm)`에 걸려 있었다 | 웹 화면, API 응답, `systemctl status` |
| 낮 12시 이후 | 서버 관리자가 수동 복구(정확한 시각은 확인 못 함) | 복구 후 `apiinfo.version` = 7.0.31 |

- 재부팅은 없었고(`uptime -s` 2026-10-14 16:19), 디스크도 여유가 있었다(14% 사용). 06:05에 사람의 SSH 접속 기록도 없다(`last -x`).
- **유력한 원인은 새벽 자동 업그레이드**이지만, 업그레이드가 서비스를 멈춘 경로는 로그로 확인하지 못했다. 원인은 **미확정(유력)**.
- 영향: 약 6시간 동안 Zabbix 수집이 비었고(액티브 에이전트는 일부 버퍼링 가능, 패시브는 빈 구간), 그 사이 `mcp-zabbix`·Backend·Scheduler의 실서버 호출은 실패했다.

## 2. 재발 방지 대책 (안)
| # | 대책 | 효과 | 비용·주의 | 누가 |
|---|---|---|---|---|
| 1 | **데모 전까지 자동 업그레이드 타이머 끄기** | 같은 원인으로 데모 중에 다시 내려가는 것을 막는다(가장 확실) | 보안 패치가 미뤄진다. 데모 후 반드시 되돌린다 | 서버 관리자 |
| 2 | 아침·데모 직전 **점검 3단계**를 한다(아래 4장) | 정지를 데모 전에 발견한다 | 사람이 직접 실행 | Zabbix·MCP 담당 |
| 3 | 정지 시 **복구 순서**를 문서대로 따른다(아래 3장) | 복구 시간을 줄이고 `zabbix-server` 꼬임을 막는다 | — | 서버 관리자 |
| 4 | 데모 날 Zabbix가 불안정하면 탈출 규칙대로 `ZABBIX_MOCK=true` 전환 | 데모가 서버 상태에 묶이지 않는다 | 실데이터가 아니다 | 팀장 |

대책 1은 아래 명령으로 한다. **서버 설정 변경이라 서버 관리자가 확인하고 실행한다.**
```bash
sudo systemctl disable --now apt-daily-upgrade.timer
```
확인:
```bash
systemctl list-timers 'apt-daily*' --no-pager
```
데모 후 되돌리기:
```bash
sudo systemctl enable --now apt-daily-upgrade.timer
```
- `Package-Blacklist`에 `mariadb-*`·`zabbix-*`를 넣는 방법은 이번 원인이 `systemd` 패키지라서 **막지 못할 수 있다**. 타이머를 끄는 쪽이 확실하다.
- 이 대책을 채택하면 `docs/decisions/`에 3줄(결정·이유·대안)로 남긴다(루트 CLAUDE.md 에이전트 협업). 번호는 서버 관리자가 정한다.

## 3. 복구 순서 (정지했을 때)
`zabbix-server`가 `deactivating`에 걸려 있으면 먼저 정리하고 DB부터 올린다.
```bash
sudo systemctl kill -s KILL zabbix-server; sudo systemctl start mariadb
```
```bash
sudo systemctl start zabbix-server && sleep 5 && systemctl is-active mariadb zabbix-server
```
둘 다 `active`가 나오고 웹이 로그인 화면으로 돌아오면 복구된 것이다. 복구 뒤에는 4장의 2·3단계를 다시 한다.

## 4. 점검 3단계 (아침·데모 직전)
1. **웹·API 응답** (토큰 불필요, `"result": "7.0.31"`이 나오면 정상):
   ```powershell
   Invoke-RestMethod -Uri $env:ZABBIX_URL -Method Post -ContentType 'application/json-rpc' -Body '{"jsonrpc":"2.0","method":"apiinfo.version","params":{},"id":1}'
   ```
2. **MCP 실호출 5도구**: `python -m mcp_zabbix.live_check` (5/5, 환경 변수로만 설정, 주소·토큰 출력 없음)
3. **수집 확인**: Zabbix Latest data에서 데모 호스트 `CPU utilization`이 30초마다 갱신되는지 본다.

`apiinfo.version`이 `Internal error`를 내면 DB 문제이므로 3장으로 간다.

## 5. 확인 못 한 것
- 업그레이드가 두 서비스를 멈춘 정확한 경로: `/var/log/apt/term.log`의 06:05 구간이나 `journalctl -b`에서 확인할 수 있다. 확인되면 1장의 "유력"을 "확정"으로 고친다.
- 타이머·`20auto-upgrades` 설정 파일의 현재 값.
- 정확한 복구 시각.
