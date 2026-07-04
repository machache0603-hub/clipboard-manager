#!/usr/bin/env bash
# 打包 deb:./packaging/build_deb.sh [版本号]
# 产物输出到 dist/clipboard-manager_<版本>_all.deb
set -euo pipefail
cd "$(dirname "$(readlink -f "$0")")/.."

PKG=clipboard-manager
VERSION=${1:-1.0.0}
ARCH=all
BUILD="dist/${PKG}_${VERSION}_${ARCH}"

rm -rf "$BUILD"
mkdir -p "$BUILD/DEBIAN" \
         "$BUILD/usr/bin" \
         "$BUILD/usr/lib/$PKG" \
         "$BUILD/usr/share/applications" \
         "$BUILD/usr/share/doc/$PKG"

# ---- 程序文件 ----
cp clipboard_manager.py "$BUILD/usr/lib/$PKG/"
cp -r clipman "$BUILD/usr/lib/$PKG/"
find "$BUILD/usr/lib/$PKG" -type d -name __pycache__ -exec rm -rf {} +
cp README.md "$BUILD/usr/share/doc/$PKG/"

# ---- 启动器 ----
cat > "$BUILD/usr/bin/$PKG" <<'EOF'
#!/bin/sh
exec python3 /usr/lib/clipboard-manager/clipboard_manager.py "$@"
EOF
chmod 755 "$BUILD/usr/bin/$PKG"

# ---- 应用菜单 ----
cat > "$BUILD/usr/share/applications/$PKG.desktop" <<'EOF'
[Desktop Entry]
Type=Application
Name=剪贴板历史
Name[en]=Clipboard History
Comment=记录复制的文本/图片/表情包,支持拖拽粘贴与排序
Comment[en]=Clipboard history with drag-and-drop paste and reordering
Exec=clipboard-manager
Icon=edit-paste
Terminal=false
Categories=Utility;
StartupNotify=false
EOF

# ---- 控制文件 ----
INSTALLED_SIZE=$(du -sk "$BUILD/usr" | cut -f1)
cat > "$BUILD/DEBIAN/control" <<EOF
Package: $PKG
Version: $VERSION
Section: utils
Priority: optional
Architecture: $ARCH
Depends: python3 (>= 3.9), python3-pyqt6, python3-xlib
Recommends: xdotool
Installed-Size: $INSTALLED_SIZE
Maintainer: machache <t01090045360@gmail.com>
Description: Clipboard history manager for Linux (PyQt6)
 剪贴板历史管理器:常驻后台记录复制过的文本、图片、表情包、文件,
 单击放回剪贴板、双击自动粘贴(需 xdotool)、支持拖拽粘贴与排序,
 历史持久化到 ~/.local/share/clipboard-manager/。
 针对 X11 会话(Ubuntu 的 Xorg);Wayland 下后台监听剪贴板受限。
EOF

dpkg-deb --build --root-owner-group "$BUILD" "dist/${PKG}_${VERSION}_${ARCH}.deb"
echo
echo "打包完成:dist/${PKG}_${VERSION}_${ARCH}.deb"
echo "安装:sudo apt install ./dist/${PKG}_${VERSION}_${ARCH}.deb"
