@rem SPDX-License-Identifier: Apache-2.0 WITH LLVM-exception
@echo off

rem Runs x.py with the Python launcher, or else the python on PATH; x.py checks the version.
setlocal
where py >nul 2>nul
if %errorlevel% equ 0 (
    py -3 "%~dp0x.py" %*
) else (
    python "%~dp0x.py" %*
)
exit /b %errorlevel%
