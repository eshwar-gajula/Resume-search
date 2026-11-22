$ErrorActionPreference = 'Stop'
$projectRoot = $PSScriptRoot
$backendPath = Join-Path $projectRoot 'backend'
$venvPython = Join-Path $backendPath '.venv\Scripts\python.exe'
$apiPort = 8010
if ($env:RESUMEAI_API_PORT) {
    try { $apiPort = [int]$env:RESUMEAI_API_PORT } catch { throw 'RESUMEAI_API_PORT must be a port number.' }
}

if (-not (Test-Path -LiteralPath $venvPython)) {
    throw 'Backend packages are not set up yet. Run .\setup.ps1 first.'
}

Push-Location $backendPath
try {
    & $venvPython -m uvicorn app.main:app --reload --host 127.0.0.1 --port $apiPort
    if ($LASTEXITCODE -ne 0) { throw 'The backend stopped with an error.' }
} finally {
    Pop-Location
}
