# Build the Windows app and its installer.
# Usage (from the repo root):  powershell -ExecutionPolicy Bypass -File packaging\build-windows.ps1
#
# Needs: Python 3.10+ and Inno Setup 6 (winget install JRSoftware.InnoSetup).
# Tip: build from a venv at a SHORT path (e.g. C:\rp-venv) - PyInstaller can
# hit Windows' 260-character path limit from deep folders.
#
# Output:
#   dist\ReadingPacer\                     the app folder (portable, runs as-is)
#   dist\ReadingPacer-<ver>-portable.zip   that folder zipped
#   dist\ReadingPacer-Setup-<ver>.exe      the installer

$ErrorActionPreference = "Stop"
Set-Location (Split-Path $PSScriptRoot -Parent)

$version = (python -c "import reading_pacer; print(reading_pacer.__version__)").Trim()
Write-Output "Building Reading Pacer $version"

python -m pip install --quiet --upgrade pyinstaller .
if ($LASTEXITCODE) { throw "pip install failed" }

# One-folder build: starts faster than --onefile, and antivirus products flag it far less.
python -m PyInstaller --noconfirm --clean --onedir --windowed `
    --name ReadingPacer `
    --icon "reading_pacer\assets\icon.ico" `
    --add-data "reading_pacer\assets;reading_pacer\assets" `
    --distpath dist --workpath build `
    packaging\launcher.py
if ($LASTEXITCODE) { throw "PyInstaller failed" }

$zip = "dist\ReadingPacer-$version-portable.zip"
if (Test-Path $zip) { Remove-Item $zip }
Compress-Archive -Path "dist\ReadingPacer" -DestinationPath $zip

$iscc = @(
    "$env:ProgramFiles\Inno Setup 6\ISCC.exe",
    "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe",
    "$env:LOCALAPPDATA\Programs\Inno Setup 6\ISCC.exe"
) | Where-Object { Test-Path $_ } | Select-Object -First 1
if (-not $iscc) { throw "Inno Setup 6 not found - install it with: winget install JRSoftware.InnoSetup" }

& $iscc /Qp "/DAppVersion=$version" packaging\installer.iss
if ($LASTEXITCODE) { throw "Inno Setup failed" }

Write-Output ""
Write-Output "Built:"
Get-ChildItem dist -File | ForEach-Object { "  dist\$($_.Name)  ($([math]::Round($_.Length / 1MB, 1)) MB)" }
