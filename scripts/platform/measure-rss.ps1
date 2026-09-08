param(
  [int]$LimitMiB = 250
)

$log = Join-Path $env:TEMP "aero-platform-rss-$PID.log"
$process = Start-Process -FilePath node -ArgumentList @("--test", "tests/platform/platform.test.ts") -WorkingDirectory (Resolve-Path "$PSScriptRoot/../..") -PassThru -NoNewWindow -RedirectStandardOutput $log -RedirectStandardError "$log.err"
$peak = 0L
while (-not $process.HasExited) {
  try { $process.Refresh(); $peak = [Math]::Max($peak, $process.WorkingSet64) } catch { }
  Start-Sleep -Milliseconds 20
}
$process.Refresh()
$peak = [Math]::Max($peak, $process.PeakWorkingSet64)
$peakMiB = [Math]::Ceiling($peak / 1MB)
Get-Content $log
if (Test-Path "$log.err") { Get-Content "$log.err" }
Remove-Item -LiteralPath $log -ErrorAction SilentlyContinue
Remove-Item -LiteralPath "$log.err" -ErrorAction SilentlyContinue
Write-Output "platform-test peak RSS: $peakMiB MiB (limit: $LimitMiB MiB)"
if ($process.ExitCode -ne 0) { exit $process.ExitCode }
if ($peakMiB -gt $LimitMiB) { Write-Error "PROJECT_RSS_LIMIT_EXCEEDED"; exit 3 }
