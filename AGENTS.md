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

## Skill 工作流

- 新功能或方向尚未收敛：`grill-with-docs`；重要事实无法快速确认时用 `research-brief` / `research`，复杂交互需要体验时用 `interaction-prototype-to-spec`。
- 结论经用户确认后：用 `decision-to-spec` 同步正式文档；需要阶段开发规划时用 `think`；用户明确要求实施后才用 `implement`，其中优先 TDD、持续测试并完成代码审查。
- 实施或修复完成后：单个改动用 `evidence-based-validation`，阶段或版本用 `phase-acceptance`，验收结论清楚且用户准备记录版本时用 `changelog-writer`。
- 报错、回归、失败测试或行为异常：直接用 `hunt`，修复后重新验证；不要先经过需求规划或阶段验收。
- 文档迁移、断链、旧路径或状态一致性：用 `docs-integrity-audit`；已确认决定未同步时再用 `decision-to-spec`。
- UI 风格需要定方向时用 `frontend-design`，用户确认方向并明确要求实现后用 `ui`；快速验证状态模型或 UI 方案用 `prototype`。
- 合并前审查 diff、PR 或发布准备用 `check`；固定基线的 Standards/Spec 双轴审查用 `code-review`。
- 创建、改造或评测 Skill 用 `skill-creator`；Skill 工作流更新用 `skill-workflow-visualizer`；Agent 指令、配置、MCP 或验证面漂移用 `health`。
- 完整的触发条件、人工关口和 Mermaid 图见 `Docs/工作流/Skill触发与协作工作流.md`；文字规则优先于图示。

## 测试与验证

- 改完跑 `pytest tests/ -q`，200+ 测试必须全绿。
- 改 padding/尺寸/对齐后，必须用 probe 脚本量所有输入控件的文本起点（不能只量一个）。
- 涉及点击热区、折叠交互、坐标变换的 UI 改动，offscreen 验不出，必须在 `windows11` 真机样式下 probe 验证。
- probe 脚本用完即删，不入库。

## 提交

- `app/config/settings.json` 和 `app/config/editor_state.json` 是本地运行时状态，已 gitignore，不要提交。
- `辅助项目/`、`Docs/`、`Mindustry-master/`、`Nieobie icons/` 均 gitignore，不入库。
- PowerShell 命令用 `;` 连接，不用 `&&`。

## Agent skills

### Issue tracker

开发票据保存在本仓库 `.scratch/` 下的本地 Markdown 文件中。详见 `docs/agents/issue-tracker.md`。

### Domain docs

本项目采用单上下文文档布局：术语在 `CONTEXT.md`，架构决策在 `Docs/ADR/`。详见 `docs/agents/domain.md`。
