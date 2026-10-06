# 开发工具入口

| 工具 | 用途 | 版本控制边界 |
| --- | --- | --- |
| [make_sample_mod.py](make_sample_mod.py) | 经 MoMA core 生成基线与厨房水槽样本；校验或显式更新基线快照 | 正式可复现生成器，随 Git 提供 |
| [extract_content_names.py](extract_content_names.py) | 从官方中文 bundle 提取内容名称表 | 随 Git 提供；需要本地 Mindustry 源码 |
| `draw_ui_mockups.py` | 本地 SVG 界面示意图生成工具 | 被忽略，不随公开克隆提供；默认输出到私有 Docs |

从仓库根目录运行：

```powershell
.venv\Scripts\python.exe tools/make_sample_mod.py --sample baseline
.venv\Scripts\python.exe tools/make_sample_mod.py --sample kitchen-sink --output sample-mod-output/kitchen-sink
```

生成器默认工作输出在 `sample-mod-output/`；基线快照在 `tests/fixtures/baseline-mod/`。只有明确需要更新输出契约时使用 `--update-baseline`，并审查快照差异。样本生成成功不代表真实引擎验证通过。

Java 元数据工具保持独立，见 [extractor](../extractor/README.md)。测试入口见 [tests](../tests/README.md)。完整环境验证规则和证据位于本地私有 `Docs/工作流/` 与 `Docs/验证反馈/`，需要另行交接。
