# libs/zabbix_ro

> 한 줄 요약: 허용 목록 강제 읽기 전용 Zabbix 클라이언트(mock·probe 포함).

여러 서비스가 함께 쓰는 읽기 전용 Zabbix 클라이언트 (uv workspace 멤버)

- 허용 메서드 밖 호출은 네트워크 요청 **전에** 예외
- 인증은 `Authorization: Bearer <ZABBIX_API_TOKEN>`, `user.login` 미사용
- `ZABBIX_MOCK=true`면 Zabbix 7.0 형식 fixture 반환

## 사용법

```python
import zabbix_ro

client = zabbix_ro.from_env()   # 환경 변수에서 만든다
problems = client.call("problem.get", {"output": "extend", "recent": True})  # JSON-RPC result
```

| 환경 변수 | 뜻 |
|---|---|
| `ZABBIX_URL` | `.../api_jsonrpc.php` 주소. 실서버 모드에서 필수 |
| `ZABBIX_API_TOKEN` | 읽기 전용 계정의 API 토큰. 실서버 모드에서 필수(값은 `.env`에만) |
| `ZABBIX_VERIFY_TLS` | `false`·`0`·`no`·`off`면 TLS 인증서 검사를 끈다. 비워 두면 `true`(검사 켬). **모르는 값(오타)은 검사를 켠 채로 두고 `call()`이 `ZabbixError`** — `ture` 한 글자로 검사가 조용히 꺼지지 않게 한다 |
| `ZABBIX_MOCK` | `true`면 네트워크 없이 fixture 를 돌려준다. URL·토큰이 없어도 된다 |
| `ZABBIX_MOCK_SCENARIO` | 목 모드에서 상황을 고른다. 비우면 `default`. 아래 "목 시나리오" 참고. **모르는 값은 `call()`이 `ZabbixError`** (조용히 `default`로 바뀌지 않음). 실서버 모드에서는 쓰이지 않는다 |

## 허용 메서드 (13개)

`apiinfo.version`, `problem.get`, `event.get`, `trigger.get`, `host.get`, `hostgroup.get`, `hostinterface.get`, `item.get`, `history.get`, `trend.get`, `maintenance.get`, `action.get`, `alert.get`

`*.create`·`*.update`·`*.delete`·`user.login` 등 그 밖의 메서드는 요청을 보내기 전에 `MethodNotAllowed`.

## 예외

| 예외 | 언제 |
|---|---|
| `zabbix_ro.MethodNotAllowed` | 허용 목록 밖 메서드 (요청 전) |
| `zabbix_ro.ZabbixError` | URL·토큰 누락, 연결 실패, 타임아웃, HTTP 오류, JSON-RPC `error` 응답 (`.code`·`.data`) |

- `from_env()`는 **항상 예외 없이** 클라이언트를 만든다. 실서버 모드에서 URL·토큰이 비어 있으면 `call()`이 요청을 보내기 전에 `ZabbixError`를 던진다. 그래서 주기 폴링처럼 호출 오류를 잡아 다음 주기에 재시도하는 쪽은 토큰이 오기 전에도 죽지 않는다. 설정 여부는 `client.configured`로 확인할 수 있다.
| `zabbix_ro.ZabbixRoError` | 위 둘의 부모. 한 번에 잡을 때 |

## 목 모드 (fixture)

`zabbix_ro/fixtures/`는 실서버(Zabbix 7.0.31) 응답을 복사한 것이다.
- `trigger.get`의 `hosts`에는 `host.get`의 `name`을 보강했다(`selectHosts`로 `name`을 요청하는 호출자를 위해).
- `history.get`은 `params.history`(0~3) 값에 맞는 파일을 쓴다.
- `eventids`·`triggerids`·`hostids`·`itemids`·`objectids`·`limit` 파라미터로 간단히 거른다. 그 밖의 필터·정렬은 하지 않는다.
- fixture 가 없는 허용 메서드(`hostgroup.get` 등)는 빈 목록.

### 목 시나리오 (`ZABBIX_MOCK_SCENARIO`)

| 값 | 상황 |
|---|---|
| `default` | 위의 실서버 응답 그대로 (호스트 1대, 디스크 장애 1건) |
| `demo` | **mcp-zabbix 목과 같은 ID**: CPU 장애 `30001`(trigger `20001`, host `10001` demo-host) 진행 중, 디스크 장애 `90002`(trigger `23002`, host `10602` MOCK-PC-02) 해결됨, 호스트 3대(MOCK-PC-03은 가용성 알 수 없음) |
| `quiet` | `demo`의 호스트인데 문제가 없음 (`problem.get`·`event.get` 빈 목록) |
| `host_down` | `demo`에서 demo-host의 에이전트 가용성이 2(불가) |
| `empty` | 목록 메서드가 전부 빈 목록 (호스트 0대), `apiinfo.version`만 값 |
| `outage` | 모든 호출이 `ZabbixError` (Zabbix 연결 불가, health는 `down`) |

`ZABBIX_MOCK=true`로 시연할 때 여러 서비스가 서로 다른 장애를 보여 주지 않도록 `demo`를 쓴다. `tests/test_mock_scenarios.py`가 mcp-zabbix 목과 ID가 같은지 매번 검사한다.

## 테스트

`uv run pytest libs/zabbix_ro` — 쓰기 메서드를 요청 없이 거부하는 테스트는 `safety_regression` 마커.

## 연결 점검 (`probe`)

Zabbix 서버에 토큰이 제대로 붙는지 한 줄로 확인한다. **환경 변수에서만** 읽고 `.env` 파일은 읽지 않는다.

```powershell
$env:ZABBIX_URL="http://<주소>/api_jsonrpc.php"; $env:ZABBIX_API_TOKEN="<토큰>"; $env:ZABBIX_MOCK="false"
uv run python -m zabbix_ro.probe
```

- 허용된 읽기 메서드 5개(`apiinfo.version`·`host.get`·`problem.get`·`trigger.get`·`item.get`)를 결과 1건으로 한 번씩 부르고 `[ OK ]`/`[FAIL]`과 걸린 시간을 줄마다 찍는다. FAIL이 하나라도 있으면 종료 코드 1, 하나 실패해도 나머지를 계속 점검한다.
- 쓰기 차단은 **실서버로 쓰기를 보내지 않고** 확인한다: 허용 목록에 쓰기 메서드(`host.update` 등)가 없는지, 목 클라이언트(네트워크 없음)가 거부하는지. 서버가 읽기 전용 계정의 쓰기를 거부하는지는 이 도구로 볼 수 없다(`docs/zabbix/readonly-account.md`의 권한 오류 캡처 참고).
- 토큰·URL은 출력하지 않는다. URL·토큰이 비었거나 설정 값이 잘못되면 `[FAIL] 설정` 한 줄로 이유를 알려 준다.
