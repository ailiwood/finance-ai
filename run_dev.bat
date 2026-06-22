@echo off
REM QuantSage dev launcher — starts Streamlit on port 8501
REM Close any previous instance first, then run this.

title QuantSage Dev Server

echo ========================================
echo   QuantSage — Dev Mode Launcher
echo ========================================
echo.

REM Kill any existing Streamlit on port 8501
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":8501.*LISTENING"') do (
    echo [INFO] Killing process on port 8501 (PID %%a)
    taskkill /F /PID %%a >nul 2>&1
)
timeout /t 2 /nobreak >nul

REM Activate conda environment
call E:\Anaconda3\Scripts\activate.bat quantsage_py311
if %errorlevel% neq 0 (
    echo [ERROR] Failed to activate conda env quantsage_py311
    pause
    exit /b 1
)

REM Set encoding
set PYTHONIOENCODING=utf-8

REM Change to project directory
cd /d E:\AI_projects\fin

REM Start Streamlit
echo [INFO] Starting Streamlit on http://localhost:8501
echo [INFO] Open your browser and go to: http://localhost:8501
echo [INFO] Press Ctrl+C in this window to stop.
echo.

streamlit run src/ui/app.py --server.port 8501

pause
