# Starts the whole project with one command: the API, the React app, and the
# Streamlit app, each in its own window so you can see what each one is doing
# and stop it on its own with Ctrl+C.
#
# Usage:  right-click this file > Run with PowerShell
#     or: double-click start-app.bat, which just calls this script
#
# What it assumes is already done once, per SETUP-WIPRO.md:
#   - backend\venv exists (py -3.12 -m venv venv, then pip install -r requirements.txt)
#   - backend\.env and frontend\.env exist and are filled in
#   - backend\loan_app.db has been seeded (python seed.py)
#   - the manual has been ingested (python -m rag.ingest)

$ErrorActionPreference = "Stop"
$root = $PSScriptRoot

# This machine's system Node is too old for this project's front-end tools
# (Vite 8 needs Node 20+; this laptop's default is 18). Node 22 was installed
# separately to Program Files, so every window below puts it first on PATH.
$nodePath = "C:\Program Files\nodejs"

function Test-Setup {
    $problems = @()
    if (-not (Test-Path "$root\backend\venv\Scripts\python.exe")) {
        $problems += "backend\venv is missing. Run: cd backend; py -3.12 -m venv venv; .\venv\Scripts\python.exe -m pip install -r requirements.txt"
    }
    if (-not (Test-Path "$root\backend\.env")) {
        $problems += "backend\.env is missing. Copy backend\.env.wipro to backend\.env and fill in the two FILL ME IN lines."
    }
    if (-not (Test-Path "$root\backend\loan_app.db")) {
        $problems += "backend\loan_app.db is missing. Run: cd backend; .\venv\Scripts\python.exe seed.py"
    }
    if (-not (Test-Path "$root\frontend\node_modules")) {
        $problems += "frontend\node_modules is missing. Run: cd frontend; npm install"
    }
    if (-not (Test-Path $nodePath)) {
        $problems += "Node 22 was not found at $nodePath. Edit the `$nodePath line in this script if it was installed somewhere else."
    }
    return $problems
}

$problems = Test-Setup
if ($problems.Count -gt 0) {
    Write-Host "Cannot start yet - some setup is missing:" -ForegroundColor Red
    $problems | ForEach-Object { Write-Host "  - $_" -ForegroundColor Yellow }
    exit 1
}

Write-Host "Starting the backend API on http://localhost:8000 ..." -ForegroundColor Cyan
Start-Process powershell -ArgumentList @(
    "-NoExit", "-Command",
    "cd '$root\backend'; .\venv\Scripts\python.exe -m uvicorn app.main:app --reload --port 8000"
) -WindowStyle Normal

Write-Host "Starting the React app on http://localhost:5173 ..." -ForegroundColor Cyan
Start-Process powershell -ArgumentList @(
    "-NoExit", "-Command",
    "`$env:PATH = '$nodePath;' + `$env:PATH; cd '$root\frontend'; npm run dev"
) -WindowStyle Normal

Write-Host "Starting the Streamlit app on http://localhost:8501 ..." -ForegroundColor Cyan
Start-Process powershell -ArgumentList @(
    "-NoExit", "-Command",
    "cd '$root\backend'; .\venv\Scripts\streamlit.exe run ../frontend-streamlit/app.py --server.port 8501"
) -WindowStyle Normal

Write-Host ""
Write-Host "All three are starting up in their own windows. Give them a few seconds," -ForegroundColor Green
Write-Host "then open http://localhost:5173 in your browser and sign in as:" -ForegroundColor Green
Write-Host "  manager   anita@bank.com   Manager@123"
Write-Host "  officer   rajan@bank.com   Officer@123"
Write-Host "  customer  priya@example.com   Customer@123"
Write-Host ""
Write-Host "To stop everything, close the three PowerShell windows (or Ctrl+C in each)." -ForegroundColor Green

Start-Sleep -Seconds 6
Start-Process "http://localhost:5173"
