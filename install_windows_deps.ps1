# Windows Dependencies Installer for WriterOS
# Installs Visual C++ Redistributable required for FastEmbed

Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "WriterOS Windows Dependencies Installer" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host ""

Write-Host "This script will help you install the required dependencies for WriterOS on Windows." -ForegroundColor Yellow
Write-Host ""

# Check if running as administrator
$isAdmin = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)

if (-not $isAdmin) {
    Write-Host "WARNING: Not running as Administrator" -ForegroundColor Yellow
    Write-Host "The Visual C++ Redistributable installer requires administrator rights." -ForegroundColor Yellow
    Write-Host ""
    Write-Host "Please right-click this script and select 'Run as Administrator'" -ForegroundColor Yellow
    Write-Host ""
    pause
    exit 1
}

Write-Host "✓ Running with administrator privileges" -ForegroundColor Green
Write-Host ""

# Download URL for VC++ Redistributable
$vcRedistUrl = "https://aka.ms/vs/17/release/vc_redist.x64.exe"
$downloadPath = "$env:TEMP\vc_redist.x64.exe"

Write-Host "Downloading Visual C++ 2015-2022 Redistributable..." -ForegroundColor Cyan
Write-Host "URL: $vcRedistUrl" -ForegroundColor Gray

try {
    # Download the installer
    $progressPreference = 'silentlyContinue'
    Invoke-WebRequest -Uri $vcRedistUrl -OutFile $downloadPath -UseBasicParsing
    Write-Host "✓ Download complete" -ForegroundColor Green
    Write-Host ""
} catch {
    Write-Host "✗ Download failed: $_" -ForegroundColor Red
    Write-Host ""
    Write-Host "Please manually download and install from:" -ForegroundColor Yellow
    Write-Host $vcRedistUrl -ForegroundColor Yellow
    pause
    exit 1
}

Write-Host "Installing Visual C++ Redistributable..." -ForegroundColor Cyan
Write-Host "This may take a few minutes..." -ForegroundColor Gray
Write-Host ""

try {
    # Install silently
    $process = Start-Process -FilePath $downloadPath -ArgumentList "/install", "/quiet", "/norestart" -Wait -PassThru

    if ($process.ExitCode -eq 0) {
        Write-Host "✓ Visual C++ Redistributable installed successfully!" -ForegroundColor Green
    } elseif ($process.ExitCode -eq 1638) {
        Write-Host "✓ Visual C++ Redistributable already installed (newer version)" -ForegroundColor Green
    } elseif ($process.ExitCode -eq 3010) {
        Write-Host "✓ Visual C++ Redistributable installed (restart required)" -ForegroundColor Yellow
        Write-Host "Please restart your computer for changes to take effect." -ForegroundColor Yellow
    } else {
        Write-Host "✗ Installation failed with exit code: $($process.ExitCode)" -ForegroundColor Red
        Write-Host "Please try installing manually from: $vcRedistUrl" -ForegroundColor Yellow
    }
} catch {
    Write-Host "✗ Installation failed: $_" -ForegroundColor Red
    Write-Host "Please try installing manually from: $vcRedistUrl" -ForegroundColor Yellow
}

Write-Host ""

# Clean up
Remove-Item $downloadPath -ErrorAction SilentlyContinue

Write-Host "Testing FastEmbed installation..." -ForegroundColor Cyan
Write-Host ""

# Test if FastEmbed can be imported
$testScript = @"
import sys
try:
    from fastembed import TextEmbedding
    print('✓ FastEmbed is working correctly!')
    sys.exit(0)
except ImportError as e:
    print(f'✗ FastEmbed import failed: {e}')
    print('\nPlease restart your terminal/IDE and try again.')
    sys.exit(1)
"@

$testScript | python 2>&1

if ($LASTEXITCODE -eq 0) {
    Write-Host ""
    Write-Host "==========================================" -ForegroundColor Green
    Write-Host "✓ All dependencies installed successfully!" -ForegroundColor Green
    Write-Host "==========================================" -ForegroundColor Green
} else {
    Write-Host ""
    Write-Host "==========================================" -ForegroundColor Yellow
    Write-Host "Next Steps:" -ForegroundColor Yellow
    Write-Host "==========================================" -ForegroundColor Yellow
    Write-Host "1. Close this terminal/IDE" -ForegroundColor White
    Write-Host "2. Open a new terminal/IDE" -ForegroundColor White
    Write-Host "3. Try importing FastEmbed again:" -ForegroundColor White
    Write-Host "   python -c `"from fastembed import TextEmbedding; print('OK')`"" -ForegroundColor Gray
}

Write-Host ""
pause
