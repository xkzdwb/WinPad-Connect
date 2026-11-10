@echo off
rem PadLink Host 启动脚本：优先使用 pythonw 无控制台窗口运行。
cd /d "%~dp0"

where pythonw >nul 2>nul
if errorlevel 1 goto console

start "" pythonw -m padlink
exit /b 0

:console
where python >nul 2>nul
if errorlevel 1 (
  echo 未找到 Python。请先安装 Python 3.10+ 并勾选 "Add python.exe to PATH"。
  pause
  exit /b 1
)
python -m padlink
pause
