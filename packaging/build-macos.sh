#!/usr/bin/env bash
# Build "Reading Pacer.app" and a drag-to-Applications .dmg (macOS only).
# Usage (from the repo root):  bash packaging/build-macos.sh
#
# Needs a python.org Python 3.10+ (universal2, ships with Tk 8.6) — that's what
# CI uses. The result is a universal app: one download for Apple Silicon and Intel.
#
# Output:
#   dist/Reading Pacer.app
#   dist/ReadingPacer-<ver>-macOS.dmg
#
# The app is ad-hoc signed, not notarized (that needs a paid Apple Developer
# account), so the first launch needs one extra step — see README "Install".

set -euo pipefail
cd "$(dirname "$0")/.."

VERSION=$(python3 -c "import reading_pacer; print(reading_pacer.__version__)")
APP="dist/Reading Pacer.app"
DMG="dist/ReadingPacer-${VERSION}-macOS.dmg"
echo "Building Reading Pacer ${VERSION} for macOS"

python3 -m pip install --quiet --upgrade pyinstaller pillow certifi .

python3 -m PyInstaller --noconfirm --clean --onedir --windowed \
    --name "Reading Pacer" \
    --icon reading_pacer/assets/icon.png \
    --add-data "reading_pacer/assets:reading_pacer/assets" \
    --osx-bundle-identifier io.github.bloodtailor.readingpacer \
    --target-arch universal2 \
    --hidden-import certifi \
    --distpath dist --workpath build \
    packaging/launcher.py

# Proper version numbers, sharp text on Retina screens, dark-mode aware title bar.
PLIST="$APP/Contents/Info.plist"
plutil -replace CFBundleShortVersionString -string "$VERSION" "$PLIST"
plutil -replace CFBundleVersion -string "$VERSION" "$PLIST"
plutil -replace NSHighResolutionCapable -bool true "$PLIST"
plutil -replace LSMinimumSystemVersion -string "11.0" "$PLIST"
plutil -replace NSHumanReadableCopyright -string "MIT License - github.com/Bloodtailor/reading-pacer" "$PLIST"

# Editing Info.plist invalidates the signature; re-sign ad-hoc (required on Apple Silicon).
codesign --force --deep --sign - "$APP"
codesign --verify --deep --strict "$APP"

# Disk image with an Applications shortcut to drag the app onto.
STAGE=$(mktemp -d)
cp -R "$APP" "$STAGE/"
ln -s /Applications "$STAGE/Applications"
rm -f "$DMG"
hdiutil create -volname "Reading Pacer" -srcfolder "$STAGE" -ov -format UDZO "$DMG"
rm -rf "$STAGE"

echo "Built: $DMG ($(du -h "$DMG" | cut -f1))"
