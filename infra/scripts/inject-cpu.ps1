<#
.SYNOPSIS
  데모용 CPU 부하 주입 (FR-INF-003, G12). 논리 코어 수만큼 부하 프로세스를 띄우고 시간이 지나면 스스로 끝난다.

.DESCRIPTION
  안전 규칙 (docs/plan.md 14장 G12, infra/scripts/README.md)
  - -Minutes 기본 10, 최대 10. 범위를 벗어나면 실행하지 않는다.
  - 부하 프로세스는 각자 종료 시각을 알고 있어서, 이 창을 닫아도 그 시각에 스스로 끝난다.
  - Ctrl+C로 멈추면 부하 프로세스를 바로 종료한다. 남은 것이 있으면 cleanup.ps1.
  - 이미 주입 중이면 새로 시작하지 않는다(중복 부하 방지).
  - 야간 실행 금지(야간 작업 루프 포함). 파일은 만들지 않는다(%TEMP%\dejafix-fill\ 은 디스크 주입용).

.EXAMPLE
  powershell -ExecutionPolicy Bypass -File infra\scripts\inject-cpu.ps1 -Minutes 5
#>
param(
    [int]$Minutes = 10
)

$ErrorActionPreference = 'Stop'
$Marker = 'DEJAFIX_INJECT_CPU'   # cleanup.ps1 이 이 표식으로 부하 프로세스를 찾는다
$MaxMinutes = 10

if ($Minutes -lt 1 -or $Minutes -gt $MaxMinutes) {
    [Console]::Error.WriteLine("[inject-cpu] -Minutes 는 1~$MaxMinutes 사이여야 합니다 (입력: $Minutes).")
    exit 2
}

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

$running = @(Get-InjectProcess)
if ($running.Count -gt 0) {
    [Console]::Error.WriteLine("[inject-cpu] 이미 주입 중인 부하 프로세스가 $($running.Count)개 있습니다. 끝나길 기다리거나 cleanup.ps1 을 먼저 실행하세요.")
    exit 3
}

$cores = [Environment]::ProcessorCount
$startUtc = [DateTime]::UtcNow
$endUtc = $startUtc.AddMinutes($Minutes)
$endTicks = $endUtc.Ticks

# 부하 프로세스: 종료 시각(UTC ticks)이 지나면 루프를 빠져나와 스스로 끝난다.
$worker = "`$tag='$Marker'; `$end=$endTicks; while ([DateTime]::UtcNow.Ticks -lt `$end) { `$x=1.0; for (`$i=0; `$i -lt 200000; `$i++) { `$x = `$x * 1.0000001 } }"
$argList = "-NoProfile -NonInteractive -WindowStyle Hidden -Command `"$worker`""

Write-Host ("[inject-cpu] 시작 {0:yyyy-MM-dd HH:mm:ss} KST / 종료 예정 {1:HH:mm:ss} KST / 부하 프로세스 {2}개(논리 코어 수) / {3}분" -f `
    $startUtc.AddHours(9), $endUtc.AddHours(9), $cores, $Minutes)

$procs = @()
try {
    for ($n = 0; $n -lt $cores; $n++) {
        $p = Start-Process -FilePath 'powershell.exe' -ArgumentList $argList -WindowStyle Hidden -PassThru
        # 같은 PC의 Zabbix agent·화면 조작이 굶지 않게 낮은 우선순위로 돈다. CPU 사용률은 그대로 100% 근처까지 오른다.
        try { $p.PriorityClass = [System.Diagnostics.ProcessPriorityClass]::BelowNormal } catch { }
        $procs += $p
    }
    Write-Host ("[inject-cpu] PID: {0}" -f (($procs | ForEach-Object { $_.Id }) -join ', '))
    Write-Host '[inject-cpu] Ctrl+C 로 즉시 중단할 수 있습니다.'

    while ([DateTime]::UtcNow -lt $endUtc) {
        Start-Sleep -Seconds 15
        $alive = @($procs | Where-Object { -not $_.HasExited }).Count
        $left = [Math]::Max(0, [int]($endUtc - [DateTime]::UtcNow).TotalSeconds)
        Write-Host ("[inject-cpu] 남은 시간 {0}초 / 살아 있는 부하 프로세스 {1}개" -f $left, $alive)
        if ($alive -eq 0) { break }
    }
}
finally {
    # 정상 만료·Ctrl+C·오류 모두 여기서 정리한다.
    $left = @($procs | Where-Object { -not $_.HasExited })
    foreach ($p in $left) {
        try { Stop-Process -Id $p.Id -Force -ErrorAction Stop } catch { }
    }
    Write-Host ("[inject-cpu] 종료 {0:HH:mm:ss} KST / 정리한 부하 프로세스 {1}개" -f [DateTime]::UtcNow.AddHours(9), $left.Count)
}
