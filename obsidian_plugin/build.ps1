Write-Host "Checking for Node.js..."
if (!(Get-Command npm -ErrorAction SilentlyContinue)) {
    Write-Error "npm is not installed. Please install Node.js from https://nodejs.org/"
    exit 1
}

Write-Host "Installing dependencies..."
npm install

Write-Host "Building WriterOS Obsidian Plugin..."
npm run build

if ($LASTEXITCODE -eq 0) {
    Write-Host "Build successful!" -ForegroundColor Green
    Write-Host "`nTo install:"
    Write-Host "1. Go to your Obsidian Vault: .obsidian/plugins/"
    Write-Host "2. Create a folder named 'writeros'"
    Write-Host "3. Copy 'main.js' and 'manifest.json' to that folder"
    Write-Host "4. Enable the plugin in Obsidian Settings"
} else {
    Write-Error "Build failed."
}
