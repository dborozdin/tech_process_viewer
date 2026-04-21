@echo off
REM Launcher for MCP server — finds Python with mcp package installed.
REM Checks venv first, then system Python.

set "VENV_PY=%~dp0..\..\..\.venv\Scripts\python.exe"
if exist "%VENV_PY%" (
    "%VENV_PY%" -c "import mcp" >nul 2>&1
    if not errorlevel 1 (
        "%VENV_PY%" "%~dp0server.py" %*
        exit /b
    )
)

REM Fallback to system Python
python "%~dp0server.py" %*
