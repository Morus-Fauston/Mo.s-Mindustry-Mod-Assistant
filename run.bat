@echo off
chcp 65001 >nul
cd /d "%~dp0"

:: Check if venv exists
if not exist ".venv\Scripts\python.exe" (
    echo [错误] 未找到虚拟环境 .venv\
    echo 请先运行: python -m venv .venv
    echo 然后: .venv\Scripts\pip install -e .
    pause
    exit /b 1
)

:: Launch MoMA
echo 正在启动 Mo's Mindustry Mod Assistant...
.venv\Scripts\python.exe -m app.main
pause
