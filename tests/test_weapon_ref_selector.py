"""Weapon references share the content-reference selector contract."""

from __future__ import annotations

import os
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtWidgets import QApplication

from app.core.metadata import Metadata
from app.core.project import Project
from app.ui.widgets.content_ref_selector import ContentRefSelector
from app.ui.widgets.weapon_array_editor import _AddWeaponDialog, _load_weapon_data


METADATA_DIR = Path(__file__).resolve().parent.parent / "metadata"


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


def test_weapon_reference_uses_shared_selector_and_keeps_project_prefix(qapp, tmp_path):
    project = Project.create(tmp_path, "probe-mod", "探针模组")
    project.contents.save("pulse", {"type": "Weapon", "name": "pulse"}, "weapons")
    metadata = Metadata(METADATA_DIR)
    dialog = _AddWeaponDialog(project, metadata)

    selector = dialog.findChild(ContentRefSelector, "weaponReferenceSelector")
    assert selector is not None
    selector.set_value("probe-mod-pulse")
    dialog._on_accept()

    assert dialog.result_data() is not None
    assert dialog.result_data()["name"] == "probe-mod-pulse"
    assert _load_weapon_data("probe-mod-pulse", project, metadata) == {
        "type": "Weapon", "name": "pulse"
    }
