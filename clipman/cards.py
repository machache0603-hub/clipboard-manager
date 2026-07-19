"""卡片控件与带动画的卡片列表容器。"""

import os

from PyQt6.QtCore import (QEasingCurve, QPoint, QPropertyAnimation, QRect,
                          Qt, QTimer, pyqtSignal)
from PyQt6.QtGui import QBrush, QColor, QDrag, QFont, QPixmap
from PyQt6.QtWidgets import (QApplication, QFrame, QHBoxLayout, QLabel,
                             QScrollArea, QToolButton, QVBoxLayout, QWidget)

from . import constants as C
from .constants import hei_font
from .clip_item import ClipItem
from .i18n import tr


class Card(QFrame):
    """一条历史记录的卡片控件(支持位移动画)。
    提供与 QListWidgetItem 兼容的方法,便于上层代码复用。"""

    def __init__(self, clip: ClipItem, listw):
        super().__init__(listw.container)
        self.clip = clip
        self.listw = listw
        self.laid_out = False        # 首次布局直接落位,之后的变化才做动画
        self.setObjectName("Card")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setProperty("selected", False)
        self.setProperty("dragging", False)

        lay = (QVBoxLayout(self) if listw.grid_mode else QHBoxLayout(self))
        lay.setContentsMargins(9, 9, 9, 9)
        lay.setSpacing(6 if listw.grid_mode else 10)
        self.label = QLabel()
        self.label.setWordWrap(True)
        self.label.setContentsMargins(0, 0, 28, 0)
        if listw.grid_mode:
            self.label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.label.setMaximumHeight(42)
        self.label.setFont(
            hei_font(int(listw.owner.config["font_size"])))
        self.img_size = None    # 图片尺寸,切换语言时重刷文案用
        self.thumb = None
        self._source_pixmap = QPixmap()
        if clip.kind in ("image", "image_files"):
            self.thumb = QLabel()
            self.thumb.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.thumb.setStyleSheet(
                "background: transparent; border: none;")
            image_path = (clip.image_path if clip.kind == "image"
                          else (clip.files[0] if clip.files else ""))
            self._source_pixmap = QPixmap(image_path)
            if not self._source_pixmap.isNull() and not listw.grid_mode:
                self.thumb.setPixmap(self._source_pixmap.scaled(
                    C.THUMB_SIZE, Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation))
            if clip.kind == "image" and not self._source_pixmap.isNull():
                self.img_size = (self._source_pixmap.width(),
                                 self._source_pixmap.height())
            lay.addWidget(self.thumb, 1 if listw.grid_mode else 0)
        else:
            self.label.setText(clip.preview())
        lay.addWidget(self.label, 1)
        self.refresh_label()
        self.setForeground(QBrush(QColor(clip.color)))

        self.preview_btn = QToolButton(self)
        self.preview_btn.setObjectName("PreviewButton")
        self.preview_btn.setText("👁")
        self.preview_btn.setToolTip(tr("查看详细内容"))
        self.preview_btn.setFixedSize(26, 24)
        self.preview_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.preview_btn.clicked.connect(
            lambda: self.listw.owner.show_item_preview(self))
        self.preview_btn.raise_()
        self._place_preview_button()

    def refresh_label(self):
        """刷新图片名称/普通预览文本，并保留完整名称作为悬浮提示。"""
        if self.clip.kind == "image":
            if self.clip.name:
                text = self.clip.name
            elif self.img_size is not None:
                text = tr("图片 {}×{}").format(*self.img_size)
            else:
                text = tr("未命名图片")
        elif self.clip.kind == "image_files":
            if self.clip.name:
                text = self.clip.name
            elif len(self.clip.files) == 1:
                text = os.path.basename(self.clip.files[0]) or tr("未命名图片")
            else:
                text = tr("{} 个图片文件").format(len(self.clip.files))
        else:
            text = self.clip.preview()
        self.label.setText(text)
        self.label.setToolTip(text if self.clip.category() == "image" else "")

    def set_grid_dimensions(self, width: int, height: int):
        """按网格单元尺寸缩放缩略图，保持比例且不裁剪。"""
        self.setFixedSize(width, height)
        if self.thumb is None:
            return
        thumb_height = max(70, height - 66)
        self.thumb.setFixedHeight(thumb_height)
        if not self._source_pixmap.isNull():
            self.thumb.setPixmap(self._source_pixmap.scaled(
                max(40, width - 20), thumb_height,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation))

    def retranslate(self):
        """切换界面语言后刷新卡片文案(文本内容本身不变)。"""
        if self.clip.kind != "text":
            self.refresh_label()
        self.preview_btn.setToolTip(tr("查看详细内容"))

    # ----- 与 QListWidgetItem 兼容的接口 -----
    def data(self, _role):
        return self.clip

    def text(self) -> str:
        return self.label.text()

    def setText(self, text: str):
        self.label.setText(text)
        self.listw.schedule_relayout()

    def setFont(self, font: QFont):
        self.label.setFont(font)
        self.listw.schedule_relayout()

    def setForeground(self, brush: QBrush):
        # 背景透明:否则会遮住卡片自身的悬浮/选中底色
        self.label.setStyleSheet(
            f"color: {brush.color().name()};"
            " background: transparent; border: none;")

    def setHidden(self, hidden: bool):
        super().setHidden(hidden)
        self.listw.schedule_relayout()

    def set_state(self, name: str, value: bool):
        self.setProperty(name, value)
        self.style().unpolish(self)
        self.style().polish(self)

    def _place_preview_button(self):
        if not hasattr(self, "preview_btn"):
            return
        self.preview_btn.move(
            max(2, self.width() - self.preview_btn.width() - 5),
            max(2, self.height() - self.preview_btn.height() - 5))
        self.preview_btn.raise_()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._place_preview_button()

    # ----- 鼠标 -----
    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.listw.on_card_press(self, event.globalPosition().toPoint())
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if event.buttons() & Qt.MouseButton.LeftButton:
            self.listw.on_card_move(self, event.globalPosition().toPoint())
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.listw.on_card_release(self)
        super().mouseReleaseEvent(event)

    def mouseDoubleClickEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.listw.on_card_double(self)
        super().mouseDoubleClickEvent(event)

    def contextMenuEvent(self, event):
        pos = self.listw.mapFromGlobal(event.globalPos())
        self.listw.customContextMenuRequested.emit(pos)


class CardList(QScrollArea):
    """卡片列表容器:所有位置变化(拖拽让位、排序、置顶、删除、过滤)
    都通过 QPropertyAnimation 平滑移动,拖拽时其他卡片实时让位。"""

    itemClicked = pyqtSignal(object)
    itemDoubleClicked = pyqtSignal(object)
    customContextMenuRequested = pyqtSignal(QPoint)

    SPACING = 4
    MARGIN = 6
    ANIM_MS = 160
    GRID_MIN_CELL_WIDTH = 180

    def __init__(self, owner, grid_mode=False):
        super().__init__()
        self.owner = owner
        self.grid_mode = grid_mode
        self.cards = []
        self.container = QWidget()
        self.container.setObjectName("CardContainer")
        self.setWidget(self.container)
        self.setWidgetResizable(False)
        self.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setAcceptDrops(True)

        self._current = None
        self._anims = {}
        self._press_card = None
        self._press_gpos = QPoint()
        self._press_dx = 0
        self._press_dy = 0
        self._dragging = False
        self._suppress_click = False
        self._grid_columns = 1
        self._cell_width = 0
        self._cell_height = 0
        self._relayout_timer = QTimer(self)
        self._relayout_timer.setSingleShot(True)
        self._relayout_timer.setInterval(0)
        self._relayout_timer.timeout.connect(lambda: self.relayout(True))

    # ---------------- 与 QListWidget 兼容的接口 ----------------
    def count(self) -> int:
        return len(self.cards)

    def item(self, row: int):
        if 0 <= row < len(self.cards):
            return self.cards[row]
        return None

    def row(self, card) -> int:
        try:
            return self.cards.index(card)
        except ValueError:
            return -1

    def itemAt(self, pos: QPoint):
        lpos = self.container.mapFromGlobal(self.mapToGlobal(pos))
        for card in self.cards:
            if not card.isHidden() and card.geometry().contains(lpos):
                return card
        return None

    def currentItem(self):
        return self._current if self._current in self.cards else None

    def setCurrentItem(self, card):
        if self._current is not None and self._current in self.cards:
            self._current.set_state("selected", False)
        self._current = card
        if card is not None:
            card.set_state("selected", True)

    def takeItem(self, row: int):
        card = self.item(row)
        if card is None:
            return None
        self.cards.pop(row)
        anim = self._anims.pop(card, None)
        if anim is not None:
            anim.stop()
        if self._current is card:
            self._current = None
        card.hide()
        card.setParent(None)
        card.deleteLater()
        self.schedule_relayout()
        return card

    def insert_card(self, clip: ClipItem, row: int):
        card = Card(clip, self)
        self.cards.insert(max(0, min(row, len(self.cards))), card)
        card.show()
        self.schedule_relayout()
        return card

    def move_row(self, src: int, target: int) -> bool:
        """把第 src 行移动到 target 落点之前;返回是否发生了移动。"""
        if src < 0 or src >= len(self.cards):
            return False
        if target > src:
            target -= 1
        target = max(0, min(target, len(self.cards) - 1))
        if target == src:
            return False
        card = self.cards.pop(src)
        self.cards.insert(target, card)
        self.setCurrentItem(card)
        self.relayout(animate=True)
        self.owner.schedule_save()
        return True

    def item_global_rect(self, card) -> QRect:
        try:
            return QRect(card.mapToGlobal(QPoint(0, 0)), card.size())
        except RuntimeError:
            return QRect()

    # ---------------- 布局与动画 ----------------
    def schedule_relayout(self):
        self._relayout_timer.start()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.relayout(animate=False)

    @classmethod
    def column_count_for_width(cls, width: int) -> int:
        """图片网格只使用 2、3、5 列，避免出现零散的 1/4 列状态。"""
        usable = max(0, width - 2 * cls.MARGIN)
        five = 5 * cls.GRID_MIN_CELL_WIDTH + 4 * cls.SPACING
        three = 3 * cls.GRID_MIN_CELL_WIDTH + 2 * cls.SPACING
        if usable >= five:
            return 5
        if usable >= three:
            return 3
        return 2

    def relayout(self, animate=True, skip=None):
        width = self.viewport().width()
        self.container.setFixedWidth(width)
        if self.grid_mode:
            self._relayout_grid(width, animate, skip)
            return
        cw = max(50, width - 2 * self.MARGIN)
        y = self.MARGIN
        for card in self.cards:
            if card.isHidden():
                continue
            card.setFixedWidth(cw)
            lay = card.layout()
            h = (lay.heightForWidth(cw) if lay.hasHeightForWidth()
                 else card.sizeHint().height())
            card.setFixedHeight(h)
            if card is not skip:            # 被拖拽的卡片跟随鼠标,不摆放
                target = QPoint(self.MARGIN, y)
                if animate and card.laid_out and card.pos() != target:
                    self._animate(card, target)
                else:
                    anim = self._anims.pop(card, None)
                    if anim is not None:
                        anim.stop()
                    card.move(target)
                card.laid_out = True
            y += h + self.SPACING
        self.container.setFixedHeight(
            max(y - self.SPACING + self.MARGIN, self.viewport().height()))

    def _relayout_grid(self, width, animate=True, skip=None):
        columns = self.column_count_for_width(width)
        available = max(100, width - 2 * self.MARGIN
                        - (columns - 1) * self.SPACING)
        cw = max(50, available // columns)
        # 缩略图区域随列宽变化，卡片高度保持紧凑且同一行齐平。
        ch = max(150, min(250, int(cw * 0.82) + 52))
        self._grid_columns = columns
        self._cell_width = cw
        self._cell_height = ch

        visible_index = 0
        for card in self.cards:
            if card.isHidden():
                continue
            card.set_grid_dimensions(cw, ch)
            row, col = divmod(visible_index, columns)
            if card is not skip:
                target = QPoint(
                    self.MARGIN + col * (cw + self.SPACING),
                    self.MARGIN + row * (ch + self.SPACING))
                if animate and card.laid_out and card.pos() != target:
                    self._animate(card, target)
                else:
                    anim = self._anims.pop(card, None)
                    if anim is not None:
                        anim.stop()
                    card.move(target)
                card.laid_out = True
            visible_index += 1

        rows = ((visible_index + columns - 1) // columns
                if visible_index else 0)
        content_height = (2 * self.MARGIN + rows * ch
                          + max(0, rows - 1) * self.SPACING)
        self.container.setFixedHeight(
            max(content_height, self.viewport().height()))

    def _animate(self, card, target: QPoint):
        anim = self._anims.pop(card, None)
        if anim is not None:
            anim.stop()
        anim = QPropertyAnimation(card, b"pos", self)
        anim.setDuration(self.ANIM_MS)
        anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        anim.setStartValue(card.pos())
        anim.setEndValue(target)
        anim.start()
        self._anims[card] = anim

    # ---------------- 卡片拖拽(实时让位动画) ----------------
    def on_card_press(self, card, gpos: QPoint):
        self.setCurrentItem(card)
        self.setFocus()
        self._press_card = card
        self._press_gpos = gpos
        press_pos = card.mapFromGlobal(gpos)
        self._press_dx = press_pos.x()
        self._press_dy = press_pos.y()
        self._dragging = False

    def on_card_move(self, card, gpos: QPoint):
        if self._press_card is not card:
            return
        if not self._dragging:
            if ((gpos - self._press_gpos).manhattanLength()
                    < QApplication.startDragDistance()):
                return
            self._dragging = True
            self.owner.preview.hide_popup()
            card.raise_()
            card.set_state("dragging", True)
        # 拖出列表范围 → 转为拖到外部应用粘贴
        local = self.mapFromGlobal(gpos)
        if not self.rect().adjusted(-40, -40, 40, 40).contains(local):
            self._start_external_drag(card)
            return
        # 列表卡片纵向移动；图片网格卡片同时跟随横纵坐标。
        anim = self._anims.pop(card, None)
        if anim is not None:
            anim.stop()
        cpos = self.container.mapFromGlobal(gpos)
        cy = cpos.y() - self._press_dy
        cx = cpos.x() - self._press_dx if self.grid_mode else self.MARGIN
        card.move(cx, cy)
        self._reorder_live(card)
        # 靠近上下边缘时自动滚动
        vy = self.viewport().mapFromGlobal(gpos).y()
        bar = self.verticalScrollBar()
        if vy < 28:
            bar.setValue(bar.value() - 14)
        elif vy > self.viewport().height() - 28:
            bar.setValue(bar.value() + 14)

    def _reorder_live(self, card):
        """拖动过程中按卡片中心实时调整顺序,其他卡片动画让位。"""
        if self.grid_mode:
            self._reorder_grid_live(card)
            return
        center = card.y() + card.height() // 2
        others = [c for c in self.cards
                  if c is not card and not c.isHidden()]
        vis_idx = sum(1 for c in others
                      if center > c.y() + c.height() // 2)
        if vis_idx < len(others):
            new_idx = self.cards.index(others[vis_idx])
            if self.cards.index(card) < new_idx:
                new_idx -= 1
        else:
            new_idx = len(self.cards) - 1
        cur_idx = self.cards.index(card)
        if new_idx != cur_idx:
            self.cards.pop(cur_idx)
            self.cards.insert(new_idx, card)
            self.relayout(animate=True, skip=card)

    def _reorder_grid_live(self, card):
        """图片网格按离鼠标最近的行列槽位计算实时落点。"""
        others = [c for c in self.cards
                  if c is not card and not c.isHidden()]
        center = card.geometry().center()
        step_x = max(1, self._cell_width + self.SPACING)
        step_y = max(1, self._cell_height + self.SPACING)
        first_x = self.MARGIN + self._cell_width // 2
        first_y = self.MARGIN + self._cell_height // 2
        col = round((center.x() - first_x) / step_x)
        row = round((center.y() - first_y) / step_y)
        col = max(0, min(col, self._grid_columns - 1))
        row = max(0, row)
        visible_target = min(row * self._grid_columns + col, len(others))

        cur_idx = self.cards.index(card)
        remaining = self.cards[:cur_idx] + self.cards[cur_idx + 1:]
        if visible_target < len(others):
            new_idx = remaining.index(others[visible_target])
        elif others:
            new_idx = remaining.index(others[-1]) + 1
        else:
            new_idx = 0
        if new_idx != cur_idx:
            self.cards.pop(cur_idx)
            self.cards.insert(new_idx, card)
            self.relayout(animate=True, skip=card)

    def on_card_release(self, card):
        if self._press_card is not card:
            return
        was_drag = self._dragging
        self._press_card = None
        self._dragging = False
        if was_drag:
            card.set_state("dragging", False)
            self.relayout(animate=True)     # 卡片动画滑入落点
            self.owner.schedule_save()
        elif self._suppress_click:
            self._suppress_click = False
        else:
            self.itemClicked.emit(card)

    def on_card_double(self, card):
        self._suppress_click = True
        self.itemDoubleClicked.emit(card)

    def _start_external_drag(self, card):
        self._press_card = None
        self._dragging = False
        card.set_state("dragging", False)
        self.relayout(animate=True)         # 先让卡片归位
        drag = QDrag(self)
        drag.setMimeData(card.clip.to_mime())
        pix = card.grab()
        if pix.width() > 320:
            pix = pix.scaledToWidth(
                320, Qt.TransformationMode.SmoothTransformation)
        drag.setPixmap(pix)
        drag.setHotSpot(pix.rect().center())
        drag.exec(Qt.DropAction.CopyAction)

    # ---------------- 键盘 / 空白处右键 ----------------
    def keyPressEvent(self, event):
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            card = self.currentItem()
            if card is not None:
                self.owner.copy_item(card)
                return
        super().keyPressEvent(event)

    def contextMenuEvent(self, event):
        self.customContextMenuRequested.emit(event.pos())

    # ---------------- 外部拖入 ----------------
    def dragEnterEvent(self, event):
        mime = event.mimeData()
        if event.source() is not self and (
                mime.hasImage() or mime.hasUrls() or mime.hasText()):
            event.acceptProposedAction()
        else:
            event.ignore()

    def dragMoveEvent(self, event):
        event.acceptProposedAction()

    def dropEvent(self, event):
        if event.source() is self:          # 自己拖出去又拖回来:忽略
            event.ignore()
            return
        event.setDropAction(Qt.DropAction.CopyAction)
        event.accept()
        # 拖进哪个页面就加到哪个列表(历史 / 常用)
        self.owner.add_dropped(self, event.mimeData())
