param(
  [ValidateSet('test', 'typecheck', 'build')]
  [string]$Task = 'test',
  [int]$TimeoutSeconds = 120
)

$repo = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$outputPath = Join-Path $env:TEMP ("aero-workbench-$Task-rss.out")
$errorPath = Join-Path $env:TEMP ("aero-workbench-$Task-rss.err")
Remove-Item $outputPath, $errorPath -Force -ErrorAction SilentlyContinue

$process = Start-Process -FilePath 'pnpm.cmd' -ArgumentList '--filter', '@aero/web', $Task `
  -WorkingDirectory $repo -RedirectStandardOutput $outputPath -RedirectStandardError $errorPath -PassThru
$peakBytes = 0L
$samples = 0
$deadline = (Get-Date).AddSeconds($TimeoutSeconds)

while (-not $process.HasExited -and (Get-Date) -lt $deadline) {
  $snapshot = Get-CimInstance Win32_Process
  $ids = [System.Collections.Generic.HashSet[int]]::new()
  [void]$ids.Add($process.Id)
  $changed = $true
  while ($changed) {
    $changed = $false
    foreach ($item in $snapshot) {
      if ($ids.Contains([int]$item.ParentProcessId) -and $ids.Add([int]$item.ProcessId)) {
        $changed = $true
      }
    }
  }

  $rssBytes = 0L
  foreach ($id in $ids) {
    try { $rssBytes += (Get-Process -Id $id -ErrorAction Stop).WorkingSet64 } catch {}
  }
  if ($rssBytes -gt $peakBytes) { $peakBytes = $rssBytes }
  $samples++
  Start-Sleep -Milliseconds 250
  $process.Refresh()
}

if (-not $process.HasExited) {
  Stop-Process -Id $process.Id -Force -ErrorAction SilentlyContinue
  throw "RSS measurement timed out after $TimeoutSeconds seconds"
}

$process.WaitForExit()
Get-Content $outputPath
if (Test-Path $errorPath) { Get-Content $errorPath }
Remove-Item $outputPath, $errorPath -Force -ErrorAction SilentlyContinue
Write-Output ("RSS_PEAK_BYTES=$peakBytes")
Write-Output ("RSS_PEAK_MIB={0:N1}" -f ($peakBytes / 1MB))
Write-Output ("RSS_SAMPLES=$samples")
exit $process.ExitCode
