@echo off
rem SPDX-License-Identifier: Apache-2.0
setlocal
cd /d "%~dp0"
py -3 -c "import sys; sys.exit(sys.version_info < (3, 11))" 2>nul
if not errorlevel 1 (
  py -3 bridge/server.py --pages-missions --pairing-guide %*
  exit /b
)
python -c "import sys; sys.exit(sys.version_info < (3, 11))" 2>nul
if not errorlevel 1 (
  python bridge/server.py --pages-missions --pairing-guide %*
  exit /b
)
echo FRONTIER requires Python 3.11 or newer. Install it from https://www.python.org/downloads/
echo FRONTIER requiert Python 3.11 ou plus recent.
pause
exit /b 1
