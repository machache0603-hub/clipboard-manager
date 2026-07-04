"""定位"正在输入"的位置,决定呼出窗口时停靠在哪。

typing_anchor() 返回 (x, y) 屏幕坐标 —— 应把窗口开在这个位置旁边;
返回 None 表示当前不在输入(窗口应停靠屏幕右上角)。

- Windows:GetGUIThreadInfo 能拿到前台线程真实的文本光标(caret)
  矩形,有 caret 即正在输入,位置精确到光标。
- Linux/X11:X 协议没有跨应用的 caret 查询;用 XGetInputFocus 判断
  是否有普通应用持有输入焦点(桌面/gnome-shell 不算),再用鼠标
  位置作近似锚点(输入时鼠标通常就停在输入框附近)。
- macOS:无轻量级 caret API(需要辅助功能框架),同样用鼠标位置
  作近似锚点。
"""

from . import constants as C


def typing_anchor():
    try:
        if C.IS_WIN:
            return _win_caret()
        if C.IS_LINUX:
            return _x11_anchor()
        return _mouse_pos()          # macOS
    except Exception:
        return None


def _mouse_pos():
    from PyQt6.QtGui import QCursor
    p = QCursor.pos()
    return (p.x(), p.y())


def _win_caret():
    import ctypes
    from ctypes import wintypes

    class GUITHREADINFO(ctypes.Structure):
        _fields_ = [("cbSize", wintypes.DWORD),
                    ("flags", wintypes.DWORD),
                    ("hwndActive", wintypes.HWND),
                    ("hwndFocus", wintypes.HWND),
                    ("hwndCapture", wintypes.HWND),
                    ("hwndMenuOwner", wintypes.HWND),
                    ("hwndMoveSize", wintypes.HWND),
                    ("hwndCaret", wintypes.HWND),
                    ("rcCaret", wintypes.RECT)]

    user32 = ctypes.windll.user32
    hwnd = user32.GetForegroundWindow()
    if not hwnd:
        return None
    tid = user32.GetWindowThreadProcessId(hwnd, None)
    info = GUITHREADINFO(cbSize=ctypes.sizeof(GUITHREADINFO))
    if not user32.GetGUIThreadInfo(tid, ctypes.byref(info)):
        return None
    if not info.hwndCaret:               # 没有文本光标 = 不在输入
        return None
    pt = wintypes.POINT(info.rcCaret.left, info.rcCaret.bottom)
    user32.ClientToScreen(info.hwndCaret, ctypes.byref(pt))
    return (pt.x, pt.y)


# 这些 WM_CLASS 属于桌面环境本身,焦点落在它们上不算"正在输入"
_DESKTOP_CLASSES = {"gnome-shell", "plasmashell", "mutter",
                    "xfdesktop", "nautilus-desktop", "desktop_window"}


def _x11_anchor():
    from Xlib import X
    from Xlib import display as xlib_display

    disp = xlib_display.Display()
    try:
        focus = disp.get_input_focus().focus
        if focus in (X.NONE, X.PointerRoot) or isinstance(focus, int):
            return None
        root_id = disp.screen().root.id
        if focus.id == root_id:
            return None
        # 焦点常落在子控件上,向上找带 WM_CLASS 的窗口判断属主
        w, cls = focus, None
        for _ in range(12):
            try:
                cls = w.get_wm_class()
            except Exception:
                cls = None
            if cls:
                break
            tree = w.query_tree()
            if tree.parent is None or tree.parent.id == root_id:
                break
            w = tree.parent
        if cls and cls[0].lower() in _DESKTOP_CLASSES:
            return None                  # 焦点在桌面上,不算输入
        return _mouse_pos()
    finally:
        disp.close()
