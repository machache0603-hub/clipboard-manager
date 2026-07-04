#!/usr/bin/env bash
# 在 macOS 上打包 .app 并制作 dmg:./packaging/build_mac.sh [版本号]
# 产物:dist/Clipboard History.app 与 dist/ClipboardHistory_<版本>.dmg
set -euo pipefail
cd "$(dirname "$0")/.."

VERSION=${1:-1.1.0}
APP_NAME="Clipboard History"

python3 -m pip install --upgrade PyQt6 pynput pyinstaller
python3 -m PyInstaller --noconfirm --clean --windowed \
    --name "$APP_NAME" \
    --osx-bundle-identifier com.clipboard-manager \
    clipboard_manager.py

hdiutil create -volname "$APP_NAME" \
    -srcfolder "dist/$APP_NAME.app" -ov -format UDZO \
    "dist/ClipboardHistory_${VERSION}.dmg"

echo
echo "打包完成:dist/$APP_NAME.app"
echo "安装镜像:dist/ClipboardHistory_${VERSION}.dmg(打开后把 App 拖进「应用程序」)"
