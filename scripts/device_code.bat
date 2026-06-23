@echo off
chcp 65001 >nul
cd /d "%~dp0.."
echo ============================================================
echo   QuantSage 设备码查看工具
echo ============================================================
echo.
python -c "from src.deployment.license import get_device_fingerprint; print(f'本机设备码: {get_device_fingerprint()}')"
echo.
echo 将此码发送给开发者以获取绑定此设备的许可证密钥。
echo.
pause
