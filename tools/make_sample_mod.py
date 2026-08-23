"""Generate the reproducible v0.3.0 minimal Mindustry mod baseline.

The two PNGs are deliberately simple Pillow fixtures. They establish the
engine-load precondition only; they do not prove a future drawing workflow.
All project, content, sprite-path and PNG write operations use MoMA core APIs.
"""

from __future__ import annotations

import argparse
import hashlib
import shutil
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from PIL import Image, ImageDraw

from app.core.metadata import Metadata
from app.core.paths import metadata_dir
from app.core.project import Project
from app.core.sprite_io import save_sprite
from app.core.template import TemplateEngine

BASELINE_MOD_ID = "moma-baseline"
BASELINE_FIXTURE = ROOT / "tests" / "fixtures" / "baseline-mod"


@dataclass(frozen=True)
class BaselineOutput:
    project_root: Path
    zip_path: Path


def make_sprite_fixture(size: int, color: tuple[int, int, int, int]) -> Image.Image:
    """Create a fixed RGBA fixture whose bytes are stable across runs."""
    image = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    draw.rectangle((2, 2, size - 3, size - 3), fill=color)
    return image


def generate_baseline(output_dir: str | Path) -> BaselineOutput:
    """Generate the smallest importable mod without touching the snapshot."""
    destination = Path(output_dir)
    project = Project.create(
        destination,
        BASELINE_MOD_ID,
        "MoMA 基线模组",
        author="MoMA",
    )
    engine = TemplateEngine(Metadata(metadata_dir()))

    wall_name = "moma-baseline-wall"
    wall = engine.create("Wall", wall_name)
    project.contents.save(wall_name, wall, "blocks")

    unit_name = "moma-baseline-mech"
    unit = engine.create("UnitType", unit_name)
    weapon = engine.create("Weapon", f"{unit_name}-gun")
    weapon.update({"reload": 25, "x": 4, "y": 2, "mirror": True})
    weapon["bullet"].update({"type": "BasicBulletType", "damage": 12, "speed": 3.5, "lifetime": 35})
    unit["weapons"] = [weapon]
    project.contents.save(unit_name, unit, "units")

    save_sprite(
        project,
        "blocks",
        wall_name,
        make_sprite_fixture(32, (154, 161, 174, 255)),
        overwrite=True,
    )
    save_sprite(
        project,
        "units",
        unit_name,
        make_sprite_fixture(32, (91, 148, 205, 255)),
        overwrite=True,
    )

    project.mod_info.description = "MoMA 自动生成的最小验证基线。"
    project.mod_info.version = "0.3.0"
    project.save_mod_info()
    zip_path = project.export_zip(destination / f"{BASELINE_MOD_ID}.zip")
    return BaselineOutput(project.root, zip_path)


def snapshot_manifest(root: str | Path) -> dict[str, str]:
    """Return strict text-or-SHA256 output evidence for a generated baseline."""
    base = Path(root)
    manifest: dict[str, str] = {}
    for path in sorted(path for path in base.rglob("*") if path.is_file()):
        relative = path.relative_to(base).as_posix()
        if path.suffix == ".png":
            manifest[relative] = f"sha256:{hashlib.sha256(path.read_bytes()).hexdigest()}"
        elif path.suffix == ".json":
            manifest[relative] = f"text:{path.read_text(encoding='utf-8')}"
        else:
            raise ValueError(f"基线不应包含未声明文件: {relative}")
    return manifest


def assert_matches_baseline(output_root: str | Path, baseline_root: str | Path = BASELINE_FIXTURE) -> None:
    """Reject any file-list, JSON-text or PNG-byte drift from the snapshot."""
    actual = snapshot_manifest(output_root)
    expected = snapshot_manifest(baseline_root)
    if actual != expected:
        raise AssertionError("基线输出与已审阅快照不一致；请检查差异后显式更新快照。")


def update_baseline_snapshot(output_root: str | Path, baseline_root: str | Path = BASELINE_FIXTURE) -> None:
    """Replace the committed snapshot only after the caller explicitly asks."""
    source = Path(output_root).resolve()
    destination = Path(baseline_root).resolve()
    if not source.is_dir():
        raise FileNotFoundError(f"找不到生成的基线目录: {source}")
    if source == destination or source in destination.parents or destination in source.parents:
        raise ValueError("基线快照目录不能与生成目录重叠")

    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=f".{destination.name}-", dir=destination.parent) as staging_dir:
        candidate = Path(staging_dir) / destination.name
        shutil.copytree(source, candidate)
        if snapshot_manifest(candidate) != snapshot_manifest(source):
            raise AssertionError("临时基线快照与生成结果不一致")

        if not destination.exists():
            candidate.replace(destination)
            return

        backup = destination.with_name(f".{destination.name}.backup")
        if backup.exists():
            raise FileExistsError(f"遗留基线备份阻止更新: {backup}")
        destination.replace(backup)
        try:
            candidate.replace(destination)
        except Exception:
            backup.replace(destination)
            raise
        shutil.rmtree(backup)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="生成 MoMA v0.3.0 基线模组")
    parser.add_argument("--output", type=Path, default=ROOT / "sample-mod-output" / "baseline")
    parser.add_argument("--update-baseline", action="store_true", help="用本次输出显式更新审阅快照")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    result = generate_baseline(args.output)
    if args.update_baseline:
        update_baseline_snapshot(result.project_root)
        print(f"已显式更新基线快照: {BASELINE_FIXTURE}")
    else:
        assert_matches_baseline(result.project_root)
    print(f"基线工程: {result.project_root}")
    print(f"基线 ZIP: {result.zip_path}")


if __name__ == "__main__":
    main()
