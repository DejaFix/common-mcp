# common-mcp

읽기 전용 Zabbix MCP 서버(`mcp-zabbix`), 허용 목록 클라이언트(`zabbix_ro`), Zabbix 7.0 조사 문서를 모은 재사용 묶음. 먼저 `docs/common-guidelines.md`와 `CLAUDE.md`.

## 역할
- `mcp-zabbix/`: MCP 도구 5개(문제 목록·문제 상세·호스트·아이템·이력)를 streamable HTTP(`:8200/mcp`, `GET /healthz`)로 제공. 공통 봉투, stale 판정(`max(delay×3, 10분)`), 목록 100건·이력 500점 제한.
- `libs/zabbix_ro/`: 읽기 전용 클라이언트(`*.get`·`apiinfo.version` 허용 목록, Bearer 토큰) + mock/시나리오 fixture + 연결 점검 `probe`.
- `docs/zabbix/`: 접속·읽기 전용 계정·버전·핵심 지표·API 요청 예시·Windows Agent 명세·정지 사고 런북. `infra/`: 시연용 부하 주입 스크립트와 템플릿 예시, `packs/it/metrics.yaml`: 지표 별칭 예시(바꿔 쓸 것).

## 실행 방법
```bash
uv sync                                   # Python 3.12, uv 필요
uv run ruff check . && uv run ruff format --check .
uv run pytest                             # 실서버 없이 통과 (mock·스텁)
ZABBIX_MOCK=true uv run --package mcp-zabbix python -m mcp_zabbix   # :8200/mcp, GET /healthz
```
실서버 점검: `.env.example`의 `ZABBIX_URL`, `ZABBIX_API_TOKEN`, `ZABBIX_MOCK=false`를 **환경 변수**로 주고 `uv run --package mcp-zabbix python -m mcp_zabbix.live_check`. 값은 `.env`에만 두고 커밋하지 않는다. 시나리오 mock: `ZABBIX_MOCK_SCENARIO=demo`.

## 입출력 계약
- 계약 원본은 `contracts/mcp-tools.md`(이 repo가 원본·소유자). 입력은 도구별 인자와 시각 인자(UTC ISO8601 또는 유닉스 초), 출력은 `{ok, collected_at, data, truncated}` 또는 `{ok:false, reason}`이고 값 없음은 `null` + 사유다.
- 소비 repo는 복사본을 직접 고치지 말고 **여기에 계약 PR을 올린다**. 도구를 늘리면 계약부터 고친다.

## 의존하는 다른 repo
- 이 repo는 `mcp-zabbix`의 원본 repo다. 소비자는 agent repo(도구 호출, `contracts/mcp-tools.md` 복사본 보유).
- 외부 의존: Zabbix 7.0 서버(읽기 전용 API 토큰, `docs/zabbix/readonly-account.md`). 서버 없이도 mock으로 동작한다.
- 새 프로젝트에 가져갈 때는 `libs/zabbix_ro`와 `mcp-zabbix`를 workspace 멤버로 복사하고 지표 키는 `packs/<도메인>/metrics.yaml`에서 읽는다.

## 하지 않는 것
- Zabbix 쓰기·설정 변경·`user.login`, 허용 목록 밖 메서드(요청 전 예외), 쓰기 MCP 도구 등록.
- DB 접근, LLM 호출, 분석·원인 문장 생성(소비자의 몫), 도메인 전용 지표 키의 엔진 하드코딩.
- 토큰·서버 주소를 코드·문서·로그·오류 메시지에 남기는 것.

## 구조
```
mcp-zabbix/        MCP 서버 (도구 5개, 봉투, stale 판정, healthz)
libs/zabbix_ro/    읽기 전용 클라이언트 + mock/fixture + probe
contracts/         mcp-tools.md 도구 계약 (원본)
docs/zabbix/       core-metrics.md(먼저) · windows-agent-api.md · access · readonly-account · version · mcp-live-test · runbook-db-stop · api-requests/ · verification/
infra/             scripts/ 부하 주입·정리·DB 백업(PowerShell), zabbix/demo/ 시연 템플릿  (예시)
packs/it/          metrics.yaml 지표 별칭 → 아이템 키 (예시)
```

## 원본과의 관계
DejaFix(장애 대응 코파일럿) 모노레포에서 Zabbix·MCP 파트(저장소 07d1db7 기준)만 분리했다. 원본 프로젝트의 규칙 번호·작업 번호는 본문에서 제거했고, 소비자 코드(agent·backend 등)는 포함하지 않는다. 일부 폴더(`infra/`, `packs/it/`)는 그 프로젝트의 예시라 새 프로젝트에서 바꿔 쓴다.
