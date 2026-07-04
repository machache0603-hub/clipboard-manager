"""快捷键格式转换(Qt / X11 / GNOME / pynput)与全局快捷键监听。

Linux(X11)用 XGrabKey;Windows / macOS 用 pynput 的 GlobalHotKeys。
"""

import re
import threading

try:
    from Xlib import X, XK
    from Xlib import display as xlib_display          # 全局快捷键(X11)
    HAVE_XLIB = True
except ImportError:
    HAVE_XLIB = False


def qt_to_x11(seq: str):
    """把 Qt 快捷键串(如 Ctrl+Alt+V / Win+V)解析为 (X11修饰键掩码, keysym)。
    无法解析时返回 None。"""
    if not seq or not HAVE_XLIB:
        return None
    mod_map = {"ctrl": X.ControlMask, "alt": X.Mod1Mask,
               "shift": X.ShiftMask, "meta": X.Mod4Mask,
               "win": X.Mod4Mask, "super": X.Mod4Mask, "cmd": X.Mod4Mask}
    parts = [p.strip() for p in seq.split("+") if p.strip()]
    if not parts:
        return None
    # "Ctrl+`" 这类以 + 结尾前的符号键:split 后最后一段就是符号本身
    *mods, key = parts
    mask = 0
    for m in mods:
        bit = mod_map.get(m.lower())
        if bit is None:
            return None
        mask |= bit
    named = {"space": "space", "esc": "Escape", "return": "Return",
             "tab": "Tab", "pgup": "Prior", "pgdown": "Next",
             "home": "Home", "end": "End", "ins": "Insert",
             "del": "Delete", "backspace": "BackSpace"}
    puncts = {"`": "grave", "-": "minus", "=": "equal",
              "[": "bracketleft", "]": "bracketright", ";": "semicolon",
              "'": "apostrophe", ",": "comma", ".": "period",
              "/": "slash", "\\": "backslash"}
    if len(key) == 1:
        name = puncts.get(key, key.lower())
    elif len(key) in (2, 3) and key[0].upper() == "F" and key[1:].isdigit():
        name = key.upper()                      # F1 ~ F35
    else:
        name = named.get(key.lower(), key)
    keysym = XK.string_to_keysym(name)
    if keysym == 0:
        return None
    return mask, keysym


def accel_parts(accel: str):
    """把 '<Super>v'(GNOME 格式)或 'Win+V'(Qt 格式)统一成
    (修饰键集合, 键名小写),用于跨格式比较。无法解析返回 None。"""
    alias = {"primary": "ctrl", "control": "ctrl", "ctrl": "ctrl",
             "super": "meta", "meta": "meta", "win": "meta", "cmd": "meta",
             "alt": "alt", "shift": "shift"}
    s = accel.strip()
    if not s:
        return None
    mods = set()
    if "<" in s:
        for t in re.findall(r"<([^>]+)>", s):
            mods.add(alias.get(t.lower(), t.lower()))
        key = re.sub(r"<[^>]+>", "", s).strip().lower()
    else:
        parts = [p.strip() for p in s.split("+") if p.strip()]
        if not parts:
            return None
        key = parts[-1].lower()
        for t in parts[:-1]:
            mods.add(alias.get(t.lower(), t.lower()))
    return (frozenset(mods), key) if key else None


def qt_to_gnome(seq: str):
    """把 Qt 快捷键串转成 GNOME 绑定格式,如 Win+V → '<Super>v'。"""
    if not seq:
        return None
    mod_tokens = {"ctrl": "<Control>", "alt": "<Alt>", "shift": "<Shift>",
                  "meta": "<Super>", "win": "<Super>",
                  "super": "<Super>", "cmd": "<Super>"}
    parts = [p.strip() for p in seq.split("+") if p.strip()]
    if not parts:
        return None
    *mods, key = parts
    out = ""
    for m in mods:
        token = mod_tokens.get(m.lower())
        if token is None:
            return None
        out += token
    named = {"space": "space", "esc": "Escape", "return": "Return",
             "tab": "Tab", "pgup": "Prior", "pgdown": "Next",
             "home": "Home", "end": "End", "ins": "Insert",
             "del": "Delete", "backspace": "BackSpace"}
    puncts = {"`": "grave", "-": "minus", "=": "equal",
              "[": "bracketleft", "]": "bracketright", ";": "semicolon",
              "'": "apostrophe", ",": "comma", ".": "period",
              "/": "slash", "\\": "backslash"}
    if len(key) == 1:
        name = puncts.get(key, key.lower())
    elif len(key) in (2, 3) and key[0].upper() == "F" and key[1:].isdigit():
        name = key.upper()
    else:
        name = named.get(key.lower(), key)
    return out + name


def qt_to_pynput(seq: str):
    """把 Qt 快捷键串转成 pynput GlobalHotKeys 格式,
    如 Ctrl+Alt+V → '<ctrl>+<alt>+v',Win+V → '<cmd>+v'。
    无法解析返回 None。"""
    if not seq:
        return None
    mod_map = {"ctrl": "<ctrl>", "alt": "<alt>", "shift": "<shift>",
               "meta": "<cmd>", "win": "<cmd>", "super": "<cmd>",
               "cmd": "<cmd>"}
    named = {"space": "<space>", "esc": "<esc>", "return": "<enter>",
             "tab": "<tab>", "pgup": "<page_up>", "pgdown": "<page_down>",
             "home": "<home>", "end": "<end>", "ins": "<insert>",
             "del": "<delete>", "backspace": "<backspace>"}
    parts = [p.strip() for p in seq.split("+") if p.strip()]
    if not parts:
        return None
    *mods, key = parts
    out = []
    for m in mods:
        token = mod_map.get(m.lower())
        if token is None:
            return None
        out.append(token)
    if len(key) == 1:
        out.append(key.lower())
    elif len(key) in (2, 3) and key[0].upper() == "F" and key[1:].isdigit():
        out.append(f"<{key.lower()}>")
    elif key.lower() in named:
        out.append(named[key.lower()])
    else:
        return None
    return "+".join(out)


class PynputHotkey:
    """Windows / macOS 的全局快捷键(pynput.GlobalHotKeys)。
    与 HotkeyGrabber 提供相同的 stop() 接口。
    macOS 首次使用需在 系统设置→隐私与安全性→辅助功能 里授权。"""

    def __init__(self, combo: str, callback):
        from pynput import keyboard
        self._listener = keyboard.GlobalHotKeys({combo: callback})
        self._listener.daemon = True
        self._listener.start()

    def stop(self):
        try:
            self._listener.stop()
        except Exception:
            pass


class HotkeyGrabber(threading.Thread):
    """用 XGrabKey 注册系统级快捷键。

    与"监听所有按键"的方案不同,X 服务器只把注册的组合键发给本线程,
    其他任何按键都不经过这里,因此不存在被异常按键搞死的问题。
    """

    # NumLock / CapsLock 的所有组合都要各 grab 一次
    LOCK_MASKS = (0, X.LockMask, X.Mod2Mask, X.LockMask | X.Mod2Mask) \
        if HAVE_XLIB else (0,)

    def __init__(self, mask, keysym, callback):
        super().__init__(daemon=True)
        self.mask = mask
        self.keysym = keysym
        self.callback = callback
        self.ready = threading.Event()   # 抓取动作已完成(无论成败)
        self.grab_failed = False         # BadAccess:被其他程序抢先抓取
        self._stop_flag = threading.Event()

    def run(self):
        try:
            disp = xlib_display.Display()
        except Exception:
            self.grab_failed = True
            self.ready.set()
            return
        try:
            errors = []
            disp.set_error_handler(lambda err, *args: errors.append(err))
            root = disp.screen().root
            keycode = disp.keysym_to_keycode(self.keysym)
            if keycode == 0:
                self.grab_failed = True
                self.ready.set()
                return
            for extra in self.LOCK_MASKS:
                root.grab_key(keycode, self.mask | extra, True,
                              X.GrabModeAsync, X.GrabModeAsync)
            disp.sync()
            if errors:
                self.grab_failed = True
                self.ready.set()
                return
            self.ready.set()
            while not self._stop_flag.is_set():
                try:
                    if disp.pending_events():
                        ev = disp.next_event()
                        if ev.type == X.KeyPress and ev.detail == keycode:
                            self.callback()
                    else:
                        self._stop_flag.wait(0.05)
                except Exception:
                    self._stop_flag.wait(0.2)   # 出错继续跑,不退出
            for extra in self.LOCK_MASKS:
                try:
                    root.ungrab_key(keycode, self.mask | extra)
                except Exception:
                    pass
            disp.sync()
        except Exception:
            pass
        finally:
            try:
                disp.close()
            except Exception:
                pass

    def stop(self):
        self._stop_flag.set()
        self.join(timeout=1)
