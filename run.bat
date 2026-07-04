@echo off
rem 启动剪贴板历史管理器(Windows)
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
    echo 首次运行:创建虚拟环境并安装依赖 ...
    py -3 -m venv .venv || python -m venv .venv
    ".venv\Scripts\python.exe" -m pip install PyQt6 pynput
)
start "" ".venv\Scripts\pythonw.exe" clipboard_manager.py %*
