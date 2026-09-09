param(
  [int]$LimitMiB = 250
)

$log = Join-Path $env:TEMP "aero-platform-rss-$PID.log"
$process = Start-Process -FilePath node -ArgumentList @("--test", "tests/platform/platform.test.ts") -WorkingDirectory (Resolve-Path "$PSScriptRoot/../..") -PassThru -NoNewWindow -RedirectStandardOutput $log -RedirectStandardError "$log.err"
$peak = 0L
$observed = [System.Collections.Generic.HashSet[int]]::new()
$treeIds = @($process.Id)
$nextTreeRefresh = [DateTime]::MinValue
function Get-WorkerTreeIds([int]$RootPid) {
  try {
    $table = @(Get-CimInstance Win32_Process -ErrorAction Stop | Select-Object ProcessId, ParentProcessId)
    $ids = [System.Collections.Generic.HashSet[int]]::new()
    [void]$ids.Add($RootPid)
    do {
      $added = $false
      foreach ($row in $table) {
        if ($ids.Contains([int]$row.ParentProcessId) -and $ids.Add([int]$row.ProcessId)) { $added = $true }
      }
    } while ($added)
    return @($ids)
  } catch { return @($RootPid) }
}
while (-not $process.HasExited) {
  if ((Get-Date) -ge $nextTreeRefresh) {
    $treeIds = Get-WorkerTreeIds $process.Id
    $nextTreeRefresh = (Get-Date).AddSeconds(1)
  }
  foreach ($id in $treeIds) { [void]$observed.Add($id) }
  $total = 0L
  foreach ($id in $observed) { try { $total += (Get-Process -Id $id -ErrorAction Stop).WorkingSet64 } catch { } }
  $peak = [Math]::Max($peak, $total)
  Start-Sleep -Milliseconds 100
}
foreach ($id in (Get-WorkerTreeIds $process.Id)) { [void]$observed.Add($id) }
$total = 0L
foreach ($id in $observed) { try { $total += (Get-Process -Id $id -ErrorAction Stop).WorkingSet64 } catch { } }
$peak = [Math]::Max($peak, $total)
$peakMiB = [Math]::Ceiling($peak / 1MB)
Get-Content $log
if (Test-Path "$log.err") { Get-Content "$log.err" }
Remove-Item -LiteralPath $log -ErrorAction SilentlyContinue
Remove-Item -LiteralPath "$log.err" -ErrorAction SilentlyContinue
Write-Output "platform-test worker-tree peak RSS: $peakMiB MiB (limit: $LimitMiB MiB; non-authoritative host aggregate)"
if ($process.ExitCode -ne 0) { exit $process.ExitCode }
if ($peakMiB -gt $LimitMiB) { Write-Error "PROJECT_RSS_LIMIT_EXCEEDED"; exit 3 }
