"""单条剪贴历史的数据模型与序列化。"""

import mimetypes
import os

from PyQt6.QtCore import QBuffer, QByteArray, QIODevice, QMimeData, QUrl
from PyQt6.QtGui import QImage

from . import constants as C
from .i18n import tr


class ClipItem:
    """一条剪贴历史。kind: text / image / image_files / audio / files"""

    def __init__(self, kind, text="", html="", image_path="", files=None,
                 color=C.DEFAULT_COLOR, sig="", name=""):
        self.kind = kind
        self.text = text
        self.html = html
        self.image_path = image_path
        self.files = files or []
        self.color = color
        self.sig = sig
        self.name = name

    # ---------- 序列化 ----------
    def to_dict(self):
        return {"kind": self.kind, "text": self.text, "html": self.html,
                "image_path": self.image_path, "files": self.files,
                "color": self.color, "sig": self.sig, "name": self.name}

    @staticmethod
    def from_dict(d):
        kind = d.get("kind", "text")
        files = d.get("files") or []
        # 旧版本把媒体 URL 保存成普通文件；加载时自动迁移分类。
        if kind == "files" and files and all(is_audio_file(f) for f in files):
            kind = "audio"
        elif (kind == "files" and files
              and all(is_image_file(f) for f in files)):
            kind = "image_files"
        sig = d.get("sig", "")
        if kind == "audio" and sig.startswith("files:"):
            sig = "audio:" + sig.removeprefix("files:")
        elif kind == "image_files" and sig.startswith("files:"):
            sig = "image-files:" + sig.removeprefix("files:")
        return ClipItem(kind, d.get("text", ""), d.get("html", ""),
                        d.get("image_path", ""), files,
                        d.get("color", C.DEFAULT_COLOR), sig,
                        d.get("name", ""))

    def category(self) -> str:
        """返回界面分类。普通文件为兼容旧功能，显示在文本页。"""
        if self.kind in ("image", "image_files"):
            return "image"
        if self.kind == "audio":
            return "audio"
        return "text"

    # ---------- 展示 ----------
    def preview(self) -> str:
        if self.kind == "text":
            lines = self.text.strip().splitlines() or [""]
            head = "\n".join(lines[:C.PREVIEW_LINES])[:C.PREVIEW_CHARS]
            if len(lines) > C.PREVIEW_LINES or len(self.text.strip()) > len(head):
                head += " …"
            return head
        if self.kind == "image":
            return self.name or tr("🖼  图片 / 表情包")
        names = [os.path.basename(f) or f for f in self.files]
        shown = "、".join(names[:3]) + ("…" if len(names) > 3 else "")
        if self.kind == "image_files":
            if self.name:
                return self.name
            return tr("🖼  {} 个图片文件:{}").format(len(names), shown)
        if self.kind == "audio":
            return tr("🎵  {} 个音频:{}").format(len(names), shown)
        return tr("📁  {} 个文件:{}").format(len(names), shown)

    def search_key(self) -> str:
        if self.kind in ("files", "image_files", "audio"):
            return " ".join([self.name, *self.files])
        # 图片条目中英文关键词都能搜到
        if self.kind == "image":
            return " ".join((self.name, "图片 表情包 image sticker"))
        return self.text

    # ---------- 转成系统剪贴板 / 拖拽用的 QMimeData ----------
    def to_mime(self) -> QMimeData:
        mime = QMimeData()
        if self.kind == "image":
            img = QImage(self.image_path)
            if not img.isNull():
                mime.setImageData(img)
                # setImageData 只保证 Qt 程序能读取
                # application/x-qt-image。Codex CLI、xclip 等非 Qt
                # 程序需要剪贴板直接提供标准 PNG 字节。
                buf = QBuffer()
                if buf.open(QIODevice.OpenModeFlag.WriteOnly):
                    if img.save(buf, "PNG"):
                        mime.setData("image/png", buf.data())
                    buf.close()
            if self.html:
                mime.setHtml(self.html)
            if os.path.exists(self.image_path):
                # 同时提供文件 URL:拖/贴到文件管理器、聊天软件时按文件处理
                mime.setUrls([QUrl.fromLocalFile(self.image_path)])
        elif self.kind in ("files", "image_files", "audio"):
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


def is_audio_file(path: str) -> bool:
    """按文件名/MIME 类型识别常见音频文件，不要求文件仍然存在。"""
    mime, _ = mimetypes.guess_type(path)
    if mime and mime.startswith("audio/"):
        return True
    return os.path.splitext(path)[1].lower() in {
        ".aac", ".aif", ".aiff", ".alac", ".amr", ".ape", ".au",
        ".flac", ".m4a", ".m4b", ".mid", ".midi", ".mp3", ".oga",
        ".ogg", ".opus", ".ra", ".wav", ".wma",
    }


def is_image_file(path: str) -> bool:
    """识别以文件 URL 复制进来的常见图片。"""
    mime, _ = mimetypes.guess_type(path)
    if mime and mime.startswith("image/"):
        return True
    return os.path.splitext(path)[1].lower() in {
        ".apng", ".avif", ".bmp", ".gif", ".heic", ".heif", ".ico",
        ".jfif", ".jpeg", ".jpg", ".png", ".svg", ".tif", ".tiff",
        ".webp",
    }
