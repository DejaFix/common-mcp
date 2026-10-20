# Zabbix 접속

> 한 줄 요약: Zabbix 접속 형식(`ZABBIX_URL`, Bearer 토큰)과 .env 주의점. 주소·토큰 값은 없음.

서버 주소·토큰 값은 이 문서에 적지 않는다(별도 안전 채널로만 전달). 주소는 `<서버 주소>`로 표기한다.

## 접속 값
| 항목 | 값 |
|---|---|
| 웹 경로 | `http://<서버 주소>/zabbix` (사례: 80번 포트. 포워딩 포트가 아니다) |
| API 주소 (`ZABBIX_URL`) | `http://<서버 주소>/zabbix/api_jsonrpc.php` |
| `ZABBIX_VERIFY_TLS` | HTTP면 TLS가 없으므로 `false`, HTTPS면 `true` |
| 인증 | `Authorization: Bearer <ZABBIX_API_TOKEN>` (읽기 전용 계정 토큰, 값은 별도 안전 채널로 전달) |
| 에이전트 트래퍼 | 10051 (서버 설정) |

## `.env` 설정에서 겪은 문제
- `.env`에서 **값 뒤에 같은 줄 주석을 붙이지 않는다.** `ZABBIX_URL=http://… # 설명`처럼 쓰면 PowerShell 로드 명령은 `#` 뒤까지 값으로 읽어 요청이 404가 된다. 주석은 윗줄에 따로 쓴다.
- `ZABBIX_URL`은 반드시 `/api_jsonrpc.php`까지. `/zabbix`만 있으면 404.
- `.env` 값을 바꾼 뒤에는 터미널 환경 변수를 다시 로드해야 한다(이미 로드된 값은 자동으로 안 바뀐다).
- 토큰을 `.env.example`에 넣지 않는다(저장소에 올라가는 파일). `.env`는 `.gitignore` 대상이다.

## 접속 확인 방법
```powershell
# 토큰 불필요. "result": "7.0.x" 가 나오면 주소가 맞다
Invoke-RestMethod -Uri $env:ZABBIX_URL -Method Post -ContentType 'application/json-rpc' -Body '{"jsonrpc":"2.0","method":"apiinfo.version","params":{},"id":1}'
```
도구별 실호출은 `mcp-live-test.md`. 아침 점검 절차는 위 명령 한 번 + `live_check`로 갈음하고, 서버 정지 시 `runbook-db-stop.md`를 따른다.
