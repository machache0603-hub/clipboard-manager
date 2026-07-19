"""自测(无显示环境也能跑):python3 clipboard_manager.py --selftest"""

import hashlib
import json
import os
import sys
import tempfile

from PyQt6.QtCore import QMimeData, QRect, QUrl
from PyQt6.QtGui import QColor, QImage
from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import QApplication

from . import constants as C
from .clip_item import ClipItem
from .constants import DEFAULT_CONFIG, ROLE_CLIP
from .hotkey import (HAVE_XLIB, accel_parts, qt_to_gnome, qt_to_pynput,
                     qt_to_x11)
from .main_window import ClipboardManager
from .settings_dialog import SettingsDialog

if HAVE_XLIB:
    from Xlib import X, XK


def _configure_output_encoding():
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            try:
                stream.reconfigure(encoding="utf-8", errors="replace")
            except (OSError, ValueError):
                pass


def run_selftest() -> int:
    _configure_output_encoding()

    # 自测使用独立的临时目录,不碰真实历史数据
    tmp = tempfile.mkdtemp(prefix="clipboard-manager-selftest-")
    C.DATA_DIR = tmp
    C.IMG_DIR = os.path.join(tmp, "images")
    C.HISTORY_FILE = os.path.join(tmp, "history.json")
    C.FAVORITES_FILE = os.path.join(tmp, "favorites.json")
    C.CONFIG_FILE = os.path.join(tmp, "config.json")
    with open(C.CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump({"hotkey": ""}, f)   # 无显示环境下不注册全局快捷键

    app = QApplication.instance() or QApplication(sys.argv)
    from .app import force_light_theme
    force_light_theme(app)
    win = ClipboardManager()
    failures = []

    total = [0]

    def check(name, cond):
        total[0] += 1
        print(("PASS  " if cond else "FAIL  ") + name)
        if not cond:
            failures.append(name)

    base = win.listw.count()

    # 文本条目
    m1 = QMimeData(); m1.setText("你好,剪贴板 hello")
    win.add_from_mime(m1)
    check("添加文本条目", win.listw.count() == base + 1)
    check("默认黑色字体", win.listw.item(0).data(ROLE_CLIP).color == "#000000")

    # 去重:同样内容不重复添加
    m2 = QMimeData(); m2.setText("你好,剪贴板 hello")
    win.add_from_mime(m2)
    check("重复文本去重", win.listw.count() == base + 1)

    # 图片条目
    img = QImage(64, 48, QImage.Format.Format_RGB32)
    img.fill(QColor("#ff8800"))
    m3 = QMimeData(); m3.setImageData(img)
    win.add_from_mime(m3)
    image_list = win.history_lists["image"]
    clip_img = image_list.item(0).data(ROLE_CLIP)
    check("添加图片条目", clip_img.kind == "image"
          and os.path.exists(clip_img.image_path)
          and image_list.count() == 1)
    image_item = image_list.item(0)
    check("图片名称显示在缩略图下方",
          "64×48" in image_item.text())
    win.update_image_name(image_item, "橙色示例图")
    win.apply_filter("橙色示例图")
    check("图片备注名可修改并搜索", clip_img.name == "橙色示例图"
          and image_item.text() == "橙色示例图"
          and not image_item.isHidden())
    win.apply_filter("")
    win.preview.hide_popup()
    image_item.preview_btn.click()
    check("眼睛按钮打开详情且悬浮链路已移除",
          win.preview.isVisible() and win.preview.item is image_item
          and not hasattr(win, "_hover_timer")
          and not hasattr(win.preview, "_watch"))
    QTest.qWait(600)
    win.switch_category("text")
    persistent = (win.preview.isVisible()
                  and win.preview.item is image_item)
    win.switch_category("image")
    check("详情在鼠标移开和切换分类后持续显示", persistent)
    win.preview.close_btn.click()
    check("右上角关闭按钮关闭详情",
          not win.preview.isVisible() and win.preview.item is None)
    image_item.preview_btn.click()
    win.preview.name_editor.setText("项目封面备注")
    win.preview._save()
    check("预览窗可编辑图片备注名",
          clip_img.name == "项目封面备注"
          and image_item.text() == "项目封面备注")
    win.preview.hide_popup()
    image_mime = clip_img.to_mime()
    png_data = bytes(image_mime.data("image/png"))
    check("图片剪贴板提供标准 PNG",
          image_mime.hasFormat("image/png")
          and png_data.startswith(b"\x89PNG\r\n\x1a\n")
          and not QImage.fromData(png_data, "PNG").isNull())

    # 文件条目
    m4 = QMimeData()
    m4.setUrls([QUrl.fromLocalFile("/etc/hostname")])
    win.add_from_mime(m4)
    check("添加文件条目", win.listw.item(0).data(ROLE_CLIP).kind == "files")

    # 从文件管理器复制的图片是 URL，也应落在图片页。
    m_image_file = QMimeData()
    m_image_file.setUrls([QUrl.fromLocalFile("/tmp/selftest-photo.webp")])
    win.add_from_mime(m_image_file)
    check("图片文件 URL 进入图片分类",
          image_list.item(0).data(ROLE_CLIP).kind == "image_files"
          and image_list.count() == 2)

    # 音频 URL 会单独进入音频页，而不是混在普通文件中。
    m_audio = QMimeData()
    m_audio.setUrls([QUrl.fromLocalFile("/tmp/selftest-song.mp3")])
    win.add_from_mime(m_audio)
    audio_list = win.history_lists["audio"]
    audio_clip = audio_list.item(0).data(ROLE_CLIP)
    check("添加音频并独立分类", audio_list.count() == 1
          and audio_clip.kind == "audio"
          and audio_clip.files == ["/tmp/selftest-song.mp3"])
    check("所有内容卡片都有眼睛按钮",
          all(hasattr(lw.item(0), "preview_btn")
              for lw in (win.listw, image_list, audio_list)))
    check("音频可回写文件 URL", audio_clip.to_mime().hasUrls())
    legacy_audio = ClipItem.from_dict({
        "kind": "files", "files": ["/tmp/legacy.wav"],
        "sig": "files:legacy",
    })
    check("旧版音频记录自动迁移", legacy_audio.kind == "audio"
          and legacy_audio.sig == "audio:legacy")

    # 三个分类标签分别切到三个真实页面。
    win.switch_category("image")
    image_page_ok = (win.current_list() is image_list
                     and win.image_tab.isChecked())
    win.switch_category(2)
    audio_page_ok = (win.current_list() is audio_list
                     and win.audio_tab.isChecked())
    win.switch_category("text")
    check("文本图片音频分类页切换", image_page_ok and audio_page_ok
          and win.current_list() is win.listw and win.text_tab.isChecked())
    check("图片页响应式列数",
          image_list.grid_mode
          and image_list.column_count_for_width(430) == 2
          and image_list.column_count_for_width(700) == 3
          and image_list.column_count_for_width(1100) == 5)

    # 再复制一次旧文本 → 应挪到顶部而不是新增
    n = win.listw.count()
    m5 = QMimeData(); m5.setText("你好,剪贴板 hello")
    win.add_from_mime(m5)
    check("旧内容重新置顶", win.listw.count() == n
          and win.listw.item(0).data(ROLE_CLIP).kind == "text")

    # 拖动排序:第 0 行移到末尾
    first_sig = win.listw.item(0).data(ROLE_CLIP).sig
    win.listw.move_row(0, win.listw.count())
    check("拖动排序", win.listw.item(win.listw.count() - 1)
          .data(ROLE_CLIP).sig == first_sig)

    # 修改字体颜色
    item0 = win.listw.item(0)
    win.set_item_color(item0, QColor("#e91e63"))
    check("修改字体颜色", item0.data(ROLE_CLIP).color == "#e91e63")

    # 恢复剪贴板(历史内容可再粘贴)
    win.copy_item(win.listw.item(win.listw.count() - 1))
    check("历史条目回写剪贴板",
          QApplication.clipboard().mimeData().hasText()
          or QApplication.clipboard().mimeData().hasImage())

    # 回归测试:单击信号必须走自动粘贴链路,不再等待双击。
    paste_calls = []
    old_is_linux = C.IS_LINUX
    old_send_paste_key = win._send_paste_key
    old_auto_paste = win.config["auto_paste"]
    try:
        C.IS_LINUX = False
        win.config["auto_paste"] = True
        win._send_paste_key = lambda: paste_calls.append(True)
        win.listw.itemClicked.emit(win.listw.item(0))
        QTest.qWait(350)
    finally:
        C.IS_LINUX = old_is_linux
        win._send_paste_key = old_send_paste_key
        win.config["auto_paste"] = old_auto_paste
    check("单击条目触发自动粘贴", len(paste_calls) == 1)

    # 持久化往返
    win.save_history()
    with open(C.HISTORY_FILE, encoding="utf-8") as f:
        saved = json.load(f)["items"]
    history_count = sum(lw.count() for lw in win.history_lists.values())
    check("历史持久化", len(saved) == history_count
          and any(i["color"] == "#e91e63" for i in saved)
          and any(i.get("name") == "项目封面备注" for i in saved))

    # QMimeData 生成
    mime = win.listw.item(0).data(ROLE_CLIP).to_mime()
    check("条目可生成 MIME 数据",
          mime.hasText() or mime.hasImage() or mime.hasUrls())

    # 快捷键格式转换(X11 掩码 + keysym)
    if HAVE_XLIB:
        check("快捷键转换",
              qt_to_x11("Ctrl+Alt+V") == (X.ControlMask | X.Mod1Mask,
                                          XK.string_to_keysym("v"))
              and qt_to_x11("Meta+F5") == (X.Mod4Mask,
                                           XK.string_to_keysym("F5"))
              and qt_to_x11("") is None
              and qt_to_x11("Ctrl+Space") == (X.ControlMask,
                                              XK.string_to_keysym("space")))
        check("Win 键别名与符号键",
              qt_to_x11("Win+V") == qt_to_x11("Meta+V") != None
              and qt_to_x11("Super+C") == (X.Mod4Mask,
                                           XK.string_to_keysym("c"))
              and qt_to_x11("Ctrl+`") == (X.ControlMask,
                                          XK.string_to_keysym("grave")))
    else:
        check("快捷键转换(缺 python-xlib,跳过)", True)

    # GNOME 快捷键格式与 Qt 格式的等价比较
    check("GNOME 格式对齐",
          accel_parts("<Super>v") == accel_parts("Meta+V")
          == accel_parts("Win+V")
          and accel_parts("<Control><Alt>Delete")
          == accel_parts("Ctrl+Alt+Delete")
          and accel_parts("<Primary>c") == accel_parts("Ctrl+C")
          and accel_parts("<Super>v") != accel_parts("<Super>m"))

    # Qt → GNOME 绑定格式
    check("GNOME 绑定格式生成",
          qt_to_gnome("Meta+V") == "<Super>v"
          and qt_to_gnome("Win+F5") == "<Super>F5"
          and qt_to_gnome("Ctrl+Shift+Space") == "<Control><Shift>space"
          and qt_to_gnome("") is None)

    # 中英文翻译:解析、切换、漏翻回退
    from . import i18n
    from .i18n import tr
    old_lang = i18n.LANG
    i18n.init("en")
    en_ok = (tr("⚙ 设置") == "⚙ Settings"
             and tr("已复制") == "Copied"
             and tr("未收录的字符串") == "未收录的字符串"
             and tr("请到目标窗口按 {} 粘贴").format("Ctrl+V")
             == "Switch to the target window and press Ctrl+V to paste")
    i18n.init("zh")
    zh_ok = tr("⚙ 设置") == "⚙ 设置"
    check("中英文翻译切换",
          en_ok and zh_ok
          and i18n.resolve("zh") == "zh" and i18n.resolve("en") == "en"
          and i18n.resolve("auto") in ("zh", "en"))
    i18n.LANG = old_lang

    # Qt → pynput 格式(Windows / macOS 全局快捷键)
    check("pynput 格式生成",
          qt_to_pynput("Ctrl+Alt+V") == "<ctrl>+<alt>+v"
          and qt_to_pynput("Win+V") == "<cmd>+v"
          and qt_to_pynput("F9") == "<f9>"
          and qt_to_pynput("Ctrl+Space") == "<ctrl>+<space>"
          and qt_to_pynput("") is None)

    # 悬浮预览:展示 → 编辑 → 保存 → 复制
    text_item = None
    for r in range(win.listw.count()):
        if win.listw.item(r).data(ROLE_CLIP).kind == "text":
            text_item = win.listw.item(r)
            break
    win.preview.show_for(text_item, QRect(0, 0, 10, 10))
    check("预览窗展示完整文本",
          win.preview.editor.toPlainText()
          == text_item.data(ROLE_CLIP).text)
    win.preview.editor.setPlainText("编辑后的新内容 abc")
    win.preview._save()
    clip_t = text_item.data(ROLE_CLIP)
    check("预览窗编辑并保存",
          clip_t.text == "编辑后的新内容 abc"
          and clip_t.sig == "text:" + hashlib.sha1(
              "编辑后的新内容 abc".encode()).hexdigest()
          and "编辑后的新内容" in text_item.text())
    win.preview._copy()
    check("预览窗复制当前内容",
          QApplication.clipboard().text() == "编辑后的新内容 abc")
    win.preview.hide_popup()
    check("预览窗可关闭", not win.preview.isVisible())

    # 配置保存/读取往返
    win.config["max_items"] = 55
    win.config["font_size"] = 13
    win.save_config()
    win.config = dict(DEFAULT_CONFIG)
    win.load_config()
    check("配置持久化", win.config["max_items"] == 55
          and win.config["font_size"] == 13)

    # 设置对话框取值
    dlg = SettingsDialog(win, win.config, autostart_on=False)
    values, autostart = dlg.values()
    check("设置对话框取值", values["max_items"] == 55
          and values["font_size"] == 13 and autostart is False)

    # 常用内容页:收藏、去重、手动添加、持久化、删除
    fav_src = win.listw.item(0)
    win.add_item_to_favorites(fav_src)
    win.add_item_to_favorites(fav_src)          # 重复收藏应去重
    check("收藏到常用与去重", win.favw.count() == 1
          and win.favw.item(0).data(ROLE_CLIP).sig
          == fav_src.data(ROLE_CLIP).sig)
    win.add_favorite_text("常用片段 xyz")
    win.add_favorite_text("   ")                # 空白内容应被忽略
    check("手动添加常用", win.favw.count() == 2
          and win.favw.item(0).data(ROLE_CLIP).text == "常用片段 xyz")
    win.save_history()
    with open(C.FAVORITES_FILE, encoding="utf-8") as f:
        saved_favs = json.load(f)["items"]
    check("常用内容持久化", len(saved_favs) == 2
          and saved_favs[0]["text"] == "常用片段 xyz")
    win.switch_page(1)
    check("页面切换", win.current_list() is win.favw
          and win.fav_tab.isChecked() and not win.hist_tab.isChecked())
    win.delete_item(win.favw.item(0))
    check("删除常用条目", win.favw.count() == 1
          and win.listw.count() > 0)            # 不影响历史列表
    win.switch_page(0)

    # 呼出定位:不在输入 → 右上角;正在输入 → 避开输入位置
    import clipman.main_window as mw
    geo = (QApplication.screenAt(win.pos())
           or QApplication.primaryScreen()).availableGeometry()
    orig_anchor = mw.typing_anchor
    try:
        mw.typing_anchor = lambda: None
        win.hide()
        win.toggle_visible()
        corner_ok = (win.x() == geo.right() - win.width() - 12
                     and win.y() == geo.top() + 12)
        mw.typing_anchor = lambda: (200, 300)
        win.hide()
        win.toggle_visible()
        protected = QRect(200 - 12, 300 - 12, 24, 24)
        placed = win.geometry()
        beside_ok = (geo.contains(placed)
                     and not placed.intersects(protected))
    finally:
        mw.typing_anchor = orig_anchor
    check("呼出窗口定位", corner_ok and beside_ok)

    print(f"\n{'全部通过' if not failures else '存在失败'}:"
          f"{total[0] - len(failures)}/{total[0]}")
    return 1 if failures else 0
