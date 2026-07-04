"""卡片控件与带动画的卡片列表容器。"""

from PyQt6.QtCore import (QEasingCurve, QPoint, QPropertyAnimation, QRect,
                          Qt, QTimer, pyqtSignal)
from PyQt6.QtGui import QBrush, QColor, QDrag, QFont, QPixmap
from PyQt6.QtWidgets import (QApplication, QFrame, QHBoxLayout, QLabel,
                             QScrollArea, QWidget)

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

        lay = QHBoxLayout(self)
        lay.setContentsMargins(9, 9, 9, 9)
        lay.setSpacing(10)
        self.label = QLabel()
        self.label.setWordWrap(True)
        self.label.setFont(
            hei_font(int(listw.owner.config["font_size"])))
        self.img_size = None    # 图片尺寸,切换语言时重刷文案用
        if clip.kind == "image":
            thumb = QLabel()
            thumb.setStyleSheet("background: transparent; border: none;")
            pix = QPixmap(clip.image_path)
            if not pix.isNull():
                thumb.setPixmap(pix.scaled(
                    C.THUMB_SIZE, Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation))
                self.img_size = (pix.width(), pix.height())
                self.label.setText(
                    tr("🖼  图片 {}×{}").format(*self.img_size))
            else:
                self.label.setText(clip.preview())
            lay.addWidget(thumb)
        else:
            self.label.setText(clip.preview())
        lay.addWidget(self.label, 1)
        self.setForeground(QBrush(QColor(clip.color)))

    def retranslate(self):
        """切换界面语言后刷新卡片文案(文本内容本身不变)。"""
        if self.img_size is not None:
            self.label.setText(tr("🖼  图片 {}×{}").format(*self.img_size))
        elif self.clip.kind != "text":
            self.label.setText(self.clip.preview())

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

    def enterEvent(self, event):
        self.listw.itemEntered.emit(self)
        super().enterEvent(event)

    def contextMenuEvent(self, event):
        pos = self.listw.mapFromGlobal(event.globalPos())
        self.listw.customContextMenuRequested.emit(pos)


class CardList(QScrollArea):
    """卡片列表容器:所有位置变化(拖拽让位、排序、置顶、删除、过滤)
    都通过 QPropertyAnimation 平滑移动,拖拽时其他卡片实时让位。"""

    itemClicked = pyqtSignal(object)
    itemDoubleClicked = pyqtSignal(object)
    itemEntered = pyqtSignal(object)
    customContextMenuRequested = pyqtSignal(QPoint)

    SPACING = 4
    MARGIN = 6
    ANIM_MS = 160

    def __init__(self, owner):
        super().__init__()
        self.owner = owner
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
        self._press_dy = 0
        self._dragging = False
        self._suppress_click = False
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

    def relayout(self, animate=True, skip=None):
        width = self.viewport().width()
        self.container.setFixedWidth(width)
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
        self._press_dy = card.mapFromGlobal(gpos).y()
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
        # 卡片纵向跟随鼠标
        anim = self._anims.pop(card, None)
        if anim is not None:
            anim.stop()
        cy = self.container.mapFromGlobal(gpos).y() - self._press_dy
        card.move(self.MARGIN, cy)
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
