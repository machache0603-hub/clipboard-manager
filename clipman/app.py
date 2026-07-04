"""程序入口:单实例、toggle.sh 生成与主循环。"""

import os
import sys

from PyQt6.QtNetwork import QLocalServer, QLocalSocket
from PyQt6.QtWidgets import QApplication, QSystemTrayIcon

from . import constants as C
from .constants import SINGLE_INSTANCE_KEY
from .i18n import tr
from .main_window import ClipboardManager


def write_toggle_script(sock_path: str):
    """生成 toggle.sh:GNOME 快捷键通过它通知本程序切换窗口显隐;
    程序没在运行时则直接启动程序。"""
    launch = C.launch_command()
    path = C.toggle_script_path()
    content = f"""#!/usr/bin/env bash
# 本文件由 clipboard_manager.py 自动生成,请勿手动修改
python3 - <<'PYEOF' || exec {launch}
import socket
s = socket.socket(socket.AF_UNIX)
s.settimeout(1)
s.connect({sock_path!r})
s.sendall(b"toggle")
PYEOF
"""
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        os.chmod(path, 0o755)
    except OSError:
        pass


def main():
    # PyQt6 默认对未捕获异常直接 abort;常驻程序只记录不退出
    import traceback

    def excepthook(etype, value, tb):
        traceback.print_exception(etype, value, tb)
    sys.excepthook = excepthook

    if "--selftest" in sys.argv:
        from .selftest import run_selftest
        sys.exit(run_selftest())
    app = QApplication(sys.argv)
    app.setApplicationName("clipboard-manager")
    app.setQuitOnLastWindowClosed(False)

    # 单实例:已有实例在运行时,通知它显示窗口,自己退出
    probe = QLocalSocket()
    probe.connectToServer(SINGLE_INSTANCE_KEY)
    if probe.waitForConnected(300):
        probe.write(b"show")
        probe.waitForBytesWritten(300)
        probe.disconnectFromServer()
        print(tr("已有实例在运行,已唤出其窗口"))
        sys.exit(0)
    QLocalServer.removeServer(SINGLE_INSTANCE_KEY)  # 清理上次异常退出的残留
    server = QLocalServer()
    server.listen(SINGLE_INSTANCE_KEY)
    if C.IS_LINUX:      # toggle.sh 是 GNOME 快捷键机制,仅 Linux 需要
        write_toggle_script(server.fullServerName())

    win = ClipboardManager()

    def on_second_instance():
        conn = server.nextPendingConnection()
        msg = b""
        if conn is not None:
            if conn.waitForReadyRead(300):
                msg = bytes(conn.readAll())
            conn.close()
        if msg == b"toggle":             # 来自 GNOME 快捷键的 toggle.sh
            win.toggle_visible()
        else:                            # 用户再次启动程序:唤出窗口
            win.show()
            win.raise_()
            win.activateWindow()

    server.newConnection.connect(on_second_instance)
    # 默认最小化到托盘启动(开机自启/手动启动都不弹主窗口),
    # 用快捷键、托盘图标或再次启动程序唤出;--show 强制显示。
    # 没有托盘时仍直接显示,避免窗口无法唤回。
    if "--show" in sys.argv or win.tray is None:
        win.show()
    else:
        win.tray.showMessage(
            tr("剪贴板历史已在后台运行"),
            tr("按 {} 或点击托盘图标打开窗口").format(
                win.config["hotkey"] or tr("快捷键")),
            QSystemTrayIcon.MessageIcon.Information, 3000)
    sys.exit(app.exec())
