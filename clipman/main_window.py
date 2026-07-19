"""主窗口:剪贴板监听、条目管理、快捷键注册与持久化。"""

import ast
import hashlib
import json
import os
import shutil
import subprocess
import uuid

from PyQt6.QtCore import (QBuffer, QIODevice, QMimeData, QPoint, Qt, QTimer,
                          pyqtSignal)
from PyQt6.QtGui import (QBrush, QColor, QCursor, QIcon, QImage,
                         QKeySequence, QPainter, QPixmap, QShortcut)
from PyQt6.QtWidgets import (QApplication, QColorDialog, QDialog,
                             QDialogButtonBox, QHBoxLayout, QLabel,
                             QInputDialog, QLineEdit, QMenu, QMessageBox,
                             QPlainTextEdit,
                             QPushButton, QStackedWidget, QSystemTrayIcon,
                             QVBoxLayout, QWidget)

from . import autostart
from . import constants as C
from . import i18n
from .constants import DEFAULT_COLOR, DEFAULT_CONFIG, ROLE_CLIP, hei_font
from .i18n import tr
from .caret import typing_anchor
from .cards import CardList
from .clip_item import ClipItem, is_audio_file, is_image_file
from .gnome import (GNOME_ENTRY_NAME, GNOME_ENTRY_PATH, GNOME_MEDIA,
                    find_gnome_conflicts, gget, gset, release_gnome_binding)
from .hotkey import (HotkeyGrabber, PynputHotkey, accel_parts,
                     qt_to_gnome, qt_to_pynput, qt_to_x11)
from .preview_popup import PreviewPopup
from .settings_dialog import SettingsDialog


class ClipboardManager(QWidget):
    hotkey_pressed = pyqtSignal()   # 从 pynput 线程安全地切回 Qt 主线程
    CATEGORIES = ("text", "image", "audio")

    def __init__(self):
        super().__init__()
        self._setting_clipboard = False
        self._prev_window = ""
        self._hotkey_listener = None
        self.config = dict(DEFAULT_CONFIG)
        self.load_config()
        i18n.init(self.config.get("language", "auto"))
        self._save_timer = QTimer(self)
        self._save_timer.setSingleShot(True)
        self._save_timer.setInterval(600)
        self._save_timer.timeout.connect(self.save_history)
        self._focus_timer = QTimer(self)
        self._focus_timer.setInterval(1000)
        self._focus_timer.timeout.connect(self._track_active_window)
        self._focus_timer.start()

        os.makedirs(C.IMG_DIR, exist_ok=True)
        self._build_ui()
        self._build_tray()
        self.preview = PreviewPopup(self)
        self.load_history()
        self.hotkey_pressed.connect(self.toggle_visible)
        self.register_hotkey()

        cb = QApplication.clipboard()
        cb.dataChanged.connect(self.on_clipboard_changed)
        # 启动时把当前剪贴板里的内容也收进来
        self.on_clipboard_changed()

    # ---------------- 界面 ----------------
    def _build_ui(self):
        self.resize(430, 640)
        self.setFont(hei_font(int(self.config["font_size"])))

        self.search = QLineEdit()
        self.search.setClearButtonEnabled(True)
        self.search.textChanged.connect(self.apply_filter)

        self.pin_btn = QPushButton()
        self.pin_btn.setCheckable(True)
        self.pin_btn.toggled.connect(self.toggle_stay_on_top)
        self.clear_btn = QPushButton()
        self.clear_btn.clicked.connect(self.clear_all)
        self.settings_btn = QPushButton()
        self.settings_btn.clicked.connect(self.open_settings)

        top = QHBoxLayout()
        top.addWidget(self.search, 1)
        top.addWidget(self.clear_btn)
        top.addWidget(self.settings_btn)
        top.addWidget(self.pin_btn)     # 窗口置顶是模式开关,放最右端

        # 第一层页签:剪贴板历史 / 常用内容
        self.hist_tab = QPushButton()
        self.fav_tab = QPushButton()
        for btn in (self.hist_tab, self.fav_tab):
            btn.setCheckable(True)
        self.hist_tab.setChecked(True)
        self.hist_tab.clicked.connect(lambda: self.switch_page(0))
        self.fav_tab.clicked.connect(lambda: self.switch_page(1))
        self.add_btn = QPushButton()    # 手动添加常用内容,仅常用页显示
        self.add_btn.clicked.connect(self.add_favorite_manual)
        self.add_btn.hide()
        tabs = QHBoxLayout()
        tabs.addWidget(self.hist_tab)
        tabs.addWidget(self.fav_tab)
        tabs.addStretch(1)
        tabs.addWidget(self.add_btn)

        # 第二层页签:文本 / 图片 / 音频。每一类使用真正独立的列表页。
        self.text_tab = QPushButton()
        self.image_tab = QPushButton()
        self.audio_tab = QPushButton()
        self.category_buttons = {
            "text": self.text_tab,
            "image": self.image_tab,
            "audio": self.audio_tab,
        }
        category_tabs = QHBoxLayout()
        category_tabs.setSpacing(6)
        for category, btn in self.category_buttons.items():
            btn.setCheckable(True)
            btn.clicked.connect(
                lambda _checked=False, value=category:
                self.switch_category(value))
            category_tabs.addWidget(btn, 1)
        self.text_tab.setChecked(True)

        self.history_lists = {
            category: CardList(self, grid_mode=(category == "image"))
            for category in self.CATEGORIES
        }
        self.favorite_lists = {
            category: CardList(self, grid_mode=(category == "image"))
            for category in self.CATEGORIES
        }
        # 旧属性继续指向文本列表，避免外部扩展升级后立即报错。
        self.listw = self.history_lists["text"]
        self.favw = self.favorite_lists["text"]
        for lw in self.all_lists():
            # 单击即完成回写剪贴板和自动粘贴。卡片仍会抑制
            # 双击的第二次 release，因此快速双击也只粘贴一次。
            lw.itemClicked.connect(self.copy_and_paste_item)
            lw.customContextMenuRequested.connect(self.show_menu)

        self.stack = QStackedWidget()
        for lists in (self.history_lists, self.favorite_lists):
            for category in self.CATEGORIES:
                self.stack.addWidget(lists[category])
        self._page_index = 0
        self._category = "text"
        self._sync_page()

        self.hint_label = QLabel()
        self.hint_label.setWordWrap(True)
        self.hint_label.setStyleSheet("color:#888; font-size:9pt;")

        lay = QVBoxLayout(self)
        lay.setContentsMargins(10, 10, 10, 8)
        lay.addLayout(top)
        lay.addLayout(tabs)
        lay.addLayout(category_tabs)
        lay.addWidget(self.stack, 1)
        lay.addWidget(self.hint_label)
        self._apply_texts()      # 统一填入当前语言的文案

        QShortcut(QKeySequence(Qt.Key.Key_Delete), self,
                  activated=self.delete_current)
        QShortcut(QKeySequence("Ctrl+F"), self,
                  activated=lambda: (self.search.setFocus(),
                                     self.search.selectAll()))

        # 白色背景;注意不要在 QSS 里给 item 设 color,否则会盖掉单条颜色
        self.setStyleSheet("""
            QWidget { background: #ffffff; }
            QLineEdit, QPushButton {
                border: 1px solid #d9d9d9; border-radius: 6px;
                padding: 6px 10px; background: #ffffff;
            }
            QPushButton:hover { background: #f2f7ff; }
            QPushButton:checked { background: #e3efff;
                                  border-color: #7fb0ff; }
            /* 下拉框与其弹出列表:同 QMenu,继承全局白底后,
               悬浮/选中项默认白字白底不可见,必须显式配色 */
            QComboBox {
                border: 1px solid #d9d9d9; border-radius: 6px;
                padding: 5px 10px; background: #ffffff; color: #202020;
            }
            QComboBox:hover { background: #f2f7ff; }
            QComboBox QAbstractItemView {
                background: #ffffff; color: #202020;
                border: 1px solid #d9d9d9; border-radius: 6px;
                padding: 4px; outline: none;
                selection-background-color: #dbeaff;
                selection-color: #000000;
            }
            QComboBox QAbstractItemView::item {
                padding: 6px 12px; border-radius: 4px;
            }
            QComboBox QAbstractItemView::item:hover,
            QComboBox QAbstractItemView::item:selected {
                background: #dbeaff; color: #000000;
            }
            /* 浅灰衬底 + 白色圆角卡片,让不同条目一眼可分 */
            CardList {
                border: 1px solid #e3e3e3; border-radius: 8px;
                background: #eef0f3;
            }
            #CardContainer { background: #eef0f3; }
            #Card {
                background: #ffffff;
                border: 1px solid #dcdfe5;
                border-radius: 6px;
            }
            #Card:hover { background: #f6faff; border-color: #a9ccff; }
            #Card[selected="true"] {
                background: #e3efff; border-color: #6ea6ff;
            }
            #Card[dragging="true"] {
                background: #f6faff; border-color: #4d8dff;
            }
            #PreviewButton {
                background: rgba(255, 255, 255, 225);
                border: 1px solid #cfd7e3; border-radius: 6px;
                padding: 0px; color: #344054; font-size: 11pt;
            }
            #PreviewButton:hover {
                background: #e3efff; border-color: #7fb0ff;
            }
            #PreviewButton:pressed { background: #d4e7ff; }
            /* 菜单会继承全局白色背景,悬浮项默认是白色高亮文字,
               白字白底不可见,必须显式给出高亮配色 */
            QMenu {
                background: #ffffff; border: 1px solid #d9d9d9;
                border-radius: 6px; padding: 4px;
            }
            QMenu::item {
                background: transparent; color: #202020;
                padding: 6px 28px 6px 12px; border-radius: 4px;
            }
            QMenu::item:selected { background: #dbeaff; color: #000000; }
            QMenu::item:disabled { color: #aaaaaa; }
            QMenu::separator {
                height: 1px; background: #e8e8e8; margin: 4px 8px;
            }
        """)

    # ---------------- 页面切换(历史 / 常用 + 内容分类) ----------------
    def all_lists(self):
        """返回全部独立列表，顺序固定，便于统一刷新与保存。"""
        return [lists[category]
                for lists in (self.history_lists, self.favorite_lists)
                for category in self.CATEGORIES]

    def current_list(self):
        """当前“历史/常用 + 分类”组合对应的列表。"""
        lists = (self.favorite_lists if self._page_index == 1
                 else self.history_lists)
        return lists[self._category]

    def list_of(self, item):
        """条目所属的列表;已被删除的条目 row 为 -1。"""
        for lw in self.all_lists():
            if lw.row(item) >= 0:
                return lw
        return self.current_list()

    def _is_history_list(self, lw) -> bool:
        return lw in self.history_lists.values()

    def _list_for_clip(self, clip: ClipItem, favorite=False):
        lists = self.favorite_lists if favorite else self.history_lists
        return lists[clip.category()]

    def _sync_page(self):
        self.stack.setCurrentWidget(self.current_list())
        self.hist_tab.setChecked(self._page_index == 0)
        self.fav_tab.setChecked(self._page_index == 1)
        for category, btn in self.category_buttons.items():
            btn.setChecked(category == self._category)
        # 手动添加只会创建文本，仅在“常用-文本”页面显示入口。
        self.add_btn.setVisible(
            self._page_index == 1 and self._category == "text")

    def switch_page(self, index: int):
        self._page_index = 1 if index == 1 else 0
        self._sync_page()

    def switch_category(self, category):
        """切换文本/图片/音频页面；也接受 0/1/2 页签序号。"""
        if isinstance(category, int):
            if not 0 <= category < len(self.CATEGORIES):
                return
            category = self.CATEGORIES[category]
        if category not in self.CATEGORIES:
            return
        self._category = category
        self._sync_page()

    def _tray_pixmap(self) -> QPixmap:
        pix = QPixmap(64, 64)
        pix.fill(Qt.GlobalColor.transparent)
        p = QPainter(pix)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setBrush(QColor("#4d8dff"))
        p.setPen(Qt.PenStyle.NoPen)
        p.drawRoundedRect(8, 4, 48, 56, 10, 10)
        p.setBrush(QColor("#ffffff"))
        p.drawRoundedRect(16, 14, 32, 38, 6, 6)
        p.setBrush(QColor("#4d8dff"))
        p.drawRoundedRect(24, 0, 16, 12, 4, 4)
        p.end()
        return pix

    def _build_tray(self):
        self.tray = None
        if not QSystemTrayIcon.isSystemTrayAvailable():
            return
        icon = QIcon(self._tray_pixmap())
        self.setWindowIcon(icon)
        self.tray = QSystemTrayIcon(icon, self)
        # setContextMenu 不接管所有权,必须自己保存引用防止被回收
        menu = self._tray_menu = QMenu()
        self._tray_toggle_act = menu.addAction(
            tr("显示/隐藏窗口"), self.toggle_visible)
        menu.addSeparator()
        self._tray_quit_act = menu.addAction(tr("退出"), self.quit_app)
        self.tray.setContextMenu(menu)
        self.tray.setToolTip(tr("剪贴板历史"))
        self.tray.activated.connect(
            lambda reason: self.toggle_visible()
            if reason == QSystemTrayIcon.ActivationReason.Trigger else None)
        self.tray.show()

    def _apply_texts(self):
        """把静态控件文案设置为当前语言(建界面与切换语言共用)。"""
        self.setWindowTitle(tr("剪贴板历史"))
        self.search.setPlaceholderText(tr("搜索历史…"))
        self.pin_btn.setText(tr("📌 最前"))
        self.pin_btn.setToolTip(tr("窗口保持在最前面,方便拖拽"))
        self.clear_btn.setText(tr("🗑 清空"))
        self.settings_btn.setText(tr("⚙ 设置"))
        self.hist_tab.setText(tr("📋 历史"))
        self.fav_tab.setText(tr("⭐ 常用"))
        self.text_tab.setText(tr("📝 文本"))
        self.image_tab.setText(tr("🖼 图片"))
        self.audio_tab.setText(tr("🎵 音频"))
        self.add_btn.setText(tr("➕ 添加"))
        self.add_btn.setToolTip(tr("手动添加一条常用内容"))
        self.hint_label.setText(
            tr("单击=复制并粘贴 · 眼睛=查看/编辑详情 · "
               "拖到目标窗口=粘贴 · 列表内拖动=排序 · "
               "右键=图片改名/字体颜色/删除"))

    def retranslate_ui(self):
        """切换语言后刷新所有已建好的界面文案。"""
        self._apply_texts()
        if self.tray is not None:
            self.tray.setToolTip(tr("剪贴板历史"))
            self._tray_toggle_act.setText(tr("显示/隐藏窗口"))
            self._tray_quit_act.setText(tr("退出"))
        self.preview.retranslate()
        for lw in self.all_lists():
            for row in range(lw.count()):
                lw.item(row).retranslate()

    def _place_window(self):
        """呼出时定位窗口:正在输入 → 在输入光标四周避让;
        否则停靠到当前屏幕右上角。"""
        anchor = typing_anchor()
        anchor_pos = QPoint(*anchor) if anchor is not None else QCursor.pos()
        # 多屏时以真实输入光标所在的屏幕为准，不依赖
        # 鼠标当前停留的屏幕。
        screen = (QApplication.screenAt(anchor_pos)
                  or QApplication.primaryScreen())
        geo = screen.availableGeometry()
        # 未显示过时 width() 还是初始值,show 后布局会撑到最小尺寸,
        # 按最终生效的尺寸定位,避免第一次呼出偏移
        hint = self.minimumSizeHint()
        w = max(self.width(), hint.width())
        h = max(self.height(), hint.height())
        if anchor is None:                   # 不在输入:右上角
            x, y = geo.right() - w - 12, geo.top() + 12
        else:
            ax, ay = anchor
            gap = 24
            spaces = {
                "above": ay - geo.top() - gap,
                "below": geo.bottom() - ay - gap,
                "left": ax - geo.left() - gap,
                "right": geo.right() - ax - gap,
            }

            # 优先放到输入行的上/下方，避免挡住同一行已输入的
            # 文本。垂直空间不足时才选左/右侧。
            vertical = [side for side in ("below", "above")
                        if spaces[side] >= h]
            horizontal = [side for side in ("right", "left")
                          if spaces[side] >= w]
            choices = vertical or horizontal
            side = (max(choices, key=lambda name: spaces[name])
                    if choices else max(spaces, key=spaces.get))

            if side == "above":
                x, y = ax - w // 2, ay - h - gap
            elif side == "below":
                x, y = ax - w // 2, ay + gap
            elif side == "left":
                x, y = ax - w - gap, ay - h // 2
            else:
                x, y = ax + gap, ay - h // 2
        x = max(geo.left(), min(x, geo.right() - w))
        y = max(geo.top(), min(y, geo.bottom() - h))
        self.move(x, y)

    def toggle_visible(self):
        # 已在最前台才隐藏;被遮挡或隐藏时都拉到前台
        if self.isVisible() and self.isActiveWindow():
            self.preview.hide_popup()
            self.hide()
        else:
            # 隐藏后呼出，或窗口在后台时再次按快捷键，都按
            # 当前输入位置重新避让。
            self._place_window()
            self.show()
            self.raise_()
            self.activateWindow()
            # GNOME 会阻止后台程序抢焦点(只闪"已就绪"提示),
            # 用 xdotool 以合规方式激活窗口
            if shutil.which("xdotool"):
                wid = str(int(self.winId()))
                QTimer.singleShot(120, lambda: subprocess.Popen(
                    ["xdotool", "windowactivate", wid],
                    stderr=subprocess.DEVNULL))

    # ---------------- 设置 ----------------
    def load_config(self):
        try:
            with open(C.CONFIG_FILE, encoding="utf-8") as f:
                data = json.load(f)
            self.config.update({k: data[k] for k in DEFAULT_CONFIG
                                if k in data})
        except (OSError, json.JSONDecodeError):
            pass

    def save_config(self):
        os.makedirs(C.DATA_DIR, exist_ok=True)
        tmp = C.CONFIG_FILE + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(self.config, f, ensure_ascii=False, indent=1)
        os.replace(tmp, C.CONFIG_FILE)

    def open_settings(self):
        dlg = SettingsDialog(self, self.config, autostart.is_enabled())
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        values, autostart_on = dlg.values()
        lang_changed = values.get("language") != self.config.get("language")
        self.config.update(values)
        self.save_config()
        if lang_changed:
            i18n.init(self.config["language"])
            self.retranslate_ui()
        self.apply_autostart(autostart_on)
        self.apply_font_size()
        self.trim_history()
        self.schedule_save()
        status = self.register_hotkey()
        self._handle_hotkey_status(status)

    def _handle_hotkey_status(self, status: str):
        seq = self.config["hotkey"]
        if not seq:
            return
        if status == "invalid":
            dep = (tr("python-xlib(且需 X11 会话)") if C.IS_LINUX
                   else "pynput(pip install pynput)")
            QMessageBox.warning(
                self, tr("快捷键未生效"),
                tr("无法解析快捷键 {},或缺少依赖 {}。"
                   "请换一个组合键。").format(seq, dep))
            return
        # 注册"成功"也可能被 GNOME 在更底层拦截(如 Win+V 是通知中心),
        # 主动查一遍系统快捷键,冲突则提示一键解除
        conflicts = find_gnome_conflicts(seq)
        if not conflicts and status == "occupied":
            QMessageBox.warning(
                self, tr("快捷键被占用"),
                tr("{} 已被其他程序注册,请换一个组合键。").format(seq))
            return
        if not conflicts:
            return
        names = "\n".join(f"    {key}({schema})"
                          for schema, key, _ in conflicts)
        ret = QMessageBox.question(
            self, tr("快捷键被系统占用"),
            tr("{} 目前被 GNOME 系统快捷键占用:\n{}\n\n"
               "是否解除系统占用,把这个组合键让给剪贴板?\n"
               "(该绑定的其他组合键会保留,可在系统设置里随时改回)"
               ).format(seq, names))
        if ret != QMessageBox.StandardButton.Yes:
            return
        for schema, key, kept in conflicts:
            release_gnome_binding(schema, key, kept)
        self.register_hotkey()   # 解除后重新注册一次

    def apply_font_size(self):
        size = int(self.config["font_size"])
        self.setFont(hei_font(size))
        for lw in self.all_lists():
            for row in range(lw.count()):
                lw.item(row).setFont(hei_font(size))

    def apply_autostart(self, enable: bool):
        try:
            autostart.set_enabled(enable)
        except OSError:
            pass

    def register_hotkey(self) -> str:
        """按当前配置注册全局快捷键。
        返回 'ok' / 'invalid'(无法解析)/ 'occupied'(被抢先抓取)。

        Win(Super)组合键被 GNOME 的 overlay-key 机制在底层接管,
        XGrabKey 收不到,所以 Win 组合键注册为 GNOME 自定义快捷键,
        由 GNOME 触发 toggle.sh 通过单实例通道通知本程序;
        其余组合键仍用 XGrabKey(即时响应,不依赖桌面环境)。"""
        if self._hotkey_listener is not None:
            self._hotkey_listener.stop()
            self._hotkey_listener = None
        seq = self.config["hotkey"]
        if not C.IS_LINUX:               # Windows / macOS 走 pynput
            if not seq:
                return "ok"
            return self._register_pynput(seq)
        is_gnome = shutil.which("gsettings") is not None
        if not seq:                      # 留空 = 不用快捷键
            if is_gnome:
                self._set_gnome_binding(None)
            return "ok"
        parts = accel_parts(seq)
        if parts is None:
            return "invalid"
        if "meta" in parts[0]:
            if not is_gnome:
                return self._register_xgrab(seq)   # 非 GNOME 直接抓
            return self._set_gnome_binding(seq)
        if is_gnome:
            self._set_gnome_binding(None)          # 清掉旧的 GNOME 绑定
        return self._register_xgrab(seq)

    def _register_xgrab(self, seq: str) -> str:
        parsed = qt_to_x11(seq)
        if parsed is None:
            return "invalid"
        try:
            grabber = HotkeyGrabber(parsed[0], parsed[1],
                                    self.hotkey_pressed.emit)
            grabber.start()
            grabber.ready.wait(1.0)
            if grabber.grab_failed:
                grabber.stop()
                return "occupied"
            self._hotkey_listener = grabber
            return "ok"
        except Exception:
            return "invalid"

    def _register_pynput(self, seq: str) -> str:
        combo = qt_to_pynput(seq)
        if combo is None:
            return "invalid"
        try:
            self._hotkey_listener = PynputHotkey(
                combo, self.hotkey_pressed.emit)
            return "ok"
        except ImportError:
            return "invalid"             # 未安装 pynput
        except Exception:
            return "occupied"

    def _set_gnome_binding(self, seq) -> str:
        """把快捷键写入/移除 GNOME 自定义快捷键(名称:剪贴板历史)。"""
        raw = gget(GNOME_MEDIA, "custom-keybindings")
        if raw.startswith("@as"):
            raw = raw[3:].strip()
        try:
            paths = ast.literal_eval(raw) if raw else []
        except (ValueError, SyntaxError):
            paths = []
        if not isinstance(paths, list):
            paths = []
        schema_path = f"{GNOME_MEDIA}.custom-keybinding:{GNOME_ENTRY_PATH}"
        if seq is None:                  # 移除绑定
            if GNOME_ENTRY_PATH in paths:
                gset("set", schema_path, "binding", "")
            return "ok"
        accel = qt_to_gnome(seq)
        if accel is None:
            return "invalid"
        if GNOME_ENTRY_PATH not in paths:
            value = "[" + ", ".join(
                "'" + p + "'" for p in paths + [GNOME_ENTRY_PATH]) + "]"
            if not gset("set", GNOME_MEDIA, "custom-keybindings", value):
                return "invalid"
        toggle = C.toggle_script_path()
        ok = (gset("set", schema_path, "name", GNOME_ENTRY_NAME)
              and gset("set", schema_path, "command", toggle)
              and gset("set", schema_path, "binding", accel))
        return "ok" if ok else "invalid"

    def move_item_to_top(self, item):
        """把条目移到所属列表顶部,并滚回顶部让用户看到效果。"""
        lw = self.list_of(item)
        lw.move_row(lw.row(item), 0)
        lw.verticalScrollBar().setValue(0)

    def toggle_stay_on_top(self, checked):
        self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, checked)
        self.show()

    def closeEvent(self, event):
        # 有托盘时关闭窗口只是隐藏,程序继续在后台记录剪贴板
        if self.tray is not None:
            event.ignore()
            self.preview.hide_popup()
            self.hide()
            self.tray.showMessage(
                tr("仍在后台记录"), tr("点击托盘图标或再次启动程序可恢复窗口"),
                QSystemTrayIcon.MessageIcon.Information, 2000)
        else:
            # 没有托盘就真正退出,避免留下无法唤回的后台进程
            self.save_history()
            event.accept()
            QApplication.instance().quit()

    def quit_app(self):
        self.save_history()
        QApplication.instance().quit()

    # ---------------- 剪贴板监听 ----------------
    def on_clipboard_changed(self):
        if self._setting_clipboard:
            return
        mime = QApplication.clipboard().mimeData()
        if mime is None:
            return
        self.add_from_mime(mime, source="复制")

    def add_from_mime(self, mime: QMimeData, source=""):
        clip = self._clip_from_mime(mime)
        if clip is None:
            return None
        # 与已有条目重复:挪到顶部即可
        found = self._find_by_sig(self.history_lists.values(), clip.sig)
        if found is not None:
            lw, row = found
            if row != 0:
                lw.move_row(row, 0)
            self._drop_orphan_image(clip)
            return clip
        self.insert_clip(clip, row=0)
        self.trim_history()
        self.schedule_save()
        return clip

    def _clip_from_mime(self, mime: QMimeData):
        if mime.hasImage():
            data = mime.imageData()
            if isinstance(data, QPixmap):
                data = data.toImage()
            image = data if isinstance(data, QImage) else QImage()
            if not image.isNull():
                buf = QBuffer()
                buf.open(QIODevice.OpenModeFlag.WriteOnly)
                image.save(buf, "PNG")
                data = bytes(buf.data())
                buf.close()
                sig = "img:" + hashlib.sha1(data).hexdigest()
                path = os.path.join(C.IMG_DIR, uuid.uuid4().hex + ".png")
                with open(path, "wb") as f:
                    f.write(data)
                return ClipItem("image", html=mime.html(),
                                image_path=path, sig=sig)
        if mime.hasUrls():
            files = [u.toLocalFile() for u in mime.urls() if u.isLocalFile()]
            if files:
                if all(is_audio_file(path) for path in files):
                    kind = "audio"
                elif all(is_image_file(path) for path in files):
                    kind = "image_files"
                else:
                    kind = "files"
                sig = kind + ":" + hashlib.sha1(
                    "\n".join(files).encode()).hexdigest()
                return ClipItem(kind, files=files, sig=sig)
        if mime.hasText():
            text = mime.text()
            if text and text.strip():
                sig = "text:" + hashlib.sha1(text.encode()).hexdigest()
                return ClipItem("text", text=text,
                                html=mime.html(), sig=sig)
        return None

    def _drop_orphan_image(self, clip: ClipItem):
        """重复图片刚存的文件没人引用,删掉避免堆积。"""
        if clip.kind != "image" or not clip.image_path:
            return
        used = any(
            lw.item(r).data(ROLE_CLIP).image_path == clip.image_path
            for lw in self.all_lists() for r in range(lw.count()))
        if not used and os.path.exists(clip.image_path):
            os.remove(clip.image_path)

    # ---------------- 常用内容 ----------------
    @staticmethod
    def _find_by_sig(lists, sig: str):
        for lw in lists:
            for row in range(lw.count()):
                if lw.item(row).data(ROLE_CLIP).sig == sig:
                    return lw, row
        return None

    def _insert_favorite(self, clip: ClipItem):
        self._list_for_clip(clip, favorite=True).insert_card(clip, 0)
        self.apply_filter(self.search.text())
        self.schedule_save()
        if self.tray is not None:
            self.tray.showMessage(
                tr("已添加到常用"), clip.preview()[:60],
                QSystemTrayIcon.MessageIcon.Information, 1200)

    def add_item_to_favorites(self, item):
        """把历史条目收藏到常用页(内容独立复制,互不影响)。"""
        src: ClipItem = item.data(ROLE_CLIP)
        if self._find_by_sig(self.favorite_lists.values(), src.sig) is not None:
            if self.tray is not None:
                self.tray.showMessage(
                    tr("该内容已在常用列表中"), src.preview()[:60],
                    QSystemTrayIcon.MessageIcon.Information, 1200)
            return
        clip = ClipItem.from_dict(src.to_dict())
        if clip.kind == "image" and os.path.exists(clip.image_path):
            # 图片文件独立复制一份:删除历史条目不影响常用条目
            new_path = os.path.join(C.IMG_DIR, uuid.uuid4().hex + ".png")
            shutil.copyfile(clip.image_path, new_path)
            clip.image_path = new_path
        self._insert_favorite(clip)

    def add_favorite_text(self, text: str):
        """新建一条文本常用内容(手动添加入口的核心逻辑)。"""
        if not text or not text.strip():
            return
        sig = "text:" + hashlib.sha1(text.encode()).hexdigest()
        found = self._find_by_sig(self.favorite_lists.values(), sig)
        if found is not None:
            lw, row = found
            lw.move_row(row, 0)
            return
        self._insert_favorite(ClipItem("text", text=text, sig=sig))

    def add_favorite_manual(self):
        dlg = QDialog(self)
        dlg.setWindowTitle(tr("添加常用内容"))
        dlg.setMinimumSize(380, 260)
        editor = QPlainTextEdit()
        editor.setPlaceholderText(tr("输入要保存的常用内容…"))
        editor.setFont(hei_font(int(self.config["font_size"])))
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(dlg.accept)
        buttons.rejected.connect(dlg.reject)
        lay = QVBoxLayout(dlg)
        lay.addWidget(editor)
        lay.addWidget(buttons)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self.add_favorite_text(editor.toPlainText())

    def add_dropped(self, lw, mime: QMimeData):
        """外部拖入内容按真实类型落到当前历史/常用的分类页。"""
        if self._is_history_list(lw):
            clip = self.add_from_mime(mime, source="拖入")
            if clip is not None:
                self.switch_category(clip.category())
            return
        clip = self._clip_from_mime(mime)
        if clip is None:
            return
        if self._find_by_sig(self.favorite_lists.values(), clip.sig) is not None:
            self._drop_orphan_image(clip)
            return
        self._insert_favorite(clip)
        self.switch_category(clip.category())

    # ---------------- 条目管理 ----------------
    def insert_clip(self, clip: ClipItem, row=0):
        self._list_for_clip(clip).insert_card(clip, row)
        self.apply_filter(self.search.text())

    def trim_history(self):
        # 分类页完全独立，上限也分别作用于每个历史分类。
        limit = int(self.config["max_items"])
        for lw in self.history_lists.values():
            while lw.count() > limit:
                item = lw.takeItem(lw.count() - 1)
                clip = item.data(ROLE_CLIP)
                if (clip.kind == "image"
                        and os.path.exists(clip.image_path)):
                    os.remove(clip.image_path)

    def apply_filter(self, query: str):
        query = query.strip().lower()
        for lw in self.all_lists():
            for row in range(lw.count()):
                item = lw.item(row)
                clip = item.data(ROLE_CLIP)
                item.setHidden(bool(query)
                               and query not in clip.search_key().lower())

    # ---------------- 详情预览 ----------------
    def show_item_preview(self, item):
        """由卡片右下角眼睛按钮打开详情，不再由悬浮自动触发。"""
        try:
            if (item is None or item.isHidden()
                    or self.list_of(item).row(item) < 0):
                return
        except RuntimeError:
            return
        gl = self.list_of(item).item_global_rect(item)
        self.list_of(item).setCurrentItem(item)
        self.preview.show_for(item, gl)

    def update_item_text(self, item, text: str):
        """详情窗口里编辑后保存:更新内容、签名和列表显示。"""
        clip: ClipItem = item.data(ROLE_CLIP)
        if clip.kind != "text":
            return
        clip.text = text
        clip.html = ""                      # 编辑后原富文本不再一致,丢弃
        clip.sig = "text:" + hashlib.sha1(text.encode()).hexdigest()
        item.setText(clip.preview())
        self.schedule_save()

    def update_image_name(self, item, name: str):
        """修改图片在粘贴板中的备注名，不重命名原始文件。"""
        clip: ClipItem = item.data(ROLE_CLIP)
        if clip.category() != "image":
            return
        clip.name = name.strip()
        item.refresh_label()
        self.apply_filter(self.search.text())
        self.schedule_save()

    def edit_image_name(self, item):
        clip: ClipItem = item.data(ROLE_CLIP)
        current = clip.name or item.text()
        name, accepted = QInputDialog.getText(
            self, tr("修改图片名称"),
            tr("输入图片备注名（留空恢复默认名称）:"),
            QLineEdit.EchoMode.Normal, current)
        if accepted:
            self.update_image_name(item, name)

    # ---------------- 复制 / 粘贴 ----------------
    def set_clipboard_mime(self, mime: QMimeData):
        self._setting_clipboard = True
        QApplication.clipboard().setMimeData(mime)
        # X11 上 dataChanged 是异步派发的,稍后再解除屏蔽
        QTimer.singleShot(300, self._unblock_clipboard)

    def copy_item(self, item):
        """把历史条目重新放回系统剪贴板,之后 Ctrl+V 即可粘贴。"""
        clip: ClipItem = item.data(ROLE_CLIP)
        self.set_clipboard_mime(clip.to_mime())
        # 不自动置顶:保留用户手动拖拽排好的顺序
        if self.tray is not None:
            self.tray.showMessage(tr("已复制"), clip.preview()[:60],
                                  QSystemTrayIcon.MessageIcon.Information,
                                  1200)

    def _unblock_clipboard(self):
        self._setting_clipboard = False

    def copy_and_paste_item(self, item):
        self.copy_item(item)
        if not self.config["auto_paste"]:
            return
        if not C.IS_LINUX:
            # Windows / macOS:隐藏本窗口让焦点回到目标应用,
            # 再用 pynput 模拟粘贴键
            self.preview.hide_popup()
            self.hide()
            QTimer.singleShot(300, self._send_paste_key)
            return
        if shutil.which("xdotool") is None:
            QMessageBox.information(
                self, tr("提示"),
                tr("已复制到剪贴板。安装 xdotool 后,单击可自动粘贴:\n"
                   "sudo apt install xdotool"))
            return
        # 不隐藏本窗口:把焦点切回上一个活动窗口后再模拟 Ctrl+V
        if self._prev_window:
            QTimer.singleShot(150, self._send_paste_key)
        elif self.tray is not None:
            self.tray.showMessage(
                tr("已复制"),
                tr("请到目标窗口按 {} 粘贴").format(C.PASTE_KEY_LABEL),
                QSystemTrayIcon.MessageIcon.Information, 1500)

    def _send_paste_key(self):
        if C.IS_LINUX:
            try:
                subprocess.Popen(
                    ["xdotool", "windowactivate", "--sync",
                     self._prev_window,
                     "key", "--clearmodifiers", "ctrl+v"])
            except OSError:
                pass
            return
        try:
            from pynput.keyboard import Controller, Key
        except ImportError:
            if self.tray is not None:
                self.tray.showMessage(
                    tr("已复制"),
                    tr("未安装 pynput,无法自动粘贴,请按 {} 粘贴"
                       ).format(C.PASTE_KEY_LABEL),
                    QSystemTrayIcon.MessageIcon.Information, 1500)
            return
        kb = Controller()
        mod = Key.cmd if C.IS_MAC else Key.ctrl
        with kb.pressed(mod):
            kb.press("v")
            kb.release("v")

    def _track_active_window(self):
        """记录最近一个非本程序的活动窗口,单击粘贴时把焦点还给它
        (仅 Linux/X11;Windows/macOS 靠隐藏窗口归还焦点)。"""
        if (not C.IS_LINUX or not self.isVisible()
                or shutil.which("xdotool") is None):
            return
        try:
            out = subprocess.run(["xdotool", "getactivewindow"],
                                 capture_output=True, text=True, timeout=1)
            wid = out.stdout.strip()
            if wid.isdigit() and int(wid) != int(self.winId()):
                self._prev_window = wid
        except (OSError, subprocess.TimeoutExpired, ValueError):
            pass

    # ---------------- 右键菜单 ----------------
    def show_menu(self, pos):
        lw = self.current_list()
        item = lw.itemAt(pos)
        menu = QMenu(self)
        if item is not None:
            clip: ClipItem = item.data(ROLE_CLIP)
            menu.addAction(tr("📋 复制"), lambda: self.copy_item(item))
            menu.addAction(tr("📤 复制并粘贴"),
                           lambda: self.copy_and_paste_item(item))
            menu.addSeparator()
            if self._is_history_list(lw):
                menu.addAction(tr("⭐ 添加到常用"),
                               lambda: self.add_item_to_favorites(item))
            if clip.category() == "image":
                menu.addAction(tr("✏ 修改图片名称"),
                               lambda: self.edit_image_name(item))
            menu.addAction(tr("🎨 修改字体颜色"),
                           lambda: self.pick_color(item))
            menu.addAction(tr("↩ 恢复默认颜色"),
                           lambda: self.set_item_color(item,
                                                       QColor(DEFAULT_COLOR)))
            menu.addSeparator()
            menu.addAction(tr("⬆ 移到顶部"),
                           lambda: self.move_item_to_top(item))
            menu.addAction(tr("❌ 删除"), lambda: self.delete_item(item))
        menu.addSeparator()
        menu.addAction(tr("🗑 清空当前页"), self.clear_all)
        menu.exec(lw.mapToGlobal(pos))

    def pick_color(self, item):
        clip: ClipItem = item.data(ROLE_CLIP)
        color = QColorDialog.getColor(QColor(clip.color), self,
                                      tr("选择该条目的字体颜色"))
        if color.isValid():
            self.set_item_color(item, color)

    def set_item_color(self, item, color: QColor):
        clip: ClipItem = item.data(ROLE_CLIP)
        clip.color = color.name()
        item.setForeground(QBrush(color))
        self.schedule_save()

    def delete_current(self):
        item = self.current_list().currentItem()
        if item is not None:
            self.delete_item(item)

    def delete_item(self, item):
        self.preview.hide_popup()
        lw = self.list_of(item)
        lw.takeItem(lw.row(item))
        clip = item.data(ROLE_CLIP)
        if clip.kind == "image" and os.path.exists(clip.image_path):
            os.remove(clip.image_path)
        self.schedule_save()

    def clear_all(self):
        lw = self.current_list()
        if lw.count() == 0:
            return
        category = tr({
            "text": "文本", "image": "图片", "audio": "音频"
        }[self._category])
        if not self._is_history_list(lw):
            title = tr("清空常用")
            msg = tr("确定清空常用中的“{}”页吗?").format(category)
        else:
            title = tr("清空历史")
            msg = tr("确定清空历史中的“{}”页吗?").format(category)
        ret = QMessageBox.question(self, title, msg)
        if ret != QMessageBox.StandardButton.Yes:
            return
        while lw.count():
            self.delete_item(lw.item(0))

    # ---------------- 持久化 ----------------
    def schedule_save(self):
        self._save_timer.start()

    def save_history(self):
        self._save_lists(self.history_lists, C.HISTORY_FILE)
        self._save_lists(self.favorite_lists, C.FAVORITES_FILE)

    def _save_lists(self, lists, path: str):
        items = [lists[category].item(row).data(ROLE_CLIP).to_dict()
                 for category in self.CATEGORIES
                 for row in range(lists[category].count())]
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump({"items": items}, f, ensure_ascii=False, indent=1)
        os.replace(tmp, path)

    def load_history(self):
        self._load_lists(self.history_lists, C.HISTORY_FILE)
        self._load_lists(self.favorite_lists, C.FAVORITES_FILE)
        self.apply_filter(self.search.text())

    def _load_lists(self, lists, path: str):
        if not os.path.exists(path):
            return
        try:
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
        except (json.JSONDecodeError, OSError):
            return
        for d in data.get("items", []):
            clip = ClipItem.from_dict(d)
            if clip.kind == "image" and not os.path.exists(clip.image_path):
                continue
            lw = lists[clip.category()]
            lw.insert_card(clip, lw.count())
