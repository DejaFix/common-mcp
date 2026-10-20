# common-mcp

읽기 전용 Zabbix MCP 서버(`mcp-zabbix`)와 허용 목록 클라이언트(`zabbix_ro`), Zabbix 7.0 조사 문서를 모은 재사용 묶음. DejaFix(장애 대응 코파일럿)에서 "Zabbix·MCP" 파트만 분리했다.

## 폴더
```
mcp-zabbix/        MCP 서버 (도구 5개, 봉투, stale 판정, healthz)  ← 엔진
libs/zabbix_ro/    읽기 전용 클라이언트 + mock/시나리오 fixture + probe  ← 엔진
contracts/         mcp-tools.md  도구 계약 (참고 사본)
docs/zabbix/       접속·계정·버전·지표·API 요청 예시·Windows Agent 명세·사고 기록
infra/scripts/     데모 부하 주입·정리·DB 백업 (PowerShell)   ← DejaFix 고유
infra/zabbix/demo/ 데모 템플릿·트리거                         ← DejaFix 고유
packs/it/          metrics.yaml  지표 별칭 → 아이템 키 예시   ← DejaFix 고유
```

## 5분 시작
```bash
uv sync                                   # Python 3.12, uv 필요
uv run ruff check . && uv run ruff format --check .
uv run pytest                             # 실서버 없이 통과 (mock·스텁)
ZABBIX_MOCK=true uv run --package mcp-zabbix python -m mcp_zabbix   # :8200/mcp, GET /healthz
```
실서버 점검: `ZABBIX_URL`(`http://<서버 주소>/zabbix/api_jsonrpc.php`), `ZABBIX_API_TOKEN`(`<토큰>`), `ZABBIX_MOCK=false`를 **환경 변수**로 주고 `uv run --package mcp-zabbix python -m mcp_zabbix.live_check`. 값은 `.env`에만 두고 커밋하지 않는다. 시나리오 mock: `ZABBIX_MOCK_SCENARIO=demo`.

## 새 프로젝트에서 재사용
1. `libs/zabbix_ro`와 `mcp-zabbix`를 통째로 복사하고 루트 `pyproject.toml`의 workspace 멤버로 등록한다.
2. 환경 변수 `ZABBIX_URL`, `ZABBIX_API_TOKEN`, `ZABBIX_VERIFY_TLS`, `ZABBIX_MOCK`, (선택) `INTERNAL_TOKEN`만 채운다.
3. Zabbix에 읽기 전용 계정·API 토큰을 만든다 (`docs/zabbix/readonly-account.md`, `access.md`).
4. 지표 키는 엔진에 넣지 않고 `packs/<도메인>/metrics.yaml` 같은 설정에서 읽어 `key_search` 인자로 넘긴다. 도구를 늘리면 `contracts/mcp-tools.md`부터 고친다.

| 재사용 가능 (엔진) | DejaFix 고유 (바꿔 쓸 것) |
|---|---|
| 읽기 전용 allow-list(`*.get`·`apiinfo.version`, 그 밖은 네트워크 요청 전 예외) | IT 지표 키(`packs/it/metrics.yaml`), core-metrics.md의 CPU/MEM/DISK 선정 |
| 공통 봉투 `{ok, collected_at, data, truncated}`와 실패 코드, 값 없음은 `null`+`unknown_reason` | 데모 트리거·템플릿(`infra/zabbix/demo`), 부하 주입 스크립트 |
| stale 판정 `max(delay×3, 10분)`, 목록 100건·이력 500점 제한 | 데모 호스트 이름·fixture 시나리오 `demo` |
| 쓰기 도구 미등록(기동 시 도구 목록 검사), MCP 도구 5개 구조 | 사고 기록, 읽기 전용 계정 이름 |
| Zabbix 7.0 API 사용법(Bearer 토큰, 요청 예시 `docs/zabbix/api-requests`) | |

## 안전 원칙
1. Zabbix는 `*.get` 조회만. 쓰기·설정 변경·`user.login` 없음.
2. 쓰기 MCP 도구를 등록하지 않는다.
3. 근거 없는 값은 지어내지 않고 `null`+사유, 오래된 값은 `stale`로 표시한다.
4. 토큰·주소는 코드와 문서에 적지 않는다(`.env`/환경 변수만). 오류 메시지에도 새지 않게 테스트로 막는다.

## 원본과의 관계
DejaFix 모노레포(agent·backend·frontend·scheduler 포함)에서 mcp-zabbix, libs/zabbix_ro, docs/zabbix, infra 일부, packs/it/metrics.yaml만 복사했다. 문서의 `T번호`·`FR-*`·`SAFE-*`·기획서 참조는 원본 요구사항 번호이며 이 저장소에는 해당 문서가 없다. 소비자(agent 등)와 `infra/zabbix/tools`, `local-server`는 포함하지 않아 일부 문서의 경로 언급은 원본 기준이다. 계약의 mcp-kb 절은 범위 밖이다.
