@echo off
rem SPDX-License-Identifier: Apache-2.0
where py >nul 2>nul
if %errorlevel% equ 0 (
  py -3 "%~dp0launch.py" %*
) else (
  python "%~dp0launch.py" %*
)
if errorlevel 1 (
  echo Python 3.10+ is required. Open START-HERE.html for the offline demo.
  echo Python 3.10+ est requis. Ouvrez START-HERE.html pour la demonstration hors ligne.
  pause
)
