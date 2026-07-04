"""GNOME 系统快捷键:gsettings 读写、冲突检测与解除。"""

import ast
import shutil
import subprocess

from .hotkey import accel_parts

GNOME_SCHEMAS = ["org.gnome.shell.keybindings",
                 "org.gnome.desktop.wm.keybindings",
                 "org.gnome.mutter.keybindings",
                 "org.gnome.settings-daemon.plugins.media-keys"]
GNOME_MEDIA = "org.gnome.settings-daemon.plugins.media-keys"
GNOME_ENTRY_NAME = "剪贴板历史"
GNOME_ENTRY_PATH = ("/org/gnome/settings-daemon/plugins/media-keys/"
                    "custom-keybindings/clipboard-manager/")


def gset(*args) -> bool:
    try:
        return subprocess.run(["gsettings", *args], capture_output=True,
                              timeout=5).returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        return False


def gget(*args) -> str:
    try:
        return subprocess.run(["gsettings", "get", *args],
                              capture_output=True, text=True,
                              timeout=5).stdout.strip()
    except (OSError, subprocess.TimeoutExpired):
        return ""


def find_gnome_conflicts(seq: str):
    """找出 GNOME 系统快捷键里占用了 seq 的绑定。
    返回 [(schema, key, 去掉冲突后应保留的列表)]。"""
    if shutil.which("gsettings") is None:
        return []
    target = accel_parts(seq)
    if target is None:
        return []
    conflicts = []
    for schema in GNOME_SCHEMAS:
        try:
            text = subprocess.run(
                ["gsettings", "list-recursively", schema],
                capture_output=True, text=True, timeout=5).stdout
        except (OSError, subprocess.TimeoutExpired):
            continue
        for line in text.splitlines():
            fields = line.split(None, 2)
            if len(fields) != 3:
                continue
            schema_name, key, value = fields
            value = value.strip()
            if value.startswith("@as"):
                value = value[3:].strip()
            if not value.startswith("["):
                continue
            try:
                lst = ast.literal_eval(value)
            except (ValueError, SyntaxError):
                continue
            if not isinstance(lst, list):
                continue
            kept = [a for a in lst
                    if not (isinstance(a, str) and accel_parts(a) == target)]
            if len(kept) != len(lst):
                conflicts.append((schema_name, key, kept))
    return conflicts


def release_gnome_binding(schema: str, key: str, kept: list):
    """把冲突的组合键从 GNOME 绑定里移除(保留该绑定的其他组合键)。"""
    value = "[" + ", ".join(
        "'" + a.replace("'", "") + "'" for a in kept) + "]"
    try:
        subprocess.run(["gsettings", "set", schema, key, value], timeout=5)
    except (OSError, subprocess.TimeoutExpired):
        pass
