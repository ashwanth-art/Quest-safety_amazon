param(
  [switch]$Install
)

$ErrorActionPreference = "Stop"

$RootDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$AppDir = Join-Path $RootDir "questsafety-spapi-backend"
$Port = 8000
$AppUrl = "http://127.0.0.1:$Port"

function Resolve-ToolPath {
  param([string[]]$Names)

  foreach ($Name in $Names) {
    $Command = Get-Command $Name -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($Command) {
      if ($Command.Source) {
        return $Command.Source
      }

      return $Command.Path
    }
  }

  return $null
}

function Resolve-PythonPath {
  if ($env:PYTHON -and (Test-Path $env:PYTHON)) {
    return $env:PYTHON
  }

  $PythonFromPath = Resolve-ToolPath @("python.exe", "python")
  if ($PythonFromPath) {
    return $PythonFromPath
  }

  $LocalPython = Join-Path $env:LOCALAPPDATA "Programs\Python\Python312\python.exe"
  if (Test-Path $LocalPython) {
    return $LocalPython
  }

  throw "Python was not found. Install Python 3.12 or set the PYTHON environment variable to python.exe."
}

function Test-HttpOk {
  param([string]$Url)

  try {
    $Response = Invoke-WebRequest -UseBasicParsing -Uri $Url -TimeoutSec 2
    return ($Response.StatusCode -ge 200 -and $Response.StatusCode -lt 500)
  } catch {
    return $false
  }
}

function Test-CombinedAppRunning {
  if (-not (Test-HttpOk "$AppUrl/health")) {
    return $false
  }

  try {
    $Response = Invoke-WebRequest -UseBasicParsing -Uri $AppUrl -TimeoutSec 2
    return $Response.Content.Contains("QuestSafety Amazon Research System")
  } catch {
    return $false
  }
}

$PythonPath = Resolve-PythonPath

if ($Install) {
  Write-Host "Installing app dependencies..."
  & $PythonPath -m pip install -r (Join-Path $AppDir "requirements.txt")
  if ($LASTEXITCODE -ne 0) {
    throw "Python dependency installation failed."
  }
}

& $PythonPath -c "import fastapi, uvicorn" 2>$null
if ($LASTEXITCODE -ne 0) {
  throw "Dependencies are missing. Run: .\run-local.cmd -Install"
}

if (Test-CombinedAppRunning) {
  Write-Host "QuestSafety app is already running at $AppUrl"
  Write-Host "UI:      $AppUrl"
  Write-Host "Catalog: $AppUrl/catalog.html"
  Write-Host "Docs:    $AppUrl/docs"
  return
} elseif (Test-HttpOk "$AppUrl/health") {
  throw "Port $Port is running an older API-only server. Stop that server, then run .\run-local.cmd again."
}

Write-Host "Starting QuestSafety combined app at $AppUrl"
Write-Host "UI:      $AppUrl"
Write-Host "Catalog: $AppUrl/catalog.html"
Write-Host "Docs:    $AppUrl/docs"
Write-Host ""
Write-Host "Press Ctrl+C to stop."

Set-Location $AppDir
$env:PORT = [string]$Port
& $PythonPath main.py
