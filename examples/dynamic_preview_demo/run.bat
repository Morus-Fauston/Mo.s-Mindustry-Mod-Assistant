@echo off
setlocal
set "ROOT=%~dp0..\.."
set "PYTHON=%ROOT%\.venv\Scripts\python.exe"

if not exist "%PYTHON%" (
    echo 未找到项目虚拟环境：%PYTHON%
    echo 请先在仓库根目录执行：python -m venv .venv
    pause
    exit /b 1
)

"%PYTHON%" "%~dp0run_demo.py"
if errorlevel 1 pause
endlocal
