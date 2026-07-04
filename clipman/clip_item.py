"""单条剪贴历史的数据模型与序列化。"""

import os

from PyQt6.QtCore import QByteArray, QMimeData, QUrl
from PyQt6.QtGui import QImage

from . import constants as C
from .i18n import tr


class ClipItem:
    """一条剪贴历史。kind: text / image / files"""

    def __init__(self, kind, text="", html="", image_path="", files=None,
                 color=C.DEFAULT_COLOR, sig=""):
        self.kind = kind
        self.text = text
        self.html = html
        self.image_path = image_path
        self.files = files or []
        self.color = color
        self.sig = sig

    # ---------- 序列化 ----------
    def to_dict(self):
        return {"kind": self.kind, "text": self.text, "html": self.html,
                "image_path": self.image_path, "files": self.files,
                "color": self.color, "sig": self.sig}

    @staticmethod
    def from_dict(d):
        return ClipItem(d.get("kind", "text"), d.get("text", ""),
                        d.get("html", ""), d.get("image_path", ""),
                        d.get("files"), d.get("color", C.DEFAULT_COLOR),
                        d.get("sig", ""))

    # ---------- 展示 ----------
    def preview(self) -> str:
        if self.kind == "text":
            lines = self.text.strip().splitlines() or [""]
            head = "\n".join(lines[:C.PREVIEW_LINES])[:C.PREVIEW_CHARS]
            if len(lines) > C.PREVIEW_LINES or len(self.text.strip()) > len(head):
                head += " …"
            return head
        if self.kind == "image":
            return tr("🖼  图片 / 表情包")
        names = [os.path.basename(f) or f for f in self.files]
        shown = "、".join(names[:3]) + ("…" if len(names) > 3 else "")
        return tr("📁  {} 个文件:{}").format(len(names), shown)

    def search_key(self) -> str:
        if self.kind == "files":
            return " ".join(self.files)
        # 图片条目中英文关键词都能搜到
        return self.text or ("图片 表情包 image sticker"
                             if self.kind == "image" else "")

    # ---------- 转成系统剪贴板 / 拖拽用的 QMimeData ----------
    def to_mime(self) -> QMimeData:
        mime = QMimeData()
        if self.kind == "image":
            img = QImage(self.image_path)
            if not img.isNull():
                mime.setImageData(img)
            if self.html:
                mime.setHtml(self.html)
            if os.path.exists(self.image_path):
                # 同时提供文件 URL:拖/贴到文件管理器、聊天软件时按文件处理
                mime.setUrls([QUrl.fromLocalFile(self.image_path)])
        elif self.kind == "files":
            urls = [QUrl.fromLocalFile(f) for f in self.files]
            mime.setUrls(urls)
            mime.setText("\n".join(self.files))
            gnome = "copy\n" + "\n".join(u.toString() for u in urls)
            # 让 GNOME 文件管理器(Nautilus)能识别"粘贴文件"
            mime.setData("x-special/gnome-copied-files",
                         QByteArray(gnome.encode()))
        else:
            mime.setText(self.text)
            if self.html:
                mime.setHtml(self.html)
        return mime
