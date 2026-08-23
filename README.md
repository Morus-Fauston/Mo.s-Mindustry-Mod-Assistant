# Mo's Mindustry Mod Assistant (MoMA)

GUI 化的 Mindustry 模组编辑器，填表单、点按钮就能做 JSON content mod，不用手写代码。

给中文 Mindustry mod 社区的新手和中级作者用：不用懂 JSON 语法，不用记字段名，不用翻文档。

---

## 特性

- **零门槛**，不用懂 JSON 语法，填表单就能做 mod
- **不查文档**，每个字段自带中文注释和原版参考值，悬停即看
- **不出错**，实时验证，非法输入直接屏蔽，引用不存在立刻标红
- **有参照**，导入原版单位/方块对比数值，不用自己猜平衡性
- **能跑通**，模板保证新建的 mod 能被游戏加载

---

## 功能一览

| 功能 | 说明 |
|------|------|
| 工程管理 | 新建/打开 mod 工程，自动生成 `mod.json` 与目录结构 |
| 内容创建 | 单位（地面/飞行/坦克/腿）、八类方块、武器，模板一键生成 |
| JSON 输出预览 | 表单与 JSON 预览切换；合法修改 500ms 后可撤销回写，错误草稿不污染工程 |
| 属性表单 | 配置驱动的分组折叠表单，字段按类型着色（马卡龙色系） |
| 字段注释 | 中文字段名 + 悬停说明 |
| 武器系统 | 引用/内联双模式，子弹多态编辑器（5 种子弹类型） |
| 精灵图预览 | 多图层叠放、缩放平移、图层导入/替换；动态模式可检查开火、方向、队伍色和血量 |
| 参考对比 | 导入原版或其他 mod，数值差异高亮 |
| 撤销/重做 | 全操作 Command Pattern，跨标签同步 |
| 实时验证 | 保存时验证，状态栏错误计数，点击可跳转到错误字段；不生效字段保留值并给出 Warning |
| 自动保存 | 固定每 3 分钟自动保存已打开工程 |
| 主题 | 浅色/深色双主题，即时切换 |

---

## 界面布局

```text
┌─────────────────────────────────────────────────────────────┐
│  菜单栏：文件 | 编辑 | 设置 | 工具 | 帮助                    │
├─────────────────────────────────────────────────────────────┤
│  工具栏：[+ 单位] [+ 方块] [+ 武器] | [保存] [撤销] [重做]  │
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
- 状态栏：显示保存状态、验证错误数量，错误可点击跳转

---

## 系统要求

- Python 3.11+
- Windows 10/11（主要目标平台）
- 目标游戏版本：Mindustry v159.7

---

## 安装与运行

```powershell
# 1. 克隆仓库
git clone https://github.com/Morus-Fauston/Mo.s-Mindustry-Mod-Assistant.git
cd Mo.s-Mindustry-Mod-Assistant

# 2. 创建虚拟环境并安装
python -m venv .venv
.venv\Scripts\pip install -e .

# 3. 启动
.venv\Scripts\python -m app.main
```

或直接双击 `run.bat`（需先完成步骤 2）。

程序启动时会自动查找仓库内的 `metadata/` 目录，该目录已随仓库提供，通常不用额外生成。

---

## 快速上手

1. 启动 MoMA。
2. 在欢迎页选择「新建工程」，填写 mod ID、名称和保存路径。
3. 使用工具栏的「+ 单位」「+ 方块」「+ 武器」创建内容。
4. 在左侧文件树中打开内容文件，右侧编辑区会显示表单。
5. 修改字段。每个字段都有中文名和悬停说明。
6. 如果有精灵图，可在右侧预览区导入 PNG 图层。
7. 按 `Ctrl+S` 保存。保存时会自动验证，错误会显示在状态栏。
8. 将整个 mod 文件夹放入 Mindustry 的 mods 目录即可测试。

常用快捷键：

| 快捷键 | 功能 |
|------|------|
| `Ctrl+Shift+N` | 新建工程 |
| `Ctrl+O` | 打开工程 |
| `Ctrl+S` | 保存 |
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
├── main.py             ← 入口
├── core/               ← 业务逻辑（纯 Python，无 Qt 依赖）
│   ├── project.py      ← 工程读写
│   ├── session.py      ← 会话管理（保存/验证/状态）
│   ├── form_plan.py    ← 表单渲染计划（配置→GroupPlan）
│   ├── template.py     ← 模板引擎
│   ├── validator.py    ← 实时验证
│   ├── commands.py     ← Command Pattern 撤销/重做
│   ├── metadata.py     ← 元数据加载
│   └── content_store.py← 内容文件读写
├── ui/                 ← 界面层（PySide6）
│   ├── main_window.py  ← 主窗口
│   ├── editor_panel.py ← 编辑区（表单）
│   ├── file_tree.py    ← 文件树
│   ├── preview_panel.py← 精灵图预览
│   ├── theme.py        ← 主题令牌
│   ├── dialogs/        ← 对话框（新建/设置）
│   └── widgets/        ← 自定义控件
├── config/             ← 配置文件（字段分组/翻译/分类）
└── resources/          ← QSS 样式表

metadata/               ← 游戏元数据（提取工具生成，已随仓库提供）
├── manifest.json       ← 总索引
├── classes/            ← 类字段定义
└── instances/          ← 原版内容实例值

extractor/              ← Java 元数据提取工具（一次性）
tests/                  ← pytest 测试（200+）
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

```powershell
pytest tests/ -q
```

测试覆盖 core 层的命令栈、配置加载、模板、验证器、元数据、工程读写、会话和表单计划。core 层不依赖 Qt，跑完约 1 秒。

---

## 开发约束

参与开发前注意以下规范：

- `app/core/` 不 import Qt，业务逻辑保持可测试
- 数据变更一律走 `CommandStack.execute()`，撤销/重做才一致
- 禁止内联 `setStyleSheet`，样式走 QSS 和主题令牌
- 字段类型着色用 QSS 属性选择器，比如 `*[fieldType="num"]`
- 验证错误标记用 `[error="true"]` 属性
- 界面纯中文，不用 emoji
- PowerShell 命令用 `;` 连接，不用 `&&`

---

## 常见问题

### 启动时提示「未找到游戏元数据」

确保 `metadata/` 目录位于仓库根目录，并且其中存在 `manifest.json`。

### 打开工程失败

检查目标 mod 文件夹中是否存在合法的 `mod.json`。MoMA 需要读取 mod 基本信息。

### 保存后出现验证错误

状态栏会显示错误数量。点击错误提示可跳转到第一个错误字段。字段变红表示该字段存在必填缺失、类型错误或引用无效等问题。

### 精灵图预览没有显示

检查 PNG 文件名是否与内容文件名一致。Mindustry 的精灵图查找依赖文件名 stem，例如 `my-unit.json` 对应 `my-unit.png`。

---

## 技术栈

| 组件 | 技术 |
|------|------|
| GUI | Python 3.11+ / PySide6 |
| 图像处理 | Pillow |
| 元数据提取 | Java 17 / Gradle（反射 Mindustry 类） |
| 测试 | pytest |

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
