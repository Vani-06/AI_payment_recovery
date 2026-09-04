# Pre-generate LLM narratives for the demo seed so the trace drawer is instant.
# No-op-fast when ANTHROPIC_API_KEY is unset (templated prose is already instant).
$root = Split-Path $PSScriptRoot -Parent
$venv = Join-Path $root "backend\.venv\Scripts\python.exe"
Push-Location (Join-Path $root "backend")
& $venv -m app.pipeline --seed 7 --mode auto --narrate
Pop-Location
