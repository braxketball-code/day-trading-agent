#Requires -Version 5.1
<#
.SYNOPSIS
    Launcher for the Day Trading Agent.

.EXAMPLE
    .\run.ps1                  # Start trading during market hours
    .\run.ps1 -Simulate        # Run offline simulation
    .\run.ps1 -Status          # Show account status
    .\run.ps1 -DryRun          # Test broker connection
#>

param(
    [switch]$Simulate,
    [switch]$Status,
    [switch]$DryRun,
    [double]$Equity = 100000
)

$ErrorActionPreference = "Stop"
$ProjectRoot = $PSScriptRoot
Set-Location $ProjectRoot

if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
    Write-Host "Python not found. Run .\setup.ps1 first." -ForegroundColor Red
    exit 1
}

if (-not (Test-Path ".\.env") -and -not $Simulate) {
    Write-Host ".env not found. Run .\setup.ps1 first." -ForegroundColor Yellow
    exit 1
}

$argsList = @("-m", "src.main")

if ($Simulate) { $argsList += "--simulate" }
if ($Status)   { $argsList += "--status" }
if ($DryRun)   { $argsList += "--dry-run" }
if ($Simulate) { $argsList += @("--equity", $Equity) }

Write-Host ""
if ($Simulate) {
    Write-Host "Running simulation..." -ForegroundColor Cyan
}
elseif ($Status) {
    Write-Host "Fetching account status..." -ForegroundColor Cyan
}
elseif ($DryRun) {
    Write-Host "Testing broker connection..." -ForegroundColor Cyan
}
else {
    Write-Host "Starting day trading agent (Ctrl+C to stop)..." -ForegroundColor Cyan
}
Write-Host ""

python @argsList
exit $LASTEXITCODE