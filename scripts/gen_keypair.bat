@echo off
chcp 65001 >nul
cd /d "%~dp0.."

echo ============================================================
echo   QuantSage Ed25519 密钥对生成器
echo   一次性运行 — 生成私钥 + 公钥
echo ============================================================
echo.

REM Try conda env first, fallback to system python
where python >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] 未找到 Python。请先安装 Python 3.11+。
    pause >nul
    exit /b 1
)

python scripts/gen_keypair.py
if %errorlevel% neq 0 (
    echo.
    echo [ERROR] 生成失败。请确认已安装 cryptography 库：
    echo   pip install cryptography
)

echo.
echo 按任意键关闭...
pause >nul
