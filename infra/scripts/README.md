# infra/scripts

> 한 줄 요약: 데모용 CPU 부하 주입·정리·DB 백업 PowerShell 스크립트 사용법.

Windows PowerShell 운영 스크립트 (담당 Zabbix·MCP 담당, 부 팀장 / 백업은 DB·메일 담당). `*.ps1`은 CRLF(`.gitattributes`).

| 스크립트 | 등급 | 내용 | 근거 |
|---|---|---|---|
| `inject-cpu.ps1` | 필수 | `-Minutes N`(기본·최대 10) 코어 수만큼 CPU 부하, 만료·Ctrl+C 시 종료 | FR-INF-003, G12 |
| `cleanup.ps1` | 필수 | 주입 프로세스 종료, `%TEMP%\dejafix-fill\` 삭제 | FR-INF-005 |
| `backup-db.ps1` | 필수 | SQLite 백업 API로 `shared.db`·`backend.db` → `backups/`, 최근 5개 | FR-INF-006, 11-3 |
| `inject-disk.ps1` | 선택 | 90% 도달에 필요한 양만, 상한 20GB·여유 10%, `%TEMP%\dejafix-fill\`에만 | FR-INF-004 |
| `check-env.ps1` | 선택 | 아침 점검 5단계(IP·VM·`apiinfo.version`·최근 데이터·`.env` 공지) | FR-INF-010, 11-2 |

- 장애 주입 스크립트는 야간에 실행하지 않는다. 야간 작업 루프도 실행 금지.

## 백업·복원 (`backup-db.ps1`, DB·메일 담당)

```powershell
powershell -ExecutionPolicy Bypass -File infra\scripts\backup-db.ps1                 # data\ → backups\<시각>\
powershell -ExecutionPolicy Bypass -File infra\scripts\backup-db.ps1 -Label golden   # 10/16 11:30 골든 백업
```

- SQLite 온라인 백업 API로 복사하므로 서비스가 켜져 있어도 된다. 파일마다 `integrity_check` 결과를 출력하고, 하나라도 `ok`가 아니면 종료 코드 1.
- 라벨 없는 백업은 최근 5개(`-Keep`)만 남는다. `-Label`을 준 백업(golden·rehearsal1 등)은 지우지 않는다.
- 언제: 매일 09:00, 스키마 변경 전, 리허설 직전, 10/16 11:30 골든(기획서 11장).
- compose에서는 DB가 named volume 안에 있으므로, 컨테이너에서 `/data`를 호스트로 꺼낸 폴더를 `-DataDir`로 준다(compose 연결은 T72 이후).

**복원** (서비스를 멈춘 상태에서만)
1. 로컬 실행: backend·agent·scheduler 프로세스를 끈다 / compose: `docker compose -f infra/docker-compose.yml stop backend agent scheduler`
2. `data\shared.db`·`data\backend.db`와 같은 이름의 `-wal`·`-shm` 파일을 지운 뒤, `backups\<폴더>\`의 두 파일을 `data\`로 복사한다.
3. 서비스를 다시 켜고 로그인·현황 화면이 열리는지 확인한다.
