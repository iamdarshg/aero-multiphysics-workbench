param(
  [ValidateSet('test', 'typecheck', 'build')]
  [string]$Task = 'test',
  [int]$TimeoutSeconds = 120,
  [int]$MemoryLimitMiB = 896,
  [int]$PollMilliseconds = 250
)

if ($MemoryLimitMiB -le 0) { throw 'MemoryLimitMiB must be positive' }
if ($TimeoutSeconds -le 0) { throw 'TimeoutSeconds must be positive' }
if ($PollMilliseconds -le 0) { throw 'PollMilliseconds must be positive' }

$repo = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$outputPath = Join-Path $env:TEMP ("aero-workbench-$Task-rss.out")
$errorPath = Join-Path $env:TEMP ("aero-workbench-$Task-rss.err")
$memoryLimitBytes = [int64]$MemoryLimitMiB * 1MB
$process = $null
$rootPid = 0
$knownPids = [System.Collections.Generic.HashSet[int]]::new()
$peakPids = [System.Collections.Generic.HashSet[int]]::new()
$peakBytes = 0L
$samples = 0
$failureReason = $null
$commandExitCode = 1

function Get-ProcessSnapshot {
  try {
    $snapshot = @(Get-CimInstance Win32_Process -ErrorAction Stop)
    if ($null -eq $snapshot) { throw 'the process snapshot was null' }
    return $snapshot
  } catch {
    throw "Process inspection failed: $($_.Exception.Message)"
  }
}

function Expand-TrackedPids([object[]]$Snapshot) {
  $changed = $true
  while ($changed) {
    $changed = $false
    foreach ($item in $Snapshot) {
      if ($knownPids.Contains([int]$item.ParentProcessId) -and $knownPids.Add([int]$item.ProcessId)) {
        $changed = $true
      }
    }
  }
}

function Stop-TrackedProcesses {
  # Children are terminated before the command wrapper/root so descendants cannot outlive the receipt.
  $descendants = @($knownPids | Where-Object { $_ -ne $rootPid })
  foreach ($processId in $descendants) {
    try { Stop-Process -Id $processId -Force -ErrorAction Stop } catch {}
  }
  if ($rootPid -gt 0) {
    try { Stop-Process -Id $rootPid -Force -ErrorAction Stop } catch {}
  }
}

try {
  Remove-Item $outputPath, $errorPath -Force -ErrorAction SilentlyContinue
  $process = Start-Process -FilePath 'pnpm.cmd' -ArgumentList '--filter', '@aero/web', $Task `
    -WorkingDirectory $repo -RedirectStandardOutput $outputPath -RedirectStandardError $errorPath -PassThru
  $rootPid = $process.Id
  [void]$knownPids.Add($rootPid)
  $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
  $rootExited = $false

  # Continue after the root exits until every discovered descendant exits. This catches detached workers
  # whose parent chain still leads back to the command root.
  while ($true) {
    if ((Get-Date) -ge $deadline) { throw "RSS measurement timed out after $TimeoutSeconds seconds" }
    $snapshot = Get-ProcessSnapshot
    Expand-TrackedPids $snapshot

    try { $process.Refresh(); $rootExited = $process.HasExited } catch { $rootExited = $true }
    $livePids = [System.Collections.Generic.List[int]]::new()
    $rssBytes = 0L
    $membership = [System.Collections.Generic.HashSet[int]]::new()
    foreach ($processId in @($knownPids)) {
      $snapshotEntry = @($snapshot | Where-Object { [int]$_.ProcessId -eq $processId })
      try {
        $child = Get-Process -Id $processId -ErrorAction Stop
        [void]$livePids.Add($processId)
        [void]$membership.Add($processId)
        $rssBytes += [int64]$child.WorkingSet64
      } catch {
        # A process can exit between the authoritative snapshot and Get-Process. Re-query once;
        # if the PID is still present, inspection failed and the monitor must fail closed.
        try { $freshEntry = @(Get-CimInstance Win32_Process -Filter "ProcessId = $processId" -ErrorAction Stop) } catch { throw "Process inspection failed for PID $processId" }
        if ($snapshotEntry.Count -gt 0 -and $freshEntry.Count -gt 0) { throw "Process inspection failed for live PID $processId" }
      }
    }

    $samples++
    if ($rssBytes -gt $peakBytes) {
      $peakBytes = $rssBytes
      $peakPids = [System.Collections.Generic.HashSet[int]]::new($membership)
    }
    if ($rssBytes -gt $memoryLimitBytes) {
      throw "Aggregate RSS ceiling exceeded: $([math]::Round($rssBytes / 1MB, 1)) MiB > $MemoryLimitMiB MiB"
    }

    if ($rootExited -and $livePids.Count -eq 0) { break }
    Start-Sleep -Milliseconds $PollMilliseconds
  }

  $process.WaitForExit()
  $commandExitCode = $process.ExitCode
} catch {
  $failureReason = $_.Exception.Message
  Stop-TrackedProcesses
} finally {
  if ($process -and -not $process.HasExited -and $failureReason) { Stop-TrackedProcesses }
  if (Test-Path $outputPath) { Get-Content $outputPath }
  if (Test-Path $errorPath) { Get-Content $errorPath }
  Remove-Item $outputPath, $errorPath -Force -ErrorAction SilentlyContinue
}

Write-Output ("RSS_ROOT_PID=$rootPid")
Write-Output ("RSS_TRACKED_PIDS=$(@($knownPids | Sort-Object) -join ',')")
Write-Output ("RSS_PEAK_PIDS=$(@($peakPids | Sort-Object) -join ',')")
Write-Output ("RSS_PEAK_MEMBERSHIP_COUNT=$($peakPids.Count)")
Write-Output ("RSS_PEAK_BYTES=$peakBytes")
Write-Output ("RSS_PEAK_MIB={0:N1}" -f ($peakBytes / 1MB))
Write-Output ("RSS_LIMIT_MIB=$MemoryLimitMiB")
Write-Output ("RSS_SAMPLES=$samples")
if ($failureReason) {
  Write-Error $failureReason
  exit 1
}
exit $commandExitCode
