# libs/zabbix_ro

> 한 줄 요약: zabbix_ro 개발 규칙. 먼저 루트 `CLAUDE.md`와 `docs/common-guidelines.md`.

## 역할
- 허용 목록 강제 클라이언트: `apiinfo.version, problem.get, event.get, trigger.get, host.get, hostgroup.get, hostinterface.get, item.get, history.get, trend.get, maintenance.get, action.get, alert.get` 외 메서드는 요청 전 `MethodNotAllowed`
- Bearer 토큰 인증, `ZABBIX_VERIFY_TLS` 반영
- `ZABBIX_MOCK=true` fixture(`problem.get`, `host.get`, `item.get`, `history.get` 등)

## 하지 않는 것
- 쓰기 메서드(`*.create/update/delete`), `user.login`
- 도메인 전용 아이템 키 하드코딩 (키는 `packs/<domain>/metrics.yaml` 같은 설정에서)

## 테스트
- `uv run pytest` — `host.update`, `item.create`, `user.login`, `problem.delete` → 요청 없이 예외 (머지 조건)
