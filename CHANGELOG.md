# Changelog

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
