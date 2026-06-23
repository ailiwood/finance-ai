@echo off
chcp 65001 >nul
cd /d "%~dp0.."

REM Launch the keygen GUI (requires tkinter, included with Python on Windows)
where python >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] 未找到 Python。请先安装 Python 3.11+。
    pause >nul
    exit /b 1
)

start "QuantSage Keygen" python scripts/keygen_gui.py
