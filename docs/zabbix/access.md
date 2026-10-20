# 팀 Zabbix 접속 (T57, FR-ZBX-006)

> 한 줄 요약: 운영 Zabbix 접속 형식(`ZABBIX_URL`, Bearer 토큰)과 .env 주의점. 주소·토큰 값은 없음.

> 서버 주소·토큰 값은 이 문서에 적지 않는다(별도 안전 채널로만 전달). 주소는 `<서버 주소>`로 표기한다.
> 확인일: 2026-10-15 (Zabbix·MCP 담당, 실서버 `live_check` 5/5 통과 후 기록)

## 확정 값
| 항목 | 값 |
|---|---|
| Zabbix 서버·프론트 버전 | 7.0.31 |
| 웹 경로 | `http://<서버 주소>/zabbix` (**80번 포트**. 8081 포워딩이 아니다) |
| API 주소 (`ZABBIX_URL`) | `http://<서버 주소>/zabbix/api_jsonrpc.php` |
| `ZABBIX_VERIFY_TLS` | `false` (HTTP라 TLS 없음) |
| 인증 | `Authorization: Bearer <ZABBIX_API_TOKEN>` (`dejafix-readonly` 계정 토큰, 값은 별도 안전 채널로 전달) |
| 에이전트 트래퍼 | 10051 (서버 설정, `docs/zabbix` 에이전트 지침 참고) |

호스트 7대(감시 대상 Windows PC 6대 + Zabbix 서버 자신)가 등록되어 있다.

## `.env` 설정에서 겪은 문제 (다음 사람을 위해)
- `.env`에서 **값 뒤에 같은 줄 주석을 붙이지 않는다.** `ZABBIX_URL=http://… # 설명`처럼 쓰면 PowerShell 로드 명령은 `#` 뒤까지 값으로 읽어 요청이 404가 된다(값 길이 203 → 정상 44). 주석은 윗줄에 따로 쓴다.
- `ZABBIX_URL`은 반드시 `/api_jsonrpc.php`까지. `/zabbix`만 있으면 404.
- `.env` 값을 바꾼 뒤에는 터미널 환경 변수를 다시 로드해야 한다(이미 로드된 값은 자동으로 안 바뀐다).
- 토큰을 `.env.example`에 넣지 않는다(저장소에 올라가는 파일). `.env`는 `.gitignore` 대상이다.

## 접속 확인 방법
```powershell
# 토큰 불필요. "result": "7.0.31" 이 나오면 주소가 맞다
Invoke-RestMethod -Uri $env:ZABBIX_URL -Method Post -ContentType 'application/json-rpc' -Body '{"jsonrpc":"2.0","method":"apiinfo.version","params":{},"id":1}'
```
도구별 실호출은 `mcp-live-test.md`.

## 아직 남은 것
- 팀 VM의 OS·설치 방식(`version.md`)과 방화벽 설정은 이 문서에 기록하지 않았다.
- 아침 점검 절차(`apiinfo.version` 한 번 + `live_check`)는 위 두 명령으로 갈음한다.
