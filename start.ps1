param(
    [ValidateRange(1, 65535)][int]$BackendPort = 8000,
    [ValidateRange(1, 65535)][int]$FrontendPort = 5173,
    [switch]$OpenBrowser
)

$ErrorActionPreference = 'Stop'
$root = $PSScriptRoot
$backendDir = Join-Path $root 'backend'
$frontendDir = Join-Path $root 'frontend'
$python = Join-Path $backendDir '.venv\Scripts\python.exe'
$vite = Join-Path $frontendDir 'node_modules\vite\bin\vite.js'
$logDir = Join-Path $root 'results\startup'
$backend = $null
$frontend = $null

function Test-PortInUse([int]$port) {
    $client = [System.Net.Sockets.TcpClient]::new()
    try {
        $attempt = $client.ConnectAsync('127.0.0.1', $port)
        return $attempt.Wait(500) -and $client.Connected
    } catch {
        return $false
    } finally {
        $client.Dispose()
    }
}

function Test-JsonEndpoint([string]$url) {
    try {
        $response = Invoke-WebRequest -Uri $url -UseBasicParsing -TimeoutSec 3
        return $response.StatusCode -eq 200 -and
            [string]$response.Headers['Content-Type'] -match 'application/json'
    } catch {
        return $false
    }
}

function Wait-ForEndpoint([string]$url, [System.Diagnostics.Process]$process) {
    for ($attempt = 0; $attempt -lt 40; $attempt++) {
        if (Test-JsonEndpoint $url) { return $true }
        $process.Refresh()
        if ($process.HasExited) { return $false }
        Start-Sleep -Milliseconds 500
    }
    return $false
}

function Stop-ProcessTree([int]$processId) {
    foreach ($child in @(Get-CimInstance Win32_Process -Filter "ParentProcessId = $processId" -ErrorAction SilentlyContinue)) {
        Stop-ProcessTree $child.ProcessId
    }
    Stop-Process -Id $processId -Force -ErrorAction SilentlyContinue
}

if ($BackendPort -eq $FrontendPort) { throw 'BackendPort and FrontendPort must differ.' }

$backendBusy = Test-PortInUse $BackendPort
$frontendBusy = Test-PortInUse $FrontendPort
$backendUrl = "http://127.0.0.1:$BackendPort"
$frontendUrl = "http://127.0.0.1:$FrontendPort"
if ($backendBusy -or $frontendBusy) {
    if ($backendBusy -and $frontendBusy -and
        (Test-JsonEndpoint "$backendUrl/health") -and
        (Test-JsonEndpoint "$frontendUrl/api/v1/demo/state")) {
        Write-Host "SkyWarden is already running at $frontendUrl"
        if ($OpenBrowser) { Start-Process $frontendUrl }
        return
    }
    throw "Port $BackendPort or $FrontendPort is already in use. Stop the existing server or choose -BackendPort and -FrontendPort."
}

if (-not (Test-Path $python)) {
    if (-not (Get-Command py -ErrorAction SilentlyContinue)) { throw 'Python 3.11 launcher (py) is required.' }
    Write-Host 'Creating the backend virtual environment...'
    & py -3.11 -m venv (Join-Path $backendDir '.venv')
    if ($LASTEXITCODE -ne 0) { throw 'Could not create the backend virtual environment.' }
    & $python -m pip install -r (Join-Path $backendDir 'requirements.lock')
    if ($LASTEXITCODE -ne 0) { throw 'Backend dependency installation failed.' }
    & $python -m pip install --no-deps -e $backendDir
    if ($LASTEXITCODE -ne 0) { throw 'Backend package installation failed.' }
}
if (-not (Test-Path $vite)) {
    if (-not (Get-Command npm -ErrorAction SilentlyContinue)) { throw 'Node.js and npm are required.' }
    Write-Host 'Installing frontend dependencies...'
    Push-Location $frontendDir
    try {
        & npm ci
        if ($LASTEXITCODE -ne 0) { throw 'Frontend dependency installation failed.' }
    } finally {
        Pop-Location
    }
}
$node = Get-Command node -ErrorAction Stop
New-Item -ItemType Directory -Path $logDir -Force | Out-Null

try {
    $env:PYTHONPATH = "$root;$backendDir"
    $backend = Start-Process -FilePath $python -ArgumentList @(
        '-m', 'uvicorn', 'app.main:app', '--host', '127.0.0.1', '--port', "$BackendPort"
    ) -WorkingDirectory $backendDir -WindowStyle Hidden -PassThru `
        -RedirectStandardOutput (Join-Path $logDir 'backend.out.log') `
        -RedirectStandardError (Join-Path $logDir 'backend.err.log')
    if (-not (Wait-ForEndpoint "$backendUrl/health" $backend)) {
        throw "Backend did not become healthy. Check $logDir\backend.err.log"
    }

    $env:VITE_API_PROXY_TARGET = $backendUrl
    $frontend = Start-Process -FilePath $node.Source -ArgumentList @(
        "`"$vite`"", '--host', '127.0.0.1', '--port', "$FrontendPort", '--strictPort'
    ) -WorkingDirectory $frontendDir -WindowStyle Hidden -PassThru `
        -RedirectStandardOutput (Join-Path $logDir 'frontend.out.log') `
        -RedirectStandardError (Join-Path $logDir 'frontend.err.log')
    if (-not (Wait-ForEndpoint "$frontendUrl/api/v1/demo/state" $frontend)) {
        throw "Dashboard API proxy did not become healthy. Check $logDir\frontend.err.log"
    }

    Write-Host "SkyWarden is ready: $frontendUrl"
    Write-Host "Backend health: $backendUrl/health"
    Write-Host 'Press Ctrl+C to stop both servers.'
    if ($OpenBrowser) { Start-Process $frontendUrl }
    while ($true) {
        $backend.Refresh()
        $frontend.Refresh()
        if ($backend.HasExited -or $frontend.HasExited) {
            throw "A server stopped unexpectedly. Check logs in $logDir"
        }
        Start-Sleep -Seconds 1
    }
} finally {
    if ($frontend) { Stop-ProcessTree $frontend.Id }
    if ($backend) { Stop-ProcessTree $backend.Id }
}
