"""Public source-launch and dependency contracts for the Web default."""

from pathlib import Path
import os
import subprocess
import sys
import tomllib

import pytest
from packaging.markers import default_environment
from packaging.requirements import Requirement


ROOT = Path(__file__).resolve().parents[1]


def test_default_entrypoint_help_runs_without_qt():
    # Model a machine without the optional Qt dependency, even in the legacy
    # test environment. Exercise the actual script and argparse, without GUI.
    program = """
import importlib.abc
import runpy
import sys

class NoQt(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname.split('.')[0] in {'PySide6', 'PyQt5', 'PyQt6', 'qtpy'}:
            raise ModuleNotFoundError('Qt is not a default runtime dependency')

sys.meta_path.insert(0, NoQt())
sys.argv = ['run.py', '--help']
runpy.run_path('run.py', run_name='__main__')
"""
    result = subprocess.run(
        [sys.executable, "-X", "utf8", "-c", program], cwd=ROOT,
        capture_output=True, text=True, encoding="utf-8", timeout=15,
    )
    assert result.returncode == 0, result.stderr
    assert "MoMA Web 桌面程序" in result.stdout


def test_windows_default_dependencies_exclude_qt_and_offer_explicit_legacy_extra():
    project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]
    windows = {**default_environment(), "sys_platform": "win32", "platform_system": "Windows"}
    requirements = [Requirement(value) for value in project["dependencies"]]
    default_names = {item.name.lower() for item in requirements if item.marker is None or item.marker.evaluate(windows)}
    assert {"pillow", "pywebview"} <= default_names
    assert not default_names.intersection({"pyside6", "pyqt5", "pyqt6", "qtpy"})
    legacy = project["optional-dependencies"].get("legacy-qt", [])
    assert "pyside6" in {Requirement(value).name.lower() for value in legacy}
    assert project["scripts"]["moma"] == "app.desktop.main:main"
    assert project["scripts"]["moma-qt"] == "app.main:main"


def test_legacy_entrypoint_still_requires_the_optional_qt_dependency():
    program = """
import importlib.abc
import runpy
import sys

class NoQt(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname.split('.')[0] == 'PySide6':
            raise ModuleNotFoundError('legacy-qt-required')

sys.meta_path.insert(0, NoQt())
try:
    runpy.run_path('run_qt.py', run_name='legacy_import')
except ModuleNotFoundError as error:
    if str(error) != 'legacy-qt-required':
        raise
    print('legacy-qt-required')
else:
    raise AssertionError('Historical entry must retain the Qt implementation')
"""
    result = subprocess.run(
        [sys.executable, "-X", "utf8", "-c", program], cwd=ROOT,
        capture_output=True, text=True, encoding="utf-8", timeout=15,
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "legacy-qt-required"


@pytest.mark.skipif(sys.platform != "win32", reason="Windows 批处理入口")
@pytest.mark.parametrize("environment_exists", [False, True])
def test_batch_launcher_explains_missing_prerequisites_without_starting(tmp_path, environment_exists):
    directory = tmp_path / "中文 空格入口"
    directory.mkdir()
    (directory / "run.bat").write_bytes((ROOT / "run.bat").read_bytes())
    if environment_exists:
        # Only satisfy the existence check; this file must never be launched.
        python = directory / ".venv-web" / "Scripts" / "python.exe"
        python.parent.mkdir(parents=True)
        python.write_bytes(b"")
    system32 = Path(os.environ["SystemRoot"]) / "System32"
    result = subprocess.run(
        f'"{system32 / "cmd.exe"}" /d /c call run.bat <NUL', cwd=directory,
        env={**os.environ, "PATH": str(system32)}, capture_output=True,
        text=True, encoding="utf-8", errors="replace", timeout=5,
    )
    assert result.returncode == 1, (result.stdout, result.stderr)
    assert ("未找到已构建的 Web 界面" if environment_exists else "未找到 Web 虚拟环境") in result.stdout
    assert not result.stderr
