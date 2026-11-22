$ErrorActionPreference = 'Stop'
$frontendPath = Join-Path $PSScriptRoot 'frontend'

if (-not (Test-Path -LiteralPath (Join-Path $frontendPath 'node_modules\next\package.json'))) {
    throw 'Frontend packages are not set up yet. Run .\setup.ps1 first.'
}

Push-Location $frontendPath
try {
    & npm run dev -- --hostname 127.0.0.1
    if ($LASTEXITCODE -ne 0) { throw 'The frontend stopped with an error.' }
} finally {
    Pop-Location
}
