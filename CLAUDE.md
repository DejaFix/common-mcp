# common-mcp

**공용 지침서: `docs/common-guidelines.md`를 먼저 읽는다.** 이어서 이 파일, 작업 폴더의 `CLAUDE.md`(`mcp-zabbix/`, `libs/zabbix_ro/`) 순으로 읽는다.

읽기 전용 Zabbix MCP 서버(`mcp-zabbix`)와 허용 목록 클라이언트(`libs/zabbix_ro`), Zabbix 7.0 조사 문서(`docs/zabbix/`)를 모은 repo다. 도구 계약 `contracts/mcp-tools.md`의 원본이다.

## 이 repo 전용 규칙
- Zabbix는 `*.get`과 `apiinfo.version` **조회만**. 쓰기·설정 변경·`user.login` 없음. 모든 호출은 `libs/zabbix_ro`를 거치고, 허용 목록 밖 메서드는 네트워크 요청 전에 예외.
- MCP 서버에 **쓰기 도구를 등록하지 않는다.** `tools/list`는 계약의 필수 5개만. 쓰기 도구가 있으면 소비자가 기동을 거부해야 한다.
- 근거 없는 값은 지어내지 않는다. 값이 없으면 `null` + `unknown_reason`(또는 `ok:false` + `reason`), 오래된 값은 `stale:true` + 수집 시각.
- 도메인 전용 아이템 키·동작 이름을 엔진 코드(`mcp-zabbix/`, `libs/`)에 하드코딩하지 않는다. 키는 `packs/<도메인>/metrics.yaml` 같은 설정에서 읽어 호출자가 `key_search`로 넘긴다.
- `.env`를 읽거나 편집하지 않는다. 토큰·서버 주소는 코드·문서·로그·커밋에 쓰지 않는다. 환경 변수 이름은 `.env.example`.
- 자기 폴더 밖 파일은 수정하지 않는다. 필요하면 Issue나 PR 본문에 변경 제안으로 남긴다. 한 세션에서 여러 폴더를 동시에 고치지 않는다.
- 계약(`contracts/mcp-tools.md`)을 바꿀 때는 계약 PR을 구현 PR보다 먼저 올린다.

## 검사
`uv run ruff check .`, `uv run ruff format --check .`, `uv run pytest` (실서버 없이 통과해야 한다. 실서버 테스트는 `live_check`로 따로).
