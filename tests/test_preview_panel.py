"""图层树渲染回归测试（v0.2.5 图层树渲染修复）。

背景：windows11 风格 + 全局 QSS 下，QTreeWidget 复选框 indicator 丢失外框
（裸勾），且两列树默认等分列宽把列 0 压到 ~100px 导致图层名被裁、
深层级复选框被列边界切掉。修复 = 列 0 自适应内容宽度 + QSS 显式定义
QTreeWidget::indicator（checked 用 SVG 橙勾）+ 状态文本移到列 1 +
选中行聚焦态去掉右侧边框。

这些测试验证修复配置存在且语义生效（防回归），不依赖具体像素字体。
"""

from __future__ import annotations

import os
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QHeaderView, QTreeWidgetItem

from app.ui.preview_panel import PreviewPanel
from app.ui.theme import load_qss

_RESOURCES_DIR = Path(__file__).resolve().parent.parent / "app" / "resources"


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


class TestWeaponCardFieldEdits:
    """编辑区武器卡片字段修改必须真正写入 dict（v0.2.5 根因修复）。

    回归：_create_override_widget 曾直接传裸 _set_field（两参数）给单参数
    控件信号 → TypeError 被 Qt 吞掉 → dict 永不更新，预览不刷新、保存被
    旧值覆写。修复 = functools.partial 绑定 field_name。
    """

    def _make_card(self, qapp):
        from PySide6.QtWidgets import QAbstractButton, QAbstractSpinBox

        from app.core.commands import CommandStack
        from app.ui.widgets.weapon_array_editor import WeaponCard

        parent = {"weapons": [{"name": "短管炮", "x": 1.0, "y": 2.0, "mirror": False}]}
        card = WeaponCard(
            weapon_data=parent["weapons"][0],
            index=0,
            parent_data=parent,
            parent_path="weapons",
            commands=CommandStack(),
            metadata=None,
            project=None,
            field_names_zh={},
            field_docs={},
            total=1,
        )
        card.show()
        qapp.processEvents()
        spins = card.findChildren(QAbstractSpinBox)
        toggles = [b for b in card.findChildren(QAbstractButton)
                   if b.isCheckable() and not b.text()]
        return parent, card, spins, toggles

    def test_spin_edit_writes_to_dict(self, qapp):
        """x/y spin 修改必须写入 dict 并触发 modified。"""
        parent, card, spins, _ = self._make_card(qapp)
        assert len(spins) == 2
        fired = []
        card.modified.connect(lambda: fired.append(1))
        spins[0].setValue(9.9)
        qapp.processEvents()
        assert parent["weapons"][0]["x"] == 9.9
        spins[1].setValue(-4.5)
        qapp.processEvents()
        assert parent["weapons"][0]["y"] == -4.5
        assert len(fired) >= 2

    def test_toggle_edit_writes_to_dict(self, qapp):
        """mirror 等 bool 覆盖字段修改必须写入 dict。"""
        parent, card, _, toggles = self._make_card(qapp)
        assert len(toggles) == 1
        toggles[0].setChecked(True)
        qapp.processEvents()
        assert parent["weapons"][0]["mirror"] is True
    """图层树布局：列 0 固定 220px，保证最宽图层名完整显示（不截断）。"""

    def test_column0_is_fixed_220(self, qapp):
        """列 0 固定 220px：容纳最深缩进复选框 + 最宽图层名（如"引擎示意"），
        不会被截断成"引擎..."。"""
        panel = PreviewPanel()
        tree = panel._layer_tree
        header = tree.header()
        assert header.sectionResizeMode(0) == QHeaderView.ResizeMode.Fixed
        assert header.sectionSize(0) >= 220

    def test_layer_tree_has_object_name(self, qapp):
        """图层树必须有 objectName=layerTree，QSS 才能单独去掉它的选中态
        （文件树等其它树保留选中态）。"""
        panel = PreviewPanel()
        assert panel._layer_tree.objectName() == "layerTree"

    def test_status_text_goes_to_column1(self, qapp):
        """图层行状态 [有]/[可选]/[缺失] 必须在列 1，避免撑宽列 0 把
        武器行输入框挤远/挤窄。"""
        panel = PreviewPanel()
        tree = panel._layer_tree
        tree.setColumnCount(2)
        root = QTreeWidgetItem(tree, ["根", ""])
        root.setExpanded(True)
        it = QTreeWidgetItem(root, ["主体", "[可选]"])
        it.setTextAlignment(1, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        tree.show()
        qapp.processEvents()
        assert it.text(0) == "主体"
        assert it.text(1) == "[可选]"


class TestTreeIndicatorQss:
    """QSS 必须显式定义 QTreeWidget::indicator，否则 windows11 下裸勾。"""

    @pytest.mark.parametrize("theme", ["light", "dark"])
    def test_indicator_rule_present(self, theme):
        qss = load_qss(theme)
        # 必须是生效的 QSS 规则（带花括号），注释里的说明文字不算
        assert "QTreeWidget::indicator, QTreeView::indicator {" in qss
        assert (
            "QTreeWidget::indicator:checked, QTreeView::indicator:checked {"
            in qss
        )

    @pytest.mark.parametrize("theme", ["light", "dark"])
    def test_checked_uses_svg_check(self, theme):
        """勾选态必须用 SVG 橙勾（@CHECK_ICON@ 被 theme.py 替换为绝对路径），
        windows11 原生勾在深色主题下几乎不可见。"""
        # 模板源文件保留占位符
        template = (_RESOURCES_DIR / "style.qss").read_text(encoding="utf-8")
        assert "image: @CHECK_ICON@;" in template
        # load_qss 后占位符被替换为 url(绝对路径)，无残留
        qss = load_qss(theme)
        assert "@CHECK_ICON@" not in qss
        assert "image: url(" in qss
        assert "check_copper.svg" in qss
        assert (_RESOURCES_DIR / "icons" / "check_copper.svg").exists()

    @pytest.mark.parametrize("theme", ["light", "dark"])
    def test_selected_focus_has_no_right_border(self, theme):
        """选中行聚焦态不得有右侧边框（用户要求去掉右侧框，避免"双框"）。

        既不能有 border-right 声明，也不能有 border 简写（简写会设四边含右框）。
        """
        qss = load_qss(theme)
        start = qss.index("QTreeWidget::item:selected:focus")
        block = qss[start : start + qss[start:].index("}") + 1]
        assert "border-right" not in block
        assert "border:" not in block

    @pytest.mark.parametrize("theme", ["light", "dark"])
    def test_layer_tree_has_no_selection_visual(self, theme):
        """图层树（#layerTree）选中态必须被 QSS 覆盖为全透明（无左条/无边框/
        不加粗）——图层树不需要选中态（用户决策，v0.2.5）。"""
        qss = load_qss(theme)
        assert "#layerTree::item:selected" in qss
        start = qss.index("#layerTree::item:selected")
        block = qss[start : start + qss[start:].index("}") + 1]
        assert "transparent" in block
        assert "border-left: none" in block or "border-left:none" in block

    def test_full_qss_applies_cleanly(self, qapp):
        """浅色完整 QSS 可正常加载（含新 indicator 规则），无异常。"""
        qss = load_qss("light")
        assert "background-color:" in qss  # 令牌已替换
        # 具体令牌名不得残留（注释里出现"@TOKEN@"字样是文档说明，不算）
        for token in ("@INK2@", "@COPPER@", "@CANVAS@"):
            assert token not in qss


class TestWeaponRowDataSync:
    """武器行数据同步（v0.2.5 修复）：重建不覆写 dict + spin 加长。"""

    def _make_panel(self, qapp, weapons: list[dict]):
        from pathlib import Path
        import tempfile

        from app.core.content_store import ContentData
        from app.core.project import Project

        tmp = Path(tempfile.mkdtemp(prefix="moma_test_"))
        Project.create(tmp, "probe-mod", "探针模组")
        project = Project.open(tmp / "probe-mod")
        content = ContentData(
            name="fly",
            category="units",
            data={
                "type": "flying",
                "engineSize": 2.0,
                "weapons": weapons,
            },
        )
        panel = PreviewPanel()
        panel.show_content(content, project)
        panel.resize(400, 600)
        panel.show()
        qapp.processEvents()
        return panel, content, project, tmp

    def _weapon_spins(self, panel):
        from PySide6.QtWidgets import QDoubleSpinBox

        tree = panel._layer_tree

        def find_weapon_row(item):
            # 武器行通过 ROLE_WEAPON_INDEX >= 0 识别（避免被图层 [生成] 按钮
            # 的 itemWidget 抢先命中，v0.2.6 normalize content_type 后图层变多）
            if item.data(0, panel._ROLE_WEAPON_INDEX) is not None and item.data(0, panel._ROLE_WEAPON_INDEX) >= 0:
                return item
            for c in range(item.childCount()):
                r = find_weapon_row(item.child(c))
                if r:
                    return r
            return None

        row = find_weapon_row(tree.topLevelItem(0))
        if row is None:
            return []
        return tree.itemWidget(row, 1).findChildren(QDoubleSpinBox)

    def test_rebuild_does_not_pollute_dict(self, qapp):
        """引用武器（无 x/y 键）重建后 dict 不得被写入默认值（blockSignals）。

        回归：重建时 spin.setValue 触发 valueChanged → _on_weapon_spin_changed
        直接把默认值写进 dict，保存后被"图层树覆写"。
        """
        panel, content, project, tmp = self._make_panel(qapp, [{"name": "炮"}])
        # 被引用武器文件带非 0 默认 x/y：重建 spin.setValue 才真正改变值并触发信号
        (project.root / "content" / "weapons").mkdir(parents=True, exist_ok=True)
        (project.root / "content" / "weapons" / "炮.json").write_text(
            '{"name": "炮", "type": "Weapon", "x": 5.0, "y": -3.0}',
            encoding="utf-8",
        )
        w0 = content.data["weapons"][0]
        assert "x" not in w0 and "y" not in w0  # 重建前
        panel._refresh_layer_tree()  # 重建
        qapp.processEvents()
        w0 = content.data["weapons"][0]
        assert "x" not in w0 and "y" not in w0, "重建把默认值写进了 dict"

    def test_weapon_spins_are_70px(self, qapp):
        """武器 x/y 输入框宽度 70px（用户要求加长显示）。"""
        panel, content, project, tmp = self._make_panel(qapp, [{"name": "炮"}])
        spins = self._weapon_spins(panel)
        assert len(spins) == 2
        assert all(s.width() == 70 for s in spins)

    def test_editor_change_reflected_after_show_content(self, qapp):
        """编辑区改 XY → show_content → 图层树 spin 显示新值（不覆写）。"""
        panel, content, project, tmp = self._make_panel(qapp, [{"name": "炮"}])
        w0 = content.data["weapons"][0]
        w0["x"] = 7.5
        w0["y"] = 2.5
        panel.show_content(content, project)
        qapp.processEvents()
        spins = self._weapon_spins(panel)
        assert [s.value() for s in spins] == [7.5, 2.5]
        assert content.data["weapons"][0]["x"] == 7.5


class TestLayerTreeBehavior:
    """图层树行为覆盖：结构、显隐联动、子类型过滤、武器/引擎虚拟层、spin 写回。"""

    def _make_panel(
        self,
        qapp,
        content_type: str = "flying",
        weapons: list[dict] | None = None,
        engine_size: float = 2.0,
        make_main_sprite: bool = True,
    ):
        import tempfile

        from app.core.content_store import ContentData
        from app.core.project import Project

        tmp = Path(tempfile.mkdtemp(prefix="moma_test_"))
        Project.create(tmp, "probe-mod", "探针模组")
        project = Project.open(tmp / "probe-mod")

        if make_main_sprite:
            from PySide6.QtGui import QColor, QImage

            sprite_dir = project.sprites_dir / "units"
            sprite_dir.mkdir(parents=True, exist_ok=True)
            # 用 QImage 现场生成有效 8x8 png（手写字节易损坏）
            img = QImage(8, 8, QImage.Format.Format_RGBA8888)
            img.fill(QColor(200, 80, 80, 255))
            assert img.save(str(sprite_dir / "fly.png"), "PNG")

        data = {"type": content_type, "engineSize": engine_size}
        if weapons is not None:
            data["weapons"] = weapons

        content = ContentData(name="fly", category="units", data=data)
        panel = PreviewPanel()
        panel.show_content(content, project)
        panel.resize(400, 600)
        panel.show()
        qapp.processEvents()
        return panel, content, project, tmp

    def _all_items(self, panel):
        out = []

        def walk(item):
            out.append(item)
            for i in range(item.childCount()):
                walk(item.child(i))

        tree = panel._layer_tree
        for i in range(tree.topLevelItemCount()):
            walk(tree.topLevelItem(i))
        return out

    def _find_by_text(self, panel, text):
        return next((it for it in self._all_items(panel) if it.text(0) == text), None)

    def _weapon_spins(self, panel):
        from PySide6.QtWidgets import QDoubleSpinBox

        tree = panel._layer_tree

        def find_weapon_row(item):
            # 武器行通过 ROLE_WEAPON_INDEX >= 0 识别（避免被图层 [生成] 按钮
            # 的 itemWidget 抢先命中，v0.2.6 normalize content_type 后图层变多）
            if item.data(0, panel._ROLE_WEAPON_INDEX) is not None and item.data(0, panel._ROLE_WEAPON_INDEX) >= 0:
                return item
            for c in range(item.childCount()):
                r = find_weapon_row(item.child(c))
                if r:
                    return r
            return None

        row = find_weapon_row(tree.topLevelItem(0))
        if row is None:
            return []
        return tree.itemWidget(row, 1).findChildren(QDoubleSpinBox)

    def test_tree_structure_for_units(self, qapp):
        """units 类型：根节点 + 主体 + 武器父节点 + 每把武器 + 引擎示意。"""
        panel, *_ = self._make_panel(qapp, weapons=[{"name": "炮A"}, {"name": "炮B"}])
        root = panel._layer_tree.topLevelItem(0)
        assert root.text(0) == "fly 图层"
        texts = [root.child(i).text(0) for i in range(root.childCount())]
        assert "主体" in texts
        assert "武器" in texts
        assert "引擎示意" in texts
        weapon_parent = self._find_by_text(panel, "武器")
        assert weapon_parent is not None
        weapon_children = [weapon_parent.child(i).text(0) for i in range(weapon_parent.childCount())]
        assert weapon_children == ["炮A", "炮B"]

    def test_no_engine_item_when_engine_size_zero(self, qapp):
        """engineSize=0 时不应出现“引擎示意”虚拟层。"""
        panel, *_ = self._make_panel(qapp, engine_size=0.0, weapons=[{"name": "炮"}])
        assert self._find_by_text(panel, "引擎示意") is None

    def test_layer_checkbox_toggles_scene_visibility(self, qapp):
        """勾选/取消主体图层 checkbox，应同步主体场景元素可见性。"""
        panel, *_ = self._make_panel(qapp, weapons=[])
        main_item = self._find_by_text(panel, "主体")
        assert main_item is not None
        suffix = main_item.data(0, panel._ROLE_SUFFIX)
        assert suffix == ""
        assert panel._scene_items[""]

        main_item.setCheckState(0, Qt.CheckState.Unchecked)
        qapp.processEvents()
        assert all(not it.isVisible() for it in panel._scene_items[""])
        assert panel._layer_visibility[suffix] is False

        main_item.setCheckState(0, Qt.CheckState.Checked)
        qapp.processEvents()
        assert all(it.isVisible() for it in panel._scene_items[""])
        assert panel._layer_visibility[suffix] is True

    def test_weapon_checkbox_toggles_only_that_weapon(self, qapp):
        """每把武器有独立 __weapon_i__ key，显隐互不影响。"""
        panel, *_ = self._make_panel(qapp, weapons=[{"name": "炮A"}, {"name": "炮B"}])
        w0_item = self._find_by_text(panel, "炮A")
        w1_item = self._find_by_text(panel, "炮B")
        assert w0_item is not None and w1_item is not None

        key0 = w0_item.data(0, panel._ROLE_SUFFIX)
        key1 = w1_item.data(0, panel._ROLE_SUFFIX)
        assert key0 == "__weapon_0__"
        assert key1 == "__weapon_1__"

        # 没精灵图时场景里可能没有 pixmap，但 key 与缓存状态仍应正确联动
        w0_item.setCheckState(0, Qt.CheckState.Unchecked)
        qapp.processEvents()
        assert panel._layer_visibility[key0] is False
        assert panel._layer_visibility.get(key1, True) is True

    def test_weapon_spin_change_writes_dict_and_emits_modified(self, qapp):
        """图层树武器 x/y spin 修改必须写回 dict，并在 editingFinished 发 content_modified。"""
        panel, content, *_ = self._make_panel(qapp, weapons=[{"name": "炮", "x": 1.0, "y": 2.0}])
        spins = self._weapon_spins(panel)
        assert len(spins) == 2

        fired = []
        panel.content_modified.connect(lambda: fired.append(1))

        spins[0].setValue(6.5)
        qapp.processEvents()
        assert content.data["weapons"][0]["x"] == 6.5

        spins[1].setValue(-3.2)
        qapp.processEvents()
        assert content.data["weapons"][0]["y"] == -3.2

        spins[0].editingFinished.emit()
        qapp.processEvents()
        assert fired

    def test_subtype_visible_for_filters_layers(self, qapp, monkeypatch):
        """sprite_layers 的 visible_for 必须过滤不适用于当前子类型的图层。

        v0.2.6：配置键是类名 "UnitType"（normalize 后），visible_for 是游戏
        子类型值（"tank"/"legs"），subtype 用原始 data["type"]（游戏值）。
        """
        panel, *_ = self._make_panel(qapp, content_type="tank", weapons=[])
        monkeypatch.setattr(
            panel,
            "_sprite_layers_config",
            {
                "UnitType": [
                    {"suffix": "", "label": "主体", "required": True},
                    {"suffix": "-treads", "label": "履带", "visible_for": ["tank"]},
                    {"suffix": "-leg", "label": "腿", "visible_for": ["legs"]},
                ]
            },
        )
        panel._refresh_layer_tree()
        qapp.processEvents()

        texts = [it.text(0) for it in self._all_items(panel)]
        assert "履带" in texts
        assert "腿" not in texts

    def test_layer_status_marks_required_missing(self, qapp):
        """required 图层缺文件时列 1 应显示 [缺失]。"""
        panel, *_ = self._make_panel(qapp, weapons=[], make_main_sprite=False)
        main_item = self._find_by_text(panel, "主体")
        assert main_item is not None
        assert main_item.text(1) == "[缺失]"


class TestShadowZOrder:
    """shadow/outline 渲染层级回归（v0.2.5 修复）。

    背景：预览曾把所有图层 z 从 1 递增，阴影被画在主体之上（半透明黑盖住
    主体），用户验收"shadow 应位于底部区域"失败。修复 = -shadow z=-3、
    -outline z=-2，均低于主体 z=0。
    """

    def _make_panel_with_layers(self, qapp, suffixes: list[str]):
        """带指定后缀 png 的预览面板。"""
        from PySide6.QtGui import QColor, QImage

        from app.core.content_store import ContentData
        from app.core.project import Project

        import tempfile
        tmp = Path(tempfile.mkdtemp(prefix="moma_test_"))
        Project.create(tmp, "probe-mod", "探针模组")
        project = Project.open(tmp / "probe-mod")
        sprite_dir = project.sprites_dir / "units"
        sprite_dir.mkdir(parents=True, exist_ok=True)
        for suffix in ["", *suffixes]:
            img = QImage(8, 8, QImage.Format.Format_RGBA8888)
            img.fill(QColor(200, 80, 80, 255))
            assert img.save(str(sprite_dir / f"fly{suffix}.png"), "PNG")

        content = ContentData(name="fly", category="units", data={"type": "UnitType"})
        panel = PreviewPanel()
        panel.show_content(content, project)
        panel.show()
        qapp.processEvents()
        return panel

    def test_shadow_z_below_base(self, qapp):
        """-shadow 图层 z 值必须低于主体（z=0），不被画在主体上方。"""
        panel = self._make_panel_with_layers(qapp, ["-shadow"])
        items = panel._scene_items.get("-shadow", [])
        assert items, "应有 shadow 场景项"
        for it in items:
            assert it.zValue() < 0, f"shadow z 应为负（主体下），实际 {it.zValue()}"

    def test_outline_z_below_base(self, qapp):
        """-outline 图层 z 值必须低于主体（z=0）。"""
        panel = self._make_panel_with_layers(qapp, ["-outline"])
        items = panel._scene_items.get("-outline", [])
        assert items, "应有 outline 场景项"
        for it in items:
            assert it.zValue() < 0

    def test_regular_layer_above_base(self, qapp):
        """普通图层（如 -cell）仍在主体之上（z>0），不受影响。"""
        panel = self._make_panel_with_layers(qapp, ["-cell"])
        items = panel._scene_items.get("-cell", [])
        assert items
        for it in items:
            assert it.zValue() > 0
