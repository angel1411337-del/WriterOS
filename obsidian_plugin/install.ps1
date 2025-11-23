# WriterOS Plugin Installer
# This script copies the plugin to your Obsidian vault

param(
    [Parameter(Mandatory=$true)]
    [string]$VaultPath
)

$pluginSource = $PSScriptRoot
$pluginDest = Join-Path $VaultPath ".obsidian\plugins\writeros"

Write-Host "Installing WriterOS Plugin..." -ForegroundColor Cyan
Write-Host "Source: $pluginSource" -ForegroundColor Gray
Write-Host "Destination: $pluginDest" -ForegroundColor Gray

# Create plugin directory
if (!(Test-Path $pluginDest)) {
    Write-Host "Creating plugin directory..." -ForegroundColor Yellow
    New-Item -ItemType Directory -Force -Path $pluginDest | Out-Null
}

# Copy required files
Write-Host "Copying files..." -ForegroundColor Yellow

$filesToCopy = @("main.js", "manifest.json")

foreach ($file in $filesToCopy) {
    $sourcePath = Join-Path $pluginSource $file
    if (Test-Path $sourcePath) {
        Copy-Item $sourcePath -Destination $pluginDest -Force
        Write-Host "  Copied $file" -ForegroundColor Green
    } else {
        Write-Host "  Missing $file" -ForegroundColor Red
    }
}

# Check for styles.css (optional)
$stylesPath = Join-Path $pluginSource "styles.css"
if (Test-Path $stylesPath) {
    Copy-Item $stylesPath -Destination $pluginDest -Force
    Write-Host "  Copied styles.css" -ForegroundColor Green
}

Write-Host ""
Write-Host "Installation complete!" -ForegroundColor Green
Write-Host ""
Write-Host "Next steps:" -ForegroundColor Cyan
Write-Host "1. Open Obsidian" -ForegroundColor White
Write-Host "2. Go to Settings -> Community plugins" -ForegroundColor White
Write-Host "3. Turn OFF Safe mode (if it's on)" -ForegroundColor White
Write-Host "4. Find 'WriterOS' in the list and toggle it ON" -ForegroundColor White
Write-Host "5. Reload Obsidian (Ctrl+R)" -ForegroundColor White
Write-Host ""
Write-Host "To verify, open Command Palette (Ctrl+P) and search for 'WriterOS'" -ForegroundColor Gray
