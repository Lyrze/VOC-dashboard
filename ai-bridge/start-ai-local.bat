@echo off
chcp 65001 >nul
title VOC Dashboard - AI bridge (Claude Code CLI)
cd /d "%~dp0"

where python >/dev/null 2>&1
if errorlevel 1 (
  echo [!] Python not found. Install Python 3.10+ and check "Add python.exe to PATH".
  pause
  exit /b 1
)

where claude >/dev/null 2>&1
if errorlevel 1 (
  echo [!] Claude Code CLI not found.
  echo     npm install -g @anthropic-ai/claude-code
  echo.
)

python server.py
pause
