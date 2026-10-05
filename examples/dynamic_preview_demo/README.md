# MoMA 动态预览示例

这个示例使用辅助项目中的真实参考模组 JSON 和 PNG，调用 MoMA 当前的 `Project`、`ContentData`、`PreviewPanel` API 展示动态预览。

## 启动

在仓库根目录执行：

```powershell
.venv\Scripts\python.exe examples\dynamic_preview_demo\run_demo.py
```

启动后可以在下拉框切换参考单位，然后在右侧动态预览中使用：

- 暂停帧 / 继续播放
- 开火一次
- 上、右、下、左方向
- 0.5x、1x、2x 速度
- 原地 / 移动
- 队伍色和血量

## 资源范围

脚本会扫描：

```text
辅助项目/参考模组/*/content/units/*.json
辅助项目/参考模组/*/sprites/units/{单位名}.png
```

当前能直接读取的标准 JSON 单位会自动出现在列表中。对应的 `-cell`、`-full`、`-base`、`-leg`、`-treads` 等同名图层如果存在，也会一并复制到临时展示工程。

示例不会修改参考模组。每次切换单位时，资源会复制到临时目录；关闭窗口后临时目录自动删除。

`mod.hjson` 或只有编译产物而没有 `content/units/*.json` 的参考包不会自动列入列表，因为 MoMA 当前 `ContentStore` 的公开读取入口是 JSON。

## 复用的 MoMA API

```python
project = Project.create(temp_root, "dynamic-preview-demo", "动态预览示例")
content = ContentData(name, "units", data, path)
preview = PreviewPanel()
preview.show_content(content, project)
```
