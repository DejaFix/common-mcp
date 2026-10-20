# 공용 지침서 (다음 프로젝트 공통)

DejaFix 개발에서 검증된 규칙 중 **프로젝트가 달라져도 그대로 쓰는 것**만 뽑았다. 새 프로젝트(repo)를 시작할 때 이 문서를 복사해 그 프로젝트의 `CLAUDE.md` 맨 위에 붙이고, DejaFix 전용 값(Zabbix·SAFE 규칙·`packs/`·구성 5개 등)은 빼거나 자기 도메인 값으로 바꾼다.
각 Claude Code 세션은 이 문서 → 자기 폴더의 `CLAUDE.md` 순으로 읽는다.

## 1. 작업 기준
- 매 작업의 기준은 **체크리스트 문서 1개**(DejaFix는 `docs/mvp-checklist.md`)다. 기획서·요구사항 원본은 참고용으로 **동결**하고 늘리지 않는다.
- 문서끼리 다르면 **`contracts/` > 기획서 > 요구사항** 순으로 따른다.
- 정해지지 않은 값(공급자·모델·계정·호스트명 등)은 임의로 채우지 않고 `(TODO: 추후결정)`로 표시한 뒤 환경 변수·설정·목(mock)으로 비워 둔다.
- 제품 정체성과 충돌하는 지시를 받으면 임의로 고르지 않고 사람에게 묻는다.
- 자잘한 수정사항은 바로 고치지 말고 백로그 문서에 모은다.

## 2. 범위 등급
- **[필수]** 데모·출시 필수 / **[선택]** 필수 완료 후 / **[이후]** 다음 단계.
- [필수]가 끝나기 전에는 [선택]에 손대지 않는다. 새 기능은 스스로 추가하지 않는다.
- 범위 밖 화면·기능의 코드는 건드리지 않는다.
- 일정이 어긋날 때의 **탈출 규칙**(시각 + 조건 → 축소안)을 프로젝트 시작 때 미리 적어 둔다.

## 3. 안전·품질 원칙
- 위험한 동작(쓰기·삭제·실행)은 코드와 규칙이 막는다. 모델의 판단에 맡기지 않는다.
- 근거 없는 값은 "확인할 수 없음"으로 표시하고 지어내지 않는다. 0·빈칸으로 대체하지 않는다.
- 분석·판정 문장은 **한 곳(한 서비스)** 에서만 만든다. 다른 곳은 표시만 한다.
- 호출 방향은 한 방향으로 고정하고 역방향 호출을 금지한다.
- 도메인 값(아이템 키·동작 ID·문구)은 엔진 코드에 하드코딩하지 않고 설정(팩)에서 읽는다. 하드코딩 검사 명령(`rg`)을 만들어 머지 조건으로 둔다.
- 안전 규칙마다 **강제 위치**와 **테스트**를 짝지어 둔다. 필수 안전 테스트가 빠지면 머지 불가.

## 4. 비밀값
- 토큰·비밀번호·API 키는 `.env`에만 둔다. 저장소에는 값 없는 `.env.example`만 올린다.
- Claude Code는 `.env`를 읽거나 편집하지 않는다(`.claude/settings.json` deny + 훅). 프롬프트·로그·커밋에 키를 붙여넣지 않는다.
- 브라우저 저장소·프론트 번들에 키를 두지 않는다. 토큰이 필요하면 `sessionStorage`만 쓴다(`localStorage` 금지).
- 유출이 의심되면 즉시 재발급한다.

## 5. 폴더 소유권과 계약
- **자기 폴더 밖 파일은 수정하지 않는다.** 필요하면 담당자에게 Issue로 요청하거나 PR 본문에 "변경 제안"으로 남긴다. 한 세션에서 여러 파트 폴더를 동시에 고치지 않는다.
- `contracts/`(API·스키마·도구 명세)가 파트 간 유일한 약속이다.
- 계약 변경은 **계약 PR → 구현 PR** 순서이고, 계약 PR은 2인 승인(소유자 + 소비자 1명)을 받는다. 계약을 바꾼 PR에서 기획서의 해당 절도 같이 고친다.
- 계약과 다른 점이 보이면 코드로 우회하지 말고 "계약 변경 제안"을 쓴다.

## 6. 명명 규칙
| 대상 | 규칙 | 예 |
|---|---|---|
| 서비스 폴더·compose 서비스 | kebab-case | `mcp-zabbix`, `scheduler` |
| Python 패키지 | snake_case | `dejafix_agent` |
| 환경 변수 | 대문자 + 서비스 접두사 | `ZABBIX_*`, `LLM_*` |
| DB 테이블 | 복수형 snake_case | `analysis_reports` |
| REST 경로 | `/api/<복수 명사>` kebab-case | `/api/mail-logs` |
| 시간 | 저장은 UTC ISO8601, 화면에서만 현지 시각 | `2026-10-16T01:23:45Z` |

## 7. 스택 표준
- Frontend: React + Vite + TypeScript, Node 22 LTS, **npm**(`npm ci`, `package-lock.json` 커밋).
- Python: 3.12, FastAPI, **uv** workspace(`uv.lock` 커밋, pip·poetry 금지).
- DB: 처음엔 SQLite(WAL). 테이블마다 작성자 1개, 읽는 쪽은 읽기 전용으로 붙인다. 스키마 원본은 `contracts/db-schema.sql`(전 문장 `IF NOT EXISTS`).
- 실시간 갱신은 폴링을 기본으로 하고 스트리밍은 꼭 필요한 곳(채팅)만 쓴다. 브라우저 스트림은 `fetch` + ReadableStream으로 읽는다(`EventSource`는 헤더를 못 붙인다).
- 개발 프록시를 쓰고 절대 주소를 환경 변수에 박지 않는다. 외부 공개 포트는 최소로 둔다.

## 8. Git·PR
- `main`: 배포·데모 안정본, 직접 push 금지. `dev`: 통합 브랜치, 직접 push 금지, PR + 승인 1명 이상, squash 머지.
- 작업 브랜치는 dev에서 따서 dev로 PR: `feat/<영역>-<주제>`, `fix/<영역>-<주제>`, `docs/<주제>`.
- 커밋은 Conventional Commits, 한 커밋 한 목적. 예) `feat(agent): 리포트 JSON 스키마 검증 추가`.
- PR은 400줄 이하를 권장한다. 본문에 **무엇 / 왜 / 테스트 방법 / 계약 변경 여부 / 충돌 확인 결과(1줄)** 를 쓴다.
- Claude가 만든 코드도 사람 리뷰 없이 dev에 들어가지 않는다.

## 9. 린트·테스트 (PR 머지 조건)
| 영역 | 명령 |
|---|---|
| Python | `uv run ruff check .`, `uv run ruff format --check .`, `uv run pytest` |
| Frontend | `npm run lint`, `npx tsc --noEmit`, `npm run build` |

## 10. 프론트엔드 공통 (UI 컴포넌트·디자인)
- 화면은 **표시만** 한다. 분석 문장·원인·판정을 화면에서 계산하거나 바꾸지 않는다.
- 값 표시 컴포넌트는 "알 수 없음" 상태를 반드시 가진다(`UnknownValue`). 확신도는 낮음/보통/높음 3단계 문자로 쓴다(퍼센트 금지).
- 스타일은 토큰(`tokens.css` → `theme.css` → `shell.css`) 순으로 쌓고, 색은 토큰만 쓴다. 글꼴은 Pretendard, 라이트·다크 모두 고려한다.
- 공통 컴포넌트(레이아웃·상태 표시·카드·배지·사용자 메뉴)는 따로 문서화하고 새 프로젝트가 가져다 쓴다. 상세는 프론트엔드 공용 템플릿 repo·노션 문서를 따른다.
- 개발 모드에서는 MSW로 백엔드 없이 전 화면이 그려져야 한다.

## 11. 에이전트 협업 (GitHub Issue)
- 작업을 시작하면 자기 파트 라벨의 열린 Issue부터 확인한다: `gh issue list --label to-<파트> --state open`.
- 응답은 코멘트 1개 + 라벨: 수락 `accepted` / 대안 `counter` / 시작 `in-progress`. 구현 PR 본문에 `Closes #번호`.
- 다른 파트 파일은 직접 고치지 않고 Issue 양식으로 요청한다.
- 2번 주고받아도 합의가 안 되거나 안전·범위·비용·되돌릴 수 없는 일이면 `needs-human`을 붙이고 멈춘다. 이 라벨은 사람만 뗀다.
- 결정한 것은 `docs/decisions/NNN-제목.md`에 3줄(결정·이유·대안)로 남기고 Issue에 링크한다.

## 12. 세션 운영
- 경로는 항상 상대경로로 쓴다.
- 편집 후 자동 포맷 훅을 켠다: frontend는 prettier, Python은 ruff format.
- 변경분 검사용 읽기 전용 서브에이전트(`plan-reviewer`)를 둔다: 안전 위반·계약 불일치·[이후] 침범·하드코딩을 보고만 한다.
- 작업 현황은 사람이 체크한다. 세션은 노션을 읽기만 하고, 끝나면 완료할 T 번호를 알린다. 30분 넘게 막히면 `BLOCKED` + 이유를 남긴다.
- 사용자 대화와 문서는 한국어로 쓴다.

## 13. 프로젝트를 repo로 분리할 때
- repo 하나 = 프로젝트 하나(frontend, backend, agent, mcp 등). 각 repo는 이 문서 + 자기 `CLAUDE.md` + `README.md` + `.env.example`을 갖는다.
- repo마다 README에 **역할 / 실행 방법 / 입출력 계약 / 의존하는 다른 repo / 하지 않는 것**을 쓴다.
- DejaFix 전용 규칙(SAFE-xx, `packs/`, Zabbix)은 해당 도메인 repo에만 남긴다.

### 계약 문서는 각 repo에 복사해 둔다 (결정)
- 계약 문서(`api.md`, `agent-api.md`, `mcp-tools.md`, `db-schema.sql`, `incident.schema.json`)는 별도 계약 repo를 만들지 않고, **쓰는 repo마다 `contracts/`로 복사**한다. repo 하나만 받아도 바로 작업할 수 있어야 한다.
- **원본은 한 곳**이다. 계약마다 원본 repo(계약 소유자 repo)를 정해 두고, 나머지 repo의 `contracts/`는 복사본이다.

  | 계약 | 원본 repo | 복사본을 두는 repo |
  |---|---|---|
  | `api.md`, `incident.schema.json` | backend | frontend |
  | `agent-api.md` | agent | backend |
  | `mcp-tools.md` | mcp-zabbix | agent |
  | `db-schema.sql` | agent (shared.db), backend (backend.db) | scheduler, backend |

- 복사본은 **직접 고치지 않는다.** 바꾸고 싶으면 원본 repo에 계약 PR을 먼저 올린다(5장 절차와 같음, 2인 승인).
- 원본이 바뀌면 같은 PR 본문에 "복사본 갱신 필요 repo" 목록을 쓰고, 소비 repo는 `docs/` 쪽 이슈로 요청받아 복사본을 갱신하는 PR을 올린다.
- 모든 복사본 파일 맨 위에 출처 한 줄을 적는다: `원본: <repo>/contracts/<파일> @ <커밋 해시> (복사일 YYYY-MM-DD)`. 해시가 원본 최신과 다르면 오래된 복사본이다.
- 복사본이 어긋났는지 확인하는 검사(원본과 diff)를 CI나 릴리스 전 점검표에 넣는다.
