# Build a standalone ReadingPacer.exe (no Python required to run it).
# Usage: run from the repo root:  powershell -File packaging\build-exe.ps1
# Output: dist\ReadingPacer.exe

$ErrorActionPreference = "Stop"

pip install pyinstaller .

pyinstaller --noconfirm --clean --onefile --windowed `
    --name ReadingPacer `
    --icon "reading_pacer\assets\icon.ico" `
    --add-data "reading_pacer\assets;reading_pacer\assets" `
    packaging\launcher.py

Write-Output "Built dist\ReadingPacer.exe"
