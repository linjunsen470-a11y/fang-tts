@echo off
setlocal DisableDelayedExpansion
chcp 65001 >nul
set "PYTHONUTF8=1"
set "TASK_PYTHON=%~dp0.venv\Scripts\python.exe"
if exist "%TASK_PYTHON%" goto run
set "TASK_PYTHON=python"
:run
"%TASK_PYTHON%" "%~dp0compress_videos.py" %*
set "TASK_EXIT=%ERRORLEVEL%"
if not defined FISH_TTS_NO_PAUSE pause
exit /b %TASK_EXIT%
