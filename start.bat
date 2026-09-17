@echo off
chcp 65001 >nul
rem ============================================================
rem  new_auto - PixelIDE hardware automation canvas
rem  Starts the local web UI at http://127.0.0.1:8765
rem
rem  NOTE: pyserial / numpy / cv2 are installed in Python 3.12,
rem  NOT in the default `python` on PATH (3.13). This script picks
rem  the interpreter that actually has the deps.
rem ============================================================
setlocal
cd /d "%~dp0"

set "PY=C:\Users\wangguangtao\AppData\Local\Programs\Python\Python312\python.exe"
if not exist "%PY%" (
    for /f "delims=" %%P in ('where py 2^>nul') do (
        py -3.12 -c "import serial" >nul 2>&1 && set "PY=py -3.12"
    )
)
if not exist "%PY%" (
    python -c "import serial" >nul 2>&1 && set "PY=python"
)
if "%PY%"=="" (
    echo [ERROR] No Python with pyserial found. Install: pip install pyserial numpy opencv-python
    pause
    exit /b 1
)

echo Using interpreter: %PY%
echo Starting server on http://127.0.0.1:8765  ^(Ctrl+C to stop^)
start "" http://127.0.0.1:8765
%PY% app/server.py --port 8765
endlocal
