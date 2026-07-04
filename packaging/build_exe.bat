@echo off
rem 在 Windows 上打包单文件 exe:packaging\build_exe.bat
rem 产物:dist\clipboard-manager.exe
cd /d "%~dp0\.."
python -m pip install --upgrade PyQt6 pynput pyinstaller
python -m PyInstaller --noconfirm --clean --onefile --windowed ^
    --name clipboard-manager clipboard_manager.py
echo.
echo 打包完成:dist\clipboard-manager.exe
