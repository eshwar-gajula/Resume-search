$ErrorActionPreference = 'Stop'

$projectRoot = $PSScriptRoot
$backendPath = Join-Path $projectRoot 'backend'
$frontendPath = Join-Path $projectRoot 'frontend'
$venvPython = Join-Path $backendPath '.venv\Scripts\python.exe'
$envPath = Join-Path $backendPath '.env'
$envExamplePath = Join-Path $backendPath '.env.example'

if (-not (Get-Command py -ErrorAction SilentlyContinue)) {
    throw 'The Python launcher was not found. Install Python 3.12 (64-bit) from python.org and retry.'
}

try {
    $pythonVersionText = (& py -3.12 --version 2>&1 | Out-String).Trim()
    if ($LASTEXITCODE -ne 0) { throw 'Python 3.12 is not installed.' }
} catch {
    throw 'Python 3.12 is required. Install Python 3.12 (64-bit) and retry.'
}

$nodeCommand = Get-Command node -ErrorAction SilentlyContinue
if (-not $nodeCommand) {
    throw 'Node.js was not found. Install Node.js 20.9 or newer and retry.'
}
$nodeVersionText = (& node --version).Trim().TrimStart('v')
try { $nodeVersion = [version]$nodeVersionText } catch { throw "Could not read the Node.js version: $nodeVersionText" }
if ($nodeVersion -lt [version]'20.9.0') {
    throw "Node.js 20.9 or newer is required; found $nodeVersionText. Install a newer Node.js and retry."
}

if (-not (Test-Path -LiteralPath $venvPython)) {
    Write-Host 'Creating the Python 3.12 virtual environment...'
    & py -3.12 -m venv (Join-Path $backendPath '.venv')
    if ($LASTEXITCODE -ne 0) { throw 'Could not create the Python virtual environment.' }
}

Write-Host 'Installing backend dependencies...'
& $venvPython -m pip install --upgrade pip
if ($LASTEXITCODE -ne 0) { throw 'Could not upgrade pip.' }
& $venvPython -m pip install -r (Join-Path $backendPath 'requirements.txt')
if ($LASTEXITCODE -ne 0) { throw 'Backend dependency installation failed.' }

if (-not (Test-Path -LiteralPath $envPath)) {
    Copy-Item -LiteralPath $envExamplePath -Destination $envPath
    $randomBytes = [byte[]]::new(48)
    $randomGenerator = [System.Security.Cryptography.RandomNumberGenerator]::Create()
    try { $randomGenerator.GetBytes($randomBytes) } finally { $randomGenerator.Dispose() }
    $jwtSecret = [Convert]::ToBase64String($randomBytes).TrimEnd('=').Replace('+', '-').Replace('/', '_')
    $envText = [IO.File]::ReadAllText($envPath)
    $envText = [regex]::Replace($envText, '(?m)^JWT_SECRET=.*$', "JWT_SECRET=$jwtSecret")
    [IO.File]::WriteAllText($envPath, $envText, [Text.UTF8Encoding]::new($false))
    Write-Host 'Created backend\.env with a generated local JWT secret.'
} else {
    Write-Host 'Keeping the existing backend\.env file.'
}

Write-Host 'Installing frontend dependencies...'
Push-Location $frontendPath
try {
    & npm ci
    if ($LASTEXITCODE -ne 0) { throw 'Frontend dependency installation failed.' }
} finally {
    Pop-Location
}

Write-Host ''
Write-Host 'Setup complete. Start each part in a separate PowerShell window:'
Write-Host '  .\start-backend.ps1'
Write-Host '  .\start-frontend.ps1'
Write-Host 'Then open http://127.0.0.1:3000'
