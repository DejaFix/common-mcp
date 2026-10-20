# infra/scripts

> 한 줄 요약: 부하 주입·정리·SQLite 백업 PowerShell 스크립트 사용법 (장애 시연용 예시).

Windows PowerShell 운영 스크립트. `*.ps1`은 CRLF(`.gitattributes`).

| 스크립트 | 내용 |
|---|---|
| `inject-cpu.ps1` | `-Minutes N`(기본·최대 10) 코어 수만큼 CPU 부하, 만료·Ctrl+C 시 종료. 이미 주입 중이면 시작하지 않음 |
| `cleanup.ps1` | 주입 프로세스(표식 `INJECT_CPU_MARKER`로 식별) 종료, `%TEMP%\inject-fill\` 삭제 |
| `backup-db.ps1` | SQLite 백업 API로 DB 두 파일(`shared.db`·`backend.db` 예시)을 `backups/`에 복사, 최근 5개 유지 |

- 장애 주입 스크립트는 업무 시간 외에 실행하지 않는다.

## 백업·복원 (`backup-db.ps1`)

```powershell
powershell -ExecutionPolicy Bypass -File infra\scripts\backup-db.ps1                 # data\ → backups\<시각>\
powershell -ExecutionPolicy Bypass -File infra\scripts\backup-db.ps1 -Label golden   # 이름 붙인 백업
```

- SQLite 온라인 백업 API로 복사하므로 서비스가 켜져 있어도 된다. 파일마다 `integrity_check` 결과를 출력하고, 하나라도 `ok`가 아니면 종료 코드 1.
- 라벨 없는 백업은 최근 5개(`-Keep`)만 남고, `-Label`을 준 백업은 지우지 않는다.
- 컨테이너 안 볼륨의 DB는 호스트로 꺼낸 폴더를 `-DataDir`로 준다.

**복원** (서비스를 멈춘 상태에서만)
1. 서비스 프로세스(또는 컨테이너)를 끈다.
2. `data\*.db`와 같은 이름의 `-wal`·`-shm` 파일을 지운 뒤, `backups\<폴더>\`의 파일을 `data\`로 복사한다.
3. 서비스를 다시 켜고 동작을 확인한다.
