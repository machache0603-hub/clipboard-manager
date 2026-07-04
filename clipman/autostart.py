"""开机自启:Linux 用 ~/.config/autostart 的 .desktop,
Windows 用注册表 HKCU Run 键,macOS 用 ~/Library/LaunchAgents 的 plist。"""

import os
import plistlib
import shlex

from . import constants as C

_WIN_RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
_WIN_VALUE_NAME = "clipboard-manager"


def is_enabled() -> bool:
    if C.IS_WIN:
        try:
            import winreg
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, _WIN_RUN_KEY) as k:
                winreg.QueryValueEx(k, _WIN_VALUE_NAME)
            return True
        except OSError:
            return False
    return os.path.exists(C.AUTOSTART_FILE)


def set_enabled(enable: bool):
    if C.IS_WIN:
        _set_windows(enable)
    elif C.IS_MAC:
        _set_mac(enable)
    else:
        _set_linux(enable)


def _set_linux(enable: bool):
    if not enable:
        if os.path.exists(C.AUTOSTART_FILE):
            os.remove(C.AUTOSTART_FILE)
        return
    os.makedirs(os.path.dirname(C.AUTOSTART_FILE), exist_ok=True)
    with open(C.AUTOSTART_FILE, "w", encoding="utf-8") as f:
        f.write("[Desktop Entry]\nType=Application\n"
                "Name=Clipboard History\n"
                "Name[zh_CN]=剪贴板历史\n"
                f"Exec={C.launch_command()}\n"
                "Terminal=false\nCategories=Utility;\n"
                "X-GNOME-Autostart-enabled=true\n")


def _set_windows(enable: bool):
    import winreg
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, _WIN_RUN_KEY) as k:
        if enable:
            winreg.SetValueEx(k, _WIN_VALUE_NAME, 0, winreg.REG_SZ,
                              C.launch_command())
        else:
            try:
                winreg.DeleteValue(k, _WIN_VALUE_NAME)
            except OSError:
                pass


def _set_mac(enable: bool):
    if not enable:
        if os.path.exists(C.AUTOSTART_FILE):
            os.remove(C.AUTOSTART_FILE)
        return
    os.makedirs(os.path.dirname(C.AUTOSTART_FILE), exist_ok=True)
    plist = {
        "Label": "com.clipboard-manager",
        "ProgramArguments": shlex.split(C.launch_command()),
        "RunAtLoad": True,
    }
    with open(C.AUTOSTART_FILE, "wb") as f:
        plistlib.dump(plist, f)
