"""MoMA 启动入口（PyInstaller 打包专用，F-53）。

开发模式用 `python -m app.main`（包方式，相对导入正常）；
打包模式必须用顶层脚本，否则 app/main.py 被当独立脚本执行，
内部 `from .ui.main_window import ...` 相对导入会失败
（attempted relative import with no known parent package）。
本文件作为打包入口，保证 `app` 以包形式导入。
"""

from app.main import main

if __name__ == "__main__":
    main()
