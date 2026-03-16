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

# Read PORT from .env if present
$port = "8080"
if (Test-Path ".env") {
    Get-Content ".env" | ForEach-Object {
        if ($_ -match "^PORT=(.+)$") { $port = $Matches[1].Trim() }
    }
}

Write-Host "  UI: http://localhost:$port" -ForegroundColor Green
Write-Host ""
Write-Host "Starting... (first run may take 2-5 minutes to build)"
Write-Host "Press Ctrl+C to stop."
Write-Host ""

docker compose up --build --remove-orphans

Read-Host "Press Enter to exit"
