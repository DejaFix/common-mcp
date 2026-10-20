<#
.SYNOPSIS
  장애 주입 정리 (FR-INF-005, G12). 주입 부하 프로세스를 끝내고 %TEMP%\dejafix-fill\ 을 지운다.

.DESCRIPTION
  - 부하 프로세스는 inject-cpu.ps1 이 명령줄에 넣는 표식(DEJAFIX_INJECT_CPU)으로만 찾는다. 다른 powershell 창은 건드리지 않는다.
  - 지우는 폴더는 %TEMP%\dejafix-fill\ 하나뿐이다(디스크 주입용, inject-disk.ps1 [선택]).
  - 끝나면 남은 부하 프로세스 수와 폴더 존재 여부를 출력한다. 둘 다 0/없음이면 종료 코드 0.

.EXAMPLE
  powershell -ExecutionPolicy Bypass -File infra\scripts\cleanup.ps1
#>
$ErrorActionPreference = 'Stop'
$Marker = 'DEJAFIX_INJECT_CPU'
$FillDir = Join-Path $env:TEMP 'dejafix-fill'

# 워커만 고른다: 표식 + 워커 명령줄 형태(-NonInteractive -WindowStyle Hidden -Command "$tag='표식'").
# 표식 문자열만 들어간 다른 셸(예: rg DEJAFIX_INJECT_CPU)은 잡지 않는다.
function Get-InjectProcess {
    Get-CimInstance Win32_Process -Filter "Name = 'powershell.exe'" |
        Where-Object {
            $_.ProcessId -ne $PID -and
            $_.CommandLine -like "*-NonInteractive -WindowStyle Hidden -Command*" -and
            $_.CommandLine -like "*`$tag='$Marker'*"
        }
}

$found = @(Get-InjectProcess)
foreach ($p in $found) {
    try { Stop-Process -Id $p.ProcessId -Force -ErrorAction Stop } catch { }
}
Write-Host ("[cleanup] 부하 프로세스 {0}개 종료 요청" -f $found.Count)

if (Test-Path -LiteralPath $FillDir) {
    try {
        Remove-Item -LiteralPath $FillDir -Recurse -Force -ErrorAction Stop
        Write-Host "[cleanup] $FillDir 삭제"
    }
    catch {
        # 삭제 실패해도 아래 확인 출력과 exit 1 로 보고한다
        [Console]::Error.WriteLine("[cleanup] $FillDir 삭제 실패: $($_.Exception.Message)")
    }
}

Start-Sleep -Seconds 1
$remain = @(Get-InjectProcess).Count
$dirLeft = Test-Path -LiteralPath $FillDir
Write-Host ("[cleanup] 확인: 남은 부하 프로세스 {0}개 / dejafix-fill {1}" -f $remain, $(if ($dirLeft) { '남아 있음' } else { '없음' }))
if ($remain -gt 0 -or $dirLeft) { exit 1 }
exit 0
