# Mo's Mindustry Mod Assistant (MoMA)

GUI 化的 Mindustry 模组编辑器，填表单、点按钮就能做 JSON content mod，不用手写代码。

给中文 Mindustry mod 社区的新手和中级作者用：不用懂 JSON 语法，不用记字段名，不用翻文档。

---

## 特性

- **零门槛**，不用懂 JSON 语法，填表单就能做 mod
- **不查文档**，每个字段自带中文注释和原版参考值，悬停即看
- **有校验**，输入格式错误及时反馈，可运行工程校验定位问题
- **有参照**，导入原版单位/方块对比数值，不用自己猜平衡性
- **有模板**，常用内容可从模板开始，实际行为仍需在游戏中确认

---

## 功能一览

| 功能 | 说明 |
|------|------|
| 工程管理 | 新建/打开 mod 工程，自动生成 `mod.json` 与目录结构 |
| 内容创建 | 单位（地面/飞行/坦克/腿）、八类方块、武器，模板一键生成 |
| JSON 源码编辑 | 表单与 JSON 源码切换；合法修改进入同一撤销历史，错误草稿不覆盖已生效结构 |
| 属性表单 | 配置驱动的分组折叠表单，字段按类型着色（马卡龙色系） |
| 字段注释 | 中文字段名 + 悬停说明 |
| 武器系统 | 引用/内联双模式，子弹多态编辑器（5 种子弹类型） |
| 精灵图预览 | 多图层叠放、缩放平移、图层导入/替换；动态模式可检查开火、方向、队伍色和血量 |
| 参考对比 | 导入原版或其他 mod，数值差异高亮 |
| 撤销/重做 | 全操作 Command Pattern，跨标签同步 |
| 输入与工程校验 | 输入错误就地反馈；“校验工程”生成问题报告，可定位支持的字段或源码位置 |
| 自动保存 | 保存所有已打开内容；默认间隔 180 秒，可在设置中调整，设为 0 可关闭 |
| 主题 | 浅色/深色双主题，即时切换 |

---

## 界面布局

```text
┌─────────────────────────────────────────────────────────────┐
│  菜单栏：文件 | 设置 | 关于                                  │
├─────────────────────────────────────────────────────────────┤
│  工具栏：打开工程 | 保存已打开内容 | 校验工程 | 导出模组      │
├──────────┬──────────────────────────────────┬───────────────┤
│          │  [my-soldier ×] [my-cannon ×]    │               │
│  文件树  │                                  │   预览区      │
│  (左边栏)│         编辑区                   │   (右边栏)    │
│  可折叠  │     (标签页 + 表单)              │   可折叠      │
│          │                                  │               │
│          │                                  ├───────────────┤
│          │                                  │  精灵图图层   │
│          │                                  │  (右边栏)     │
├──────────┴──────────────────────────────────┴───────────────┤
│  状态栏：验证状态 | 当前文件 | 游戏版本 v159.7               │
└─────────────────────────────────────────────────────────────┘
```

- 左边栏：工程文件树，按内容类型虚拟分组
- 中间：标签页编辑区，每个打开的 content 文件一个标签
- 右边栏上半：精灵图预览，支持滚轮缩放、拖动平移
- 右边栏下半：精灵图图层树，可导入/替换图层
- 状态栏：显示当前操作状态与游戏资料版本；校验问题在报告面板查看和定位

---

## 系统要求

- 便携目录包：Windows 10/11 x64 与 Microsoft Edge WebView2 Runtime；运行无需 Python、Node 或联网。
- 源码开发：Python 3.14、Node 24；已锁定的依赖和命令见 [Web 开发说明](frontend/README.md)。
- 目标游戏版本：随包离线元数据；本项目基线为 Mindustry v159.7。
- 当前为上半 UI 重构候选，最终验收状态与已知限制见 [发行使用说明](PACKAGE-GUIDE.md)。

---

## 安装与运行

便携用户解压完整目录后双击 `MoMA-Web.exe`，不要只复制 exe。缺 WebView2 时按 [发行使用说明](PACKAGE-GUIDE.md) 准备微软官方离线安装程序。

源码开发在仓库根目录运行：

```powershell
py -3.14 -m venv .venv-web
.venv-web/Scripts/python.exe -m pip install -r requirements-web.lock
.venv-web/Scripts/python.exe -m pip install --no-deps -e .
npm.cmd --prefix frontend ci
npm.cmd --prefix frontend run build
.venv-web/Scripts/python.exe run.py
```

完成准备后也可双击 `run.bat`。默认 `run.py` 与 `moma` 使用 React + pywebview/WebView2；运行时只读取随包静态资源和离线元数据。旧 Qt 仅供历史回退与测试：另建环境安装 `.[legacy-qt]` 后运行 `run_qt.py`，不进入新发行依赖。

---

## 快速上手

1. 启动 MoMA。
2. 在文件菜单或左侧选择“新建工程”，填写模组 ID、显示名称和作者，再通过系统对话框选择父目录。
3. 点击左侧“新建内容”，选择内容类别和模板并填写名称。
4. 在左侧文件树中打开内容文件，中间编辑区会显示表单。
5. 修改字段。每个字段都有中文名和悬停说明。
6. 如果有精灵图，可在右侧预览区导入 PNG 图层。
7. 按 `Ctrl+S` 保存所有已打开内容；需要检查工程问题时点击“校验工程”，在报告中查看和定位。
8. 将整个 mod 文件夹放入 Mindustry 的 mods 目录即可测试。

常用快捷键：

| 快捷键 | 功能 |
|------|------|
| `Ctrl+Shift+N` | 新建工程 |
| `Ctrl+O` | 打开工程 |
| `Ctrl+S` | 保存所有已打开内容 |
| `Ctrl+Q` | 退出 |

---

## 支持的内容类型

模板系统支持创建以下内容：

| 类型 | 说明 |
|------|------|
| `UnitType` | 地面单位 |
| `UnitType-flying` | 飞行单位 |
| `UnitType-tank` | 坦克单位 |
| `UnitType-legs` | 腿足单位 |
| `Wall` | 墙 |
| `ItemTurret` | 物品炮台 |
| `PowerTurret` | 电力炮台 |
| `Weapon` | 武器 |

武器可以引用已有武器，也可以内联定义。子弹支持 5 种常见 `BulletType` 子类型的多态编辑。

---

## 项目结构

```text
app/                    ← 主程序
├── desktop/            ← WebView2 宿主、桥接与编辑服务
├── main.py             ← 历史 Qt 入口实现
├── core/               ← 业务逻辑（纯 Python，无 Qt 依赖）
│   ├── project.py      ← 工程读写
│   ├── session.py      ← 会话管理（保存/验证/状态）
│   ├── form_plan.py    ← 表单渲染计划（配置→GroupPlan）
│   ├── template.py     ← 模板引擎
│   ├── validator.py    ← 实时验证
│   ├── commands.py     ← Command Pattern 撤销/重做
│   ├── metadata.py     ← 元数据加载
│   └── content_store.py← 内容文件读写
├── ui/                 ← 历史 Qt 界面层（PySide6）
│   ├── main_window.py  ← 主窗口
│   ├── editor_panel.py ← 编辑区（表单）
│   ├── file_tree.py    ← 文件树
│   ├── preview_panel.py← 精灵图预览
│   ├── theme.py        ← 主题令牌
│   ├── dialogs/        ← 对话框（新建/设置）
│   └── widgets/        ← 自定义控件
├── config/             ← 配置文件（字段分组/翻译/分类）
└── resources/          ← 历史 Qt 的 QSS 样式表

frontend/               ← React + TypeScript 界面与宿主验收脚本
run.py                  ← 默认 Web 桌面入口
run_qt.py               ← 历史 Qt 独立入口

metadata/               ← 游戏元数据（提取工具生成，已随仓库提供）
├── manifest.json       ← 总索引
├── classes/            ← 类字段定义
└── instances/          ← 原版内容实例值

extractor/              ← Java 元数据提取工具（一次性）
tests/                  ← Python 业务、桥接与历史 Qt 测试
```

---

## 配置说明

程序配置位于 `app/config/`：

| 文件 | 用途 |
|------|------|
| `field_groups.json` | 字段分组、字段可见性、默认字段配置 |
| `field_names_zh.json` | 字段中文显示名 |
| `field_docs.json` | 字段悬停说明文本 |
| `block_categories.json` | 方块分类配置 |
| `category_names_zh.json` | 分类中文名 |
| `sprite_layers.json` | 精灵图图层规则 |
| `settings_default.json` | 默认设置 |

---

## 元数据提取（可选）

`metadata/` 目录已随仓库提供。如需重新提取：

```bash
cd extractor
gradle run    # 需要 JDK 17+，首次构建从 JitPack 拉取 Mindustry 依赖
```

提取工具会通过 Java 反射读取 Mindustry 类结构，并输出：

- 类字段定义（`metadata/classes/`）
- 原版内容实例值（`metadata/instances/`）
- 总索引（`metadata/manifest.json`）

---

## 测试

完整 Python 测试包含历史 Qt 用例，须在安装了 `.[legacy-qt]` 与 pytest 的独立测试环境中运行；目录包构建环境仍保持无 Qt。

```powershell
python -m pytest tests/ -q
npm.cmd --prefix frontend run typecheck
npm.cmd --prefix frontend test
npm.cmd --prefix frontend run build
```

测试覆盖纯 Python 业务、桌面桥接、前端状态与历史 Qt 界面。Windows WebView2 实际宿主和发行包验收命令见 [Web 开发说明](frontend/README.md)；无头测试不能代替原生宿主验证。

---

## 开发约束

参与开发前注意以下规范：

- `app/core/` 不 import Qt，业务逻辑保持可测试
- 数据变更一律走 `CommandStack.execute()`，撤销/重做才一致
- 新 Web 界面使用集中 CSS 变量与 CSS Modules，字段类型用 `data-field-type`，错误标记用 `aria-invalid`，保留马卡龙饰条
- 历史 Qt 界面禁止内联 `setStyleSheet`，动态 hex 颜色值除外；字段类型用 QSS 属性选择器，如 `*[fieldType="num"]`，错误标记用 `[error="true"]`
- 界面纯中文，不用 emoji
- PowerShell 命令用 `;` 连接，不用 `&&`

---

## 常见问题

### 启动时提示「未找到游戏元数据」

确保 `metadata/` 目录位于仓库根目录，并且其中存在 `manifest.json`。

### 打开工程失败

检查目标 mod 文件夹中是否存在合法的 `mod.json`。MoMA 需要读取 mod 基本信息。

### 输入或工程校验出现错误

输入错误会在对应字段或源码处反馈；“校验工程”将生成问题报告，支持的问题可跳转到字段或源码位置。保存失败时修改仍保留，解除文件占用或权限问题后再试；保存成功不等于所有游戏行为已经验证。

### 精灵图预览没有显示

检查 PNG 文件名是否与内容文件名一致。Mindustry 的精灵图查找依赖文件名 stem，例如 `my-unit.json` 对应 `my-unit.png`。

---

## 技术栈

| 组件 | 技术 |
|------|------|
| 默认界面 | React + TypeScript；Python / pywebview + Windows WebView2 |
| 历史界面 | PySide6，仅通过 `legacy-qt` 可选依赖安装 |
| 图像处理 | Pillow |
| 元数据提取 | Java 17 / Gradle（反射 Mindustry 类） |
| 测试 | pytest、Vitest、Playwright 与 Windows 原生宿主验证 |

---

## 文档

- `CONTEXT.md`，术语表
- `CHANGELOG.md`，更新日志
- `extractor/README.md`，元数据提取工具说明

---

## 版本状态

当前版本：v0.3.0-alpha.5 候选。

工程管理、单位/八类方块/武器模板、配置驱动表单、JSON 输出预览、Research 对象编辑、武器与子弹编辑、动态精灵图预览、参考对比、撤销/重做、主题系统、实时验证均已可用。

候选验证包含可复现基线和厨房水槽样本；动态预览是 Demo，不包含机甲步行动画、多足 IK、粒子或连续旋转。

---

## 许可证

[MIT](LICENSE)
