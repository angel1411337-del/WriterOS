# Build WriterOS Obsidian Plugin
# This script builds the plugin using the local node_modules

$ErrorActionPreference = "Stop"

Write-Host "Building WriterOS Plugin..." -ForegroundColor Cyan

# Check if node_modules exists
if (!(Test-Path "node_modules")) {
    Write-Host "node_modules not found. Please run npm install first." -ForegroundColor Red
    exit 1
}

Write-Host "Running TypeScript compiler..." -ForegroundColor Yellow
& "C:\Program Files\nodejs\node.exe" ".\node_modules\typescript\bin\tsc" -noEmit

if ($LASTEXITCODE -ne 0) {
    Write-Host "TypeScript compilation failed!" -ForegroundColor Red
    exit 1
}

Write-Host "Running esbuild..." -ForegroundColor Yellow
& "C:\Program Files\nodejs\node.exe" esbuild.config.mjs production

if ($LASTEXITCODE -eq 0) {
    Write-Host ""
    Write-Host "✓ Build successful!" -ForegroundColor Green
    Write-Host "  Output: main.js" -ForegroundColor Gray
    Write-Host ""
    Write-Host "Next step: Run .\install.ps1 -VaultPath 'C:\Path\To\Your\Vault'" -ForegroundColor Cyan
} else {
    Write-Host "Build failed!" -ForegroundColor Red
    exit 1
}
