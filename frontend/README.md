# Web 桌面开发入口

在仓库根目录使用 Windows PowerShell。需要 Python 3.14、Node 24 和 Microsoft Edge WebView2 Evergreen Runtime；Node 仅用于开发构建，发行包运行不需要 Node。

```powershell
py -3.14 -m venv .venv-web
.venv-web/Scripts/python.exe -m pip install -r requirements-web.lock
.venv-web/Scripts/python.exe -m pip install --no-deps -e .
npm.cmd --prefix frontend ci
npm.cmd --prefix frontend run typecheck
npm.cmd --prefix frontend test
npm.cmd --prefix frontend run build
.venv-web/Scripts/python.exe run.py
```

真实 Windows WebView2 自动化验收（先构建，执行时避免操作测试窗口）：

```powershell
npm.cmd --prefix frontend run test:e2e
```

此命令启动独立的真实宿主，通过测试专用 CDP 端口检查桥接与渲染，结束后关闭窗口；生产入口不启用 CDP。结果及截图位于 `frontend/test-results/`。浏览器开发服务器仅供样式调试，没有桌面桥接时显示中文错误，不提供演示数据回退。

便携目录包（在无 Qt 的 `.venv-web` 环境构建）：

```powershell
.venv-web/Scripts/python.exe -m PyInstaller --noconfirm moma-web.spec
Copy-Item PACKAGE-GUIDE.md dist/MoMA-Web/PACKAGE-GUIDE.md
npm.cmd --prefix frontend run test:package
dist/MoMA-Web/MoMA-Web.exe
```

分发必须包含整个 `dist/MoMA-Web/`，不能只复制 exe。目标机器需要 WebView2 Runtime，无需 Python/Node。构建前先完成前端 build；运行时设置写入用户配置目录，静态文件和离线元数据从包中读取。默认 `run.py` / `moma` 现已切换到 Web；历史 Qt 使用 `run_qt.py` / `moma-qt` 和可选依赖 `legacy-qt`。产品版本与候选日志标识分别记录；源码入口切换不代表清洁 Windows 或全部 DPI 验收通过。详见 [发行使用说明](../PACKAGE-GUIDE.md)。

发行 EXE 拒绝调试参数与远程调试环境变量。`test:package` 使用正常发行入口及 Windows 原生控件操作，临时用户配置与测试工程独立隔离；开发机净 PATH 结果不能替代无开发环境、断网的清洁 Windows 验收。源码宿主的测试 CDP 不进入发行路径。
