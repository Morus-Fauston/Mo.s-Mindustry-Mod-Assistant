"""Load real reference-mod assets into MoMA's dynamic preview panel."""

from __future__ import annotations

import json
import shutil
import sys
import tempfile
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QComboBox, QLabel, QMainWindow, QVBoxLayout, QWidget

ROOT = Path(__file__).resolve().parents[2]
REFERENCE_ROOT = ROOT / "辅助项目" / "参考模组"

sys.path.insert(0, str(ROOT))

from app.core.content_store import ContentData
from app.core.project import Project
from app.ui.preview_panel import PreviewPanel
from app.ui.theme import apply_theme


class ReferenceAsset:
    def __init__(self, mod_name: str, content_path: Path, sprite_path: Path) -> None:
        self.mod_name = mod_name
        self.content_path = content_path
        self.sprite_path = sprite_path
        self.name = content_path.stem

    @property
    def label(self) -> str:
        return f"{self.mod_name} / {self.name}"


def find_reference_assets() -> list[ReferenceAsset]:
    assets: list[ReferenceAsset] = []
    if not REFERENCE_ROOT.is_dir():
        return assets

    for mod_dir in sorted(REFERENCE_ROOT.iterdir()):
        units_dir = mod_dir / "content" / "units"
        sprites_dir = mod_dir / "sprites" / "units"
        if not units_dir.is_dir() or not sprites_dir.is_dir():
            continue
        for content_path in sorted(units_dir.rglob("*.json")):
            sprite_matches = sorted(sprites_dir.rglob(f"{content_path.stem}.png"))
            if sprite_matches:
                assets.append(
                    ReferenceAsset(mod_dir.name, content_path, sprite_matches[0])
                )
    return assets


def copy_asset_to_demo_project(asset: ReferenceAsset, demo_root: Path) -> tuple[Project, ContentData]:
    project = Project.create(demo_root, "dynamic-preview-demo", "动态预览示例")
    content = json.loads(asset.content_path.read_text(encoding="utf-8"))
    content_type = str(content.get("type", "UnitType"))
    if content_type not in {"flying", "tank", "legs", "mech", "UnitType"}:
        content_type = "UnitType"
    content["type"] = content_type

    content_path = project.contents.content_dir / "units" / f"{asset.name}.json"
    content_path.write_text(
        json.dumps(content, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    sprite_path = project.sprite_path("units", asset.name)
    shutil.copy2(asset.sprite_path, sprite_path)

    for suffix_path in sorted(asset.sprite_path.parent.glob(f"{asset.name}-*.png")):
        suffix = suffix_path.stem[len(asset.name):]
        shutil.copy2(
            suffix_path,
            project.sprite_path("units", asset.name, suffix),
        )
    return project, ContentData(name=asset.name, category="units", data=content, path=content_path)


class DemoWindow(QMainWindow):
    def __init__(self, assets: list[ReferenceAsset]) -> None:
        super().__init__()
        self.setWindowTitle("MoMA 动态预览示例")
        self.resize(760, 900)
        self._assets = assets
        self._temp_root = Path(tempfile.mkdtemp(prefix="moma_dynamic_preview_demo_"))
        self._project: Project | None = None

        central = QWidget()
        layout = QVBoxLayout(central)
        layout.setContentsMargins(8, 8, 8, 8)
        selector = QComboBox()
        selector.addItems([asset.label for asset in assets])
        selector.currentIndexChanged.connect(self._show_asset)
        layout.addWidget(QLabel("选择参考模组单位"))
        layout.addWidget(selector)

        self._preview = PreviewPanel()
        layout.addWidget(self._preview, stretch=1)
        self.setCentralWidget(central)
        self._selector = selector
        self._show_asset(0)

    def _show_asset(self, index: int) -> None:
        asset = self._assets[index]
        project, content = copy_asset_to_demo_project(asset, self._temp_root)
        self._project = project
        self._preview.show_content(content, project)
        self._preview._dynamic_button.click()

    def closeEvent(self, event) -> None:
        shutil.rmtree(self._temp_root, ignore_errors=True)
        super().closeEvent(event)


def main() -> None:
    assets = find_reference_assets()
    if not assets:
        raise SystemExit(
            "没有找到可直接读取的参考单位。请确认辅助项目/参考模组/*/content/units/*.json "
            "和同名 sprites/units/*.png 存在。"
        )
    app = QApplication(sys.argv)
    apply_theme(app, "light")
    window = DemoWindow(assets)
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
