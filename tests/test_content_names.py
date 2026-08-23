"""内容名总表（E-4 / ADR-013）与科技双语搜索（E-5）测试。"""

from __future__ import annotations

import json
import os
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

from app.core.config_loader import get_content_names_zh
from app.ui.widgets.resource_editors import TechRefEditor, _tech_display


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


class TestExtractContentNames:
    """提取脚本核心逻辑：解析 properties 行。"""

    def _write_bundle(self, tmp_path):
        p = tmp_path / "bundle_zh_CN.properties"
        p.write_text(
            "block.copper-wall.name = 铜墙\n"
            "unit.dagger.name = 尖刀\n"
            "item.copper.name = 铜\n"
            "block.limit = 限制（非 name 键，应跳过）\n"
            "unit.blockssquared = 格（非 name 键，应跳过）\n"
            "status.burning.name = 燃烧\n"
            "planet.serpulo.name = 塞普罗\n"
            "sector.groundZero.name = 零号地区\n"
            "weapon.meltdown.name = 熔毁\n"
            "block.unknown.name = [scarlet]未知\n",
            encoding="utf-8",
        )
        return p

    def test_extract_structure(self, tmp_path):
        import sys

        sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))
        from extract_content_names import extract

        result = extract(self._write_bundle(tmp_path))
        assert result["blocks"]["copper-wall"] == "铜墙"
        assert result["units"]["dagger"] == "尖刀"
        assert result["items"]["copper"] == "铜"
        assert result["status"]["burning"] == "燃烧"
        assert result["planets"]["serpulo"] == "塞普罗"
        assert result["sectors"]["groundZero"] == "零号地区"
        assert result["weapons"]["meltdown"] == "熔毁"
        # 非 .name 键跳过
        assert "limit" not in result["blocks"]
        assert "blockssquared" not in result["units"]
        # 标记颜色代码剥离
        assert result["blocks"]["unknown"] == "未知"


class TestContentNamesConfig:
    """内容名总表 JSON 已入库且结构正确。"""

    def test_config_exists_and_shape(self):
        data = get_content_names_zh()
        for cat in ("items", "liquids", "blocks", "units", "weapons", "status", "planets", "sectors"):
            assert cat in data, f"缺少 {cat} 分类"
        assert data["items"]["copper"] == "铜"
        assert data["blocks"]["copper-wall"] == "铜墙"
        assert len(data["blocks"]) >= 400, "blocks 应有 400+ 条"


class TestTechDisplay:
    def test_with_zh(self):
        assert _tech_display("copper-wall") == "铜墙 (copper-wall)"

    def test_without_zh(self):
        # 无中文名的原样英文
        assert _tech_display("some-custom-thing") == "some-custom-thing"

    def test_empty(self):
        assert _tech_display("") == ""


class _StubMetadata:
    """最小 metadata stub：提供两个科技候选。"""

    def list_instance_categories(self):
        return ["Blocks", "Units"]

    def list_instances(self, cat):
        return ["copper-wall"] if cat == "Blocks" else ["dagger"]


class TestTechRefBilingualSearch:
    """E-5：下拉显示中文+英文，存储英文。"""

    def _make_editor(self, data, stack, multi=False):
        return TechRefEditor(
            data=data,
            path="research",
            command_stack=stack,
            multi=multi,
            metadata=_StubMetadata(),
        )

    def test_single_stores_english(self, qapp):
        from app.core.commands import CommandStack

        data = {"type": "Wall", "research": "copper-wall"}
        stack = CommandStack()
        editor = self._make_editor(data, stack)
        # 当前值铜墙显示为中文串
        le = editor._combo.lineEdit()
        assert le.text() == "铜墙 (copper-wall)", f"应显示中文串，实际 {le.text()}"
        # 改动后存储英文
        editor._on_single_changed("尖刀 (dagger)")
        assert data["research"] == "dagger", f"应存储英文名，实际 {data['research']}"
        stack.undo()
        assert data["research"] == "copper-wall"

    def test_display_to_value_map(self, qapp):
        from app.core.commands import CommandStack

        editor = self._make_editor({}, CommandStack())
        # 映射表包含中文 → 英文
        assert editor._display_to_value.get("铜墙 (copper-wall)") == "copper-wall"
        assert editor._display_to_value.get("尖刀 (dagger)") == "dagger"

    def test_completer_installed(self, qapp):
        from app.core.commands import CommandStack
        from PySide6.QtWidgets import QCompleter

        editor = self._make_editor({}, CommandStack())
        assert isinstance(editor._combo.completer(), QCompleter), "应安装 QCompleter"
        comp = editor._combo.completer()
        assert comp.caseSensitivity() == Qt.CaseSensitivity.CaseInsensitive
