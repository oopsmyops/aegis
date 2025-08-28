@echo off
REM Local build script for AEGIS CLI binary on Windows
REM This script builds a standalone binary using PyInstaller

setlocal enabledelayedexpansion

REM Configuration
set PYTHON_VERSION=3.11
set BINARY_NAME=aegis
set VERSION=%1
if "%VERSION%"=="" set VERSION=0.1.0

echo [INFO] Building AEGIS CLI binary v%VERSION%
echo [INFO] Working directory: %CD%

REM Check if Python is available
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python is not installed or not in PATH
    exit /b 1
)

for /f "tokens=2" %%i in ('python --version 2^>^&1') do set PYTHON_VER=%%i
echo [INFO] Using Python version: %PYTHON_VER%

REM Check if virtual environment exists, create if not
if not exist "venv" (
    echo [INFO] Creating virtual environment...
    python -m venv venv
)

REM Activate virtual environment
echo [INFO] Activating virtual environment...
call venv\Scripts\activate.bat

REM Upgrade pip and install dependencies
echo [INFO] Installing dependencies...
python -m pip install --upgrade pip
pip install -r requirements.txt
pip install pyinstaller

REM Update version in setup.py
echo [INFO] Updating version to %VERSION%...
powershell -Command "(Get-Content setup.py) -replace 'version=\"[^\"]*\"', 'version=\"%VERSION%\"' | Set-Content setup.py"

REM Clean previous builds
echo [INFO] Cleaning previous builds...
if exist "build" rmdir /s /q build
if exist "dist" rmdir /s /q dist
if exist "*.spec" del /q *.spec

REM Detect architecture
set ARCH=x64
if "%PROCESSOR_ARCHITECTURE%"=="ARM64" set ARCH=arm64
if "%PROCESSOR_ARCHITEW6432%"=="ARM64" set ARCH=arm64

set BINARY_FULL_NAME=%BINARY_NAME%-windows-%ARCH%.exe
echo [INFO] Building binary: %BINARY_FULL_NAME%

REM Build with PyInstaller
echo [INFO] Running PyInstaller...
pyinstaller --clean ^
    --onefile ^
    --name "%BINARY_FULL_NAME%" ^
    --add-data "aegis-config.yaml;." ^
    --hidden-import=aegis.cli.main ^
    --hidden-import=aegis.discovery.discovery ^
    --hidden-import=aegis.questionnaire.questionnaire_runner ^
    --hidden-import=aegis.catalog.catalog_manager ^
    --hidden-import=aegis.ai.ai_policy_selector ^
    --hidden-import=boto3 ^
    --hidden-import=botocore ^
    --hidden-import=kubernetes ^
    --hidden-import=yaml ^
    --hidden-import=click ^
    --console ^
    aegis\cli\main.py

REM Check if build was successful
if not exist "dist\%BINARY_FULL_NAME%" (
    echo [ERROR] Binary build failed - file not found: dist\%BINARY_FULL_NAME%
    exit /b 1
)

REM Test the binary
echo [INFO] Testing binary...
dist\%BINARY_FULL_NAME% --help >nul 2>&1
if errorlevel 1 (
    echo [WARNING] Binary test failed, but binary was created
) else (
    echo [SUCCESS] Binary test passed
)

REM Generate checksums
echo [INFO] Generating checksums...
cd dist
certutil -hashfile "%BINARY_FULL_NAME%" SHA256 > "%BINARY_FULL_NAME%.sha256"
certutil -hashfile "%BINARY_FULL_NAME%" MD5 > "%BINARY_FULL_NAME%.md5"

REM Display results
echo [SUCCESS] Build completed successfully!
echo.
echo 📦 Binary Information:
for %%A in ("%BINARY_FULL_NAME%") do echo    • Name: %BINARY_FULL_NAME%
for %%A in ("%BINARY_FULL_NAME%") do echo    • Size: %%~zA bytes
echo    • Location: %CD%\%BINARY_FULL_NAME%
echo.
echo 🔐 Checksums generated:
echo    • SHA256: %BINARY_FULL_NAME%.sha256
echo    • MD5: %BINARY_FULL_NAME%.md5
echo.
echo 🧪 Test the binary:
echo    %BINARY_FULL_NAME% --help
echo    %BINARY_FULL_NAME% --version
echo.
echo 📋 Installation:
echo    Copy %BINARY_FULL_NAME% to a directory in your PATH

cd ..
echo [SUCCESS] Build process completed!

endlocal