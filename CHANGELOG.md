# Changelog

## v0.2.0 (2026-07-30 18:45)

### 架构改进

- **集中式配置加载（config_loader）**：新增 `app/core/config_loader.py`，统一管理所有 JSON 配置文件的加载、缓存和访问
  - 消除 `editor_panel.py`、`bullet_editor.py`、`weapon_array_editor.py`、`reference_panel.py` 四处重复的 `_load_field_names_zh` / `_load_field_docs` / `_display_name` 函数
  - 模块级缓存，配置文件只读一次
  - 提供 `reload_config()` / `clear_cache()` 用于测试和热更新
- **多态编辑器统一抽象（ADR-006）**：新增 `app/ui/widgets/polymorphic_editor.py`
  - 通用交互模式：类型下拉框 → 从 `field_groups.json` 读取字段组 → 渲染表单
  - 子弹、能力（v0.2.2）、单位子类型共用此组件
  - 新增多态类型只改 JSON 配置，不动代码
- **汉化数据外置**：`VANILLA_WEAPON_NAMES_ZH`（54 条）和 `CATEGORY_NAMES_ZH`（6 条）从 Python 代码迁移到 `app/config/vanilla_weapon_names_zh.json` 和 `app/config/category_names_zh.json`

### 新增

- **显示名模式四位一体**：`config_loader.display_name()` 支持 zh_en / en_zh / zh / en 四种模式，全局切换
- **子类型字段过滤（visible_for）**：`field_groups.json` 分组支持 `visible_for` 条件，坦克只显示坦克组，飞行只显示飞行组
- **字段默认值配置（defaults）**：分组内 `defaults` 键提供编辑器级默认值，添加字段不再全是 0
- **Color 字段调色盘**：颜色字段使用色块按钮 + QColorDialog，替代普通文本输入框
- **5 种 BulletType 子类完整分组**：`field_groups.json` 新增 BasicBulletType / LaserBulletType / MissileBulletType / ArtilleryBulletType / FlakBulletType 的字段分组（含 required / optional / defaults）
- **资源/科技控件接口**：新增 `app/ui/widgets/resource_editors.py`，定义 ResourceListEditor / ResourceSlotEditor / TechRefEditor 接口（v0.2.2 实现）
- **核心层测试**：新增 `tests/` 目录，49 个 pytest 测试覆盖 commands / config_loader / template

### 重构

- **BulletEditor 薄包装化**：从 200 行硬编码实现 → 80 行委托 `PolymorphicTypeEditor`，字段显示完全由 `field_groups.json` 驱动
- **WeaponCard 内联字段配置驱动**：移除硬编码的 14 个 `inline_fields`，改为从 Weapon 分组配置读取
- **WeaponCard 子弹子表单**：移除硬编码的 4 字段 + 类型下拉，改为嵌入 `BulletEditor`（→ `PolymorphicTypeEditor`）
- **reference_panel.py 去循环导入**：不再从 `weapon_array_editor` 导入 `VANILLA_WEAPON_NAMES_ZH`，改为直接调用 `config_loader`

### 文档

- 新增 ADR-006：多态编辑器统一抽象
- PRD 更新至 v1.1：P1 拆为 v0.2.0 / v0.2.1 / v0.2.2 三段（F-31~F-54）
- 设计规格文档更新至 v1.1：新增子类型过滤、默认值、字段删除规则、多态编辑器、视觉规范、验收标准 53 项
- CONTEXT.md 新增 7 个术语（Ability、保留字段、子类型、多态编辑器、资源列表、资源槽、字段类型着色、锁定组）
- 新增 `Docs/v021-UI设计需求书.md`：B 阶段 UI 设计完整需求

### 文件变更表

| 文件 | 变更 |
|:-----|:------|
| `app/core/config_loader.py` | **新增** — 集中配置加载 + 显示名模式 |
| `app/ui/widgets/polymorphic_editor.py` | **新增** — 多态编辑器通用组件 |
| `app/ui/widgets/resource_editors.py` | **新增** — 资源/科技控件接口 |
| `app/config/vanilla_weapon_names_zh.json` | **新增** — 原版武器汉化 |
| `app/config/category_names_zh.json` | **新增** — 分类汉化 |
| `tests/test_commands.py` | **新增** — 命令系统测试（19 项） |
| `tests/test_config_loader.py` | **新增** — 配置加载测试（20 项） |
| `tests/test_template.py` | **新增** — 模板引擎测试（10 项） |
| `app/ui/editor_panel.py` | 配置驱动 + visible_for + defaults + Color 调色盘 |
| `app/ui/widgets/bullet_editor.py` | 重写为 PolymorphicTypeEditor 薄包装 |
| `app/ui/widgets/weapon_array_editor.py` | 内联字段/子弹子表单配置驱动，汉化外置 |
| `app/ui/widgets/reference_panel.py` | 去循环导入，委托 config_loader |
| `app/config/field_groups.json` | +5 种 BulletType 子类分组 |
| `Docs/ADR/006-多态编辑器统一抽象.md` | **新增** |
| `Docs/v021-UI设计需求书.md` | **新增** |
| `Docs/PRD.md` | v1.1 更新 |
| `Docs/设计规格文档.md` | v1.1 更新 |
| `CONTEXT.md` | +7 术语 |
| `.gitignore` | +Nieobie icons/ |

---

## v0.1.2 (2026-07-30 02:07)

### 新增

- **武器数组编辑器（WeaponArrayEditor）**：单位表单中 `weapons` 字段的专用编辑组件
  - 每个武器显示为折叠卡片，支持 [+] 添加、[×] 删除
  - 引用/内联双模式，隐式判断（有 `bullet` 键 = 内联，否则 = 引用）
  - 引用模式：名称输入 + 可选覆盖字段（x/y/reload/top/rotate/mirror）+ [展开为内联]
  - 内联模式：武器字段 + 子弹子表单预览
  - 添加武器弹窗支持"引用已有"和"内联新建"两种方式
  - "展开为内联"自动从工程文件或原版元数据加载完整武器数据
- **子弹编辑器（BulletEditor）**：武器表单中 `bullet` 字段的内联编辑组件
  - 类型下拉选择（5 种：Basic / Laser / Missile / Artillery / Flak）
  - 显示常用子弹字段（damage / speed / lifetime 等）
  - 所有变更通过 CommandStack 支持撤销/重做
- **参考对比面板（ReferencePanel）**：工具 → 导入参考 → 选分类 → 选实例 → 并排对比表格
  - 表格列：字段 / 我的值 / 参考值，差异行黄色高亮
  - 数据源：`metadata/instances/`（含新增的 Weapons/ 分类）
- **撤销/重做 UI 接线**：工具栏新增撤销/重做按钮，状态跟随 `can_undo` / `can_redo`；菜单 Ctrl+Z / Ctrl+Y 同步更新
- **实时字段验证**：修改字段时即时检查类型，非法输入显示红色边框 + tooltip 错误信息；保存时状态栏显示错误计数
- **类型别名映射**：`PowerTurret`、`payload`、`tank`、`Liquid` 等 10 种无独立元数据类的 type 值自动映射到最近的父类
- **快速启动入口**：`run.bat` 双击启动，自动检测 venv
- **数组操作命令**：新增 `ArrayInsertCommand` / `ArrayRemoveCommand`，精确到单元素撤销

### 优化

- **字段分组更贴近 Mindustry 语义**：补充武器、子弹、移动方式、视觉与音效等默认分组规则，减少常见字段被归入“自定义字段”
- **编辑器交互体验提升**：武器/子弹子表单在同一界面内支持更自然的展开、收起、引用/内联切换，减少上下文切换
- **参考数据与实例覆盖更完整**：扩充 Weapons / BulletType 相关实例与分类数据，便于对比面板和类型解析更稳定地工作

### 提取工具 v1.1

- `ClassExtractor` 新增 5 个 BulletType 子类提取（Basic / Laser / Missile / Artillery / Flak）
- `InstanceExtractor` 新增原版武器实例提取（遍历所有 UnitType 的 weapons，递归序列化 Weapon + BulletType）
- 处理匿名子类（`getConcreteClassName` 向上遍历找到非匿名类名）
- 输出：17 个类定义（+5）、624 个实例（+54 Weapons）、6 个分类（+Weapons）

### 修复

- 武器模板缺少 `type` 字段，导致编辑面板无法加载类型定义
- 电力炮台（PowerTurret）无法加载类型定义（无独立元数据类）
- 武器引用模式下添加覆盖字段导致 KeyError（`_get_nested` 访问不存在键时崩溃）
- Undo 删除覆盖字段后键未被清理（新增 `_del_nested` + `_NOT_FOUND` 哨兵）
- 武器卡片 UI 重建时 Qt 布局清理不安全（改为临时 widget 托管旧布局）

### 文档

- 新增 ADR-005：武器编辑组件架构（专用组件 + 隐式引用/内联判断）
- 设计规格文档更新：武器编辑章节细化、元数据章节补充 Weapons 分类、ADR 表格新增 005
- CONTEXT.md 术语表更新：细化引用/内联定义，新增"覆盖字段"术语
- `.gitignore` 新增 `Mindustry-master/` 和 `run.bat`

---

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
