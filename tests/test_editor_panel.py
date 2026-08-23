"""EditorPanel 构建回归测试（F-50 widgets 配置路由崩溃修复）。

背景：v0.2.x 引入 field_groups.json 的 widgets 配置后，_create_configured_widget
读取的 stack 属性名写错（self._command_stack，实际为 self._commands），
导致任何打开含 widgets 路由字段的方块类型（如 GenericCrafter 的
requirements/consumes/research）都会抛 AttributeError 而无法打开编辑器。

这些测试验证：构造 EditorPanel（构造即触发 _rebuild_form → 完整渲染）
不会抛异常，且 widgets 路由控件真实创建。
"""

from __future__ import annotations

import os
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication
from PySide6.QtTest import QTest

from app.core.commands import CommandStack, ReplaceDataCommand
from app.core.content_store import ContentData
from app.core.metadata import Metadata
from app.core.project import Project
from app.core.template import TemplateEngine
from app.core.validator import Validator
from app.ui.editor_panel import EditorPanel
from app.ui.widgets.content_ref_selector import ContentRefSelector
from app.ui.widgets.planet_set_editor import PlanetSetEditor
from app.ui.widgets.research_editor import ResearchEditor
from app.ui.widgets.resource_editors import (
    ConsumesEditor,
    ResourceListEditor,
    ResourceSlotEditor,
)

METADATA_DIR = Path(__file__).resolve().parent.parent / "metadata"


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


@pytest.fixture
def project(tmp_path):
    Project.create(tmp_path, "probe-mod", "探针模组")
    return Project.open(tmp_path / "probe-mod")


class TestConfiguredWidgetRouting:
    """widgets 路由字段打开编辑器不得抛 AttributeError（回归：属性名笔误）。"""

    def _make_panel(self, qapp, project, data):
        meta = Metadata(METADATA_DIR)
        panel = EditorPanel(
            content=ContentData(name="probe", category="blocks", data=data),
            metadata=meta,
            command_stack=CommandStack(),
            validator=Validator(meta),
            project=project,
        )
        panel.show()
        qapp.processEvents()
        return panel

    def test_block_requirements_resource_list_opens(self, qapp, project):
        """build 组 required=['requirements'] 走 resource_list，构造不得抛异常。"""
        panel = self._make_panel(
            qapp, project, {"type": "GenericCrafter", "name": "探针"}
        )
        assert panel.findChildren(ResourceListEditor), "requirements 应渲染为 ResourceListEditor"

    def test_block_consumes_widget_opens(self, qapp, project):
        """consumption 组 optional=['consumes'] 在 data 带值时走 consumes 控件。"""
        panel = self._make_panel(
            qapp,
            project,
            {"type": "GenericCrafter", "name": "探针", "consumes": {"power": 1.0}},
        )
        # consumes 渲染为 ConsumesEditor；build 组的 requirements 仍渲染 resource_list
        assert panel.findChildren(ResourceListEditor), "requirements 应渲染为 ResourceListEditor"

    def test_block_output_item_slot_opens(self, qapp, project):
        """production 组 required=['outputItem'] 走 resource_slot 路由。"""
        panel = self._make_panel(
            qapp, project, {"type": "GenericCrafter", "name": "探针"}
        )
        assert panel.findChildren(ResourceSlotEditor), "outputItem 应渲染为 ResourceSlotEditor"

    def test_research_uses_the_inline_object_editor_even_when_the_field_is_absent(self, qapp, project):
        panel = self._make_panel(
            qapp, project, {"type": "Wall", "name": "探针"}
        )

        assert panel.findChildren(ResearchEditor), "科技树组应提供 Research 内联对象编辑器"

    def test_plain_string_reference_uses_the_shared_selector(self, qapp, project):
        panel = self._make_panel(
            qapp, project, {"type": "Wall", "name": "探针", "itemDrop": "copper"}
        )

        assert panel.findChildren(ContentRefSelector), "STRING_REF 应复用统一内容选择器"

    def test_shown_planets_uses_the_basic_group_planet_set_editor(self, qapp, project):
        panel = self._make_panel(
            qapp, project,
            {"type": "Wall", "name": "探针", "shownPlanets": ["serpulo"]},
        )

        assert panel.findChildren(PlanetSetEditor), "基础属性组应提供星球集合编辑器"


class TestResearchEditor:
    def test_legacy_string_is_preserved_until_an_object_field_changes(self, qapp, project):
        metadata = Metadata(METADATA_DIR)
        data = {"type": "Wall", "research": "copper-wall"}
        stack = CommandStack()
        editor = ResearchEditor(data, "research", stack, metadata, project)

        assert editor.value == "copper-wall"
        parent = editor.findChild(ContentRefSelector, "researchParentSelector")
        assert parent is not None
        parent.set_value("dagger", emit=True)

        assert data["research"] == {"parent": "dagger"}
        stack.undo()
        assert data["research"] == "copper-wall"

    def test_objective_type_rebuilds_its_candidate_scope_and_writes_through_commands(self, qapp, project):
        metadata = Metadata(METADATA_DIR)
        data = {"type": "Wall"}
        stack = CommandStack()
        editor = ResearchEditor(data, "research", stack, metadata, project)

        editor.findChild(__import__("PySide6.QtWidgets", fromlist=["QPushButton"]).QPushButton, "addResearchObjective").click()
        type_selector = editor.findChild(__import__("PySide6.QtWidgets", fromlist=["QComboBox"]).QComboBox, "researchObjectiveType0")
        assert type_selector is not None
        type_selector.setCurrentIndex(type_selector.findData("OnPlanet"))
        target = editor.findChild(ContentRefSelector, "researchObjectiveContent0")
        assert target is not None
        target.set_value("serpulo", emit=True)

        assert data["research"] == {"objectives": [{"type": "OnPlanet", "planet": "serpulo"}]}
        assert stack.can_undo


class TestShownPlanetsEditor:
    def test_planet_set_is_rendered_in_basic_and_uses_the_command_stack(self, qapp, project):
        metadata = Metadata(METADATA_DIR)
        data = {"type": "Wall", "name": "探针", "shownPlanets": ["serpulo"]}
        stack = CommandStack()
        editor = PlanetSetEditor(data, "shownPlanets", stack, metadata, project)

        selector = editor.findChild(ContentRefSelector, "shownPlanetsSelector0")
        assert selector is not None
        selector.set_value("erekir", emit=True)

        assert data["shownPlanets"] == ["erekir"]
        stack.undo()
        assert data["shownPlanets"] == ["serpulo"]


class TestJsonOutputPreview:
    """合法 JSON 通过命令栈回写，非法草稿只停留在视图中。"""

    def _make_panel(self, qapp, project, data):
        metadata = Metadata(METADATA_DIR)
        stack = CommandStack()
        panel = EditorPanel(
            content=ContentData(name="json-probe", category="blocks", data=data),
            metadata=metadata,
            command_stack=stack,
            validator=Validator(metadata),
            project=project,
        )
        panel.show()
        qapp.processEvents()
        return panel, stack

    def test_legal_json_replaces_data_after_debounce_and_can_be_undone(self, qapp, project):
        from PySide6.QtWidgets import QPlainTextEdit

        data = {"type": "Wall", "health": 100}
        panel, stack = self._make_panel(qapp, project, data)
        panel.findChild(__import__("PySide6.QtWidgets", fromlist=["QPushButton"]).QPushButton, "jsonModeBtn").click()
        editor = panel.findChild(QPlainTextEdit, "jsonOutputEditor")
        assert editor is not None

        editor.setPlainText('{"type": "Wall", "health": 250, "armor": 4}')
        QTest.qWait(550)

        assert data == {"type": "Wall", "health": 250, "armor": 4}
        stack.undo()
        assert data == {"type": "Wall", "health": 100}

    def test_invalid_json_draft_does_not_change_data_or_enter_command_history(self, qapp, project):
        from PySide6.QtWidgets import QPlainTextEdit

        data = {"type": "Wall", "health": 100}
        panel, stack = self._make_panel(qapp, project, data)
        panel.findChild(__import__("PySide6.QtWidgets", fromlist=["QPushButton"]).QPushButton, "jsonModeBtn").click()
        editor = panel.findChild(QPlainTextEdit, "jsonOutputEditor")
        assert editor is not None

        editor.setPlainText('{"type": "Wall",')
        QTest.qWait(550)

        assert data == {"type": "Wall", "health": 100}
        assert not stack.can_undo
        assert editor.property("error") == "true"

    def test_save_while_json_draft_is_invalid_keeps_the_last_legal_content(self, qapp, project):
        from PySide6.QtWidgets import QPlainTextEdit

        data = {"type": "Wall", "health": 100}
        project.contents.save("json-probe", data, "blocks")
        panel, _ = self._make_panel(qapp, project, data)
        panel.findChild(__import__("PySide6.QtWidgets", fromlist=["QPushButton"]).QPushButton, "jsonModeBtn").click()
        editor = panel.findChild(QPlainTextEdit, "jsonOutputEditor")
        assert editor is not None
        editor.setPlainText('{"type":')
        QTest.qWait(550)

        panel.save()

        assert project.contents.get("json-probe").data == {"type": "Wall", "health": 100}

    def test_format_command_keeps_an_invalid_draft_intact(self, qapp, project):
        from PySide6.QtWidgets import QPlainTextEdit

        panel, _ = self._make_panel(qapp, project, {"type": "Wall", "health": 100})
        panel.findChild(__import__("PySide6.QtWidgets", fromlist=["QPushButton"]).QPushButton, "jsonModeBtn").click()
        editor = panel.findChild(QPlainTextEdit, "jsonOutputEditor")
        assert editor is not None
        editor.setPlainText('{"type":')
        panel.findChild(__import__("PySide6.QtWidgets", fromlist=["QPushButton"]).QPushButton, "formatJsonBtn").click()

        assert editor.toPlainText() == '{"type":'

    def test_legal_json_issues_are_listed_and_clicking_one_selects_its_key_line(self, qapp, project):
        from PySide6.QtWidgets import QListWidget, QPlainTextEdit

        panel, _ = self._make_panel(qapp, project, {"type": "Wall", "health": 100})
        panel.findChild(__import__("PySide6.QtWidgets", fromlist=["QPushButton"]).QPushButton, "jsonModeBtn").click()
        editor = panel.findChild(QPlainTextEdit, "jsonOutputEditor")
        issues = panel.findChild(QListWidget, "jsonIssuesList")
        assert editor is not None and issues is not None

        editor.setPlainText('{\n  "type": "UnknownType"\n}')
        qapp.processEvents()

        assert issues.count() == 1
        assert issues.isVisible()
        QTest.mouseClick(
            issues.viewport(),
            Qt.MouseButton.LeftButton,
            pos=issues.visualItemRect(issues.item(0)).center(),
        )
        assert editor.textCursor().blockNumber() == 1

    def test_refresh_after_undo_or_redo_resyncs_the_form_type(self, qapp, project):
        data = {"type": "Wall", "health": 100}
        panel, stack = self._make_panel(qapp, project, data)

        stack.execute(ReplaceDataCommand(data, {"type": "GenericCrafter", "name": "探针"}))
        panel.refresh_from_data()
        assert panel._type_label.text() == "GenericCrafter"
        assert panel._class_def is not None and panel._class_def.name == "GenericCrafter"

        stack.undo()
        panel.refresh_from_data()
        assert panel._type_label.text() == "Wall"
        assert panel._class_def is not None and panel._class_def.name == "Wall"


class TestConsumesRendering:
    """consumes 字段渲染为 ConsumesEditor（F-22，合成 FieldDef 回归）。"""

    def _panel_with_template(self, qapp, project, block_type: str):
        """用真实模板数据打开方块，验证 consumes 渲染。"""
        meta = Metadata(METADATA_DIR)
        data = TemplateEngine(meta).create(block_type, "探针方块")
        panel = EditorPanel(
            content=ContentData(name="probe", category="blocks", data=data),
            metadata=meta,
            command_stack=CommandStack(),
            validator=Validator(meta),
            project=project,
        )
        panel.show()
        qapp.processEvents()
        return panel

    def test_generic_crafter_consumes(self, qapp, project):
        panel = self._panel_with_template(qapp, project, "GenericCrafter")
        assert panel.findChildren(ConsumesEditor), "GenericCrafter consumes 应渲染为 ConsumesEditor"

    def test_drill_consumes(self, qapp, project):
        panel = self._panel_with_template(qapp, project, "Drill")
        assert panel.findChildren(ConsumesEditor), "Drill consumes 应渲染为 ConsumesEditor"

    def test_battery_consumes(self, qapp, project):
        panel = self._panel_with_template(qapp, project, "Battery")
        assert panel.findChildren(ConsumesEditor), "Battery consumes 应渲染为 ConsumesEditor"

    def test_mend_projector_consumes(self, qapp, project):
        panel = self._panel_with_template(qapp, project, "MendProjector")
        assert panel.findChildren(ConsumesEditor), "MendProjector consumes 应渲染为 ConsumesEditor"


class TestConfiguredWidgetUndo:
    """复合编辑器撤销粒度回归（v0.2.5 双重命令修复）。

    真实面板接线（valueChanged → _on_field_changed(committed=True)）下，
    每次修改只产生一条命令，撤销一次即恢复。
    """

    def _make_panel(self, qapp, project, data):
        meta = Metadata(METADATA_DIR)
        panel = EditorPanel(
            content=ContentData(name="probe", category="blocks", data=data),
            metadata=meta,
            command_stack=CommandStack(),
            validator=Validator(meta),
            project=project,
        )
        panel.show()
        qapp.processEvents()
        return panel

    def test_resource_slot_undo_once(self, qapp, project):
        """outputItem 下拉改值后，撤销一次即恢复（不产生双重命令）。"""
        from PySide6.QtWidgets import QComboBox

        data = TemplateEngine(Metadata(METADATA_DIR)).create("GenericCrafter", "探针方块")
        panel = self._make_panel(qapp, project, data)
        slot = panel.findChildren(ResourceSlotEditor)[0]
        combo = slot.findChild(QComboBox)
        combo.setCurrentText("lead")
        qapp.processEvents()
        assert data["outputItem"]["item"] == "lead"
        panel._commands.undo()
        qapp.processEvents()
        assert data["outputItem"]["item"] == "copper", "撤销一次必须恢复（双重命令会失效）"

    def test_resource_list_add_undo_once(self, qapp, project):
        """requirements 添加行后，撤销一次移除该行。"""
        data = TemplateEngine(Metadata(METADATA_DIR)).create("GenericCrafter", "探针方块")
        panel = self._make_panel(qapp, project, data)
        # 面板内可能有多个 ResourceListEditor（如 consumes.items），取 requirements 那个
        rl = next(r for r in panel.findChildren(ResourceListEditor) if r._path == "requirements")
        rl._add_row()
        qapp.processEvents()
        assert len(data["requirements"]) == 3  # 模板 2 行 + 新增 1 行
        panel._commands.undo()
        qapp.processEvents()
        assert len(data["requirements"]) == 2, "撤销一次应移除新增行"

    def test_consumes_spin_undo_once(self, qapp, project):
        """consumes.power 修改后，撤销一次恢复。"""
        from PySide6.QtWidgets import QDoubleSpinBox

        data = TemplateEngine(Metadata(METADATA_DIR)).create("GenericCrafter", "探针方块")
        panel = self._make_panel(qapp, project, data)
        ce = panel.findChildren(ConsumesEditor)[0]
        spin = ce.findChildren(QDoubleSpinBox)[0]  # power 消耗
        spin.setValue(2.5)
        spin.editingFinished.emit()
        qapp.processEvents()
        assert data["consumes"]["power"] == 2.5
        panel._commands.undo()
        qapp.processEvents()
        assert data["consumes"]["power"] == 1.0, "撤销一次必须恢复"


class TestResourceEditorStyling:
    """资源编辑器样式与汉化回归（v0.2.5 验收修复）。

    覆盖：
    - 下拉/数字框 fieldType 属性（QSS 马卡龙命中）
    - 下拉选项汉化「中文 (英文)」
    - 行删除按钮统一 weaponRemoveBtn 样式
    - consumes 添加默认初始行
    """

    def _panel(self, qapp, project, data):
        meta = Metadata(METADATA_DIR)
        panel = EditorPanel(
            content=ContentData(name="probe", category="blocks", data=data),
            metadata=meta,
            command_stack=CommandStack(),
            validator=Validator(meta),
            project=project,
        )
        panel.show()
        qapp.processEvents()
        return panel

    def _req_row(self, panel, path="requirements"):
        rl = next(r for r in panel.findChildren(ResourceListEditor) if r._path == path)
        assert rl._row_widgets, "应有行"
        return rl._row_widgets[0]

    def test_row_combo_fieldtype(self, qapp, project):
        """requirements 行内下拉应带 fieldType=ref（QSS 马卡龙）。"""
        data = TemplateEngine(Metadata(METADATA_DIR)).create("GenericCrafter", "探针方块")
        panel = self._panel(qapp, project, data)
        row = self._req_row(panel)
        from PySide6.QtWidgets import QComboBox

        combo = row.findChild(QComboBox)
        assert combo is not None
        assert combo.property("fieldType") == "ref", "行内下拉缺马卡龙 fieldType"

    def test_row_spin_fieldtype(self, qapp, project):
        """requirements 行内数字框应带 fieldType=num。"""
        data = TemplateEngine(Metadata(METADATA_DIR)).create("GenericCrafter", "探针方块")
        panel = self._panel(qapp, project, data)
        row = self._req_row(panel)
        from PySide6.QtWidgets import QSpinBox

        spin = row.findChild(QSpinBox)
        assert spin.property("fieldType") == "num"

    def test_row_delete_btn_style(self, qapp, project):
        """行删除按钮应为 weaponRemoveBtn 样式（非默认灰色矩形）。"""
        data = TemplateEngine(Metadata(METADATA_DIR)).create("GenericCrafter", "探针方块")
        panel = self._panel(qapp, project, data)
        row = self._req_row(panel)
        from PySide6.QtWidgets import QPushButton

        btns = [b for b in row.findChildren(QPushButton) if b.objectName() == "weaponRemoveBtn"]
        assert len(btns) == 1, "行删除按钮应复用 weaponRemoveBtn 样式"

    def test_row_combo_hanzi_display(self, qapp, project):
        """下拉选项应显示「铜 (copper)」汉化格式，且存值仍为英文。"""
        data = TemplateEngine(Metadata(METADATA_DIR)).create("GenericCrafter", "探针方块")
        panel = self._panel(qapp, project, data)
        row = self._req_row(panel)
        from PySide6.QtWidgets import QComboBox

        combo = row.findChild(QComboBox)
        texts = [combo.itemText(i) for i in range(combo.count())]
        assert "铜 (copper)" in texts, "下拉应有汉化显示名"
        # 选中铅后，数据存储值应为纯英文 'lead'
        lead_idx = combo.findData("lead")
        assert lead_idx >= 0, "下拉项应以原始英文为 data"
        combo.setCurrentIndex(lead_idx)
        qapp.processEvents()
        assert data["requirements"][0]["item"] == "lead", "存储值应为纯英文"

    def test_consumes_add_default_row(self, qapp, project):
        """添加物品消耗默认给初始一行（非空列表，避免'添加后看不到内容'）。"""
        data = TemplateEngine(Metadata(METADATA_DIR)).create("GenericCrafter", "探针方块")
        data["consumes"] = {"power": 1.0}
        panel = self._panel(qapp, project, data)
        ce = panel.findChildren(ConsumesEditor)[0]
        add_combo = ce._sub_widgets["__add__"].findChild(
            __import__("PySide6.QtWidgets", fromlist=["QComboBox"]).QComboBox
        )
        idx = add_combo.findData("items")
        add_combo.setCurrentIndex(idx)
        add_combo.activated.emit(idx)
        qapp.processEvents()
        assert data["consumes"]["items"] == [{"item": "", "amount": 1}], (
            f"添加后应有初始行，实际 {data['consumes']['items']}"
        )

    def test_resource_display_roundtrip(self):
        """汉化显示名与存储值互转。"""
        from app.ui.widgets.resource_editors import _resource_display, _resource_value

        assert _resource_display("copper", "item") == "铜 (copper)"
        assert _resource_value("铜 (copper)") == "copper"
        assert _resource_display("my-item", "item") == "my-item"  # 无中文原样


class TestResourceDropdownFixes:
    """资源下拉三问题回归（v0.2.5 第二轮验收修复）。

    覆盖：
    - 下拉箭头改用 SVG 图片（border transparent 三角在 windows11 editable
      combo 上渲染成黑块矩形）
    - consumes 添加下拉占位项（重复点击同一项仍触发 activated）
    - editable combo 光标归位（setEditText/setCurrentIndex 后光标在末尾
      导致视口滚到末尾、左侧中文看不见）
    - 弹出列表按最长选项撑宽
    """

    def _panel(self, qapp, project, data):
        meta = Metadata(METADATA_DIR)
        panel = EditorPanel(
            content=ContentData(name="probe", category="blocks", data=data),
            metadata=meta,
            command_stack=CommandStack(),
            validator=Validator(meta),
            project=project,
        )
        panel.show()
        qapp.processEvents()
        return panel

    def test_arrow_qss_uses_svg(self):
        """QSS 下拉箭头必须是 SVG 图片，不是 border transparent 三角。"""
        from app.ui.theme import load_qss

        template = (METADATA_DIR.parent / "app" / "resources" / "style.qss").read_text(encoding="utf-8")
        assert "image: @ARROW_ICON@;" in template, "箭头必须用图片"
        assert "border-left: 4px solid transparent" not in template, "旧 border 三角已移除"
        qss = load_qss("light")
        assert "@ARROW_ICON@" not in qss  # 已被 theme.py 替换
        assert "arrow_down.svg" in qss

    def test_arrow_icon_file_exists(self):
        """SVG 箭头文件必须存在（否则 QSS url 失效）。"""
        icon = METADATA_DIR.parent / "app" / "resources" / "icons" / "arrow_down.svg"
        assert icon.exists()

    def test_consumes_add_combo_has_placeholder(self, qapp, project):
        """添加消耗下拉必须有占位项（data=None）在 index 0，防止重复点击失效。"""
        data = TemplateEngine(Metadata(METADATA_DIR)).create("GenericCrafter", "探针方块")
        data["consumes"] = {"power": 1.0}
        panel = self._panel(qapp, project, data)
        ce = panel.findChildren(ConsumesEditor)[0]
        combo = ce._sub_widgets["__add__"].findChild(
            __import__("PySide6.QtWidgets", fromlist=["QComboBox"]).QComboBox
        )
        assert combo.itemData(0) is None, "index 0 应为占位项"
        assert combo.currentIndex() == 0, "默认停在占位项"

    def test_consumes_add_same_item_twice(self, qapp, project):
        """重复点击同一消耗类型仍有效（占位项保证每次 activated 触发）。"""
        data = TemplateEngine(Metadata(METADATA_DIR)).create("GenericCrafter", "探针方块")
        data["consumes"] = {"power": 1.0}
        panel = self._panel(qapp, project, data)
        ce = panel.findChildren(ConsumesEditor)[0]
        combo = ce._sub_widgets["__add__"].findChild(
            __import__("PySide6.QtWidgets", fromlist=["QComboBox"]).QComboBox
        )
        combo.activated.emit(combo.findData("items"))  # 点击物品消耗
        qapp.processEvents()
        assert "items" in data["consumes"]
        # rebuild 后新 combo 回到占位，再次点击同一类型必须仍有效
        combo2 = ce._sub_widgets["__add__"].findChild(
            __import__("PySide6.QtWidgets", fromlist=["QComboBox"]).QComboBox
        )
        assert combo2.currentIndex() == 0, "rebuild 后回占位"
        combo2.activated.emit(combo2.findData("items"))
        qapp.processEvents()
        assert data["consumes"]["items"] == [{"item": "", "amount": 1}]

    def test_row_combo_cursor_at_start(self, qapp, project):
        """行内下拉光标必须在开头（否则长文本左侧中文被滚出视野）。"""
        data = TemplateEngine(Metadata(METADATA_DIR)).create("GenericCrafter", "探针方块")
        panel = self._panel(qapp, project, data)
        rl = next(r for r in panel.findChildren(ResourceListEditor) if r._path == "requirements")
        combo = rl._row_widgets[0].findChild(
            __import__("PySide6.QtWidgets", fromlist=["QComboBox"]).QComboBox
        )
        le = combo.lineEdit()
        assert le is not None
        assert le.cursorPosition() <= 1, f"光标应在开头，实际 {le.cursorPosition()}"

    def test_row_combo_popup_view_wide_enough(self, qapp, project):
        """弹出列表 view 最小宽度 ≥ 最长选项宽度（不截断英文长名）。"""
        from PySide6.QtGui import QFontMetrics

        data = TemplateEngine(Metadata(METADATA_DIR)).create("GenericCrafter", "探针方块")
        panel = self._panel(qapp, project, data)
        rl = next(r for r in panel.findChildren(ResourceListEditor) if r._path == "requirements")
        combo = rl._row_widgets[0].findChild(
            __import__("PySide6.QtWidgets", fromlist=["QComboBox"]).QComboBox
        )
        fm = QFontMetrics(combo.font())
        longest = max(fm.horizontalAdvance(combo.itemText(i)) for i in range(combo.count()))
        assert combo.view().minimumWidth() >= longest, (
            f"view 最小宽 {combo.view().minimumWidth()} < 最长选项 {longest}"
        )


class TestNestedPathValue:
    """资源编辑器嵌套路径读写回归（v0.2.5 第三轮修复）。

    背景：resource_editors 的 value getter/setter 曾用 dict.get(点路径)/
    data[点路径]，顶层字段（requirements/outputItem）碰巧能用，但嵌套路径
    （consumes.items、consumes.liquids）读不到 → 列表显示为空、"+ 添加"看似
    失效（数据其实加了但显示层读不到）。与 PolymorphicTypeEditor 同根因蔓延。
    """

    def _panel(self, qapp, project, data):
        meta = Metadata(METADATA_DIR)
        panel = EditorPanel(
            content=ContentData(name="probe", category="blocks", data=data),
            metadata=meta,
            command_stack=CommandStack(),
            validator=Validator(meta),
            project=project,
        )
        panel.show()
        qapp.processEvents()
        return panel

    def test_nested_items_value_readable(self, qapp, project):
        """consumes.items 嵌套路径 value 必须读得到（原 dict.get 返回空）。"""
        data = TemplateEngine(Metadata(METADATA_DIR)).create("GenericCrafter", "探针方块")
        panel = self._panel(qapp, project, data)
        ce = panel.findChildren(ConsumesEditor)[0]
        items_editor = next(
            (e for e in ce.findChildren(ResourceListEditor) if e._path == "consumes.items"),
            None,
        )
        assert items_editor is not None, "应有 consumes.items 编辑器"
        assert items_editor.value == [{"item": "lead", "amount": 1}], (
            f"嵌套路径应读到模板数据，实际 {items_editor.value}"
        )
        assert len(items_editor._row_widgets) == 1, "应显示 1 行（原为 0 行=显示空）"

    def test_nested_add_row_renders(self, qapp, project):
        """consumes.items 点 + 添加 后新行必须显示（原数据加了但行不显示）。"""
        data = TemplateEngine(Metadata(METADATA_DIR)).create("GenericCrafter", "探针方块")
        panel = self._panel(qapp, project, data)
        ce = panel.findChildren(ConsumesEditor)[0]
        items_editor = next(
            (e for e in ce.findChildren(ResourceListEditor) if e._path == "consumes.items"),
            None,
        )
        items_editor._add_row()
        qapp.processEvents()
        assert len(data["consumes"]["items"]) == 2, "数据应新增一行"
        assert len(items_editor._row_widgets) == 2, (
            f"显示应同步为 2 行，实际 {len(items_editor._row_widgets)}（原为 0=添加失效）"
        )

    def test_nested_liquids_readable(self, qapp, project):
        """consumes.liquids 嵌套路径同样可读。"""
        data = TemplateEngine(Metadata(METADATA_DIR)).create("GenericCrafter", "探针方块")
        data["consumes"]["liquids"] = [{"liquid": "water", "amount": 1}]
        panel = self._panel(qapp, project, data)
        ce = panel.findChildren(ConsumesEditor)[0]
        liquids_editor = next(
            (e for e in ce.findChildren(ResourceListEditor) if e._path == "consumes.liquids"),
            None,
        )
        assert liquids_editor is not None, "应有 consumes.liquids 编辑器"
        assert liquids_editor.value == [{"liquid": "water", "amount": 1}]
        assert len(liquids_editor._row_widgets) == 1

    def test_nested_setter_writes_path(self):
        """value setter 必须写嵌套路径，不得创建字面键 'consumes.items'。"""
        from app.core.commands import CommandStack
        from app.ui.widgets.resource_editors import ResourceListEditor

        data = {"consumes": {}}
        rl = ResourceListEditor(data, "consumes.items", CommandStack())
        rl.value = [{"item": "copper", "amount": 1}]
        assert "consumes.items" not in data, "不得创建字面键"
        assert data["consumes"]["items"] == [{"item": "copper", "amount": 1}]


class TestGroupBarRendering:
    """复合字段容器渲染测试（E-2 / ADR-012 19.3）"""

    def _make_panel(self, qapp, project, data):
        meta = Metadata(METADATA_DIR)
        panel = EditorPanel(
            content=ContentData(name="probe", category="blocks", data=data),
            metadata=meta,
            command_stack=CommandStack(),
            validator=Validator(meta),
            project=project,
        )
        panel.show()
        qapp.processEvents()
        return panel

    def test_requirements_wrapped_in_group_bar(self, qapp, project):
        """requirements 走 resource_list 路由，应被 GroupBar 包裹且 fieldType=arr"""
        from app.ui.widgets.group_bar import GroupBar

        data = TemplateEngine(Metadata(METADATA_DIR)).create("GenericCrafter", "测试方块")
        panel = self._make_panel(qapp, project, data)
        bars = panel.findChildren(GroupBar)
        assert bars, "面板上应有 GroupBar"
        req_bar = next(
            (b for b in bars if b.editor and isinstance(b.editor, ResourceListEditor)
             and b.editor._path == "requirements"),
            None,
        )
        assert req_bar is not None, "requirements 应包在 GroupBar 里"
        assert req_bar.field_type == "arr", f"requirements 应为 arr，实际 {req_bar.field_type}"

    def test_output_item_group_bar_ref(self, qapp, project):
        """outputItem 走 resource_slot 路由，GroupBar fieldType=ref"""
        from app.ui.widgets.group_bar import GroupBar

        data = TemplateEngine(Metadata(METADATA_DIR)).create("GenericCrafter", "测试方块")
        panel = self._make_panel(qapp, project, data)
        bars = panel.findChildren(GroupBar)
        slot_bar = next(
            (b for b in bars if b.editor and isinstance(b.editor, ResourceSlotEditor)
             and b.editor._path == "outputItem"),
            None,
        )
        assert slot_bar is not None, "outputItem 应包在 GroupBar 里"
        assert slot_bar.field_type == "ref"

    def test_group_bar_has_bar_and_container(self, qapp, project):
        """GroupBar 应含 4px 色条 + 容器 + 编辑器"""
        from app.ui.widgets.group_bar import GroupBar

        data = TemplateEngine(Metadata(METADATA_DIR)).create("GenericCrafter", "测试方块")
        panel = self._make_panel(qapp, project, data)
        bars = panel.findChildren(GroupBar)
        assert bars
        bar = bars[0]
        from PySide6.QtWidgets import QFrame
        assert bar.findChildren(QFrame), "GroupBar 应含色条/容器 QFrame"
        assert bar.editor is not None
