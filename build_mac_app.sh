#!/bin/bash
set -euo pipefail

APP_NAME="FAT32 Image Editor"
ROOT="$(cd "$(dirname "$0")" && pwd)"
PYTHON="${PYTHON:-python3}"
MTOOLS_SOURCE="${MTOOLS_SOURCE:-/opt/homebrew/bin}"
WORK_DIR="$HOME/Library/Caches/$APP_NAME/build"
ICONSET="$WORK_DIR/fat32_image_editor.iconset"
APP_PATH="$HOME/Applications/$APP_NAME.app"

if ! "$PYTHON" -m PyInstaller --version >/dev/null 2>&1; then
    echo "Install build dependencies with: $PYTHON -m pip install -r \"$ROOT/requirements-build.txt\"" >&2
    exit 1
fi

mkdir -p "$ICONSET" "$HOME/Applications"
MASTER_ICON="$ICONSET/icon_512x512@2x.png"
swift "$ROOT/generate_app_icon.swift" "$MASTER_ICON"

for entry in \
    "16 icon_16x16.png" \
    "32 icon_16x16@2x.png" \
    "32 icon_32x32.png" \
    "64 icon_32x32@2x.png" \
    "128 icon_128x128.png" \
    "256 icon_128x128@2x.png" \
    "256 icon_256x256.png" \
    "512 icon_256x256@2x.png" \
    "512 icon_512x512.png" \
    "1024 icon_512x512@2x.png"; do
    set -- $entry
    sips -z "$1" "$1" "$MASTER_ICON" --out "$ICONSET/$2" >/dev/null
done

ICON_PATH="$WORK_DIR/fat32_image_editor.icns"
iconutil -c icns "$ICONSET" -o "$ICON_PATH"

TOOLS=(mdir mcopy mdel mdeltree mmd mren)
BINARY_ARGS=()
for tool in "${TOOLS[@]}"; do
    executable="$MTOOLS_SOURCE/$tool"
    if [[ ! -x "$executable" ]]; then
        echo "Required mtools executable not found: $executable" >&2
        exit 1
    fi
    BINARY_ARGS+=(--add-binary "$executable:mtools")
done

"$PYTHON" -m PyInstaller \
    --noconfirm \
    --clean \
    --windowed \
    --name "$APP_NAME" \
    --icon "$ICON_PATH" \
    --osx-bundle-identifier "com.sbickham.fat32-image-editor" \
    --distpath "$HOME/Applications" \
    --workpath "$WORK_DIR/pyinstaller" \
    --specpath "$WORK_DIR" \
    "${BINARY_ARGS[@]}" \
    "$ROOT/fat32_image_editor.py"

APP_VERSION="${APP_VERSION:-1.0.1}"
PLIST="$APP_PATH/Contents/Info.plist"
/usr/libexec/PlistBuddy -c "Set :CFBundleShortVersionString $APP_VERSION" "$PLIST"
/usr/libexec/PlistBuddy -c "Set :CFBundleVersion $APP_VERSION" "$PLIST" 2>/dev/null \
    || /usr/libexec/PlistBuddy -c "Add :CFBundleVersion string $APP_VERSION" "$PLIST"

codesign --force --deep --sign - "$APP_PATH"
echo "Built: $APP_PATH"
