# 읽기 전용 계정 `dejafix-readonly` (T56, FR-ZBX-004)

> 한 줄 요약: 읽기 전용 Zabbix 계정(역할·그룹·API 토큰) 구성 절차. 토큰 값 없음.

> 토큰 값은 이 문서에 적지 않는다(별도 안전 채널). 확인일: 2026-10-15, 팀 Zabbix 7.0.31 웹 화면과 실호출로 확인.
> 운영 Zabbix 쓰기(역할·사용자·토큰 생성)는 DejaFix 서비스가 아니라 **사람이 웹에서** 했다.

## 구성
| 항목 | 설정 |
|---|---|
| 사용자 역할 `dejafix-readonly` | 유형 **User**, Access to API **Enabled**, **Allow list**: `action.get`, `alert.get`, `event.get`, `history.get`, `host.get`, `hostgroup.get`, `hostinterface.get`, `item.get`, `maintenance.get`, `problem.get`, `trend.get`, `trigger.get` (12개) |
| `apiinfo.version` | 허용 목록에 넣지 않는다(인증 없이 누구나 호출 가능하고 역할 선택지에도 없음). `libs/zabbix_ro`도 이 메서드는 토큰 없이 보낸다 |
| 사용자 그룹 `dejafix-readonly` | Frontend access **Disabled**, Debug mode Disabled, Host permissions: `Windows`·`Zabbix servers` 그룹에 **Read** |
| 사용자 `dejafix-readonly` | 위 그룹·역할, Frontend access Disabled, **API access Enabled** |
| API 토큰 | 사용자 `dejafix-readonly`, 만료일 설정(날짜는 기록하지 않음). 값은 생성 직후 한 번만 보이므로 DM으로만 전달 |

허용 메서드 13개는 기획서 6-2 기준이고 그중 `apiinfo.version`을 뺀 12개를 역할에 넣었다. `user.login`은 쓰지 않는다.

## 보완 여지 (필수 아님)
역할의 **Access to actions**(문제 확인·종료, 스크립트 실행, API 토큰 관리 등)와 "Default access to new actions·modules"가 기본값 그대로 켜져 있다. API 허용 목록이 실제 호출을 막고 Frontend access가 Disabled라 영향은 없지만, 풀어 두면 더 안전하다.

## 확인한 것
- `dejafix-readonly` 토큰으로 `problem.get`·`event.get`·`trigger.get`·`host.get`·`item.get`·`history.get` 성공 → `mcp-live-test.md`
- 로컬 개발 서버에서는 허용 목록 밖 `user.get`이 차단되는 것을 확인했다(`verification/api-probe-2026-10-14/`).

## `host.update` 권한 오류 증빙 (FR-ZBX-004, NFR-SAFE-001)
2026-10-15, `dejafix-readonly` 토큰으로 `Invoke-RestMethod`(PowerShell)를 직접 호출했다. `libs/zabbix_ro`는 쓰기 메서드를 요청 전에 막기 때문에 라이브러리로는 못 보이고, 헤더 `Authorization: Bearer <토큰>`으로 API를 바로 불렀다. 존재하지 않는 `hostid`(`"0"`)를 써서 권한이 있더라도 아무것도 바뀌지 않게 했다. 토큰·주소는 출력에 나타나지 않는다.

`host.update` (쓰기) → **거부**:
```json
{"jsonrpc": "2.0", "error": {"code": -32500, "message": "Application error.", "data": "No permissions to call \"host.update\"."}, "id": 1}
```

`problem.get` (읽기, 같은 토큰) → **성공**: `result`에 문제 1건(`eventid`, `severity`, `name` 등)이 돌아왔다.

같은 토큰으로 읽기는 되고 쓰기는 Zabbix 서버가 거부한다는 증빙이다. 이 보호는 `libs/zabbix_ro`(허용 목록, SAFE-02)와 별개로 서버 쪽 역할 허용 목록이 한 번 더 막는 것이다.
