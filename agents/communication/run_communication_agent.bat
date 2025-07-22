@echo off
REM Run communication_agent.py in the background using the venv Python and log output to output.log
REM Set PYTHONIOENCODING to handle Unicode characters properly
set PYTHONIOENCODING=utf-8
start "" /b ..\..\\.venv\Scripts\python.exe communication_agent.py > output.log 2>&1
