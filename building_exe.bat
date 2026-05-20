@echo off
setlocal EnableExtensions EnableDelayedExpansion
title CUT Embedded Wall - Build ONEFILE EXE

cd /d "%~dp0"

taskkill /f /im CUT_Embedded_Wall.exe >nul 2>&1

if exist build rmdir /s /q build
if exist dist rmdir /s /q dist
if exist CUT_Embedded_Wall.spec del /q CUT_Embedded_Wall.spec

set "MANUAL_ADD_DATA="
if exist CUT_Embedded_Wall_Description.pdf set "MANUAL_ADD_DATA=--add-data CUT_Embedded_Wall_Description.pdf;."

set "ASSETS_ADD_DATA="
if exist assets (
    set "ASSETS_ADD_DATA=!ASSETS_ADD_DATA! --add-data assets;assets"
)

py -3.11 --version
py -3.11 -m pip install --upgrade pip
py -3.11 -m pip install --upgrade pyinstaller numpy scipy matplotlib

py -3.11 -m PyInstaller ^
--noconfirm ^
--clean ^
--windowed ^
--onefile ^
--name "CUT_Embedded_Wall" ^
--icon "home.ico" ^
!ASSETS_ADD_DATA! ^
--add-data "home.png;." ^
%MANUAL_ADD_DATA% ^
--add-data "CUT_Embedded_Wall_SOLVER_DISPATCHER_v6.py;." ^
--add-data "cut_embedded_wall_solvers;cut_embedded_wall_solvers" ^
--hidden-import=numpy ^
--hidden-import=scipy ^
--hidden-import=scipy.integrate ^
--hidden-import=scipy.interpolate ^
--hidden-import=scipy.optimize ^
--hidden-import=matplotlib ^
--hidden-import=matplotlib.backends.backend_tkagg ^
--hidden-import=tkinter ^
--collect-submodules=cut_embedded_wall_solvers ^
CUT_Embedded_Wall_GUI_v6.py

if errorlevel 1 (
    echo BUILD FAILED
    pause
    exit /b 1
)

echo.
echo EXE created:
echo %cd%\dist\CUT_Embedded_Wall.exe
pause
