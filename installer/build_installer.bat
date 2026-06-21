@echo off
REM QuantSage Installer Build Script
REM ================================
REM Prerequisites:
REM   1. Inno Setup 6.3+ installed (iscc.exe on PATH)
REM   2. PyInstaller-built dist\QuantSage\ directory exists
REM   3. Python 3.11+ with required packages installed
REM
REM Output: dist\installer\QuantSage_Setup_v1.0.0.exe

setlocal enabledelayedexpansion

echo ========================================
echo   QuantSage Installer Builder
echo ========================================
echo.

REM Check for Inno Setup
where iscc >nul 2>&1
if %errorlevel% neq 0 (
    echo ERROR: Inno Setup Compiler (iscc.exe) not found on PATH.
    echo Install Inno Setup from: https://jrsoftware.org/isinfo.php
    echo Or run with explicit path.
    exit /b 1
)

REM Check for PyInstaller output
set "DIST_DIR=..\dist\QuantSage"
if not exist "%DIST_DIR%" (
    echo ERROR: dist\QuantSage\ directory not found.
    echo Run PyInstaller first:
    echo   pyinstaller pyinstaller_quantsage.spec --clean --noconfirm
    exit /b 1
)

REM Step 1: Build main application (if not already built)
echo.
echo [1/3] Checking PyInstaller build...
if not exist "%DIST_DIR%\QuantSage*.exe" (
    echo Building QuantSage.exe with PyInstaller...
    cd ..
    pyinstaller pyinstaller_quantsage.spec --clean --noconfirm
    if %errorlevel% neq 0 (
        echo ERROR: PyInstaller build failed.
        cd installer
        exit /b 1
    )
    cd installer
) else (
    echo QuantSage.exe already built. Skipping PyInstaller.
)

REM Step 2: Prepare license files
echo.
echo [2/3] Preparing license files...

set "LICENSE_DIR=assets\licenses"
if not exist "%LICENSE_DIR%" mkdir "%LICENSE_DIR%"

REM Copy QuantSage license (MIT)
echo MIT License > "%LICENSE_DIR%\LICENSE.txt"
echo. >> "%LICENSE_DIR%\LICENSE.txt"
echo Copyright (c) 2025 QuantSage >> "%LICENSE_DIR%\LICENSE.txt"
echo. >> "%LICENSE_DIR%\LICENSE.txt"
echo Permission is hereby granted, free of charge, to any person obtaining a copy >> "%LICENSE_DIR%\LICENSE.txt"
echo of this software and associated documentation files (the "Software"), to deal >> "%LICENSE_DIR%\LICENSE.txt"
echo in the Software without restriction... >> "%LICENSE_DIR%\LICENSE.txt"

REM Copy third-party licenses
if exist "..\THIRD_PARTY_LICENSES.md" (
    copy /Y "..\THIRD_PARTY_LICENSES.md" "%LICENSE_DIR%\THIRD_PARTY_LICENSES.txt" >nul
) else (
    echo Third-party licenses not found. Creating placeholder...
    echo See https://github.com/ailiwood/finance-ai/blob/main/THIRD_PARTY_LICENSES.md > "%LICENSE_DIR%\THIRD_PARTY_LICENSES.txt"
)

REM Step 3: Build installer
echo.
echo [3/3] Building installer with Inno Setup...
iscc quantsage.iss
if %errorlevel% neq 0 (
    echo ERROR: Installer build failed.
    exit /b 1
)

echo.
echo ========================================
echo   Build Complete!
echo   Installer: dist\installer\QuantSage_Setup_v1.0.0.exe
echo ========================================

REM Optional: compute SHA-256
where certutil >nul 2>&1
if %errorlevel% equ 0 (
    echo.
    echo SHA-256 checksum:
    certutil -hashfile "..\dist\installer\QuantSage_Setup_v1.0.0.exe" SHA256
)

endlocal
