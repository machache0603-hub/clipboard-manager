"""中英文界面翻译。

中文原文直接作为 key,tr() 在英文模式下查表返回译文,查不到原样返回,
因此漏翻的字符串只会显示中文而不会崩溃。
语言设置存在 config["language"]:auto(跟随系统)/ zh / en。
"""

from PyQt6.QtCore import QLocale

LANG = "zh"          # 当前生效语言,init() 会覆盖

EN = {
    # ---- app.py ----
    "已有实例在运行,已唤出其窗口":
        "Already running; brought its window to front",
    "剪贴板历史已在后台运行":
        "Clipboard History is running in the background",
    "按 {} 或点击托盘图标打开窗口":
        "Press {} or click the tray icon to open the window",
    "快捷键": "the hotkey",
    # ---- 主窗口 ----
    "剪贴板历史": "Clipboard History",
    "搜索历史…": "Search history…",
    "📌 最前": "📌 On Top",
    "窗口保持在最前面,方便拖拽":
        "Keep the window above others for easy dragging",
    "🗑 清空": "🗑 Clear",
    "⚙ 设置": "⚙ Settings",
    "单击=复制并粘贴 · 悬浮=预览/编辑完整内容 · "
    "拖到目标窗口=粘贴 · 列表内拖动=排序 · 右键=改字体颜色/删除":
        "Click = copy & paste · Hover = preview/edit · "
        "Drag out = paste · "
        "Drag in list = reorder · Right-click = color/delete",
    "显示/隐藏窗口": "Show/Hide Window",
    "退出": "Quit",
    "快捷键未生效": "Hotkey not active",
    "python-xlib(且需 X11 会话)": "python-xlib (X11 session required)",
    "无法解析快捷键 {},或缺少依赖 {}。请换一个组合键。":
        "Cannot parse hotkey {} or missing dependency {}. "
        "Please choose another combination.",
    "快捷键被占用": "Hotkey occupied",
    "{} 已被其他程序注册,请换一个组合键。":
        "{} is already registered by another program. "
        "Please choose another combination.",
    "快捷键被系统占用": "Hotkey taken by the system",
    "{} 目前被 GNOME 系统快捷键占用:\n{}\n\n"
    "是否解除系统占用,把这个组合键让给剪贴板?\n"
    "(该绑定的其他组合键会保留,可在系统设置里随时改回)":
        "{} is currently taken by GNOME system shortcuts:\n{}\n\n"
        "Release it and give it to Clipboard History?\n"
        "(Other combinations of those bindings are kept and can be "
        "restored in system settings.)",
    "仍在后台记录": "Still recording in background",
    "点击托盘图标或再次启动程序可恢复窗口":
        "Click the tray icon or launch the program again "
        "to restore the window",
    "已复制": "Copied",
    "提示": "Note",
    "已复制到剪贴板。安装 xdotool 后,单击可自动粘贴:\n"
    "sudo apt install xdotool":
        "Copied to clipboard. Install xdotool to enable auto-paste "
        "on click:\nsudo apt install xdotool",
    "请到目标窗口按 {} 粘贴":
        "Switch to the target window and press {} to paste",
    "未安装 pynput,无法自动粘贴,请按 {} 粘贴":
        "pynput is not installed, cannot auto-paste. Press {} to paste",
    "📋 复制": "📋 Copy",
    "📤 复制并粘贴": "📤 Copy & Paste",
    "🎨 修改字体颜色": "🎨 Change Font Color",
    "↩ 恢复默认颜色": "↩ Reset Color",
    "⬆ 移到顶部": "⬆ Move to Top",
    "❌ 删除": "❌ Delete",
    "🗑 清空全部": "🗑 Clear All",
    "选择该条目的字体颜色": "Choose font color for this item",
    "清空历史": "Clear history",
    "确定清空全部剪贴板历史吗?": "Clear all clipboard history?",
    # ---- 常用内容页 ----
    "📋 历史": "📋 History",
    "⭐ 常用": "⭐ Favorites",
    "➕ 添加": "➕ Add",
    "手动添加一条常用内容": "Add a favorite entry manually",
    "添加常用内容": "Add Favorite",
    "输入要保存的常用内容…": "Enter the content to save…",
    "⭐ 添加到常用": "⭐ Add to Favorites",
    "已添加到常用": "Added to favorites",
    "该内容已在常用列表中": "Already in favorites",
    "清空常用": "Clear favorites",
    "确定清空全部常用内容吗?": "Clear all favorite items?",
    # ---- 悬浮预览 ----
    "💾 保存修改": "💾 Save Changes",
    "表情包/图片": "Image / Sticker",
    "可直接编辑": "Editable",
    "文件列表(只读)": "File list (read-only)",
    "✓ 已复制": "✓ Copied",
    "✓ 已保存": "✓ Saved",
    # ---- 条目 / 卡片 ----
    "🖼  图片 / 表情包": "🖼  Image / Sticker",
    "📁  {} 个文件:{}": "📁  {} file(s): {}",
    "🖼  图片 {}×{}": "🖼  Image {}×{}",
    # ---- 设置对话框 ----
    "设置": "Settings",
    "常用 ▾": "Presets ▾",
    "呼出/隐藏窗口快捷键:": "Show/hide window hotkey:",
    "历史条数上限:": "Max history items:",
    "列表字体大小:": "List font size:",
    "语言:": "Language:",
    "跟随系统": "Follow system",
    "单击条目时自动粘贴到上一个窗口":
        "Auto-paste to the previous window on click",
    "登录系统后自动启动": "Start automatically after login",
    "提示:快捷键在输入框内直接按组合键即可,"
    "Cmd 组合键请从「常用」菜单选择;留空表示不使用全局快捷键。"
    "首次使用需在 系统设置→隐私与安全性→辅助功能 里为本程序授权。":
        "Tip: press the key combination directly in the input box; "
        "pick Cmd combinations from the Presets menu. Leave empty to "
        "disable the global hotkey. On first use, grant permission in "
        "System Settings → Privacy & Security → Accessibility.",
    "提示:快捷键在输入框内直接按组合键即可,"
    "Win 组合键请从「常用」菜单选择(多数已被系统占用,不推荐);"
    "留空表示不使用全局快捷键。":
        "Tip: press the key combination directly in the input box; "
        "pick Win combinations from the Presets menu (most are taken "
        "by the system, not recommended). Leave empty to disable "
        "the global hotkey.",
    "提示:快捷键在输入框内直接按组合键即可,"
    "Win 组合键请从「常用」菜单选择(若被系统占用会提示一键解除);"
    "留空表示不使用全局快捷键。单独的 Win 键被系统的活动概览占用,不支持。":
        "Tip: press the key combination directly in the input box; "
        "pick Win combinations from the Presets menu (if taken by the "
        "system you'll be offered a one-click release). Leave empty to "
        "disable the global hotkey. The bare Win key is reserved by "
        "the Activities overview and not supported.",
}


def resolve(setting: str) -> str:
    """把配置值(auto/zh/en)解析成实际语言。"""
    if setting in ("zh", "en"):
        return setting
    name = QLocale.system().name()          # 如 zh_CN / en_US
    return "zh" if name.startswith("zh") else "en"


def init(setting: str):
    global LANG
    LANG = resolve(setting)


def tr(text: str) -> str:
    if LANG == "zh":
        return text
    return EN.get(text, text)
