"""由卡片眼睛按钮打开的详情预览/编辑弹窗。"""

from PyQt6.QtCore import QMimeData, QRect, Qt, QTimer
from PyQt6.QtGui import QCursor, QPixmap
from PyQt6.QtWidgets import (QApplication, QHBoxLayout, QLabel,
                             QLineEdit, QPlainTextEdit, QPushButton,
                             QToolButton, QVBoxLayout, QWidget)

from . import constants as C
from .constants import hei_font
from .i18n import tr


class PreviewPopup(QWidget):
    """点击卡片眼睛按钮后弹出的完整内容预览窗。
    打开后持续显示，只由右上角关闭按钮或内容失效场景关闭。"""

    def __init__(self, owner):
        super().__init__(None)
        self.owner = owner
        self.item = None
        self.setWindowFlags(Qt.WindowType.Tool
                            | Qt.WindowType.FramelessWindowHint
                            | Qt.WindowType.WindowStaysOnTopHint)
        # 弹出时不抢焦点,点击编辑区时才获得焦点
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)

        self.editor = QPlainTextEdit()
        self.editor.textChanged.connect(self._on_edited)
        self.img_label = QLabel()
        self.img_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.name_editor = QLineEdit()
        self.name_editor.textEdited.connect(self._on_edited)
        self.name_editor.setClearButtonEnabled(True)
        self.title_label = QLabel()
        self.title_label.setStyleSheet(
            "font-weight: 600; color: #344054; border: none;")
        self.close_btn = QToolButton()
        self.close_btn.setObjectName("DetailCloseButton")
        self.close_btn.setText("×")
        self.close_btn.setFixedSize(28, 28)
        self.close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.close_btn.clicked.connect(self.hide_popup)
        self.tip = QLabel()
        self.tip.setStyleSheet("color:#999; font-size:9pt; border:none;")
        self.copy_btn = QPushButton(tr("📋 复制"))
        self.copy_btn.clicked.connect(self._copy)
        self.save_btn = QPushButton(tr("💾 保存修改"))
        self.save_btn.clicked.connect(self._save)

        btns = QHBoxLayout()
        btns.addWidget(self.tip)
        btns.addStretch(1)
        btns.addWidget(self.copy_btn)
        btns.addWidget(self.save_btn)
        header = QHBoxLayout()
        header.setContentsMargins(2, 0, 0, 0)
        header.addWidget(self.title_label)
        header.addStretch(1)
        header.addWidget(self.close_btn)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(10, 10, 10, 8)
        lay.addLayout(header)
        lay.addWidget(self.img_label)
        lay.addWidget(self.name_editor)
        lay.addWidget(self.editor)
        lay.addLayout(btns)

        self.setStyleSheet("""
            PreviewPopup {
                background: #ffffff;
                border: 1px solid #8fb4e8; border-radius: 8px;
            }
            QLineEdit, QPlainTextEdit {
                background: #ffffff; color: #000000;
                border: 1px solid #e3e3e3; border-radius: 6px;
            }
            QLineEdit { padding: 6px 8px; }
            QPushButton {
                border: 1px solid #d9d9d9; border-radius: 6px;
                padding: 5px 12px; background: #ffffff;
            }
            QPushButton:hover { background: #f2f7ff; }
            QPushButton:disabled { color: #bbbbbb; }
            #DetailCloseButton {
                background: transparent; color: #667085;
                border: none; border-radius: 6px;
                padding: 0px; font-size: 17pt;
            }
            #DetailCloseButton:hover {
                background: #fee4e2; color: #b42318;
            }
            #DetailCloseButton:pressed { background: #fecdca; }
        """)

        self._reset_timer = QTimer(self)
        self._reset_timer.setSingleShot(True)
        self._reset_timer.timeout.connect(self._reset_buttons)

    def _reset_buttons(self):
        self.copy_btn.setText(tr("📋 复制"))
        self.save_btn.setText(tr("💾 保存修改"))
        self.name_editor.setPlaceholderText(tr("输入图片备注名…"))
        self.close_btn.setToolTip(tr("关闭详情"))

    def retranslate(self):
        self._reset_buttons()

    # ---------- 显示 ----------
    def show_for(self, item, anchor: QRect):
        clip = item.data(C.ROLE_CLIP)
        self.item = item
        self._reset_buttons()
        if clip.category() == "image":
            self.title_label.setText(tr("图片详情"))
        elif clip.category() == "audio":
            self.title_label.setText(tr("音频详情"))
        elif clip.kind == "text":
            self.title_label.setText(tr("文本详情"))
        else:
            self.title_label.setText(tr("文件详情"))
        is_image = clip.category() == "image"
        self.name_editor.blockSignals(True)
        self.name_editor.setText(clip.name or item.text() if is_image else "")
        self.name_editor.blockSignals(False)
        self.name_editor.setVisible(is_image)
        if clip.kind == "image":
            pix = QPixmap(clip.image_path)
            if pix.isNull():
                return
            if pix.width() > 480 or pix.height() > 360:
                pix = pix.scaled(480, 360,
                                 Qt.AspectRatioMode.KeepAspectRatio,
                                 Qt.TransformationMode.SmoothTransformation)
            self.img_label.setPixmap(pix)
            self.img_label.show()
            self.editor.hide()
            self.save_btn.show()
            self.save_btn.setEnabled(False)
            self.tip.setText(tr("可修改图片备注名"))
        else:
            text = clip.text if clip.kind == "text" \
                else "\n".join(clip.files)
            self.editor.blockSignals(True)
            self.editor.setPlainText(text)
            self.editor.blockSignals(False)
            self.editor.setReadOnly(clip.kind != "text")
            self.editor.setFont(
                hei_font(int(self.owner.config["font_size"])))
            self.editor.setFixedSize(390, 240)
            self.editor.show()
            self.img_label.hide()
            self.img_label.setPixmap(QPixmap())
            self.save_btn.setVisible(clip.kind == "text" or is_image)
            self.save_btn.setEnabled(False)
            if clip.kind == "text":
                tip = tr("可直接编辑")
            elif clip.kind == "image_files":
                tip = tr("文件列表只读，图片名称可修改")
            elif clip.kind == "audio":
                tip = tr("音频文件(只读)")
            else:
                tip = tr("文件列表(只读)")
            self.tip.setText(tip)
        self.adjustSize()
        self._place(anchor)
        self.show()

    def _place(self, anchor: QRect):
        screen = (QApplication.screenAt(QCursor.pos())
                  or QApplication.primaryScreen())
        geo = screen.availableGeometry()
        w, h = self.sizeHint().width(), self.sizeHint().height()
        win = self.owner.frameGeometry()
        x = win.right() + 8                 # 优先放在窗口右侧
        if x + w > geo.right():
            x = win.left() - w - 8          # 放不下就放左侧
        x = max(geo.left(), x)
        y = max(geo.top(), min(anchor.top(), geo.bottom() - h))
        self.move(x, y)

    def hide_popup(self):
        self.item = None
        self.hide()

    # ---------- 关闭时机 ----------
    def _item_alive(self) -> bool:
        try:
            return (self.item is not None
                    and self.owner.list_of(self.item).row(self.item) >= 0)
        except RuntimeError:                # 条目已被删除
            return False

    # ---------- 动作 ----------
    def _on_edited(self, *_args):
        if self.item is not None:
            self.save_btn.setEnabled(True)

    def _copy(self):
        if not self._item_alive():
            return
        clip = self.item.data(C.ROLE_CLIP)
        if clip.kind != "text":
            self.owner.copy_item(self.item)
        else:
            mime = QMimeData()
            mime.setText(self.editor.toPlainText())
            self.owner.set_clipboard_mime(mime)
        self.copy_btn.setText(tr("✓ 已复制"))
        self._reset_timer.start(1200)

    def _save(self):
        if not self._item_alive():
            return
        clip = self.item.data(C.ROLE_CLIP)
        if clip.category() == "image":
            self.owner.update_image_name(
                self.item, self.name_editor.text())
        else:
            self.owner.update_item_text(
                self.item, self.editor.toPlainText())
        self.save_btn.setText(tr("✓ 已保存"))
        self.save_btn.setEnabled(False)
        self._reset_timer.start(1200)
