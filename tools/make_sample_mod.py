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
from app.core.sprite_generator import generate_full, generate_outline, generate_shadow
from app.core.template import TemplateEngine

BASELINE_MOD_ID = "moma-baseline"
BASELINE_FIXTURE = ROOT / "tests" / "fixtures" / "baseline-mod"
KITCHEN_SINK_MOD_ID = "moma-kitchen-sink"


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


def _save_fixture_sprite(
    project: Project,
    category: str,
    name: str,
    color: tuple[int, int, int, int],
    *,
    derived: bool = False,
) -> Image.Image:
    """Write a deterministic main sprite and, when requested, its derived set."""
    main = make_sprite_fixture(32, color)
    save_sprite(project, category, name, main, overwrite=True)
    if derived:
        outline = generate_outline(main, color="#20242c")
        shadow = generate_shadow(main)
        full = generate_full(main, layers=[outline])
        save_sprite(project, category, name, outline, "-outline", overwrite=True)
        save_sprite(project, category, name, shadow, "-shadow", overwrite=True)
        save_sprite(project, category, name, full, "-full", overwrite=True)
    return main


def _bullet_for(kind: str) -> dict:
    """Return the smallest documented payload for each supported bullet subtype."""
    if kind == "LaserBulletType":
        return {"type": kind, "damage": 16, "length": 96, "width": 8}
    return {"type": kind, "damage": 12, "speed": 3.5, "lifetime": 35}


def generate_kitchen_sink(output_dir: str | Path) -> BaselineOutput:
    """Generate the v0.3 candidate sample without changing the baseline fixture.

    The five project-Weapon references are deliberately isolated one-per-unit.
    Their actual engine registration remains an A4 conclusion, not an assumption.
    """
    destination = Path(output_dir)
    project = Project.create(destination, KITCHEN_SINK_MOD_ID, "MoMA 厨房水槽样本", author="MoMA")
    engine = TemplateEngine(Metadata(metadata_dir()))

    unit_specs = [
        ("UnitType", "moma-sink-mech", (89, 148, 205, 255)),
        ("UnitType-flying", "moma-sink-flying", (112, 198, 184, 255)),
        ("UnitType-tank", "moma-sink-tank", (177, 132, 89, 255)),
        ("UnitType-legs", "moma-sink-legs", (156, 104, 186, 255)),
    ]
    units: dict[str, dict] = {}
    for template_kind, name, color in unit_specs:
        unit = engine.create(template_kind, name)
        project.contents.save(name, unit, "units")
        _save_fixture_sprite(project, "units", name, color, derived=name == "moma-sink-mech")
        units[name] = unit

    inline_weapon = engine.create("Weapon", "moma-sink-inline-gun")
    inline_weapon["bullet"] = _bullet_for("BasicBulletType")
    units["moma-sink-mech"]["weapons"] = [inline_weapon]
    project.contents.save("moma-sink-mech", units["moma-sink-mech"], "units")

    for index, bullet_type in enumerate(
        ["BasicBulletType", "LaserBulletType", "MissileBulletType", "ArtilleryBulletType", "FlakBulletType"]
    ):
        weapon_name = f"moma-sink-{bullet_type.lower()}-weapon"
        weapon = engine.create("Weapon", weapon_name)
        weapon["bullet"] = _bullet_for(bullet_type)
        project.contents.save(weapon_name, weapon, "weapons")
        _save_fixture_sprite(project, "weapons", weapon_name, (210, 154 + index * 10, 78, 255))

        unit_name = f"moma-sink-{bullet_type.lower()}-ref"
        unit = engine.create("UnitType", unit_name)
        unit["weapons"] = [{"name": weapon_name}]
        project.contents.save(unit_name, unit, "units")
        _save_fixture_sprite(project, "units", unit_name, (74, 122, 173 + index * 8, 255))

    for index, template_kind in enumerate(
        ["Wall", "ItemTurret", "PowerTurret", "GenericCrafter", "Drill", "Conveyor", "Battery", "MendProjector"]
    ):
        name = f"moma-sink-{template_kind.lower()}"
        block = engine.create(template_kind, name)
        project.contents.save(name, block, "blocks")
        _save_fixture_sprite(project, "blocks", name, (126 + index * 10, 136, 151, 255))

    # Rename-sprites contract: create only the old fixture name, rename it,
    # then write the content JSON under the resulting name.
    old_name = "moma-sink-rename-source"
    renamed_name = "moma-sink-renamed-wall"
    _save_fixture_sprite(project, "blocks", old_name, (192, 122, 95, 255), derived=True)
    project.rename_sprites("blocks", old_name, renamed_name)
    project.contents.save(renamed_name, engine.create("Wall", renamed_name), "blocks")

    project.mod_info.description = "MoMA v0.3.0 厨房水槽候选验收样本。"
    project.mod_info.version = "0.3.0"
    project.save_mod_info()
    zip_path = project.export_zip(destination / f"{KITCHEN_SINK_MOD_ID}.zip")
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
    parser.add_argument("--sample", choices=("baseline", "kitchen-sink"), default="baseline")
    parser.add_argument("--update-baseline", action="store_true", help="用本次输出显式更新审阅快照")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    result = generate_baseline(args.output) if args.sample == "baseline" else generate_kitchen_sink(args.output)
    if args.update_baseline:
        if args.sample != "baseline":
            raise ValueError("只有 baseline 样本可以更新审阅快照")
        update_baseline_snapshot(result.project_root)
        print(f"已显式更新基线快照: {BASELINE_FIXTURE}")
    elif args.sample == "baseline":
        assert_matches_baseline(result.project_root)
    print(f"基线工程: {result.project_root}")
    print(f"基线 ZIP: {result.zip_path}")


if __name__ == "__main__":
    main()
