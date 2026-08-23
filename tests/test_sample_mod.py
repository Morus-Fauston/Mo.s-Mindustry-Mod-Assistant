"""Tests for the reproducible v0.3.0 baseline mod generator."""

from __future__ import annotations

import importlib.util
from pathlib import Path
import sys
import zipfile

import pytest


ROOT = Path(__file__).parents[1]
SPEC = importlib.util.spec_from_file_location("make_sample_mod", ROOT / "tools" / "make_sample_mod.py")
assert SPEC is not None and SPEC.loader is not None
sample_mod = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = sample_mod
SPEC.loader.exec_module(sample_mod)


def test_generate_baseline_uses_minimal_core_output_chain(tmp_path: Path) -> None:
    result = sample_mod.generate_baseline(tmp_path)

    assert (result.project_root / "mod.json").exists()
    assert (result.project_root / "content" / "blocks" / "moma-baseline-wall.json").exists()
    unit_json = result.project_root / "content" / "units" / "moma-baseline-mech.json"
    assert unit_json.exists()
    assert (result.project_root / "sprites" / "blocks" / "moma-baseline-wall.png").exists()
    assert (result.project_root / "sprites" / "units" / "moma-baseline-mech.png").exists()
    assert '"type": "BasicBulletType"' in unit_json.read_text(encoding="utf-8")

    with zipfile.ZipFile(result.zip_path) as archive:
        assert set(archive.namelist()) == {
            "mod.json",
            "content/blocks/moma-baseline-wall.json",
            "content/units/moma-baseline-mech.json",
            "sprites/blocks/moma-baseline-wall.png",
            "sprites/units/moma-baseline-mech.png",
        }


def test_normal_generation_does_not_modify_committed_baseline_snapshot(tmp_path: Path) -> None:
    result = sample_mod.generate_baseline(tmp_path)
    snapshot = tmp_path / "snapshot"
    sample_mod.update_baseline_snapshot(result.project_root, snapshot)
    before = sample_mod.snapshot_manifest(snapshot)

    other = sample_mod.generate_baseline(tmp_path / "second")

    assert sample_mod.snapshot_manifest(snapshot) == before
    sample_mod.assert_matches_baseline(other.project_root, snapshot)


def test_generate_baseline_is_repeatable_for_the_same_output_directory(tmp_path: Path) -> None:
    first = sample_mod.generate_baseline(tmp_path)
    before = sample_mod.snapshot_manifest(first.project_root)

    second = sample_mod.generate_baseline(tmp_path)

    assert second.project_root == first.project_root
    assert sample_mod.snapshot_manifest(second.project_root) == before


def test_snapshot_comparison_rejects_json_text_drift(tmp_path: Path) -> None:
    result = sample_mod.generate_baseline(tmp_path)
    snapshot = tmp_path / "snapshot"
    sample_mod.update_baseline_snapshot(result.project_root, snapshot)
    (result.project_root / "content" / "blocks" / "moma-baseline-wall.json").write_text("{}\n", encoding="utf-8")

    with pytest.raises(AssertionError, match="快照"):
        sample_mod.assert_matches_baseline(result.project_root, snapshot)


def test_snapshot_comparison_rejects_png_hash_drift(tmp_path: Path) -> None:
    result = sample_mod.generate_baseline(tmp_path)
    snapshot = tmp_path / "snapshot"
    sample_mod.update_baseline_snapshot(result.project_root, snapshot)
    (result.project_root / "sprites" / "units" / "moma-baseline-mech.png").write_bytes(b"changed")

    with pytest.raises(AssertionError, match="快照"):
        sample_mod.assert_matches_baseline(result.project_root, snapshot)


def test_snapshot_comparison_rejects_file_list_drift(tmp_path: Path) -> None:
    result = sample_mod.generate_baseline(tmp_path)
    snapshot = tmp_path / "snapshot"
    sample_mod.update_baseline_snapshot(result.project_root, snapshot)
    (result.project_root / "sprites" / "units" / "unexpected.png").write_bytes(b"extra")

    with pytest.raises(AssertionError, match="快照"):
        sample_mod.assert_matches_baseline(result.project_root, snapshot)


def test_committed_baseline_snapshot_matches_generated_output(tmp_path: Path) -> None:
    result = sample_mod.generate_baseline(tmp_path)
    sample_mod.assert_matches_baseline(result.project_root)


def test_kitchen_sink_covers_templates_weapon_references_and_derived_sprites(tmp_path: Path) -> None:
    result = sample_mod.generate_kitchen_sink(tmp_path)

    unit_names = {path.stem for path in (result.project_root / "content" / "units").glob("*.json")}
    block_names = {path.stem for path in (result.project_root / "content" / "blocks").glob("*.json")}
    weapon_names = {path.stem for path in (result.project_root / "content" / "weapons").glob("*.json")}

    assert {"moma-sink-mech", "moma-sink-flying", "moma-sink-tank", "moma-sink-legs"} <= unit_names
    assert len(weapon_names) == 5
    assert {"moma-sink-wall", "moma-sink-itemturret", "moma-sink-mendprojector"} <= block_names
    assert "moma-sink-renamed-wall" in block_names
    assert not (result.project_root / "sprites" / "blocks" / "moma-sink-rename-source.png").exists()
    for suffix in ("-outline", "-shadow", "-full"):
        assert (result.project_root / "sprites" / "units" / f"moma-sink-mech{suffix}.png").exists()

    mech = (result.project_root / "content" / "units" / "moma-sink-mech.json").read_text(encoding="utf-8")
    assert '"type": "BasicBulletType"' in mech
    with zipfile.ZipFile(result.zip_path) as archive:
        assert "content/weapons/moma-sink-basicbullettype-weapon.json" in archive.namelist()


def test_snapshot_update_keeps_existing_snapshot_when_staging_copy_fails(tmp_path: Path, monkeypatch) -> None:
    result = sample_mod.generate_baseline(tmp_path)
    snapshot = tmp_path / "snapshot"
    sample_mod.update_baseline_snapshot(result.project_root, snapshot)
    before = sample_mod.snapshot_manifest(snapshot)

    def fail_copy(*args, **kwargs) -> None:
        raise OSError("disk full")

    monkeypatch.setattr(sample_mod.shutil, "copytree", fail_copy)
    with pytest.raises(OSError, match="disk full"):
        sample_mod.update_baseline_snapshot(result.project_root, snapshot)

    assert sample_mod.snapshot_manifest(snapshot) == before
