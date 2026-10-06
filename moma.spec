# -*- mode: python ; coding: utf-8 -*-
# MoMA 历史 Qt PyInstaller 打包配置（F-53 / 规格 18.11）
# 新默认 WebView2 发行使用 moma-web.spec；本配方需安装 legacy-qt extra。
#
# 用法：
#   pyinstaller moma.spec --noconfirm
# 产物：dist/MoMA.exe（单文件，目标 <150MB）
#
# 入口：run_qt.py（历史 Qt 顶层脚本）——app/main.py 用相对导入，
# 直接作脚本入口会在打包后报 "attempted relative import with no known parent"。
#
# 路径约定（见 app/core/paths.py）：
#   - 只读数据（metadata/、app/config、app/resources）打进 _MEIPASS
#   - 可写用户配置（settings.json/editor_state.json）写 %APPDATA%/MoMA/

from PyInstaller.utils.hooks import collect_data_files

block_cipher = None

a = Analysis(
    ['run_qt.py'],
    pathex=[],
    binaries=[],
    datas=[
        # 只读配置与元数据
        ('app/config', 'app/config'),
        ('metadata', 'metadata'),
        # 应用资源（QSS / 图标）
        ('app/resources', 'app/resources'),
    ],
    hiddenimports=[
        'PySide6.QtSvg',
        'PIL._tkinter_finder',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='MoMA',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,  # GUI 应用，无控制台窗口
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
