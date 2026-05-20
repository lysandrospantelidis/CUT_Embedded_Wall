@echo off
title CUT Embedded Wall v7.4

cd /d "%~dp0"

REM Activate local venv if it exists
if exist ".venv\Scripts\activate.bat" (
    call ".venv\Scripts\activate.bat"
)

REM Alternative common virtual environment names
if exist "venv\Scripts\activate.bat" (
    call "venv\Scripts\activate.bat"
)

REM Run desktop application
python CUT_Embedded_Wall_GUI_v6.py

pause