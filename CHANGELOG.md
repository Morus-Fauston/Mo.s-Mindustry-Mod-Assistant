# Changelog

## v0.3.0-alpha.5 (2026-08-23 23:10) - 批次 4：字段依赖、动态预览与候选验收

### 新增

- **字段依赖反馈**：以配置声明五条已证实规则；表单禁用不生效字段并显示警告，Validator 对已写入的无效前置组合给出可定位 Warning，原 JSON 值保持不变。
- **动态预览 Demo**：新增无 Qt 动画状态、播放/暂停、开火、四向朝向、三档速度、移动、队伍色和血量控制；支持引擎与 cell 脉动、武器后坐、热图、枪口闪光及存在帧图时的坦克履带切换。
- **厨房水槽样本**：样本生成器可独立输出四类单位、八类方块、内联武器、五种工程 Weapon 引用、资源重命名与 outline/shadow/full 派生图。

### 调整

- **候选版本信息**：README 和 Python 包版本同步为 v0.3.0-alpha.5 候选状态。

### 验证

- **自动与原生交互**：`pytest tests/ -q` 共 452 项通过；Windows 原生 probe 确认动态控件热区、方向变换、队伍色和血量场景效果。
- **真实引擎 A4**：厨房水槽 9 方块与 9 单位、基线 1 方块与 1 单位均在 Mindustry 159.7 完成 600 tick，`ERROR = 0`；33 条新样本 Warning 与 34 条基线 Warning 均归档研判。

---

## v0.3.0-alpha.4 (2026-08-23 21:50) - 批次 3：Research、统一内容选择器与字段组整理

### 新增

- **Research 对象编辑**：兼容旧字符串写法和七字段对象写法；常用的前置、需求、目标直接编辑，星球、根节点、名称和解锁条件按需展开，全部变更通过命令栈支持撤销/重做。
- **统一内容选择器**：引用控件、Research 目标和武器引用复用同一双语选择器；支持分类、空结果、键盘确认及不挤占列表的双向浮动书签导航，保存始终使用英文标识符。
- **真实星球与战区候选**：元数据新增 7 个 Planets、95 个 SectorPresets 及对应中文名；五种 objective 分别限定可解锁内容、战区或星球。

### 调整

- **科技树与星球范围**：所有已支持内容类型将 `research` 迁入统一科技树组；`shownPlanets` 进入基础属性，以专用星球集合编辑器和校验约束数组内容。
- **UnitType 战斗分组**：原 `combat` 拆分为武器与射程、目标选择、攻击行为三个组，按新组默认状态显示，不迁移旧折叠状态。

### 验证

- **自动与原生交互**：`pytest tests/ -q` 共 440 项通过；Windows Qt 原生探针确认选择器点击热区、双向书签、低频展开和星球集合写入。
- **真实引擎 A4**：Research、Produce、SectorComplete、OnSector、OnPlanet 及 `shownPlanets` 在 Mindustry 159.7 中加载并运行 600 tick，`ERROR = 0`；14 条既有 Warning 已关联研判。

---

## v0.3.0-alpha.3 (2026-08-23 20:52) - 批次 2：输出预览与可撤销 JSON 回写

### 新增

- **输出预览编辑**：编辑器在表单与 JSON 视图间切换；JSON 初值直接来自内存内容的标准序列化，停止输入 500ms 后才处理合法草稿。
- **完整结构命令**：新增无 Qt 的 `ReplaceDataCommand` 与 JSON 草稿模块；整体替换保持共享 data 引用，支持撤销/重做、格式化与嵌套问题路径定位。
- **安全的错误草稿**：无效 JSON 保留在编辑器中并显示独立错误态，不进入命令栈、不污染表单数据或磁盘；合法 JSON 的 Error/Warning 可从问题列表跳到字段行。

### 修复

- **撤销/重做类型同步**：完整 JSON 替换改变 `type` 后，编辑器刷新时同步元数据类型并重建正确表单；补齐深浅主题的警告色令牌，避免 QSS 留下未替换占位符。

### 验证

- **自动回归**：`pytest tests/ -q` 共 421 项通过，覆盖整体替换、非法草稿隔离、格式化、真实列表点击定位、类型回退刷新和主题令牌解析。
- **真实界面与引擎**：Windows11 原生样式 probe 确认表单/JSON/格式化热区可点击；合法 JSON 回写后的 A4 复验 `ERROR = 0`，墙放置与 mech AI 各 600 tick 通过，34 条既有 Warning 已有逐项研判。

---

## v0.3.0-alpha.2 (2026-08-23 20:19) - 批次 1：跨平台快照修复

### 修复

- **Ubuntu CI 基线快照失败**：现象 → GitHub Actions 重新生成最小样本时 PNG SHA-256 与 Windows 审阅快照不同；根因 → Pillow 的平台 PNG/zlib 编码流不保证字节一致；修复 → `save_sprite()` 固定写入 RGBA、无过滤行与未压缩 deflate 块的规范 PNG，使同一像素输入跨平台得到相同文件字节。

### 验证

- **回归保护**：新增固定 2x2 RGBA 输入的已知 PNG SHA-256 断言；基线两张 PNG 仅重新编码，像素尺寸、模式和非透明边界未变。
- **自动与真实引擎**：`pytest tests/ -q` 共 406 项通过；Windows GPU A4 复验 `ERROR = 0`，墙放置与 mech AI 各 600 tick 通过，34 条既有 Warning 已在本地 `Docs/验证反馈/v0.3.0-003/` 关联研判。

---

## v0.3.0-alpha.1 (2026-08-23 20:01) - 批次 1：可信输出基础

### 新增

- **统一 PNG 写盘 API**：新增无 Qt 依赖的 `import_sprite()` 与 `save_sprite()`；真实 PNG 导入保持原始字节，默认拒绝覆盖，调用方必须显式授权覆盖。
- **最小基线模组**：生成器通过 Project、模板、ContentStore 与 PNG core API 产出一面墙、一个 mech、内联基础子弹及两张固定 PNG；快照严格比较文件清单、JSON 文本和 PNG SHA-256。

### 调整

- **预览精灵图流程**：导入、outline、shadow 与 full 写盘统一复用 core API；覆盖已有图层前要求确认，写入使用同目录临时文件后原子替换，失败不损坏旧图。
- **基线快照更新**：仅 `--update-baseline` 能替换审阅快照；先在同级临时目录复制与校验，切换失败自动保留旧快照。

### 验证

- **自动测试**：405 项 pytest 全绿，覆盖 PNG 格式与覆盖契约、原子写入失败保护、可重复生成，以及快照的文件清单、JSON 和 PNG 漂移检测。
- **真实引擎 A4**：Windows GPU 环境加载 `moma-baseline.zip` 成功，墙放置与 mech AI 各运行 600 tick，`ERROR = 0`；34 条运行时默认字段 Warning 已在本地 `Docs/验证反馈/v0.3.0-002/` 逐条研判。

### 文件变更表

| 文件 | 变更 |
|:-----|:------|
| `app/core/sprite_io.py` | **新增** - 可复用、原子化的 PNG 导入与写盘 API |
| `app/ui/preview_panel.py` | 修改 - 预览导入与派生图写盘接入 core API |
| `tools/make_sample_mod.py` | 重写 - 可重复的基线生成、快照比较与显式更新 |
| `tests/test_sprite_io.py` | **新增** - PNG API 与失败保护回归测试 |
| `tests/test_sample_mod.py` | **新增** - 基线输出与快照契约测试 |
| `tests/fixtures/baseline-mod/` | **新增** - 生成器产出的审阅快照 |

---

## v0.2.6.revised.2 (2026-08-02 22:18) — 修复单位 type 不被游戏识别（致命）

> 用户实测：用 MoMA 生成的示例模组导入游戏，所有单位报错 `Invalid unit type: 'UnitType'`。根因是单位模板把 `type` 字段写成 Java 类名 `UnitType`，而游戏解析单位时 `type` 必须是实体子类型字符串（flying/mech/legs/tank/naval/payload/missile/tether/crawl）——游戏源码 `ContentParser.unitType()` 的 switch 里没有 `UnitType`。方块/武器的 `type` 是类名、正确，只有单位特殊。顺带修复验证器把内联武器误报为「引用不存在」。

### 修复

- **单位 type 字段游戏不认（致命）**：现象 → 新建任何单位导入游戏全部报 `Invalid unit type: 'UnitType'`；根因 → `app/core/template.py` 四个单位模板把 `type` 写死为 `UnitType`（Java 类名），游戏单位 `type` 必须是实体子类型字符串；修复 → 模板写入游戏值：地面 `mech` / 飞行 `flying` / 坦克 `tank` / 多足 `legs`
- **编辑器兼容子类型 type**：MoMA 内部多处用 `data["type"]` 查配置（键是类名 `UnitType`），直接改成子类型会让编辑器查空 → `metadata.py` 新增 `normalize_content_type()`（子类型→`UnitType`）统一收敛，`form_plan.py` 的 `infer_subtype` 识别游戏子类型字符串，`editor_panel`/`preview_panel` 查 field_groups/sprite_layers 前规范化（图层 visible_for 过滤仍用原始游戏值）
- **验证器内联武器误报**：内联武器（含 `bullet` 键的完整定义）带 name 是合法标识，`_check_weapon_refs` 却当外部引用检查 → 报「武器引用不存在」；修复 = 含 bullet 键的条目跳过引用检查（只查纯引用模式）

### 技术

- **metadata 子类型别名补全**：`_TYPE_ALIASES` 新增 `flying`/`missile`/`tether`/`crawl`（此前只有 mech/tank/legs/payload/naval/hover/crawler），`get_class("mech")` 等映射回 `UnitType` 类定义

### 验证

- 388 测试全绿（+1 内联武器回归测试；测试 helper 改为按 `ROLE_WEAPON_INDEX` 定位武器行，不受图层生成按钮干扰）
- 示例模组重新打包：单位 type = flying/mech/tank，validator 0 问题，offscreen 冒烟编辑器正常渲染所有内容

### 文件变更表

| 文件 | 变更 |
|:-----|:------|
| `app/core/template.py` | 修改 — 单位模板 type 改为游戏子类型值（mech/flying/tank/legs） |
| `app/core/metadata.py` | 修改 — 新增 `normalize_content_type()` + 子类型别名补全 |
| `app/core/form_plan.py` | 修改 — content_type 规范化 + infer_subtype 识别子类型 |
| `app/ui/editor_panel.py` | 修改 — 6 处 field_groups 查询规范化 |
| `app/ui/preview_panel.py` | 修改 — 图层配置查询规范化 |
| `app/core/validator.py` | 修改 — 内联武器跳过引用检查 |
| `.gitignore` | 修改 — 忽略生成脚本与示例模组输出 |
| `tests/*` | 修改 — 断言更新 + 内联武器回归测试 + helper 修复 |

---

## 特殊更新 (2026-08-02 18:23) — 新增 CI 自动化测试

> 工程基础设施更新，不计入软件版本号（不影响软件功能）。首次引入 GitHub Actions：每次 push 到 main 或提交 PR 时，云端自动跑全部 386 个测试。真机验证仍是人工流程（offscreen 验不出观感），CI 负责单元测试层。

### 新增

- **CI 自动化测试**：新增 `.github/workflows/ci.yml`——Ubuntu 无头环境装 PySide6 所需系统库（libegl1/libgl1/libxkbcommon0/libdbus），`pip install -e .` 后以 `QT_QPA_PLATFORM=offscreen` 跑 `pytest tests/ -q`
  - push 到 main 或 PR 时自动触发
  - 测试数据源 `metadata/`（665 文件）已入库，clone 即可跑

### 文件变更表

| 文件 | 变更 |
|:-----|:------|
| `.github/workflows/ci.yml` | **新增** — GitHub Actions 自动测试工作流 |

---

## v0.2.6.revised.1 (2026-08-02 17:57) — 修复打包后 exe 崩溃（相对导入）

> 用户实测：打包出的 MoMA.exe 双击即弹「Failed to execute script 'main'」。根因是 PyInstaller 把 `app/main.py` 当独立脚本执行，其内部相对导入（`from .ui.main_window import ...`）失效。新增顶层入口 `run.py` 解决，并放行 `moma.spec` 入库。

### 修复

- **打包后 exe 立即崩溃**：`moma.spec` 入口是 `app/main.py`，打包运行时被当顶层脚本（`__package__` 为空）→ 相对导入报 `attempted relative import with no known parent package`。新增 `run.py` 顶层入口（`from app.main import main`），spec 改为指向 `run.py`，`app` 恢复包方式导入

### 技术

- **`moma.spec` 入库**：`.gitignore` 有 `*.spec` 规则导致打包配置从未进 git，clone 源码无法复现打包。新增 `!moma.spec` 例外放行
- **`run.py` 入库**：打包专用入口，含注释说明为何不能直接用 `app/main.py` 作入口

### 验证

- 重新打包成功：`dist/MoMA.exe`（52MB，<150MB 达标）
- 启动 8 秒进程存活无崩溃（旧版瞬间弹错退出）
- `pyi-archive_viewer` 确认 exe 内含 `run` 入口 + metadata/config/resources 数据完整

### 文件变更表

| 文件 | 变更 |
|:-----|:------|
| `run.py` | **新增** — 打包顶层入口（修复相对导入崩溃） |
| `moma.spec` | **新增** — PyInstaller 配置（入口改 run.py，入库） |
| `.gitignore` | 修改 — 放行 moma.spec（`!moma.spec`） |

---

## v0.2.6.revised (2026-08-02 17:46) — 修复参考面板关闭 + 新增导出 Mod

> 用户实测反馈两个问题：参考对比面板没有关闭按钮、工程缺少导出功能。本次修复 dock 特性并新增「导出 Mod」打包功能。测试 383 → 386 全绿。

### 修复

- **参考面板无法关闭**：参考对比 dock 设置了 `NoDockWidgetFeatures`（禁止全部特性，连关闭按钮都没有）→ 改为 `DockWidgetClosable`，保留关闭按钮、仍禁止浮动/移动/停靠（固定右栏）

### 新增

- **导出 Mod（F-55）**：文件菜单「保存」下新增「导出 Mod...」——把整个工程打包为 Mindustry 可导入的 zip（`mod.json` 位于压缩包根目录，覆盖 content/sprites/scripts/maps 等全部文件，自动跳过 `.git`/`__pycache__`/隐藏文件）
  - 打开工程时启用、关闭工程时禁用
  - 导出前自动保存未落盘修改，避免打包旧数据
  - 完成后右下角 toast 提示，导出失败弹窗报错

### 测试（383 → 386 全绿）

- **`test_project.py`**（+3）：zip 含 mod.json 与 content / 跳过隐藏目录 / 空工程打包

### 文件变更表

| 文件 | 变更 |
|:-----|:------|
| `app/core/project.py` | **新增** — `Project.export_zip()` 打包逻辑（F-55） |
| `app/ui/main_window.py` | 修改 — 导出菜单项 + 启用/禁用接线 + 参考 dock 关闭按钮 |
| `tests/test_project.py` | 修改 — +3 导出测试 |

---

## v0.2.6 (2026-08-02 17:40) — 工程化三件套：文件监听 + 全量验证 + 外部参考 + 渲染统一

> v0.2.6 是「工程化」版本：让编辑器从单方块编辑走向工程级工作流——精灵图改动自动刷新预览、一键校验整个项目、可从外部 mod 导入参考对照；同时把字段渲染统一成单一推断函数 + 复合字段色条容器，并完成 PyInstaller 打包的路径基建。测试从 327 → 383 全绿。

### 新增

- **精灵图文件监听（F-21）**：新增 `sprite_watcher.py`（递归监听工程 `sprites/`，300ms 防抖合并）。新建/打开/恢复工程自动开始监听，关闭工程停止；当前 content 精灵图被外部修改 → 自动刷新预览，目录结构变化（增删文件）→ 刷新图层树
- **项目级全量验证（F-51）**：`validator.py` 新增 `validate_project()`——检查 mod.json（存在/可解析/name 合法）、每个 content JSON 可解析 + type 存在、同分类重名、武器引用存在、requirements 物品存在、精灵图缺失，error 排前 warning 排后；新增 `validate_report_dialog.py` 报告窗口（严重度/文件/消息表格，点击行跳转定位字段）
- **外部 mod 参考导入（F-52）**：新增 `external_mod.py`（文件夹/zip 双来源解析，zip 一层包裹自动识别，临时目录用后清理）+ `external_mod_picker.py` 选择对话框；菜单「导入参考」改为子菜单（原版实例 / mod 文件夹 / mod zip）
- **内容名总表（E-4）**：`tools/extract_content_names.py` 从官方汉化包提取 **524 条**内容名 → `content_names_zh.json`（items/liquids/blocks/units/status），作为科技引用双语搜索的数据源
- **PyInstaller 打包基建（F-53）**：新增 `app/core/paths.py`（开发/冻结双模式路径解析）+ `moma.spec`（单文件 exe 配置，含 QtSvg）；settings/config_loader/theme/main 全部接入

### 架构改进

- **字段类型统一推断（E-1）**：新增 `field_type_for_value(value, hint=None)` 纯函数，editor_panel / weapon_card / polymorphic 三处重复推断全部收敛，hint 支持 ref/col 强制
- **复合字段色条容器（E-2）**：新增 `group_bar.py`（4px 马卡龙原色色条 + 淡染容器 + fieldType 属性）+ QSS 选择器；requirements/consumes/outputItem 等复合字段统一包裹；按 widget_cfg 判 `is_compound`，修复 outputItem 这类 PRIMITIVE-mode 复合字段被当普通行渲染的问题
- **卡片内部行统一（E-3）**：能力卡片内部行走同一推断函数
- **科技引用双语搜索（E-5）**：TechRefEditor 下拉显示「中文名 (英文名)」，QCompleter 支持 Contains + 大小写不敏感过滤，选择后落盘存英文

### 修复

- **outputItem 不包色条**：输出物品在元数据里是 PRIMITIVE 模式（java=ItemStack）但走 resource_slot 控件路由 → 被当普通行渲染。按 widget_cfg 判 `is_compound`，复合字段统一包 GroupBar

### 测试（327 → 383 全绿）

- **`test_sprite_watcher.py`**（+7）：归属判定（主体 `-` 图层区分）/ 防抖合并 / 目录结构变化
- **`test_validator_project.py`**（+13）：mod.json / 重名 / 引用 / 排序
- **`test_external_mod.py`**（+10）：文件夹 / zip / 包裹结构 / 清理
- **`test_theme_field_type.py`**（+9）：推断表
- **`test_content_names.py`**（+8）：提取逻辑 / 双语显示 / completer
- **`test_paths.py`**（+6）：开发 / 冻结双模式
- **`test_editor_panel.py`**（+3）：GroupBar 渲染（requirements=arr / outputItem=ref / 色条容器）

### 文件变更表

| 文件 | 变更 |
|:-----|:------|
| `app/ui/widgets/sprite_watcher.py` | **新增** — 精灵图文件监听（F-21） |
| `app/ui/dialogs/validate_report_dialog.py` | **新增** — 全量验证报告窗口（F-51） |
| `app/core/external_mod.py` | **新增** — 外部 mod 解析（F-52） |
| `app/ui/dialogs/external_mod_picker.py` | **新增** — 参考选择对话框 |
| `app/ui/widgets/group_bar.py` | **新增** — 复合字段色条容器（E-2） |
| `app/core/paths.py` | **新增** — 路径双模式解析（F-53） |
| `app/config/content_names_zh.json` | **新增** — 内容名总表 524 条（E-4） |
| `tools/extract_content_names.py` | **新增** — 内容名提取脚本 |
| `moma.spec` | **新增** — PyInstaller 打包配置 |
| `app/core/validator.py` | 大改 — validate_project + Issue 定位字段（F-51） |
| `app/ui/editor_panel.py` | 修改 — GroupBar 接入 + is_compound 判定 + highlight_field |
| `app/ui/main_window.py` | 修改 — 监听/验证/导入子菜单接线 |
| `app/ui/theme.py` | 修改 — field_type_for_value 统一推断 |
| `app/ui/widgets/resource_editors.py` | 修改 — 双语显示 + completer（E-5） |
| `app/ui/widgets/weapon_array_editor.py` | 修改 — 统一推断 |
| `app/ui/widgets/polymorphic_editor.py` | 修改 — 统一推断 |
| `app/resources/style.qss` | 修改 — groupBar 色条 + 容器样式 |
| `app/core/config_loader.py` | 修改 — 路径接入 + content_names_zh |
| `app/core/settings.py` | 修改 — 路径接入 |
| `app/main.py` | 修改 — 路径接入 |
| `pyproject.toml` | 修改 — 版本 0.2.6 + build 可选依赖 |
| `tests/test_editor_panel.py` | 修改 — +3 GroupBar 测试（乱码修复） |
| `tests/test_ability_array_editor.py` | 修改 — 尾行空白 |

---

## v0.2.5 (2026-08-02 17:09) — 功能填充：更多方块 + Abilities + 资源控件 + 精灵图生成

> v0.2.5 是功能填充版本：把 v0.2.1 预留的占位区域填成完整功能——5 种新方块类型、Abilities 能力编辑器、资源/科技复合控件、精灵图自动生成。同时修复了这一批功能暴露出的全部渲染与交互问题。测试从 258 → 327 全绿。

### 新增

- **5 种新方块类型（F-22）**：GenericCrafter（合成器）/ Drill（钻机）/ Conveyor（传送带）/ Battery（电池）/ MendProjector（维修投影仪）。每种都有完整模板（`template.py`）+ 字段组配置（`field_groups.json`）+ 元数据（提取器重跑产出）
- **Abilities 能力编辑器（F-49）**：新增 `ability_array_editor.py`，15 种能力子类卡片式编辑（类型下拉 → 字段表单），全部走命令栈可撤销；`abilities` 懒初始化——无能力时 JSON 不产生该键，首次添加才经命令栈创建
- **资源/科技复合控件（F-50）**：`resource_editors.py` 新增 ResourceListEditor（多行资源列表）/ ResourceSlotEditor（单资源槽）/ TechRefEditor（科技引用）/ ConsumesEditor（消耗定义），全部走命令栈 + 嵌套路径读写
- **精灵图自动生成（F-20）**：`sprite_generator.py`（Pillow 纯算法，core 层不 import Qt）——outline 轮廓 / shadow 阴影 / full 合成
- **资源中文名表**：`resource_names_zh.json`（22 物品 + 9 液体官方译名），资源下拉显示 `铜 (copper)`、落盘存英文

### 修复

- **资源编辑器双重命令**：编辑器内部已走命令栈，主面板又发一条 → 撤销要撤多次。改用 `committed=True` 只做副作用（标记脏 + 通知刷新）
- **consumes 永不渲染**：`consumes` 不在提取元数据 → 字段被隐藏。`form_plan.py` 新增 `synthetic_field_def`——按值类型合成 FieldDef，缺失字段仍走正常渲染（含 widgets 路由）
- **能力字段全空**：`PolymorphicTypeEditor.value` 用 `dict.get("abilities.0")` → 读不到嵌套数组元素。改用 `_get_nested` 点路径读取
- **嵌套路径「+ 添加」失效**：ResourceListEditor 值读写用 `dict.get` 读不到嵌套路径 → 重建清空。4 个值读写全部改 `_get_nested`/`_set_nested`/`_del_nested`
- **下拉框黑块三角**：QSS border-transparent 三角在 windows11 editable 下拉上渲染成黑块 → 换 SVG 箭头图标（`arrow_down.svg`）
- **下拉文字右对齐**：`setEditText` 后光标在末尾 → 视口滚到末尾，左侧中文被挤出。所有 editable 下拉设置后光标归位 `setCursorPosition(0)`
- **consumes「+ 添加」失效**：添加下拉默认选中第一项，重建后重选不触发信号 → 加占位项（`请选择消耗类型…`，data=None）
- **预览阴影盖主体**：预览 z 序全递增 → 阴影叠在主体上。阴影 z=-3、轮廓 z=-2，主体 z 从 1 起

### 体验优化

- **字段名翻译 +75**：`field_names_zh.json` 补齐方块/能力字段中文显示名
- **新建方块对话框分组**：方块类型按 `block_categories.json` 大类分组展示（仅列已有模板的类型）
- **设置项接线（F-54）**：显示名模式 / 自动保存间隔（0 = 关闭）/ 精灵图缩放倍率生效
- **下拉弹出宽度**：长选项（如 `爆破混合物 (blast-compound)`）不再被截断，弹出列表按最长项撑宽

### 测试（258 → 327 全绿）

- **`test_sprite_generator.py`**（新增）：outline/shadow/full 纯算法验证
- **`test_ability_array_editor.py`**（新增）：空态 / 添加撤销重做 / 卡片渲染 / FieldRow 包裹 / 卡片内删除 / 字段编辑撤销
- **`test_editor_panel.py`**（新增）：widgets 路由 / consumes 渲染 / 资源编辑器撤销与样式 / 下拉修复（SVG 箭头、占位、光标、弹出宽度）/ 嵌套路径读写
- **`test_form_plan.py`**（+）：synthetic_field_def 推断
- **`test_preview_panel.py`**（+）：阴影 z 序

### 文件变更表

| 文件 | 变更 |
|:-----|:------|
| `app/ui/widgets/ability_array_editor.py` | **新增** — Abilities 卡片编辑器（F-49） |
| `app/core/sprite_generator.py` | **新增** — 精灵图 outline/shadow/full 生成（F-20） |
| `app/config/resource_names_zh.json` | **新增** — 资源中文名总表 |
| `app/resources/icons/arrow_down.svg` | **新增** — 下拉箭头图标（替代黑块三角） |
| `metadata/classes/` | **新增** — 5 新方块 + 15 Ability 子类 + PowerBlock 元数据 |
| `app/ui/widgets/resource_editors.py` | 大改 — 4 个复合控件 + 嵌套路径 + 双语言下拉 |
| `app/core/form_plan.py` | 修改 — synthetic_field_def 缺失字段合成 |
| `app/core/template.py` | 修改 — 5 种新方块模板 |
| `app/config/field_groups.json` | 修改 — 新方块类型字段组 + widgets 路由 |
| `app/config/field_names_zh.json` | 修改 — +75 字段中文名 |
| `app/ui/editor_panel.py` | 修改 — committed=True / 能力懒初始化 / 下拉光标 |
| `app/ui/widgets/polymorphic_editor.py` | 修改 — _get_nested 嵌套读取 / FieldRow 包裹 |
| `app/ui/preview_panel.py` | 修改 — 阴影 z 序 / sprite_zoom 接线 |
| `app/ui/dialogs/new_content.py` | 修改 — 方块类型按大类分组 |
| `app/ui/dialogs/settings_dialog.py` | 修改 — 显示名/自动保存/缩放接线（F-54） |
| `app/ui/main_window.py` | 修改 — 设置项应用后刷新 |
| `app/ui/theme.py` | 修改 — @ARROW_ICON@ 令牌 |
| `app/resources/style.qss` | 修改 — SVG 箭头样式 |
| `extractor/` | 修改 — ClassExtractor 支持 Ability/新方块提取 |
| `tests/` | 新增/修改 — 327 测试全绿 |

---

## v0.2.4.revised (2026-08-02 03:19) — 架构深化 + 图层树渲染修复 + 测试补全

> 一次完整的架构审查驱动的重构：把渲染坐标公式、字段组操作、控件创建、颜色选择四块逻辑从 UI 层提取为可独立测试的深模块；修复图层树在 windows11 下的一串渲染问题；补齐图层树行为测试。测试从 219 → 258 全绿。

### 架构改进

- **渲染数学层**：新增 `app/core/preview_math.py`（不 import Qt）——PPU=4 坐标映射 / 武器 mirror 双份 / 引擎双圆几何提取为纯数据描述（`LayerSpec`/`CircleSpec`/`SceneSpec`），坐标公式脱离 Qt 可 pytest 直接验证（ADR-003 "渲染公式可提取"的落地）
- **字段组操作层**：新增 `app/core/group_ops.py`（不 import Qt）——字段组的缓存/恢复/移除逻辑从 editor_panel 三处重复（能力勾选、能力联动、添加字段组）集中为 5 个纯函数，走 CommandStack 可撤销。历史 bug 高发区（Bug1/2/3）现在只需修一次
- **控件工厂**：新增 `app/ui/widgets/field_widget_factory.py`——bool/int/float 控件创建从四处复制粘贴（editor_panel / polymorphic_editor / weapon_array_editor / preview_panel）收敛为 `create_value_widget()` 单点，统一 range/decimals/宽度/滚轮禁用/blockSignals 初始化
- **颜色控件独立**：`_create_color_widget` 60 行内联代码提取为 `app/ui/widgets/color_picker.py`（`ColorPicker` 控件 + `parse_color` 纯函数），editor_panel 调用缩至 7 行。hex 解析 / rgba dict 转换 / QColorDialog 交互封装在控件内部

### 修复（图层树渲染系列）

- **复选框裸勾/勾不可见**：QSS 显式定义 `QTreeWidget::indicator`（16px 圆角方框 + `:hover`/`:checked`/`:disabled`），勾选态用 SVG 橙勾——windows11 风格叠加 QSS 后原生 indicator 丢外框，且原生勾在深色主题下几乎不可见
- **图层名被裁、「引擎示意」截断成「引擎...」**：列 0 从 `ResizeToContents` 改 `Fixed` 220px——RTC 在带 itemWidget 的行上会把列算窄
- **选中态双橙条**：图层树整体去掉选中态（`#layerTree::item:selected` 覆盖为透明）+ `:selected:focus` 去掉右侧边框
- **双击复选框误触发「更换图片」**：viewport `eventFilter` 拦截落在 indicator 区域的双击，只 toggle 不换图
- **编辑区武器 XY 修改静默失败**：控件信号只传一个值、裸 `_set_field`（两参数）→ TypeError 被 Qt 静默吞掉 → dict 永不更新。改用 `functools.partial` 绑定字段名
- **编辑区武器修改不刷新预览/被覆写**：`WeaponArrayEditor.valueChanged` 补连 `data_changed`
- **重建污染 dict**：图层树重建时 `spin.setValue` 触发 `valueChanged` 把默认值写进 dict → 重建期间 `blockSignals`
- **数值框显示 bug**：`textFromValue` 用 `:g` 在 decimals 小时吞小数位（1.1→"1"）或产生科学计数法（10→"1e+01"）→ 改定点 `f` 格式 + 手动去尾零
- **editor_panel 启动崩溃**：`_on_capability_toggled` docstring 未闭合（缺 `"""`）+ 丢失变量赋值行 → Python 把后续中文注释当代码 → SyntaxError。补回闭合引号 + import + 赋值

### 体验优化

- **武器 x/y 输入框加长**：55→70px，显示更宽松
- **图层行状态文本移列 1**：列 0 只留图层名，`[有]/[可选]/[缺失]` 右对齐到列 1，输入框不再被挤远
- **preview 武器 spin 换 NumDoubleSpinBox**：获得滚轮保护（不再误改值）+ 去尾零显示

### 测试（219 → 258 全绿）

- **`test_preview_math.py`**（+17）：坐标公式脱离 Qt 验证——PPU 缩放 / y 翻转 / mirror 对称 / 引用回退 / 引擎圆半径+z 切换+颜色归一化
- **`test_group_ops.py`**（+15）：字段组缓存/恢复/移除脱离 Qt 验证——缓存优先级 / 存在标记 / optional 恢复 / 撤销对称性
- **`test_preview_panel.py`**（+24）：图层树行为覆盖——树结构 / 主体 checkbox 显隐联动场景 / 武器逐把独立 key / spin 写回 dict + 信号 / visible_for 子类型过滤 / engineSize=0 无引擎层 / required 缺图标 [缺失] / QSS 配置回归

### 文件变更表

| 文件 | 变更 |
|:-----|:------|
| `app/core/preview_math.py` | **新增** — 渲染纯数学层（坐标/武器/引擎），不 import Qt |
| `app/core/group_ops.py` | **新增** — 字段组缓存/恢复/移除，不 import Qt |
| `app/ui/widgets/field_widget_factory.py` | **新增** — 控件工厂，消灭四处复制粘贴 |
| `app/ui/widgets/color_picker.py` | **新增** — 颜色选择控件（色块+hex 输入） |
| `tests/test_preview_math.py` | **新增** — 坐标公式测试 17 条 |
| `tests/test_group_ops.py` | **新增** — 字段组操作测试 15 条 |
| `tests/test_preview_panel.py` | **新增** — 图层树/武器行/行为测试 24 条 |
| `app/resources/icons/check_copper.svg` | **新增** — 复选框 SVG 橙勾 |
| `app/ui/editor_panel.py` | 重构 — group_ops 替换三处重复 + 颜色控件提取 + docstring 修复（净减 ~160 行） |
| `app/ui/preview_panel.py` | 修改 — 列 0 Fixed 220 / 去选中态 / 双击拦截 / spin 70px+blockSignals / NumDoubleSpinBox |
| `app/resources/style.qss` | 修改 — indicator 显式定义 + SVG 勾 + `#layerTree` 去选中态 |
| `app/ui/widgets/weapon_array_editor.py` | 修改 — partial 修复 + 工厂重构 |
| `app/ui/widgets/polymorphic_editor.py` | 修改 — 工厂重构 |
| `app/ui/widgets/num_spin.py` | 修改 — 定点格式去尾零（修 :g 科学计数法） |
| `app/ui/theme.py` | 修改 — `@CHECK_ICON@` 绝对路径注入 |
| `app/ui/main_window.py` | 修改 — 右栏 280→360 |
| `app/ui/widgets/__init__.py` | 修改 — 导出 create_value_widget |
| `AGENTS.md` | **新增** — 项目硬约束文档 |

---

## v0.2.4 (2026-08-01) — 下半 Batch 4：预览渲染纠正 + 武器图层树 + 子类型过滤 + 交互增强

> grill 收敛 9 项设计决策 + 003 调研报告落地。纠正 Batch 3 的坐标/引擎/图层多处与游戏不符，新增武器行内编辑、子类型图层过滤、图层双击替换/右键菜单。

### 新增

- **武器图层树每把独立行**（D1）：每把武器独立一行，行内嵌 `QDoubleSpinBox` 编辑 x/y（范围 -40~40，步长 0.1）
- **SpinBox 实时预览/延迟提交**（D7）：`valueChanged` 直接改 dict + 实时重绘预览（不入 CommandStack）；`editingFinished` 发射 `content_modified` 信号标记 dirty
- **引用武器默认值解析**（D2）：引用武器 x/y 无覆盖时自动读被引用武器 JSON 的默认值
- **子类型图层过滤**（R3）：`sprite_layers.json` 加 `visible_for` 字段，飞行单位不显示腿/履带图层，坦克不显示腿图层等
- **图层双击替换**（D8）：已存在精灵图双击打开文件选择对话框替换
- **图层右键菜单**（D8）：替换精灵图 / 在文件管理器中打开 / 删除精灵图
- **`data_changed` 信号**（D4）：`editor_panel` 字段变更后发射信号，`main_window` 连接预览实时刷新，修复"添加武器后图层树不出现"和"引擎切标签才生效"

### 纠正（003 调研结论落地）

- **坐标 PPU=4**（R1）：武器/引擎偏移从 1:1 改为 4 像素=1 世界单位，修正 Batch 3 武器位置偏小 4 倍的错误
- **引擎双实心圆**（D6）：从半透明蓝圈改为外圈 `engineColor`（未设置→亮黄/橙占位）+ 内圈 `engineColorInner`（默认白色），内圈沿 rotation 偏移形成喷口感
- **引擎 z-order 修正**：默认 `engineLayer ≤ 0` 时引擎画在主体**下方**（zValue=-1），`engineLayer > 0` 才提升到主体上方
- **武器每把独立 scene key**：从笼统 `__weapons__` 改为 `__weapon_{i}__`，支持逐武器显隐控制

### 修复

- **抬头对齐错位**（D5）：删 `#editorTitle` 的 `margin-bottom: 8px`，修复小字上缘对齐大字下缘的视觉 bug
- **explorer 中文路径跳"文档"**（D9）：`_reveal_in_file_manager` 改用字符串形式调 `explorer /select,"{path}"`，修复中文/空格路径下 explorer 参数解析失败

### 测试

- 202 个 pytest 全绿（0.89s）
- offscreen 冒烟测试通过

### 文件变更表

| 文件 | 变更 |
|:-----|:------|
| `app/ui/preview_panel.py` | **重写** — PPU=4 坐标、引擎双圆、武器独立行+SpinBox、引用武器默认值、visible_for 过滤、双击替换、右键菜单 |
| `app/config/sprite_layers.json` | 修改 — UnitType 加 `visible_for` + 新增 `-leg-base`/`-joint`/`-joint-base`/`-foot`/`-base` 图层 |
| `app/ui/editor_panel.py` | 修改 — 新增 `data_changed` 信号 + `_on_field_changed` 末尾发射 |
| `app/ui/main_window.py` | 修改 — 连接 `data_changed` → 预览刷新 |
| `app/resources/style.qss` | 修改 — 删 `#editorTitle` 的 `margin-bottom` |
| `app/ui/file_tree.py` | 修改 — `_reveal_in_file_manager` 改字符串形式调 explorer |

---

## v0.2.4 (2026-08-01) — 下半 Batch 3：预览增强 + 重命名修复

> 预览里能看到武器装在哪、引擎发光；重命名不再丢图。

### 新增

- **预览武器/引擎叠加**（F-72）：读 `weapons` 数组按 x/y 叠加武器 png + mirror 水平翻转双份 + 悬浮显武器名 tooltip；按 `engineOffset`/`engineSize` 画引擎示意圆
- **图层树 PS 式眼睛开关**（F-73）：每层 checkbox 控制预览中该层显隐；`_layer_visibility` 缓存跨刷新保持
- **多层精灵合成**：预览从单张主体图改为多层合成（主体 + `-cell`/`-full`/`-treads` 等按 `sprite_layers.json` 加载并居中对齐）
- **武器精灵三级查找**：`sprites/weapons/{name}.png` → 单位精灵同目录 → `sprites/` 递归 rglob
- **重命名精灵图全跟改**（F-81）：`Project.rename_sprites()` 先收集所有 `{old}.png` + `{old}-*.png` 再批量改名（修复 glob 匹配已改名文件的 bug）；不误改 `{old}XYZ.png`（如"坦候"不改"坦候武器"）
- **重命名后预览刷新**：`_on_content_renamed` 触发 `preview.show_content`，重命名后图层树立即显示新名

### 修复

- **rename_sprites 双重改名 bug**：先收集再批量改名，避免 `old_name` 是 `new_name` 前缀时 glob 匹配已改名文件

### 测试

- 202 个 pytest 全绿（0.94s）
- offscreen 冒烟测试通过
- probe 验证：武器坐标/mirror/引擎圆/图层隐藏/rename_sprites 全过（probe 已删）

### 文件变更表

| 文件 | 变更 |
|:-----|:------|
| `app/ui/preview_panel.py` | **重写** — 多层合成 + 武器叠加 + 引擎圆 + 图层 checkbox + `_scene_items` 跟踪 |
| `app/core/project.py` | 修改 — 新增 `rename_sprites()` 方法 |
| `app/ui/file_tree.py` | 修改 — `_do_rename` 加 `rename_sprites` 调用 |
| `app/ui/main_window.py` | 修改 — `_on_content_renamed` 加预览刷新 |

---

## v0.2.4 (2026-08-01) — 下半 Batch 2：字段组交互系统 + 抬头 + 标签 + 能力开关组

> 让字段组“能加能删能开关”，抬头从静态标签变成可交互名片，长标签不再顶控件。含 3 轮 bug 修复（结构性根因：能力组 required+default 为空导致勾选/添加后 data 无新字段，rebuild 后组状态丢失）。

### 新增

- **添加/删除字段组**（F-68）：抬头右侧 [添加字段组] 按钮，菜单列出当前未显示的可见组；删组 = 确认弹窗 → JSON 移除 → 值缓存 → 重新添加时恢复
- **能力开关组**（F-69）：mining/building/boost/capacity 四组带复选框，组头 = ▾ ☐ 标题；未勾选 = 禁用态 + 组体不渲染；勾 mining → 自动勾 capacity（单向联动）
- **模板补全**（F-71）：8 种模板补全 default 级字段（range/targetAir/targetGround/accel/drag/inaccuracy/description 等）
- **抬头排版重设计**（F-80）：名字大字粗 + 双击原地编辑 + 右键重命名；类型小字 12px 淡化、同行底对齐、去括号
- **name 字段只读**（F-82）：basic 组 name 字段不可编辑，显示 = 文件名 stem，tooltip 提示“名称由文件名决定”

### 调整

- **长字段名截断**（F-79）：标签固定列宽 180px，英文 `elidedText` 截断加 …，tooltip 含完整英文名
- **重命名信号解耦**：抬头双击编辑发射 `rename_requested` 信号，由 `main_window` 连接 `file_tree._rename_content_by_name`；ADR-009 三恒等原则：仅在 JSON 已有 name 字段时跟改，不注入

### 修复（3 轮）

- **Round 1**：movement/combat 组显示删除按钮但实际不可删（required 字段重建后复活）→ 加 `locked: true`；能力组勾选后不展开（`has_required=False`）→ `is_group_expanded` 加 `is_capability` 参数
- **Round 2**：禁用/删组后字段值丢失 → 新增 `_CACHED_VALUES` 缓存；能力组消失 → 恢复 `is_cap` 渲染 + `_DELETED_GROUPS`；添加字段菜单出现在屏幕中央 → `sender()` 返回 CollapsibleGroup 而非 QPushButton，改用 `sender._add_btn` 定位
- **Round 3（结构性根因）**：能力组和大多数普通组 required+default 为空，勾选/添加时不写任何字段到 data，rebuild 后组状态丢失 → 新增 `_ENABLED_GROUPS` 独立追踪 + `GroupPlan.capability_enabled` + optional 存在标记 + `locked_for` 子类型锁定
- **跳顶根治**：能力组切换不再调用 `_rebuild_form()` 销毁重建所有控件，改为 `_refresh_group()` 原地刷新受影响的组；拆分 `_render_group` 为 `_render_group` + `_populate_group_body`；`CollapsibleGroup` 新增 `set_capability_enabled` 公共方法

### 测试

- 202 个 pytest 全绿（0.85s）
- offscreen 冒烟测试通过

### 文件变更表

| 文件 | 变更 |
|:-----|:------|
| `app/ui/editor_panel.py` | **重写** — 添加/删除组、能力开关、抬头、name 只读、原地刷新 |
| `app/ui/widgets/collapsible_group.py` | 修改 — 能力复选框 + 点击语义 + `set_capability_enabled` |
| `app/ui/widgets/label_helper.py` | 修改 — 固定 180px + 英文截断 + tooltip |
| `app/core/form_plan.py` | 修改 — `CAPABILITY_GROUPS`/`CAPABILITY_LINKAGE` + `capability_enabled` + `enabled_groups` 参数 |
| `app/core/template.py` | 修改 — 8 种模板补全 default 级字段 |
| `app/config/field_groups.json` | 修改 — `defaults` + `locked` + `locked_for` |
| `app/ui/file_tree.py` | 修改 — `_do_rename` 提取 + `_rename_content_by_name` |
| `app/ui/main_window.py` | 修改 — `rename_requested` 信号连接 |
| `app/resources/style.qss` | 修改 — `#editorTypeLabel` + `#addGroupBtn` 样式 |
| `app/config/field_names_zh.json` | 修改 — 新增字段中文名 |
| `app/config/field_docs.json` | 修改 — 新增字段提示文本 |
| `tests/test_form_plan.py` | 修改 — `is_group_expanded` 新参数 |

---

## v0.2.4 (2026-08-01) — 下半 Batch 1：配置驱动 + 渲染逻辑 + 视觉快赢

> 让字段组“该出现的出现、不该出现的不出现”，同时把视觉打磨中“改一行 QSS 就见效”的快赢项一次性收掉。

### 新增

- **字段三级可见性**（F-70）：`field_groups.json` 每组加 `default` 列表；`form_plan.py` 渲染逻辑改为 required 始终 + default 新建/data 中 + optional 仅 data 中
- **字段组可见性过滤**（F-67）：子类型特征组加 `visible_for`；空组（required+default 都空且 JSON 无该组字段）不渲染
- **Qt 全局中文翻译**（F-78）：`main.py` 启动时 `QTranslator` 加载 `qtbase_zh_CN.qm`，对话框按钮显示“确定/取消”

### 调整

- **预览分割比例**（F-74）：`preview_panel.py` 的 `setSizes` 从 [400, 200] 改为 [360, 240]（6:4）
- **设置菜单独立**（F-75）：菜单栏加「设置(&S)」顶级菜单，工具菜单移除设置入口
- **fieldBar 色条圆角**（F-76）：`#fieldBar` 加 `border-radius: 1.1px`
- **选中态重设计**（F-77）：铜橙左条 + 中性背景 + 冷蓝聚焦框 + 加粗（双主题）；`theme.py` 新增 `SEL_BG`/`SEL_FOCUS` 令牌

### 测试

- 200 个 pytest 全绿
- offscreen 冒烟测试通过

### 文件变更表

| 文件 | 变更 |
|:-----|:------|
| `app/config/field_groups.json` | 修改 — 每组加 `default` 列表 + `visible_for` |
| `app/core/form_plan.py` | 修改 — 三级字段渲染 + 空组隐藏 + `group_visible` |
| `app/main.py` | 修改 — `_install_qt_translations()` 加载中文翻译 |
| `app/resources/style.qss` | 修改 — 选中态三层 + fieldBar 圆角 |
| `app/ui/theme.py` | 修改 — `SEL_BG`/`SEL_FOCUS` 令牌 |
| `app/ui/preview_panel.py` | 修改 — 分割比例 6:4 |
| `app/ui/main_window.py` | 修改 — 设置菜单独立 |
| `CONTEXT.md` | 修改 — +5 术语（内容标识符/显示名/文件名/字段默认可见性/能力开关组） |
| `tests/test_form_plan.py` | 修改 — 适配新参数 |

---

## v0.2.4 (2026-07-31 19:55) — 上半补充 3：问题 7 真根因（spinbox 内部偏移）

> 用户实测：换字体后数字左留白仍大于名称。推翻「字体差异」假设。probe 证实：QSS 后代选择器无法命中 QAbstractSpinBox 内部 QLineEdit；windows11 样式下内部 lineEdit 继承基础 QSS 的 border+padding，文本起点 = editfield(6) + border(1) + padding(4) = 10px vs 普通 QLineEdit 6px。

### 修复

- **spinbox 内部 QLineEdit 编程式补偿**：`num_spin.py` 构造时对 `lineEdit()` 设局部样式 `padding: 0; border: none;`（QSS 后代选择器对内部 lineEdit 无效，只能实例级局部样式）→ 文本起点 = editfield 起点，与普通输入框对齐（实测 windows11 样式下 6px = 6px）
- **删除无效 QSS 规则**：此前加的 `QSpinBox QLineEdit { padding: 0 }`（实测不生效）移除，注释说明机制

### 测试

- 200 个 pytest 全绿（0.84s）
- offscreen + windows11 样式冒烟：spinbox 文本起点 = QLineEdit = 6px

### 文件变更表

| 文件 | 变更 |
|:-----|:------|
| `app/ui/widgets/num_spin.py` | 修改 — 构造时补偿内部 lineEdit 局部样式 |
| `app/resources/style.qss` | 修改 — 移除无效后代规则 + 注释 |

---

## v0.2.4 (2026-07-31 19:40) — 上半补充 2：问题 7 字体统一

> 依据截图重述：输入框文字左缘不齐 + 左留白偏大。核实：容器起点此前已对齐（9px），不齐来自字体字形差异（JetBrains Mono 等宽下 `1` 带左 bearing 偏右、`0`/`8` 贴左；名称框 MiSans 与数值框等宽是两套字体族）。采纳用户方案 C：数值统一用 MiSans。

### 调整

- **数值框字体统一为 MiSans**：删除 `QSpinBox/QDoubleSpinBox` 的 JetBrains Mono 等宽声明，与字符串输入框同一字体族 → 消除等宽/比例字体的字形左缘差异（颜色 hex 输入框等宽保留，hex 码需要等宽可读性）
- **左留白收紧**：输入控件基础 padding 左内边距 8→5px，文本起点 9px→6px（容器起点实测全部 6px 一致）
- **删死规则**：`QSpinBox QLineEdit { padding-left: 6px }`（实测未生效的遗留规则）

### 测试

- 200 个 pytest 全绿（0.88s）
- offscreen 冒烟：5 字段容器起点全部 6px + 字体族统一 MiSans

### 文件变更表

| 文件 | 变更 |
|:-----|:------|
| `app/resources/style.qss` | 修改 — 数值框去等宽字体 + 基础 padding 8→5px + 删死规则 |

---

## v0.2.4 (2026-07-31 19:20) — 上半补充：跟进修复

> 上半修复后的 4 项跟进问题（含 1 项上半引入的回归）。

### 修复

- **滚轮仍会误改数值**：上半的「未聚焦拦截」不可靠——hover 时焦点会转移，聚焦判断失效 → **彻底禁用滚轮改值**（`wheelEvent` 一律 `event.ignore()`，数值只允许键盘/点击调整，滚轮只用于滚动页面）
- **复选框小于马卡龙饰条**：`CheckToggle` 18×18 在 26px 行高下比色条矮 → 加大至 **22×22**，与色条/输入框比例协调
- **字段名之间空间偏大**：标签文字 13px 在固定 26px 行内留白多 → 标签中文加大至 **14px**、英文 11.5→**12px**，填满行内间距
- **武器列表被压扁成窄条（回归）**：上半 `row_container.setFixedHeight(26)` 无差别作用于所有字段行，weapons 复合控件（武器卡片）也被压成 26px → **仅普通字段行（PRIMITIVE/STRING_REF）固定行高**，复合控件行自适应高度

### 测试

- 200 个 pytest 全绿（0.78s）
- offscreen 冒烟 5/5 通过（聚焦时滚轮不改值 / 复选框 22px / 标签 14px+12px / 武器行自适应高度）

### 文件变更表

| 文件 | 变更 |
|:-----|:------|
| `app/ui/editor_panel.py` | 修改 — 固定行高仅限普通字段行（修复武器列表压扁回归） |
| `app/ui/widgets/num_spin.py` | 修改 — wheelEvent 彻底禁用（不再依赖焦点判断） |
| `app/ui/widgets/check_toggle.py` | 修改 — 18→22px |
| `app/ui/widgets/label_helper.py` | 修改 — 中文 14px / 英文 12px |

---

## v0.2.4 (2026-07-31 18:59) — 上半：UI 体验问题全量修复

> 用户反馈的 7 项 UI 问题全量修复（根因报告：`Docs/辅助文档/v024-UI体验问题根因报告.md`）。

### 修复

- **字段行间距/高度不齐**（问题 1）：各行 `row_container` 固定行高 26px，消除 CheckToggle（18px）与输入框（23px）的高度差；标签富文本英文从 10.5px 调至 11.5px，协调标签与控件字号比例
- **tooltip 黑底白字**（问题 2）：`style.qss` 的 `QToolTip` 令牌语义用反（`background: @INK@; color: @CANVAS@` 在浅色下恰好黑底白字）→ 改为 `background: @PANEL@; color: @INK@` + 描边，深浅主题都正确
- **添加字段后已展开的组被折叠**（问题 3）：双重 bug——① chevron 点击的记忆 lambda 被 `clicked(bool)` 信号参数污染，记忆 key 变成 `False/True` 而非组名（记忆从未真正生效）；② 点组头展开不写记忆 → 统一改为 `CollapsibleGroup.expandedChanged(str, bool)` 信号，组头点击与 chevron 点击都触发记忆
- **新建武器对话框切换后大片空白**（问题 4）：`QDialog` 默认布局约束「变大不缩回」——内联→引用切换后窗口保持内联高度，多余空间被标题 QLabel 拉伸 → `layout.setSizeConstraint(SetMinimumSize)` + `_on_mode_changed` 末尾 `adjustSize()`
- **数值框未聚焦时滚轮误改值**（问题 5）：`NumSpinBox` / `NumDoubleSpinBox` 补 `wheelEvent`——未聚焦时 `event.ignore()` 交给父级滚动
- **武器卡片字段无马卡龙着色**（问题 6）：`WeaponCard` 用 `form.addRow` 放裸控件、未设 `fieldType` 属性、未包 `FieldRow` → `_create_widget_for_value` 统一用 `FieldRow` 包裹 + `fieldType` 动态属性，与主面板一致
- **输入框左内边距不齐**（问题 7）：`QAbstractSpinBox` 内部 QLineEdit 被 Qt 固定放在 x=3 处 → QSS 补 `QSpinBox QLineEdit { padding-left: 6px }`，数值框文本起点与字符串框对齐（实测均 9px）

### 清理

- 删除 `WeaponCard._create_primitive_widget` 死代码（无调用点）

### 测试

- 200 个 pytest 全绿（0.79s）
- offscreen 冒烟 13/13 通过（行高统一 / tooltip 令牌 / 折叠记忆保留 / 对话框约束 / 滚轮拦截 / 卡片 FieldRow+fieldType / 文本起点对齐 9px=9px）

### 文件变更表

| 文件 | 变更 |
|:-----|:------|
| `app/ui/editor_panel.py` | 修改 — 行容器固定高度 + expandedChanged 信号替代被污染 lambda |
| `app/ui/widgets/collapsible_group.py` | 修改 — 新增 `expandedChanged(str, bool)` 信号（组头/chevron 统一记忆通道） |
| `app/ui/widgets/weapon_array_editor.py` | 修改 — 对话框 SetMinimumSize+adjustSize；卡片 FieldRow 包裹+fieldType；删死代码 |
| `app/ui/widgets/num_spin.py` | 修改 — wheelEvent 未聚焦拦截 |
| `app/ui/widgets/label_helper.py` | 修改 — 英文 10.5→11.5px |
| `app/resources/style.qss` | 修改 — QToolTip 令牌修正 + spinbox 内部 padding 对齐 |

---

## v0.2.3 (2026-07-31 17:55)

> Bug 修复与体验优化：修 8 类崩溃/逻辑 bug、清规范遗留、补体验细节。测试 186 → 200。

### 崩溃 / 数据安全

- **坏 mod.json 打开崩槽**：`Project.open` 中 `json.loads` 抛 `JSONDecodeError`（`ValueError`）未被 UI 捕获，打开坏工程直接崩 → 转成带路径的友好 `ValueError`，打开/恢复上次工程统一弹警告
- **重命名静默覆盖**：重命名内容无重名检查，直接覆盖已有文件；且已打开的旧名标签会"复活"旧文件 → 改名前查重 + 校验名称字符，新增 `content_renamed` 信号同步标签页（名称 + 标题）
- **新建同名内容静默覆盖**：重复创建同名单位/方块/武器直接丢旧数据 → 创建前 `session.content_exists()` 查重，弹窗确认覆盖
- **新建工程参数无校验**：mod_id 含非法字符崩槽、路径留空写错位置 → 对话框正则校验（小写字母/数字/连字符，失败不关框）+ `Project.create` 双重防御

### 逻辑修复

- **跨标签撤销/重做失同步**：标签 A 编辑 → 切 B → Ctrl+Z，A 控件仍显示旧值，切回后编辑把过期值写回 → 撤销/重做后刷新全部打开面板，切换标签时也从数据重建表单
- **「+ 添加字段」绕过命令栈**：直接写 data 不可撤销（删除可撤销、添加不可，撤销历史被污染）→ 改用 `SetFieldCommand`，与删除对称
- **用户备注丢失**：每次重建表单即清空、从不持久化 → 持久化到 `data["$notes"]`（已核实 Mindustry `ContentParser.ignoreUnknownFields=true`，游戏忽略未知键）
- **关标签保存路径不一致**：`EditorPanel.save()` 直接写盘不校验、dirty 标志不清 → 关标签保存统一走 session（带验证 + 错误跳转）

### 规范 / 一致性

- **validator 死代码回潮**：`_is_internal_field` 双黑名单残留（与 `FieldDef.is_internal` 不一致）→ 删除
- **版本号漂移**：关于对话框显示 v0.1.0，实际已 v0.2.2 → `APP_VERSION` 常量 + `pyproject.toml` 统一为 0.2.3
- **测试污染真实配置**：pytest 运行覆盖 `editor_state.json` 的 `last_project` → `tests/conftest.py` autouse fixture 把 `save/load_editor_state` 重定向到 tmp
- **死代码清理**：`icon_loader.py`（撤图标后零引用整模块）、`_add_group_separator`、`template._default`、QSS `QCheckBox[fieldType="bool"]` / `QCheckBox[error="true"]` 死规则、`field_groups.json.bak` 杂散文件
- **重复子弹类型表**：`BULLET_TYPE_CHOICES`（weapon_array_editor）与 `BULLET_TYPES`（polymorphic_editor）内容相同各自维护 → 收敛为 `polymorphic_editor.BULLET_TYPES` 单一来源
- **漏 `short` 类型检查**：`_check_primitive` 覆盖 float/double/int/long 但漏 short → 补上
- **未用导入清理**：`metadata.py` lru_cache、`editor_panel.py` get_tokens、`reference_panel.py` QHBoxLayout

### 体验优化

- **参考对比差异行硬编码黄底**（深色主题刺眼）→ 新增 `DIFF_BG` / `DIFF_FG` 主题令牌，深浅自适应
- **关闭/退出多个脏标签只问第一个**，其余静默丢弃 → 统计全部未保存标签统一确认
- **颜色色块内联 setStyleSheet**（border/border-radius 静态部分）→ 移入 QSS `#colorSwatch`，仅保留动态背景色 hex（唯一正当例外）

### 测试

- **总量**：186 → 200 全绿（0.87s）
- **新增 `tests/test_project.py`**：坏 mod.json → ValueError、mod_id 校验（8 个）
- **扩展**：`content_store.exists`（4）、`session.content_exists`（2）、validator short 类型检查（1）
- **隔离**：conftest 重定向 editor state，测试不再写真实配置文件

### 文件变更表

| 文件 | 变更 |
|:-----|:------|
| `app/core/project.py` | 修改 — 坏 JSON 转 ValueError + mod_id 校验 |
| `app/core/content_store.py` | 修改 — 新增 `exists()` |
| `app/core/session.py` | 修改 — 新增 `content_exists()` |
| `app/core/validator.py` | 修改 — 删死代码黑名单 + 补 short 检查 |
| `app/core/template.py` | 修改 — 删 `_default` 死方法 |
| `app/core/metadata.py` | 修改 — 删未用导入 |
| `app/ui/main_window.py` | 修改 — 坏 JSON 捕获 / 全面板刷新 / 查重 / 关标签统一保存 / 版本号 / 脏标签确认 / 重命名同步 |
| `app/ui/editor_panel.py` | 修改 — 添加字段走命令栈 / 备注持久化 / save 带验证 / 删死代码 |
| `app/ui/file_tree.py` | 修改 — 重命名查重 + `content_renamed` 信号 |
| `app/ui/dialogs/new_project.py` | 修改 — 对话框校验 |
| `app/ui/theme.py` | 修改 — +DIFF_BG/DIFF_FG 令牌 |
| `app/ui/widgets/reference_panel.py` | 修改 — 差异高亮走主题令牌 |
| `app/ui/widgets/weapon_array_editor.py` | 修改 — BULLET_TYPES 收敛 |
| `app/resources/style.qss` | 修改 — 删 QCheckBox 死规则 + `#colorSwatch` |
| `app/ui/icon_loader.py` | **删除** — 零引用模块 |
| `app/config/field_groups.json.bak` | **删除** — 杂散备份 |
| `tests/conftest.py` | **新增** — editor state 隔离 fixture |
| `tests/test_project.py` | **新增** — 8 个用例 |
| `tests/`（3 个文件） | 扩展 — exists / content_exists / short 检查 |
| `pyproject.toml` | 修改 — version 0.2.3 |

---

## v0.2.2 (2026-07-31 13:34)

> 代码库架构全量优化：消除 God Object、统一规则来源、补全核心测试。测试 49 → 186。

### 架构改进

- **字段可见性规则统一**：`validator.py` 和 `editor_panel.py` 各有一份 `_is_internal_field` 黑名单且内容不同步 → 合并为 `FieldDef.is_internal` 属性（`metadata.py`），两处共用同一规则，消除"验证报错但编辑器不显示该字段"的矛盾 bug 类
- **表单计算逻辑提取**：EditorPanel（~850 行）中"显示哪些分组/字段"的决策逻辑（子类型推断、visible_for 过滤、锁定、折叠、可添加字段）提取为 `core/form_plan.py` 纯函数模块，零 Qt 依赖，可无头测试；EditorPanel 降至 ~720 行，只负责渲染
- **ProjectSession 深模块**：MainWindow 的服务组装（Metadata + CommandStack + TemplateEngine + Validator）、工程生命周期（open/create/close）、内容创建、带验证保存、上次工程记忆全部收进 `core/session.py`；MainWindow 退化为布局壳 + 信号转发，`_project` 变为只读属性指向 session 唯一实例
- **config 逃逸口收拢**：`file_tree.py`、`preview_panel.py`、`main_window.py`（editor_state）三处直接读 JSON 的逃逸口改为走 `config_loader`；新增 `get_block_categories()`、`get_sprite_layers()`、`load/save_editor_state()` 便捷函数
- **BulletEditor 透传删除**：70 行纯转发包装（`.value`/`.valueChanged` 全部委托 PolymorphicTypeEditor）删除；`BULLET_TYPES` 常量移入 `polymorphic_editor.py`，调用方直接实例化 PolymorphicTypeEditor

### 修复

- **QDockWidget 未导入**：`main_window.py` 的 `_show_reference_comparison` 使用 `QDockWidget` 但从未 import，参考对比功能首次使用时必崩 → 补入导入
- **无用导入清理**：`main_window.py` 的 `import json`（editor_state 已移入 config_loader）、`file_tree.py` / `preview_panel.py` 的 `import json`（改走 config_loader）

### 测试

- **核心模块覆盖**：新增 `test_metadata.py`（继承链合并、类型别名、is_internal 规则）、`test_content_store.py`（CRUD + 原子写入 + 中文 + 坏 JSON 容错）、`test_validator.py`（三级验证、类型检查、内部字段跳过）
- **表单逻辑覆盖**：新增 `test_form_plan.py`（子类型推断、分组可见性、锁定、折叠、可添加字段过滤）
- **会话流程覆盖**：新增 `test_session.py`（工程 open/create/close、内容创建、带验证保存、undo/redo 委托），全程无 QApplication
- **总量**：49 → 186 个测试，0.3 秒全绿

### 文档

- **CONTEXT.md**：+4 术语（FormPlan / GroupPlan / ProjectSession / SaveReport）

---

## v0.2.1 (2026-07-31 03:04)

> B 阶段 UI 重构全面落地：从"能用但简陋的 Qt 默认界面"重构为"VS Code 气质现代化 IDE 风格编辑器"。

### 新增模块

- **主题系统（theme.py）**：40 个设计令牌（LIGHT/DARK），单一 QSS 模板 + `@TOKEN@` 占位符注入，`apply_theme()` 即时切换无需重启
- **欢迎页（welcome_page.py）**：品牌大字两行错落（第二行缩进铜橙）+ 新建/打开按钮 + 上次工程恢复
- **设置面板（settings_dialog.py + core/settings.py）**：左分类列表 + 右分页表单；主题切换即时生效；其余设置项占位禁用
- **可折叠分组（collapsible_group.py）**：继承 QFrame（非 QWidget，解决 QSS border 不渲染问题），独立圆角白卡片，组头灰底 + 折叠箭头 `▾/▸` + 英文标签 + 操作按钮
- **字段行容器（field_row.py）**：3px 类型色条 + 2px 间隙 + 控件 + 可选红 X 删除按钮（hover 浮现）
- **Toast 提示（toast.py）**：右下角浮层，自动计时 + 淡出动画
- **自绘复选框（check_toggle.py）**：`paintEvent` 画圆角框 + 白勾，颜色从主题令牌读取，深浅自适应
- **去尾零数值框（num_spin.py）**：`NumSpinBox` / `NumDoubleSpinBox`，`textFromValue` 用 `:.Ng` 格式去尾零（300.000→300）
- **自动撑宽输入框（auto_width_edit.py）**：名称档，最小 120px 随文本撑长，上限 280px
- **富文本标签（label_helper.py）**：中文正常 + 英文淡化缩小等宽（`#INK2 / 10.5px / mono`），对齐 HTML 设计稿
- **C 阶段预留（reserved_panel.py）**：统一禁用态按钮 + tooltip「v0.2.2 实现」

### UI 重构

- **三栏布局**：QDockWidget → QSplitter（左 200 / 中自适应 / 右 280），中央 QStackedWidget 切换欢迎页/标签页
- **预览区**：QLabel → QGraphicsView（滚轮缩放 1.15x / 拖动平移 / 像素画 FastTransformation）+ 空态导入引导 + 内部 QSplitter 垂直分割预览/图层
- **标签页**：右键菜单（关闭/关闭其他/关闭全部）+ 文本 `×` 关闭按钮（捕获 panel 引用防索引漂移）
- **文件树**：缩进 18px/级 + 撤 Nieobie 分类图标（纯文本）+ 面板头标题「文件」+ 右键菜单完善
- **工具栏/菜单**：撤全部 Nieobie SVG 图标，改纯文本按钮（`+ 单位` / `保存` / `撤销` 等）
- **状态栏**：自管 `_StatusBar(QStatusBar)` 子类，override `showMessage` 写入自管 QLabel，绕开 Qt 内置 tempLabel 不渲染的 bug

### 交互改进

- **命令描述系统**：Command 基类加 `description` 属性；撤销/重做 tooltip 显示操作描述（如「撤销: 修改 health 为 300」）
- **验证错误跳转**：状态栏可点击错误胶囊 → 切换标签 + 滚动高亮第一个错误字段
- **自动保存反馈**：toast「已自动保存」/「已保存 · N 个验证错误」
- **字段删除**：可选字段红 X 按钮 + `DeleteFieldCommand`（可撤销）；required 字段无红 X
- **武器排序**：`↑/↓` 文本按钮 + `ArrayMoveCommand`（可撤销）
- **新建武器对话框**：模式选择移到最前面；引用模式隐藏名称框（名称从下拉取）；内联模式才显示名称框
- **布尔字段**：全仓 `QCheckBox` → `CheckToggle`（自绘白勾），含基础组/武器组/子弹组
- **字段标签**：全仓纯文本 → 富文本（中文正常 + 英文淡化缩小等宽）

### 视觉设计

- **字段类型马卡龙着色**：7 种类型（num/bool/str/ref/col/arr/obj）淡底 + 同色系描边 + 3px 色条
- **字段组独立卡片**：QFrame + `border: 1px solid @LINE@` + `border-radius: 6px`，白底浮在白底编辑区上靠边框分隔（对齐 HTML 设计稿 `.group`）
- **组头**：灰底 `#F5F5F5` + 折叠箭头 + 中文标题 + 英文标签（mono 10.5px）+ 操作按钮（hover 显示）
- **字段行布局**：逐行 `QHBoxLayout`（标签固定 150px + 控件在右 + stretch），替代 QFormLayout 网格
- **描述字段**：方案 Y（标签独占上一行 + 多行 QTextEdit 撑满下一行，初始 3 行高）
- **三档宽度模型**：短值档 70px（数字）/ 名称档 120→280 撑长 / 描述档撑满多行
- **数值框**：隐藏 spinner（CSS 三角 hack 在 Qt 下失效）+ `padding-left: 8px` 对齐 QLineEdit
- **面板区域标题**：`#panelHeader`（文件树「文件」/ 预览「预览」），对齐 HTML `.panel-h`

### 规范清理

- **内联 setStyleSheet 清零**：全仓仅剩颜色色块动态 hex（正当例外）+ `theme.py` 全局加载器
- **QCheckBox / setArrowType 清零**：全仓仅剩 `check_toggle.py` 注释
- **core 层无 Qt 依赖**：`settings.py` 纯 Python，不 import Qt

### 文件变更表

| 文件 | 变更 |
|:-----|:------|
| `app/ui/theme.py` | **新增** — 40 令牌 LIGHT/DARK + apply_theme + field_type_property |
| `app/resources/style.qss` | **新增** — 单一 QSS 模板，@TOKEN@ 占位符 |
| `app/ui/icon_loader.py` | **新增** — Nieobie SVG 染色缓存（本版本已撤用，保留备用） |
| `app/ui/welcome_page.py` | **新增** — 欢迎页 |
| `app/ui/widgets/collapsible_group.py` | **新增** — QFrame 可折叠分组卡片 |
| `app/ui/widgets/field_row.py` | **新增** — 色条 + 控件 + 红 X 行容器 |
| `app/ui/widgets/toast.py` | **新增** — 右下角浮层提示 |
| `app/ui/widgets/check_toggle.py` | **新增** — 自绘复选框 |
| `app/ui/widgets/num_spin.py` | **新增** — 去尾零数值框 |
| `app/ui/widgets/auto_width_edit.py` | **新增** — 自动撑宽输入框 |
| `app/ui/widgets/label_helper.py` | **新增** — 富文本标签辅助 |
| `app/ui/widgets/reserved_panel.py` | **新增** — C 阶段预留禁用态 |
| `app/core/settings.py` | **新增** — 设置读写模块（无 Qt） |
| `app/ui/dialogs/settings_dialog.py` | **新增** — 设置面板 |
| `app/ui/editor_panel.py` | 重构 — 逐行布局 + 三档宽度 + 富文本标签 + 描述 Y + QFrame 卡片 |
| `app/ui/main_window.py` | 重构 — QSplitter 三栏 + 欢迎页栈 + 自管状态栏 + 撤图标 + 文本关闭按钮 |
| `app/ui/preview_panel.py` | 重构 — QGraphicsView + 空态 + 内部 QSplitter + 面板头 |
| `app/ui/file_tree.py` | 重构 — 撤图标 + 面板头 + 缩进 18px |
| `app/ui/widgets/weapon_array_editor.py` | 重构 — 文本排序 + 左对齐操作按钮 + 对话框重排 + 三档宽度 + 富文本 |
| `app/ui/widgets/polymorphic_editor.py` | 重构 — 三档宽度 + 富文本 + spacing 4 |
| `app/core/commands.py` | 扩展 — description 属性 + DeleteFieldCommand + ArrayMoveCommand |
| `app/main.py` | 修改 — 启动时读取已保存主题 |
| `app/config/settings_default.json` | 修改 — 新增 theme 字段 |

---

## 特别更新：汉化翻译规范与全量重写 (2026-07-31 02:09)

> 不计入版本号。本次为翻译质量专项整改，涉及全部 732 个字段的名称翻译和提示文本。

### 架构改进

- **汉化翻译规范体系（ADR-007）**：建立完整的翻译执行标准，确保后续维护一致性
  - 布尔字段按语义分五类句式：能力（是否可）/ 被动可能性（是否会）/ 行为开关（是否要）/ 固有属性（是否是/是否）/ 许可（是否允许）/ 绘制（是否绘制）
  - 提示文本按字段类型采用结构化模板：布尔三段式（定义→true表现→false表现→适用范围）、数值四段式（定义+单位→效果→范围→原版参考）
  - 单位规范：时间用 tick（60 tick = 1 秒）、距离用像素（1 格 = 8 像素）、概率标注 0~1
  - 字段分三级：核心（完整模板+源码验证）/ 常用（完整模板）/ 内部（精简+标注"通常无需修改"）

### 调整

- **布尔字段名称全量修正**：239 个布尔字段统一为规范句式，消除语义歧义
  - `omniMovement`：是否全向移动 → 是否可全向移动（能力类）
  - `rotateMoveFirst`：是否先转向再移动 → 是否要先转向再移动（行为开关类）
  - `canDrown`：是否可溺水 → 是否会溺水（被动可能性类）
  - `solid`：是否固体 → 是否是固体（名词谓语加"是"）
  - `killable`/`hittable`/`targetable`：是否可击杀 → 是否会被击杀（被动可能性）
- **非布尔字段名称纠错**：`blockArmorMultiplier` 建筑护甲倍率 → 方块护甲倍率（术语一致性）
- **6 个字段分类修正**：`databaseTabs`/`despawnUnit`/`envDisabled`/`envEnabled`/`envRequired`/`scaledHealth` 从错误的布尔句式改回非布尔名称
- **提示文本全量重写**：732 条提示文本按结构化模板重写
  - 布尔字段：统一"设为 true 时…设为 false 时…"对比格式
  - 数值字段：补充单位标注、典型值范围、原版参考值
  - 内部字段：精简为一句话 + "内部字段，通常无需修改"
  - 总字符数从 17,619 → 27,240（信息密度提升 55%）

### 文档

- **新增 `Docs/ADR/007-汉化翻译规范与结构化提示文本.md`**：决策记录（背景、决策、否决方案）
- **新增 `Docs/汉化翻译规范.md`**：执行参照标准（五类句式规则、模板格式、单位规范、术语表、验收标准）
- **更新 `CONTEXT.md`**：新增 3 个术语条目（字段名称翻译、提示文本、字段分级）

### 文件变更表

| 文件 | 变更 |
|:-----|:------|
| `app/config/field_names_zh.json` | 全量修正 — 239 个布尔字段句式统一 + 非布尔纠错 + 补充 4 条 |
| `app/config/field_docs.json` | 全量重写 — 732 条结构化提示文本 + 补充 13 条 |
| `Docs/ADR/007-汉化翻译规范与结构化提示文本.md` | **新增** — 决策记录 |
| `Docs/汉化翻译规范.md` | **新增** — 执行参照标准 |
| `CONTEXT.md` | 新增 3 个术语条目 |

---

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
