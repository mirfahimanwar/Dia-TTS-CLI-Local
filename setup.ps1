# setup.ps1 -- One-click Windows setup for DiaTTS
# Run from the DiaTTS folder:
#   .\setup.ps1
#
# What it does:
#   1. Clones nari-labs/dia into dia/
#   2. Creates a Python venv
#   3. Installs PyTorch 2.6 with CUDA 12.4
#   4. Installs dia and its dependencies
#   5. Installs sounddevice for --play support

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$ROOT = $PSScriptRoot

# ── 1. Clone dia repo ─────────────────────────────────────────────────────────
if (Test-Path "$ROOT\dia\.git") {
    Write-Host "[1/5] dia/ already cloned -- skipping" -ForegroundColor Cyan
} else {
    Write-Host "[1/5] Cloning RobertAgee/dia (optimized fork)..." -ForegroundColor Cyan
    git clone https://github.com/RobertAgee/dia "$ROOT\dia"
    if ($LASTEXITCODE -ne 0) { throw "git clone failed" }
}

# ── 2. Create venv ────────────────────────────────────────────────────────────
if (Test-Path "$ROOT\venv\Scripts\python.exe") {
    Write-Host "[2/5] venv already exists -- skipping" -ForegroundColor Cyan
} else {
    Write-Host "[2/5] Creating virtual environment..." -ForegroundColor Cyan
    python -m venv "$ROOT\venv"
    if ($LASTEXITCODE -ne 0) { throw "venv creation failed" }
}

$PIP = "$ROOT\venv\Scripts\pip.exe"
$PYTHON = "$ROOT\venv\Scripts\python.exe"

# ── 3. Install PyTorch 2.6 with CUDA 12.4 ────────────────────────────────────
# Install torch first with --index-url (not --extra-index-url) so the CUDA build
# is selected. PyPI hosts a CPU-only torch build that would otherwise win on version.
Write-Host "[3/5] Installing PyTorch 2.6 (CUDA 12.4)..." -ForegroundColor Cyan
& $PIP install torch==2.6.0 torchaudio==2.6.0 --index-url https://download.pytorch.org/whl/cu124
if ($LASTEXITCODE -ne 0) { throw "PyTorch install failed" }

# ── 4. Install dia and dependencies ──────────────────────────────────────────
Write-Host "[4/5] Installing dia and dependencies..." -ForegroundColor Cyan
& $PIP install -e "$ROOT\dia"
if ($LASTEXITCODE -ne 0) { throw "dia install failed" }

# ── 5. Install extras ─────────────────────────────────────────────────────────
Write-Host "[5/5] Installing extras (sounddevice)..." -ForegroundColor Cyan
& $PIP install sounddevice
if ($LASTEXITCODE -ne 0) { throw "extras install failed" }

# ── Done ──────────────────────────────────────────────────────────────────────
Write-Host ""
Write-Host "Setup complete!" -ForegroundColor Green
Write-Host ""

# Activate the venv in the current shell (only works when dot-sourced: . .\setup.ps1)
. "$ROOT\venv\Scripts\Activate.ps1"
Write-Host "Venv activated." -ForegroundColor Green
Write-Host ""
Write-Host "Quick start:" -ForegroundColor Yellow
Write-Host '  python dia_tts.py "[S1] Hello world, this is Dia TTS."'
Write-Host '  python dia_tts.py "[S1] Hey! [S2] Hey yourself! [S1] (laughs)" --play'
Write-Host '  python dia_tts.py --interactive'
Write-Host ""
Write-Host "Note: First run downloads the ~3 GB model from Hugging Face." -ForegroundColor DarkGray
