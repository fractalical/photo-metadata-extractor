# Photo Metadata Extractor — Windows PowerShell launcher

Write-Host ""
Write-Host "+======================================+" -ForegroundColor Cyan
Write-Host "|    Photo Metadata Extractor          |" -ForegroundColor Cyan
Write-Host "+======================================+" -ForegroundColor Cyan
Write-Host ""

try { docker info 2>&1 | Out-Null } catch {
    Write-Host "ERROR: Docker is not running. Please start Docker Desktop." -ForegroundColor Red
    Read-Host "Press Enter to exit"; exit 1
}

# Defaults
$port         = "8080"
$numColors    = "5"
$skipExisting = "true"

# Read settings from .env if present
if (Test-Path ".env") {
    Get-Content ".env" | ForEach-Object {
        if ($_ -match "^PORT=(.+)$")          { $port         = $Matches[1].Trim() }
        if ($_ -match "^NUM_COLORS=(.+)$")    { $numColors    = $Matches[1].Trim() }
        if ($_ -match "^SKIP_EXISTING=(.+)$") { $skipExisting = $Matches[1].Trim() }
        if ($_ -match "^BROWSE_ROOT=(.+)$")   { $env:BROWSE_ROOT = $Matches[1].Trim() }
    }
}

# Auto-detect BROWSE_ROOT from user profile parent (e.g. C:\Users)
if (-not $env:BROWSE_ROOT) {
    $env:BROWSE_ROOT = Split-Path -Parent $env:USERPROFILE
}

$image = "ghcr.io/fractalical/photo-metadata-extractor:latest"

Write-Host "  UI: http://localhost:$port" -ForegroundColor Green
Write-Host ""
Write-Host "Pulling image (first run downloads ~500 MB, subsequent runs are instant)..."
docker pull $image
Write-Host ""
Write-Host "Starting... Press Ctrl+C to stop."
Write-Host ""

docker run --rm `
    --name photo-metadata-extractor-web `
    -p "${port}:8080" `
    -v "$($env:BROWSE_ROOT):/data:rw" `
    -v "pme-model-cache:/app/models" `
    -e PME_ROOT_DIR=/data `
    -e PME_EXECUTION_PROVIDER=CPUExecutionProvider `
    -e "PME_NUM_COLORS=$numColors" `
    -e "PME_SKIP_EXISTING=$skipExisting" `
    -e "BROWSE_ROOT=$($env:BROWSE_ROOT)" `
    $image

Read-Host "Press Enter to exit"
