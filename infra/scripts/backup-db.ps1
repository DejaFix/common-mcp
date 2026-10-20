<#
.SYNOPSIS
  SQLite 2파일 백업. SQLite DB 두 파일(shared.db·backend.db 예시)을 SQLite 백업 API로 backups\ 에 복사한다.

.DESCRIPTION
  - 파일 복사(cp)가 아니라 SQLite 온라인 백업 API를 쓴다. 서비스가 켜져 있어도(WAL 쓰는 중) 일관된 사본이 나온다.
  - 실행마다 backups\<yyyyMMdd-HHmmss>[-라벨]\ 폴더 하나에 두 파일을 만들고, 각각 PRAGMA integrity_check 결과를 출력한다.
  - 라벨 없는 백업은 최근 -Keep 개(기본 5)만 남기고 오래된 것부터 지운다. -Label 을 준 백업(예: golden)은 지우지 않는다.
  - 원본 DB는 읽기만 한다. backups\ 는 git 제외(.gitignore).
  - 복원은 이 스크립트가 하지 않는다. 서비스를 멈춘 뒤 파일을 되돌려 놓는다(아래 README 「복원」).

.PARAMETER DataDir
  원본 DB 폴더. 기본: 저장소 루트의 data\ (로컬 실행 기본 경로).

.PARAMETER OutDir
  백업을 둘 폴더. 기본: 저장소 루트의 backups\

.PARAMETER Keep
  라벨 없는 백업을 몇 개 남길지. 기본 5.

.PARAMETER Label
  폴더 이름 뒤에 붙일 라벨(영문·숫자·-·_). 라벨이 있으면 자동 정리 대상이 아니다. 예: golden, rehearsal1

.EXAMPLE
  powershell -ExecutionPolicy Bypass -File infra\scripts\backup-db.ps1

.EXAMPLE
  powershell -ExecutionPolicy Bypass -File infra\scripts\backup-db.ps1 -Label golden
#>
param(
    [string]$DataDir = '',
    [string]$OutDir = '',
    [ValidateRange(1, 100)][int]$Keep = 5,
    [ValidatePattern('^[A-Za-z0-9_-]{0,32}$')][string]$Label = ''
)
$ErrorActionPreference = 'Stop'

$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
if (-not $DataDir) { $DataDir = Join-Path $RepoRoot 'data' }
if (-not $OutDir) { $OutDir = Join-Path $RepoRoot 'backups' }
$DataDir = [IO.Path]::GetFullPath($DataDir)
$OutDir = [IO.Path]::GetFullPath($OutDir)

$Names = @('shared.db', 'backend.db')
$sources = @($Names | ForEach-Object { Join-Path $DataDir $_ } | Where-Object { Test-Path -LiteralPath $_ })
if ($sources.Count -eq 0) {
    Write-Host "[backup] $DataDir 에 shared.db·backend.db 가 없습니다. -DataDir 를 확인하세요."
    exit 1
}

$stamp = (Get-Date).ToString('yyyyMMdd-HHmmss')
$folderName = if ($Label) { "$stamp-$Label" } else { $stamp }
$dest = Join-Path $OutDir $folderName
New-Item -ItemType Directory -Force -Path $dest | Out-Null

# SQLite 백업 API + integrity_check. 원본은 읽기 전용 URI 로 연다.
$py = @'
import pathlib, sqlite3, sys
src, dst = pathlib.Path(sys.argv[1]), pathlib.Path(sys.argv[2])
s = sqlite3.connect(src.resolve().as_uri() + "?mode=ro", uri=True, timeout=10)
d = sqlite3.connect(dst)
with d:
    s.backup(d)
s.close()
check = d.execute("PRAGMA integrity_check").fetchone()[0]
tables = d.execute("select count(*) from sqlite_master where type='table'").fetchone()[0]
d.close()
print(f"{check}|{tables}")
sys.exit(0 if check == "ok" else 2)
'@

$failed = 0
foreach ($src in $sources) {
    $name = Split-Path $src -Leaf
    $target = Join-Path $dest $name
    $out = $py | uv run --no-project --python 3.12 python -I - $src $target
    if ($LASTEXITCODE -ne 0) {
        $failed++
        Write-Host "[backup] $name 실패: $out"
        continue
    }
    $check, $tables = ($out | Select-Object -Last 1).Split('|')
    $kb = [math]::Round((Get-Item -LiteralPath $target).Length / 1KB, 1)
    Write-Host ("[backup] {0} → {1} ({2} KB, 테이블 {3}개, integrity_check={4})" -f $name, $target, $kb, $tables, $check)
}
foreach ($missing in ($Names | Where-Object { -not (Test-Path -LiteralPath (Join-Path $DataDir $_)) })) {
    Write-Host "[backup] $missing 없음 — 건너뜀"
}

# 라벨 없는 백업(이름이 정확히 yyyyMMdd-HHmmss)만 최근 $Keep 개 유지
$auto = @(Get-ChildItem -LiteralPath $OutDir -Directory |
    Where-Object { $_.Name -match '^\d{8}-\d{6}$' } |
    Sort-Object Name -Descending)
foreach ($old in ($auto | Select-Object -Skip $Keep)) {
    Remove-Item -LiteralPath $old.FullName -Recurse -Force
    Write-Host "[backup] 오래된 백업 삭제: $($old.Name)"
}

if ($failed -gt 0) { exit 1 }
Write-Host "[backup] 완료: $dest"
exit 0
