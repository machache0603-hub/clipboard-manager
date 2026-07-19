# 剪贴板历史管理器(Linux / Windows / macOS)

基于 PyQt6 的剪贴板增强工具:常驻后台记录你复制过的**文本、图片、表情包、音频、文件**,
随时点一下就能把历史内容重新粘贴出来。
主力平台是 Linux(X11);Windows / macOS 通过 pynput 提供全局快捷键与
自动粘贴,功能对齐(平台差异见文末)。

## 功能

| 操作 | 效果 |
| --- | --- |
| 复制任何内容(Ctrl+C) | 自动进入对应历史分类(文本 / 图片·表情包 / 音频;普通文件兼容显示在文本页) |
| **单击** 条目 | 复制并自动粘贴到上一个活动窗口,Linux 下本窗口保持打开(依赖 `xdotool`) |
| **👁 眼睛按钮** | 点击卡片右下角的眼睛打开详情窗口，可查看完整内容、编辑文本或图片备注名；详情会持续显示，鼠标移开或切换分类不会关闭，点击详情右上角「×」关闭 |
| **回车** | 将选中条目放回系统剪贴板,到目标应用按 Ctrl+V 粘贴 |
| **拖拽条目到其他应用** | 直接完成粘贴(文本拖进编辑器、图片拖进聊天框/文件夹) |
| **列表内上下拖动** | 调整条目位置(排序会保存) |
| **右键** 条目 | 复制 / 添加到常用 / 修改字体颜色 / 恢复默认 / 移到顶部 / 删除 |
| **📋 历史 / ⭐ 常用** 页签 | 历史页自动记录复制内容;常用页存放固定条目,右键历史条目「⭐ 添加到常用」收藏,或在常用页点「➕ 添加」手动新建文本,单击/拖拽用法与历史页相同 |
| **📝 文本 / 🖼 图片 / 🎵 音频** 分类页签 | 三类内容分别使用独立列表、独立排序和独立清空;图片页随窗口宽度自动切换每行 2 / 3 / 5 列，名称显示在缩略图下方，可在眼睛详情窗口或右键菜单中修改备注名;复制或拖入音频文件时会自动识别到音频页 |
| 搜索框(Ctrl+F) | 按内容过滤历史 |
| Delete 键 | 删除选中条目 |
| 📌 最前(工具栏最右) | 窗口保持在最前,方便拖拽;条目置顶用右键菜单的"移到顶部" |
| ⚙ 设置 | 全局快捷键(默认 **Ctrl+Alt+V** 呼出/隐藏窗口)、历史上限、字体大小、界面语言(跟随系统/中文/English,切换即时生效)、单击自动粘贴开关、开机自启 |
| Ctrl+Alt+V(可改) | 在任何应用里一键呼出/隐藏本窗口;**正在输入时窗口优先停靠在输入行上方或下方,空间不足再放到左右侧,不覆盖输入光标;否则停靠屏幕右上角**(Windows 按真实文本光标定位;Linux/macOS 以鼠标位置近似) |
| Win 组合键(如 Win+V) | 从设置里的「常用 ▾」菜单选择;自动注册为 GNOME 系统快捷键,若与系统冲突(Win+V 默认是通知中心)会提示一键解除 |
| 关闭窗口 | 缩到系统托盘继续记录(托盘图标或**再次运行 run.sh** 都能唤回窗口) |
| 重复启动 | 不会开第二个实例,只会唤出已有窗口 |

- 白色背景;文本默认**黑体黑字**,每条可单独改颜色。
- 历史自动保存在 `~/.local/share/clipboard-manager/`(常用内容存
  `favorites.json`),重启不丢失;即使复制来源的程序已经关闭,
  历史内容仍可粘贴。常用条目与历史条目相互独立,删除历史不影响常用。
- 从外部把文字/图片/音频/文件**拖进**窗口,内容会按真实类型进入当前历史或常用下的对应分类页。
- 常用页不受"每类历史条数上限"限制,不会被自动清理。
- 历史条数上限分别应用于文本、图片、音频三个独立分类。

## 运行

```bash
./run.sh        # Linux / macOS:首次运行自动创建虚拟环境并安装依赖
run.bat         # Windows:双击或在 cmd 里运行
```

启动后**默认最小化到系统托盘**,不弹出主窗口(开机自启同样如此),
按快捷键(默认 Ctrl+Alt+V)、点击托盘图标或再次运行 `run.sh` 即可打开窗口;
`./run.sh --show` 可在启动时直接显示窗口。

自测(无界面环境也可):

```bash
QT_QPA_PLATFORM=offscreen .venv/bin/python clipboard_manager.py --selftest
```

## 打包安装程序(三平台)

| 平台 | 产物 | 本机构建命令(需在对应系统上运行) |
| --- | --- | --- |
| Linux | `dist/clipboard-manager_<版本>_all.deb` | `./packaging/build_deb.sh 1.1.0` |
| Windows | `dist\clipboard-manager.exe`(单文件,PyInstaller) | `packaging\build_exe.bat` |
| macOS | `dist/ClipboardHistory_<版本>.dmg`(内含 .app) | `./packaging/build_mac.sh 1.1.0` |

```bash
sudo apt install ./dist/clipboard-manager_1.1.0_all.deb  # Linux 安装,自动装依赖
```

- Linux 安装后可在应用菜单找到「剪贴板历史」,或直接运行
  `clipboard-manager`;卸载 `sudo apt remove clipboard-manager`。
- Windows:双击 exe 即可运行(免安装);macOS:打开 dmg 把 App 拖进
  「应用程序」。两者均为未签名程序,首次运行需在系统安全提示里选择
  "仍要运行 / 仍要打开"。
- **PyInstaller 不能跨平台交叉打包**:exe 只能在 Windows 上构建、
  dmg 只能在 macOS 上构建。没有对应机器时,把仓库推到 GitHub 后在
  Actions 页面手动运行 **package** workflow(`.github/workflows/package.yml`),
  云端真机会同时产出 deb / exe / dmg,在运行记录的 Artifacts 里下载。
  推 `v*` 标签会自动构建三平台安装包、生成 SHA256 校验文件,
  并将它们发布到对应的 GitHub Release。

## 代码结构

```
clipboard_manager.py     启动入口(薄壳,run.sh / toggle.sh 调用它)
clipman/
  constants.py           路径、默认配置、界面常量与黑体字体
  hotkey.py              快捷键格式转换(Qt/X11/GNOME)与 XGrabKey 全局快捷键
  gnome.py               GNOME 系统快捷键查询、冲突检测与自定义绑定
  clip_item.py           单条剪贴历史的数据模型与序列化
  settings_dialog.py     设置对话框
  preview_popup.py       眼睛按钮打开的详情预览/编辑弹窗
  cards.py               卡片控件与带动画的卡片列表容器
  main_window.py         主窗口(剪贴板监听、条目管理、持久化)
  selftest.py            无显示环境也能跑的自测
  app.py                 程序入口(单实例、toggle.sh 生成)
```

## 开机自启 / 添加到应用菜单

```bash
# 应用菜单
cp clipboard-manager.desktop ~/.local/share/applications/
# 开机自启
cp clipboard-manager.desktop ~/.config/autostart/
```

## 依赖与说明

- Python ≥ 3.9,PyQt6 与 python-xlib(`run.sh` 自动安装);中文黑体使用系统的
  SimHei / Noto Sans CJK SC。
- 全局快捷键:普通组合键(Ctrl/Alt/Shift)用 X11 XGrabKey 直接抓取;
  **Win(Super)组合键**被 GNOME 底层接管、无法直接抓取,程序会自动把它
  注册为 GNOME 自定义快捷键(系统设置 → 键盘 → 自定义快捷键里可见,
  名称"剪贴板历史"),通过 `toggle.sh` 通知程序切换显隐;程序未运行时
  按快捷键会直接启动程序。单独的 Win 键被系统"活动概览"占用,不支持。
- 配置保存在 `~/.local/share/clipboard-manager/config.json`;
  "开机自启"开关会自动写入/移除 `~/.config/autostart/clipboard-manager.desktop`。
- **界面语言**:默认跟随系统(中文系统显示中文,其余显示英文),
  可在 设置 → 语言 里固定为中文或 English,三平台通用,切换立即生效
  (翻译表在 `clipman/i18n.py`,中文原文即 key,漏翻会回退显示中文)。
- `xdotool`(可选):Linux 下单击"复制并粘贴"需要它 —— `sudo apt install xdotool`。
- 本程序针对 **X11** 会话(Ubuntu 默认的 Xorg)。在 Wayland 会话下,
  后台监听剪贴板受系统限制,建议登录界面选择 "Ubuntu on Xorg"。
- 在终端里粘贴请用 Ctrl+Shift+V(终端惯例)。

## 跨平台差异(Windows / macOS)

| 功能 | Linux | Windows | macOS |
| --- | --- | --- | --- |
| 界面 / 托盘 / 历史 / 单实例 | ✅ | ✅ | ✅ |
| 全局快捷键 | X11 XGrabKey / GNOME 绑定 | pynput | pynput(需授权,见下) |
| 单击自动粘贴 | xdotool 切窗口,窗口保持打开 | 隐藏窗口后模拟 Ctrl+V | 隐藏窗口后模拟 Cmd+V |
| 开机自启 | `~/.config/autostart` | 注册表 HKCU Run 键 | `~/Library/LaunchAgents` |
| 数据目录 | `~/.local/share/clipboard-manager` | `%APPDATA%\clipboard-manager` | `~/Library/Application Support/clipboard-manager` |

- Windows / macOS 依赖 **pynput**(run.bat / run.sh 自动安装);
  Win+V 在 Windows 上被系统剪贴板历史占用,请用 Ctrl+Alt+V 等组合。
- macOS 首次使用需授权:系统设置 → 隐私与安全性 → **辅助功能**
  (全局快捷键与自动粘贴都要);监视剪贴板无需额外权限。
- GNOME 快捷键注册、toggle.sh、deb 打包仅 Linux 有效,其余平台自动跳过。
- CI:`.github/workflows/selftest.yml` 会在 Ubuntu / Windows / macOS
  三平台自动跑 `--selftest`,推到 GitHub 即生效。
