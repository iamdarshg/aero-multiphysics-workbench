# RP-G1 one-flag experiment: enable the per-sample occupancy objective.
#
# Everything except --geometry-occupancy-mean-weight matches the run1 recipe
# recorded in HANDOFF_ORCHESTRATOR.md §17.2 (660/96 procedural corpus, 14 epochs,
# corpus-only i.e. no latent augmentation). The weight is the only changed knob.
#
# Usage:  pwsh -File run_rp_g1_occupancy.ps1 -Weight 0.5 -Epochs 14 -Tag w0p5
param(
    [double]$Weight = 0.5,
    [int]$Epochs = 14,
    [string]$Tag = "w0p5",
    [int]$StopAfterUpdates = 0
)

$ErrorActionPreference = "Stop"
$rp = "E:\engineering-portfolio-audit\repos\research-paper"
$run = "E:\engineering-portfolio-audit\evidence\research-paper\rp-g1"
$manifest = Join-Path $run "corpus\manifest.jsonl"
$saveDir = Join-Path $run "run-$Tag\checkpoints"
$history = Join-Path $run "run-$Tag\history.json"
$updates = Join-Path $run "run-$Tag\updates.jsonl"

if (-not (Test-Path $manifest)) { throw "corpus manifest missing: $manifest" }
New-Item -ItemType Directory -Force -Path (Split-Path $saveDir) | Out-Null

$env:PYTHONPATH = "$rp\CLI"
Set-Location $rp

$args = @(
    "CLI/run_monitored_training.py",
    "--manifest", $manifest,
    "--num-epochs", "$Epochs",
    "--batch-size", "1",
    "--latent-dim", "192",
    "--grid-size", "32",
    "--learning-rate", "0.00002",
    "--precision", "float32",
    "--solver", "D3Q27",
    "--save-dir", $saveDir,
    "--history-output", $history,
    "--updates-output", $updates,
    "--geometry-occupancy-mean-weight", "$Weight",
    "--training-split", "train",
    "--promotion-split", "holdout",
    "--no-enable-tensorboard",
    "--no-enable-compile",
    "--no-enable-gradient-checkpointing",
    "--no-stop-on-promotion-pass",
    "--no-save-final-checkpoint"
)
if ($StopAfterUpdates -gt 0) {
    $args += @("--stop-after-updates", "$StopAfterUpdates")
}

Write-Host "=== RP-G1 run tag=$Tag weight=$Weight epochs=$Epochs stopAfter=$StopAfterUpdates ==="
Write-Host "manifest: $manifest"
Write-Host "save-dir: $saveDir"
& python @args 2>&1 | Tee-Object -FilePath (Join-Path $run "run-$Tag\train.log")
exit $LASTEXITCODE
