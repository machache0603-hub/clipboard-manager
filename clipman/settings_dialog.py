"""设置对话框。"""

from PyQt6.QtGui import QKeySequence
from PyQt6.QtWidgets import (QCheckBox, QComboBox, QDialog, QDialogButtonBox,
                             QFormLayout, QHBoxLayout, QKeySequenceEdit,
                             QLabel, QMenu, QPushButton, QSpinBox,
                             QVBoxLayout)

from . import constants as C
from .i18n import tr


class SettingsDialog(QDialog):
    def __init__(self, parent, config, autostart_on):
        super().__init__(parent)
        self.setWindowTitle(tr("设置"))
        self.setMinimumWidth(360)

        self.key_edit = QKeySequenceEdit(QKeySequence(config["hotkey"]))
        try:
            self.key_edit.setMaximumSequenceLength(1)
            self.key_edit.setClearButtonEnabled(True)
        except AttributeError:
            pass

        # Win/Cmd 组合键会被系统拦截、无法在输入框里按出来,从预设菜单选
        mod_name = "Cmd" if C.IS_MAC else "Win"
        presets = [(f"{mod_name}+V", "Meta+V"),
                   (f"{mod_name}+C", "Meta+C"),
                   (f"{mod_name}+X", "Meta+X"),
                   ("Ctrl+Alt+V", "Ctrl+Alt+V"),
                   ("Alt+Shift+V", "Alt+Shift+V"),
                   ("F9", "F9")]
        if C.IS_WIN:
            # Windows 上 Win+V 被系统剪贴板历史占用,不作推荐
            presets = [p for p in presets if p[1] != "Meta+V"]
        preset_btn = QPushButton(tr("常用 ▾"))
        preset_menu = QMenu(preset_btn)
        for label, seq in presets:
            preset_menu.addAction(
                label, lambda s=seq: self.key_edit.setKeySequence(
                    QKeySequence(s)))
        preset_btn.setMenu(preset_menu)
        key_row = QHBoxLayout()
        key_row.addWidget(self.key_edit, 1)
        key_row.addWidget(preset_btn)

        self.max_spin = QSpinBox()
        self.max_spin.setRange(20, 2000)
        self.max_spin.setValue(int(config["max_items"]))

        self.font_spin = QSpinBox()
        self.font_spin.setRange(8, 20)
        self.font_spin.setValue(int(config["font_size"]))

        # 语言下拉框:中英文名并排展示,任何语言下都能认出来
        self.lang_combo = QComboBox()
        self.lang_combo.addItem(tr("跟随系统"), "auto")
        self.lang_combo.addItem("中文", "zh")
        self.lang_combo.addItem("English", "en")
        idx = self.lang_combo.findData(config.get("language", "auto"))
        self.lang_combo.setCurrentIndex(max(0, idx))

        self.paste_chk = QCheckBox(tr("单击条目时自动粘贴到上一个窗口"))
        self.paste_chk.setChecked(bool(config["auto_paste"]))

        self.autostart_chk = QCheckBox(tr("登录系统后自动启动"))
        self.autostart_chk.setChecked(autostart_on)

        form = QFormLayout()
        form.addRow(tr("呼出/隐藏窗口快捷键:"), key_row)
        form.addRow(tr("每类历史条数上限:"), self.max_spin)
        form.addRow(tr("列表字体大小:"), self.font_spin)
        form.addRow(tr("语言:"), self.lang_combo)
        form.addRow(self.paste_chk)
        form.addRow(self.autostart_chk)

        if C.IS_MAC:
            hint_text = tr("提示:快捷键在输入框内直接按组合键即可,"
                           "Cmd 组合键请从「常用」菜单选择;留空表示不使用"
                           "全局快捷键。首次使用需在 系统设置→隐私与安全性→"
                           "辅助功能 里为本程序授权。")
        elif C.IS_WIN:
            hint_text = tr("提示:快捷键在输入框内直接按组合键即可,"
                           "Win 组合键请从「常用」菜单选择(多数已被系统"
                           "占用,不推荐);留空表示不使用全局快捷键。")
        else:
            hint_text = tr("提示:快捷键在输入框内直接按组合键即可,"
                           "Win 组合键请从「常用」菜单选择(若被系统占用会"
                           "提示一键解除);留空表示不使用全局快捷键。"
                           "单独的 Win 键被系统的活动概览占用,不支持。")
        hint = QLabel(hint_text)
        hint.setWordWrap(True)
        hint.setStyleSheet("color:#888; font-size:9pt;")

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        lay = QVBoxLayout(self)
        lay.addLayout(form)
        lay.addWidget(hint)
        lay.addWidget(buttons)

    def values(self):
        seq = self.key_edit.keySequence().toString()
        return {
            "hotkey": seq.split(",")[0].strip(),
            "max_items": self.max_spin.value(),
            "font_size": self.font_spin.value(),
            "auto_paste": self.paste_chk.isChecked(),
            "language": self.lang_combo.currentData(),
        }, self.autostart_chk.isChecked()
