$ErrorActionPreference = "Stop"
$root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$workspacePath = Join-Path $root "pnpm-workspace.yaml"
$workspaceText = Get-Content -Raw $workspacePath
$patterns = [regex]::Matches($workspaceText, '^\s*-\s*[\x27\"]([^\x27\"]+)[\x27\"]', [Text.RegularExpressions.RegexOptions]::Multiline) | ForEach-Object { $_.Groups[1].Value }
if ($patterns.Count -eq 0) { throw "WORKSPACE_HAS_NO_PACKAGE_GLOBS" }
$manifests = @()
foreach ($pattern in $patterns) {
  $folder = $pattern -replace "/\*$", ""
  $packageRoot = Join-Path $root $folder
  if (-not (Test-Path -LiteralPath $packageRoot -PathType Container)) { continue }
  Get-ChildItem -LiteralPath $packageRoot -Directory | ForEach-Object {
    $manifestPath = Join-Path $_.FullName "package.json"
    if (Test-Path -LiteralPath $manifestPath -PathType Leaf) {
      $manifest = Get-Content -Raw $manifestPath | ConvertFrom-Json
      if ([string]::IsNullOrWhiteSpace($manifest.name)) { throw "PACKAGE_NAME_MISSING: $manifestPath" }
      if ([string]::IsNullOrWhiteSpace($manifest.scripts.test)) { throw "PACKAGE_TEST_SCRIPT_MISSING: $manifestPath" }
      $manifests += $manifestPath
    }
  }
}
if ($manifests.Count -eq 0) { throw "NO_WORKSPACE_PACKAGE_MANIFESTS" }
Write-Output ("Verified {0} workspace package manifests with test commands." -f $manifests.Count)
