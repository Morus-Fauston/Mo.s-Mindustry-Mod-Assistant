# Changelog

## v0.1.1 (2026-07-29)

### 新增

- 单位模板支持 4 种移动方式：地面（双足）、飞行、坦克（履带）、多足（蜘蛛）
- 方块模板新增电力炮台（PowerTurret），含 shootType 和 consumes 字段
- 物品炮台模板自带 ammoTypes 示例（copper → BasicBulletType）
- 墙模板自带 requirements 和 category 字段
- 武器模板增加 mirror、alternate、bullet width/height 字段
- 方块文件树虚拟分组扩展至 7 大类 22 小类（炮台/防御/生产/分配/电力/液体/单位）
- 精灵图图层配置新增：履带（-treads）、腿（-leg）、队伍色（-team）、武器热发光（-heat）
- 编辑面板新增分组：容量与建造、坦克特性、飞行引擎、技能、研究树与说明、射击模式、消耗、音效与特效
- 新建单位弹窗支持选择移动方式（地面/飞行/坦克/多足）

### 修改

- 新建方块弹窗增加电力炮台选项
- 字段分组配置基于真实 mod 写法（蓝钢工业 v3.8）重新整理
- 模板默认值改为硬编码合理数值（提取器读出的 0 值不再被采用）

### 修复

- Metadata 构造函数接受字符串路径（之前只接受 Path 对象导致 TypeError）
- 验证器过滤内部引擎字段（Region、Sound、Effect、Controller 等），消除 50+ 条误报

---

## v0.1.0 (2026-07-29 03:40)

### 新增

- **Java 元数据提取工具**：通过反射从 Mindustry v159 中提取类定义和原版实例数据，输出结构化 JSON 目录
  - 提取 12 个类定义（含完整继承链：Content → UnlockableContent → UnitType / Block / Weapon / BulletType 等）
  - 提取 570 个原版实例（68 单位、446 方块、22 物品、11 液体、23 状态效果）
  - 支持 headless 模式运行，无需启动游戏窗口
- **Python 主程序骨架**：基于 PySide6 的 IDE 式 GUI 编辑器
  - 主窗口：菜单栏 + 工具栏 + 左边栏（文件树）+ 中间（标签页编辑区）+ 右边栏（预览 + 图层树）
  - 文件树：两级虚拟分组（炮台/防御 → 物品炮台/墙），配置驱动
  - 编辑面板：根据元数据自动生成属性表单，按分组折叠显示
  - 预览面板：静态精灵图叠放 + 图层管理树 + 导入按钮
  - 新建工程/单位/方块/武器弹窗
- **Core 逻辑层**（纯 Python，不依赖 Qt）
  - `metadata.py`：懒加载元数据访问（3 方法接口）
  - `commands.py`：Command Pattern 撤销/重做（支持连续编辑合并）
  - `project.py` + `content_store.py`：工程管理与原子写入
  - `validator.py`：三层验证（field / content / project），自动过滤引擎内部字段
  - `template.py`：最小可运行模板生成（默认值从元数据读取）
- **字段中文化**：100+ 字段汉化，显示格式为"中文 (英文)"
- **字段自由添加**：每个分组右上角"+"按钮，弹出可用字段菜单，按需加入表单
- **配置文件体系**：field_groups / block_categories / sprite_layers / field_names_zh / settings_default

### 架构改进

- **深模块设计**：core 层对外仅 12 个方法，UI 层通过信号槽解耦
- **接缝隔离**：元数据接缝（Java ↔ Python）、磁盘接缝（ContentStore）、命令接缝（CommandStack）
- **配置驱动**：分组、分类、图层变体、字段汉化全部外置 JSON，改配置不动代码

### 文件变更表

| 文件 | 变更 |
|:-----|:------|
| `extractor/` | **新增** — Java 提取工具（Gradle 项目，4 个源文件） |
| `metadata/` | **新增** — 提取工具输出（manifest + 12 类定义 + 570 实例） |
| `app/main.py` | **新增** — 程序入口，检测 metadata 后启动主窗口 |
| `app/core/metadata.py` | **新增** — 元数据查询层（懒加载 + 继承链合并） |
| `app/core/commands.py` | **新增** — Command Pattern 基础设施 |
| `app/core/project.py` | **新增** — 工程打开/创建 |
| `app/core/content_store.py` | **新增** — Content 文件读写（原子写入） |
| `app/core/validator.py` | **新增** — 统一验证引擎 |
| `app/core/template.py` | **新增** — 模板生成 |
| `app/ui/main_window.py` | **新增** — 主窗口（菜单/工具栏/边栏/标签页） |
| `app/ui/file_tree.py` | **新增** — 文件树（两级虚拟分组） |
| `app/ui/editor_panel.py` | **新增** — 属性表单（分组折叠 + 字段添加菜单） |
| `app/ui/preview_panel.py` | **新增** — 精灵图预览 + 图层树 |
| `app/ui/dialogs/` | **新增** — 新建工程/方块弹窗 |
| `app/config/*.json` | **新增** — 5 个配置文件 |
| `pyproject.toml` | **新增** — 项目配置（PySide6 + Pillow） |
| `.gitignore` | 修改 — 忽略 Docs/、extractor 构建产物 |
