# Web 桌面开发入口

在仓库根目录使用 Windows PowerShell。需要 Python 3.14、Node 24 和 Microsoft Edge WebView2 Evergreen Runtime；Node 仅用于开发构建，发行包运行不需要 Node。

```powershell
py -3.14 -m venv .venv-web
.venv-web/Scripts/python.exe -m pip install -r requirements-web.lock
npm.cmd --prefix frontend ci
npm.cmd --prefix frontend run typecheck
npm.cmd --prefix frontend test
npm.cmd --prefix frontend run build
.venv-web/Scripts/python.exe run_web.py
```

真实 Windows WebView2 自动化验收（先构建，执行时避免操作测试窗口）：

```powershell
npm.cmd --prefix frontend run test:e2e
```

此命令启动独立的真实宿主，通过测试专用 CDP 端口检查桥接与渲染，结束后关闭窗口；生产入口不启用 CDP。结果及截图位于 `frontend/test-results/`。浏览器开发服务器仅供样式调试，没有桌面桥接时显示中文错误，不提供演示数据回退。

开发壳目录包：

```powershell
.venv-web/Scripts/python.exe -m PyInstaller --noconfirm moma-web.spec
npm.cmd --prefix frontend run test:package
dist/MoMA-Web/MoMA-Web.exe
```

分发必须包含整个 `dist/MoMA-Web/`，不能只复制 exe。目标机器需要 WebView2 Runtime，无需 Python/Node。构建前先完成前端 build；运行时设置写入用户配置目录，静态文件和离线元数据从包中读取。此开发入口逐票迁移中，默认 `run.py` 仍为原 Qt 版本；它不代表完整上半版本已交付。
