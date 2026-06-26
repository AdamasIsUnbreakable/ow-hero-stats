param(
    [switch]$Check
)

$ErrorActionPreference = "Stop"

function Write-Step {
    param([string]$Message)
    Write-Host ""
    Write-Host "==> $Message" -ForegroundColor Cyan
}

function Find-Python {
    param([string]$RepoRoot)

    $venvPython = Join-Path $RepoRoot ".venv\Scripts\python.exe"
    if (Test-Path -LiteralPath $venvPython) {
        return $venvPython
    }

    $pythonCommand = Get-Command python -ErrorAction SilentlyContinue
    if ($pythonCommand) {
        return $pythonCommand.Source
    }

    $pyCommand = Get-Command py -ErrorAction SilentlyContinue
    if ($pyCommand) {
        return $pyCommand.Source
    }

    throw "Could not find Python. Create the virtual environment first, then run this again."
}

function Test-PortFree {
    param([int]$Port)

    $listener = $null
    try {
        $listener = [System.Net.Sockets.TcpListener]::new([System.Net.IPAddress]::Loopback, $Port)
        $listener.Start()
        return $true
    } catch {
        return $false
    } finally {
        if ($listener) {
            $listener.Stop()
        }
    }
}

function Find-FreePort {
    foreach ($port in 8000..8010) {
        if (Test-PortFree -Port $port) {
            return $port
        }
    }

    throw "Could not find a free port between 8000 and 8010."
}

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = Resolve-Path (Join-Path $scriptDir "..")
$siteDir = Join-Path $repoRoot "site"
$manifestPath = Join-Path $siteDir "public\data\v1\manifest.json"
$python = Find-Python -RepoRoot $repoRoot

if ($Check) {
    Write-Host "Launcher check passed."
    Write-Host "Repo: $repoRoot"
    Write-Host "Python: $python"
    exit 0
}

Set-Location $repoRoot

if (-not (Test-Path -LiteralPath $siteDir)) {
    throw "Could not find the site folder."
}

if (-not (Test-Path -LiteralPath $manifestPath)) {
    Write-Step "Generating website data"
    & $python -m overwatch_stats.cli web-data
    if ($LASTEXITCODE -ne 0) {
        throw "Website data generation failed."
    }
} else {
    Write-Step "Using existing website data"
    Write-Host "To refresh it later, run:"
    Write-Host ".\.venv\Scripts\python.exe -m overwatch_stats.cli web-data --refresh"
}

$port = Find-FreePort
$url = "http://localhost:$port/"

Write-Step "Opening OW Hero Stats"
Write-Host "Serving the site at $url"
Write-Host "Keep this window open while using the website."
Write-Host "Press Ctrl+C in this window to stop the server."

Start-Process $url

Set-Location $siteDir
& $python -m http.server $port --bind localhost
