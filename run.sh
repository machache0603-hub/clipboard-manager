#!/usr/bin/env bash
# 启动剪贴板历史管理器
cd "$(dirname "$(readlink -f "$0")")"
if [ ! -x .venv/bin/python ]; then
    echo "首次运行:创建虚拟环境并安装依赖 …"
    python3 -m venv .venv
    if [ "$(uname)" = "Darwin" ]; then
        .venv/bin/pip install PyQt6 pynput      # macOS:全局快捷键/粘贴模拟
    else
        .venv/bin/pip install PyQt6 python-xlib # Linux:X11 快捷键
    fi
fi
exec .venv/bin/python clipboard_manager.py "$@"
