@echo off
setlocal
cd /d "%~dp0"
if "%STORYBOARD_BRIDGE_PORT%"=="" set STORYBOARD_BRIDGE_PORT=8788
if "%STORYBOARD_BRIDGE_HOST%"=="" set STORYBOARD_BRIDGE_HOST=127.0.0.1
python scripts\bridge_server.py --host %STORYBOARD_BRIDGE_HOST% --port %STORYBOARD_BRIDGE_PORT% --jobs-root bridge-jobs
