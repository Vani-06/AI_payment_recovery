# One-command dev start: Postgres (Docker) + backend + frontend.
# Usage:  .\scripts\dev.ps1
$ErrorActionPreference = "Stop"
$root = Split-Path $PSScriptRoot -Parent
Set-Location $root

Write-Host "==> Postgres" -ForegroundColor Cyan
docker compose up -d
for ($i = 0; $i -lt 30; $i++) {
  $s = (docker inspect -f '{{.State.Health.Status}}' sherlock-db 2>$null)
  if ($s -eq "healthy") { break }
  Start-Sleep 2
}
Write-Host "    db: $s"

$venv = Join-Path $root "backend\.venv\Scripts\python.exe"
if (-not (Test-Path $venv)) {
  Write-Host "==> Creating backend venv" -ForegroundColor Cyan
  python -m venv (Join-Path $root "backend\.venv")
  & $venv -m pip install -q -r (Join-Path $root "backend\requirements.txt")
}

Write-Host "==> Seeding + running batch (seed 7)" -ForegroundColor Cyan
Push-Location (Join-Path $root "backend")
& $venv -m app.pipeline --seed 7 --mode auto | Out-Null
Pop-Location

Write-Host "==> Backend  http://localhost:8000" -ForegroundColor Cyan
Start-Process -WindowStyle Minimized $venv -ArgumentList "-m","uvicorn","app.main:app","--port","8000","--reload" -WorkingDirectory (Join-Path $root "backend")

if (-not (Test-Path (Join-Path $root "frontend\node_modules"))) {
  Write-Host "==> Installing frontend deps" -ForegroundColor Cyan
  Push-Location (Join-Path $root "frontend"); pnpm install; Pop-Location
}

Write-Host "==> Frontend  http://localhost:3000" -ForegroundColor Cyan
Start-Process -WindowStyle Minimized pnpm -ArgumentList "dev" -WorkingDirectory (Join-Path $root "frontend")

Start-Sleep 6
Start-Process "http://localhost:3000"
Write-Host "`nUp. Stop with: taskkill /F /IM node.exe ; docker compose down" -ForegroundColor Green
