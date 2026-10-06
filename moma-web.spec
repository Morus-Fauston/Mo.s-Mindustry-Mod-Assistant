# Build after npm.cmd --prefix frontend run build.
from pathlib import Path
from PyInstaller.utils.hooks import copy_metadata

root = Path(SPECPATH)
config = root / "app" / "config"
data = [(str(p), "app/config") for p in config.glob("*.json")
        if p.name not in {"settings.json", "editor_state.json"}]
data += [(str(root / "metadata"), "metadata"),
         (str(root / "frontend" / "dist"), "frontend/dist")]
data += copy_metadata("moma")

a = Analysis(
    [str(root / "run_web.py")], pathex=[str(root)], datas=data,
    hiddenimports=["webview.platforms.winforms", "webview.platforms.edgechromium"],
    excludes=["PySide6", "PyQt5", "PyQt6", "qtpy", "tkinter"],
)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name="MoMA-Web",
          console=False, debug=False, strip=False, upx=False)
coll = COLLECT(exe, a.binaries, a.datas, name="MoMA-Web", strip=False, upx=False)
