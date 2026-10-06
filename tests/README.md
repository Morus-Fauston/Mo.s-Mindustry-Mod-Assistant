# 测试入口与证据边界

在仓库根目录运行完整回归：

```powershell
.venv\Scripts\python.exe -m pytest tests/ -q
```

本次保留现有测试路径，按用途导航：

| 测试层 | 示例 | 能证明的范围 |
| --- | --- | --- |
| 纯业务规则与文件读写 | `test_commands.py`、`test_project.py`、`test_research_model.py`、`test_preview_math.py` | 命令栈、序列化、引用规则和固定时刻预览计算 |
| 配置、元数据与样本契约 | `test_config_loader.py`、`test_metadata.py`、`test_sample_mod.py` | 配置加载、样本生成及与已审阅快照一致 |
| Qt 控件与场景行为 | `test_editor_panel.py`、`test_content_ref_selector.py`、`test_preview_panel.py` | 控件逻辑与场景接线；含离屏测试，需要 PySide6 |

完整 pytest 包含 Qt 测试，不能把整套测试视为纯 core 测试。离屏结果不证明 Windows11 下的实际点击热区、折叠、坐标变换或文字对齐；此类改动按 AGENTS 使用真实样式 probe，脚本用后删除。

样本快照由 [make_sample_mod.py](../tools/make_sample_mod.py) 生成，位于 [fixtures/baseline-mod](fixtures/baseline-mod/)。常规测试不自动更新快照。A4 完整环境验证不属于常规 pytest，通过条件与证据归档见本地私有 `Docs/工作流/验证反馈与贴图渲染缺口闭环工作流.md`。

历史验收结果只适用于记录的代码、环境和日期；当前测试结果与人工或原生环境确认分别报告。
