@echo off
setlocal
chcp 65001 >nul
cd /d "%~dp0"

:: 默认开发入口使用独立的 Web 环境，历史 Qt 入口为 run_qt.py。
if not exist ".venv-web\Scripts\python.exe" (
    echo [错误] 未找到 Web 虚拟环境 .venv-web\
    echo 请先运行: python -m venv .venv-web
    echo 然后: .venv-web\Scripts\python.exe -m pip install -e .
    pause
    exit /b 1
)

if not exist "frontend\dist\index.html" (
    echo [错误] 未找到已构建的 Web 界面。
    echo 请先运行: npm.cmd --prefix frontend ci
    echo 然后: npm.cmd --prefix frontend run build
    pause
    exit /b 1
)

echo 正在启动 MoMA 模组助手...
".venv-web\Scripts\python.exe" "%~dp0run.py" %*
set "moma_exit_code=%errorlevel%"
pause
exit /b %moma_exit_code%
