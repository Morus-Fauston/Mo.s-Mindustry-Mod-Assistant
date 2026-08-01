# AGENTS.md

本文件列出"违反即返工"的硬约束。术语见 `CONTEXT.md`。

## 架构

- `app/core/` 禁止 import Qt（PySide6）。业务逻辑必须可脱离 GUI 独立测试。
- 所有数据变更通过 `CommandStack.execute()`，保证撤销/重做一致。禁止绕过命令栈直接改数据。

## 样式

- 禁止内联 `setStyleSheet`。唯一直例外：动态 hex 颜色值。
- 字段类型着色走 QSS 属性选择器 `*[fieldType="num"]`，不在代码里硬编码颜色。
- 验证错误标记用 `[error="true"]` 属性，由 QSS 统一渲染红色。

## 界面

- 纯中文界面，禁 emoji。
- 字段显示名来自 `app/config/field_names_zh.json`，提示文本来自 `app/config/field_docs.json`，不在代码里硬编码字符串。

## 测试与验证

- 改完跑 `pytest tests/ -q`，200+ 测试必须全绿。
- 改 padding/尺寸/对齐后，必须用 probe 脚本量所有输入控件的文本起点（不能只量一个）。
- 涉及点击热区、折叠交互、坐标变换的 UI 改动，offscreen 验不出，必须在 `windows11` 真机样式下 probe 验证。
- probe 脚本用完即删，不入库。

## 提交

- `app/config/settings.json` 和 `app/config/editor_state.json` 是本地运行时状态，已 gitignore，不要提交。
- `蓝钢-欢迎您/`、`Docs/`、`Mindustry-master/`、`Nieobie icons/` 均 gitignore，不入库。
- PowerShell 命令用 `;` 连接，不用 `&&`。
