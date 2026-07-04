"""路径、默认配置、界面常量与黑体字体。

DATA_DIR 等路径在自测时会被整体替换到临时目录,
其他模块必须通过 `from clipman import constants as C` 以属性方式访问,
不要 `from clipman.constants import DATA_DIR` 拷贝一份。
"""

import getpass
import os
import shlex
import shutil
import sys

from PyQt6.QtCore import QSize, Qt
from PyQt6.QtGui import QFont

IS_WIN = sys.platform == "win32"
IS_MAC = sys.platform == "darwin"
IS_LINUX = not IS_WIN and not IS_MAC

# 项目根目录(run.sh / toggle.sh 所在处,即本包的上一级)
SCRIPT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

if IS_WIN:
    DATA_DIR = os.path.join(
        os.environ.get("APPDATA", os.path.expanduser("~")),
        "clipboard-manager")
elif IS_MAC:
    DATA_DIR = os.path.expanduser(
        "~/Library/Application Support/clipboard-manager")
else:
    DATA_DIR = os.path.expanduser("~/.local/share/clipboard-manager")
IMG_DIR = os.path.join(DATA_DIR, "images")
HISTORY_FILE = os.path.join(DATA_DIR, "history.json")
FAVORITES_FILE = os.path.join(DATA_DIR, "favorites.json")
CONFIG_FILE = os.path.join(DATA_DIR, "config.json")
# Linux 的自启 .desktop / macOS 的 LaunchAgent plist;Windows 走注册表
if IS_MAC:
    AUTOSTART_FILE = os.path.expanduser(
        "~/Library/LaunchAgents/com.clipboard-manager.plist")
else:
    AUTOSTART_FILE = os.path.expanduser(
        "~/.config/autostart/clipboard-manager.desktop")
DEFAULT_CONFIG = {
    "hotkey": "Ctrl+Alt+V",   # 全局快捷键:呼出/隐藏窗口
    "max_items": 200,         # 历史条数上限
    "font_size": 11,          # 列表字体大小
    "auto_paste": True,       # 双击时自动粘贴到上一个窗口
    "language": "auto",       # 界面语言:auto(跟随系统)/ zh / en
}
PREVIEW_CHARS = 300      # 文本条目预览的最大字符数
PREVIEW_LINES = 6        # 文本条目预览的最大行数
THUMB_SIZE = QSize(160, 120)
ROLE_CLIP = Qt.ItemDataRole.UserRole
DEFAULT_COLOR = "#000000"
# Windows 没有 os.getuid,用用户名区分
SINGLE_INSTANCE_KEY = "clipboard-manager-" + (
    str(os.getuid()) if hasattr(os, "getuid") else getpass.getuser())

# 粘贴组合键的叫法(提示文案用)
PASTE_KEY_LABEL = "Cmd+V" if IS_MAC else "Ctrl+V"

# 黑体优先;Windows 自带 SimHei/微软雅黑,macOS 用苹方,
# Ubuntu 一般装有 Noto Sans CJK SC
HEI_FAMILIES = ["SimHei", "黑体", "Microsoft YaHei",
                "PingFang SC", "Hiragino Sans GB", "Noto Sans CJK SC",
                "WenQuanYi Micro Hei", "Droid Sans Fallback", "sans-serif"]


def _quote(path: str) -> str:
    if IS_WIN:
        return f'"{path}"' if " " in path else path
    return shlex.quote(path)


def launch_command() -> str:
    """启动本程序的命令(写进开机自启 / toggle.sh 的兜底启动用),
    已做 shell 转义。开发目录里用 run.sh;deb 安装后用 PATH 里的
    clipboard-manager;Windows 用 pythonw 避免弹出控制台窗口。"""
    if getattr(sys, "frozen", False):
        # PyInstaller 打包的 exe / .app:程序本身就是可执行文件
        return _quote(sys.executable)
    entry = os.path.join(SCRIPT_DIR, "clipboard_manager.py")
    if IS_WIN:
        pyw = os.path.join(os.path.dirname(sys.executable), "pythonw.exe")
        py = pyw if os.path.exists(pyw) else sys.executable
        return f"{_quote(py)} {_quote(entry)}"
    run_sh = os.path.join(SCRIPT_DIR, "run.sh")
    if os.access(run_sh, os.X_OK):
        return _quote(run_sh)
    exe = shutil.which("clipboard-manager")
    if exe:
        return _quote(exe)
    return f"{_quote(sys.executable)} {_quote(entry)}"


def toggle_script_path() -> str:
    """toggle.sh 的生成位置:开发目录可写就放在项目根,
    系统安装(/usr/lib 只读)则放到用户数据目录。"""
    if os.access(SCRIPT_DIR, os.W_OK):
        return os.path.join(SCRIPT_DIR, "toggle.sh")
    return os.path.join(DATA_DIR, "toggle.sh")


def hei_font(point_size: int = 11) -> QFont:
    font = QFont()
    font.setFamilies(HEI_FAMILIES)
    font.setPointSize(point_size)
    return font
