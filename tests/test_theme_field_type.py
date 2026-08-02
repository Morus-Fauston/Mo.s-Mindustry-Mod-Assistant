"""统一 fieldType 推断函数（E-1 / ADR-012）测试。

验证 field_type_for_value(value, hint) 的推断表：
bool→bool / int→num / float→num / list→arr / dict→obj /
str 无 hint→str / str+"ref"→ref / str+"col"→col。
"""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from app.ui.theme import field_type_for_value


class TestFieldTypeForValue:
    def test_bool(self):
        assert field_type_for_value(True) == "bool"
        assert field_type_for_value(False) == "bool"

    def test_num(self):
        assert field_type_for_value(1) == "num"
        assert field_type_for_value(1.5) == "num"

    def test_arr(self):
        assert field_type_for_value([1, 2]) == "arr"
        assert field_type_for_value([]) == "arr"

    def test_obj(self):
        assert field_type_for_value({"a": 1}) == "obj"
        assert field_type_for_value({}) == "obj"

    def test_str_no_hint(self):
        assert field_type_for_value("copper") == "str"

    def test_str_ref_hint(self):
        assert field_type_for_value("copper", "ref") == "ref"

    def test_str_col_hint(self):
        assert field_type_for_value("#FFAABB", "col") == "col"

    def test_none_is_str(self):
        """None/未知类型按 str 兜底（无 hint 时）。"""
        assert field_type_for_value(None) == "str"

    def test_hint_ignored_for_non_str(self):
        """hint 只对 str 生效；list/dict 按值类型。"""
        assert field_type_for_value([], "ref") == "arr"
        assert field_type_for_value({}, "col") == "obj"
