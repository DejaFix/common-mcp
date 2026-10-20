# 읽기 전용 계정 구성

> 한 줄 요약: 읽기 전용 Zabbix 계정(역할·그룹·API 토큰) 구성 절차와 쓰기 거부 증빙. 토큰 값 없음. 아래 이름 `zabbix-readonly`는 예시다.

토큰 값은 이 문서에 적지 않는다(별도 안전 채널). 운영 Zabbix의 역할·사용자·토큰 생성은 애플리케이션이 아니라 **사람이 웹에서** 한다.

## 구성
| 항목 | 설정 |
|---|---|
| 사용자 역할 `zabbix-readonly` | 유형 **User**, Access to API **Enabled**, **Allow list**: `action.get`, `alert.get`, `event.get`, `history.get`, `host.get`, `hostgroup.get`, `hostinterface.get`, `item.get`, `maintenance.get`, `problem.get`, `trend.get`, `trigger.get` (12개) |
| `apiinfo.version` | 허용 목록에 넣지 않는다(인증 없이 누구나 호출 가능하고 역할 선택지에도 없음). `libs/zabbix_ro`도 이 메서드는 토큰 없이 보낸다 |
| 사용자 그룹 `zabbix-readonly` | Frontend access **Disabled**, Debug mode Disabled, Host permissions: 감시 대상 호스트 그룹에 **Read** |
| 사용자 `zabbix-readonly` | 위 그룹·역할, Frontend access Disabled, **API access Enabled** |
| API 토큰 | 위 사용자, 만료일 설정. 값은 생성 직후 한 번만 보이므로 안전한 채널(DM 등)로만 전달 |

허용 메서드 13개 중 `apiinfo.version`을 뺀 12개를 역할에 넣었다. `user.login`은 쓰지 않는다.

## 보완 여지
역할의 **Access to actions**(문제 확인·종료, 스크립트 실행, API 토큰 관리 등)와 "Default access to new actions·modules"가 기본값으로 켜져 있을 수 있다. API 허용 목록이 실제 호출을 막고 Frontend access가 Disabled라 영향은 없지만, 풀어 두면 더 안전하다.

## 확인 방법
- 토큰으로 `problem.get`·`event.get`·`trigger.get`·`host.get`·`item.get`·`history.get`이 성공하는지 본다(`mcp-live-test.md`).
- 허용 목록 밖 `user.get`이 차단되는지 본다.

## 쓰기 거부 증빙 (`host.update`)
`libs/zabbix_ro`는 쓰기 메서드를 요청 전에 막으므로 라이브러리로는 보일 수 없다. 서버 쪽 거부는 `Invoke-RestMethod`로 헤더 `Authorization: Bearer <토큰>`을 직접 달아 확인한다. 존재하지 않는 `hostid`(`"0"`)를 써서 권한이 있더라도 아무것도 바뀌지 않게 한다.

`host.update` (쓰기) → **거부**:
```json
{"jsonrpc": "2.0", "error": {"code": -32500, "message": "Application error.", "data": "No permissions to call \"host.update\"."}, "id": 1}
```
`problem.get` (읽기, 같은 토큰) → **성공**: `result`에 문제 목록이 돌아온다.

같은 토큰으로 읽기는 되고 쓰기는 서버가 거부한다는 증빙이다. 클라이언트 허용 목록(`libs/zabbix_ro`)과 별개로 서버 쪽 역할 허용 목록이 한 번 더 막는다.
