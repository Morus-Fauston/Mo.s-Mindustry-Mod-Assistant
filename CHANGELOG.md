# Changelog

## v0.4.0-alpha.18 (2026-10-06 06:26) — 上半 UI 重构：现有内容与工程操作

### 新增

- **真实文件操作**：从核心模板取得类别与名称规则，新建、覆盖、重命名、删除及系统定位连接真实工程；匹配贴图随既有命名规则迁移，跨类别同名互不影响，不扩展全工程引用重写。
- **工程与单一历史**：通过原生父目录选择创建现有格式工程；内容与新工程命令共用当前会话命令栈，撤销新工程后的空工作台仍可重做。未保存修改提供保存已打开内容、放弃受影响修改与取消。

### 修复

- **身份与失败保护**：文件命令同步对象、源码、表单附属状态及历史路径，保留根数据身份；回调失败恢复磁盘与内存，拒绝外部改写，重复请求不重复执行。超时可在操作弹窗内查询原请求。
- **无变化与资源释放**：同名重命名不再清掉非法源码输入；新工程历史仅保留必需文档身份服务，释放旧预览缓存。资源管理器参数拆分开关与路径，修复中文空格路径回落文档目录。

### 技术

- **自动检查**：准确快照1220项Python、208项前端、类型检查与构建通过；6条Windows WebView2路径覆盖原生取消、模板与覆盖、实际磁盘历史、超时查询、同名草稿及资源管理器真实选中项。测量全部新增输入文本起点。
- **输出对照**：130次真实桥接请求后厨房水槽ZIP由53变58条目，新增13、移除8、原路径字节变化0；两组引擎零错误，警告33到34的净增为新建Wall默认字段，完整差异已核对。旧核心Categorys与独立Weapon输出限制保持单列。
- **交付边界**：第18票自动化完成；新建工程最近路径持久化由第20票合并状态写入处理，实际系统DPI、最终50轮组合回归及发行包仍由21/22集中验收，不代表上半版本完成。

---

## v0.4.0-alpha.17 (2026-10-06 05:51) — 上半 UI 重构：贴图生成与命名输出

### 新增

- **真实贴图生成**：迁移既有轮廓、阴影和完整图算法，中文参数与PNG候选可预览、取消或明确覆盖后写入，整批生成进入同一命令栈并可撤销重做。
- **失败与恢复**：来源、目标及参数复核，批次失败恢复旧文件；旧会话隔离、候选和缓存图片清理。预览与确认超时只查询原请求，恢复的预览释放后重新选择，确认不重复写入。

### 技术

- **自动检查**：准确快照1129项Python、168项前端、类型检查与构建通过；2条Windows WebView2路径覆盖真实PNG、全部输入起点、取消/覆盖/历史与两次超过15秒的结果查询。
- **实际输出**：厨房水槽ZIP仅新增3张、修改3张PNG，23个内容JSON不变；基线与生成后均E0/W33/I5，全部诊断一致。六图字节、尺寸与alpha对照通过；保留旧核心9条引用错误、独立Weapon输出限制、每组16音乐错误及Unsafe警告。
- **交付边界**：第17票自动化完成，未扩充生成算法或引入下半格式；系统DPI、50轮及发行包仍由21/22集中验收。

---

## v0.4.0-alpha.16 (2026-10-06 05:37) — 上半 UI 重构：现有动态预览

### 新增

- **动态预览**：从真实素材与核心描述迁移播放、暂停、单步、开火及移动、速度、方向、队伍和生命值控制；保留现有履带、后坐、引擎与热图子集。
- **时钟与资源**：按实际耗时有界推进，隐藏、最小化和切内容释放旧绘制；染色使用Qt像素参考，统一资源预算，不逐帧桥接或修改业务历史。

### 修复

- **恢复最大化**：最小化后恢复到最大化未触发restored事件，补maximized通知以恢复动画。
- **外部素材刷新**：NTFS快速同大小覆写可保留相同时间戳，原stat观察漏检；增加单轮32MiB、单文件16MiB的摘要轮询和公平轮转，读取失败清旧摘要并释放句柄。

### 技术

- **验证**：准确快照1077项Python、150项前端、类型检查和构建通过。5条相关WebView2回归通过，最终修复后再验完整动态与原生资源操作2条；覆盖滚动隐藏、最小化恢复、非白像素染色及全部输入起点。
- **交付边界**：第15票自动化完成；本票不改变游戏输出、不新增渲染范围。系统DPI矩阵、50轮组合回归及发行包留21/22，未宣告整版验收通过。

---

## v0.4.0-alpha.15 (2026-10-06 05:17) — 上半 UI 重构：校验定位与现有导出

### 新增

- **真实校验**：从当前会话内存和未打开文件读取核心校验结果，按完整文件路径展示错误与警告；定位展开字段或源码，缺少精确位置明确退到文件。
- **现有导出闭环**：沿保存已打开内容路径生成真实 ZIP，原生取消仍同步已保存状态；输出字节数与 SHA256，失败保留原目标并清理临时文件。

### 修复

- **读取竞态**：导出与校验读取前核验已打开文件句柄归属及身份，再从同一句柄有界读取，阻断检查后替换为工程外链接。
- **定位与恢复**：过期报告不套用旧字段位置；首次打开文件后重新核验问题。源码行列转换兼容 Unicode，无行列也可切源码；超时仅查询原导出请求并保留准确结果。

### 技术

- **自动检查**：准确隔离快照1043项Python、128项前端与类型检查构建通过；最终3条相关Windows WebView2路径通过，实测原生取消、超过15秒超时查询、ZIP读回、同名定位及全部输入起点，复用本票前轮源码与保存回归。
- **输出对照**：厨房水槽53条目真实导出，仅预期Wall描述变化；两组引擎均E0/W33。旧核心9条Categorys引用错误保持一致，沿既有未完成配置策略允许导出；独立武器输出限制单列。每组另有16音乐错误、1网络连接重置及4行Unsafe告警。
- **交付边界**：第12票自动化完成；系统DPI矩阵、50轮及发行包留21/22，未宣告整版完成或新增下半文件格式。

---

## v0.4.0-alpha.14 (2026-10-06 04:50) — 上半 UI 重构：图层与安装坐标

### 新增

- **真实图层**：静态图层树和武器分支使用真实场景与稳定项身份；选择、显隐、折叠分离，镜像同步显隐，表单与图层可双向定位。
- **安装坐标**：图层复用字段输入与唯一命令栈；引用武器缺失坐标显示预览同源值而不写入默认，编辑、重排、撤销及保存重开保持一致。

### 修复

- **视图保留**：过期定位不随刷新重放，同项重复定位可以滚动，关闭活动标签保留其他文档图层状态；坐标编辑保持视口，未改变的贴图保持资源身份。
- **错误反馈**：PNG加载失败不再因文件存在而误标可用，损坏引用保留显式坐标并标明问题；图层列表不再被素材区挤成单行。

### 技术

- **自动检查**：本票准确隔离992项pytest、112项前端、类型检查与构建通过；5条相关Windows WebView2路径通过。实测镜像、负坐标、PPU=4与Y翻转、所有输入起点，核对最终截图。
- **游戏输出**：79次真实请求与7份场景构造同名镜像武器坐标样本，A4基线与编辑样本均E0/W27且警告相同。两组各16音乐文件错误，旧武器引用输出限制单列。
- **交付边界**：第14票自动化完成；系统DPI矩阵、集中50轮与发行包仍未验收，不代表整个上半完成；第12票校验导出代码独立保留待接入。

---

## v0.4.0-alpha.13 (2026-10-06 04:31) — 上半 UI 重构：JSON 源码共享编辑

### 新增

- **源码编辑**：CodeMirror 中文查找替换、行号、显式格式化与每文档视图记忆；约500ms提交及输入组合边界，和表单共用唯一会话命令栈，保留未知字段与大整数。
- **损坏内容修复**：首次坏JSON显示原文与位置，不伪造空对象；修复、表单修改、撤销重做及保存点沿用真实核心身份。非法草稿禁止保存，旧表单只读并允许明确放弃或取消关闭。

### 修复

- **异步反馈**：隔离迟到格式化、旧会话与关闭重开；首次解析错误不再取消修正后的自动提交，非法输入失焦时保留提示位置，避免切视图按钮移位。
- **数据边界**：放弃修改同时恢复表单缓存；降级表单返回完整结构；非法Unicode内容保持可修复状态，不破坏工程响应。源码预算同时覆盖缩进、Windows换行与保存后的重新读取。

### 技术

- **请求恢复**：源码请求按4MiB及深度/节点预算校验；响应缓存有总量限制和已执行墓碑，结果过期仅刷新实际状态，不重放写入。
- **自动检查**：准确本票隔离946项pytest、107项前端、类型检查与构建通过；5条真实Windows WebView2路径通过，全部输入起点与截图已复核。独立审查发现均已修复复验。
- **游戏输出**：59次真实请求验证源码与表单、保存和既有核心导出；A4基线E0/W15、编辑样本E0/W14，新增描述消除空描述警告，其余14条相同。两组各16音乐文件错误，未据此声称音频验收通过。
- **交付边界**：第11票自动化完成；真实中文输入法体验、完整系统DPI、50轮回归及发行包仍待21/22集中验收。本票未增加下半格式或崩溃恢复。

---

## v0.4.0-alpha.12 (2026-10-06 04:09) — 上半 UI 重构：研究与星球配置

### 新增

- **研究编辑**：父节点、研究材料、五种目标及星球、根节点、名称、解锁设置接真实配置表单；研究需求支持1到999999整数，同名项稳定重排删除与撤销。
- **星球集合**：读取保留原值，用户明确添加或修改时按既有集合规则去重；空集合移除字段。引用使用正确类别的中英文候选，未知类型和旧字符串不自动转换。

### 修复

- **上下文说明**：研究名称、材料需求和目标类型改用集中配置中的专用中文帮助，避免将科技树名称解释为文件名、研究材料解释为建造材料。

### 技术

- **统一状态**：源码仍为既有存储格式，研究与深层武器/能力共用同一表单状态、草稿和命令栈；校验、旧会话、请求去重及保存失败沿用真实桥接保护。
- **自动检查**：准确本票隔离873项pytest、97项前端、类型检查与构建通过；5条相关Windows WebView2路径通过，测量全部输入起点并核对截图。独立审查发现的说明问题已修复复验。
- **游戏输出**：155次真实请求构造研究样本，保存导出重新读取一致；A4基线与编辑样本均结构化E0/W14，告警逐条相同。原生日志各16条音乐错误和1条社区服务器连接重置单列，不计作音频或联网验收。
- **交付边界**：第10票自动化完成，不代表战役中五种研究目标条件均已实际达成；系统DPI、最终50轮回归和发布包由21/22集中验收。

---

## v0.4.0-alpha.11 (2026-10-06 03:55) — 上半 UI 重构：武器编辑

### 新增

- **武器数组**：真实工程支持引用与内联两种新增方式、覆盖字段、显式展开、稳定身份重排删除及撤销，内嵌子弹与独立武器共用配置表单和原会话命令栈。
- **明确转换**：展开优先保留使用处覆盖且不修改独立源，缺源仅在明确确认后创建空白内联；损坏源与非有限数据反馈错误，保留引用。

### 修复

- **候选隔离**：某个工程JSON顶层为数组曾使全部工程候选消失，现在逐文件跳过非对象，正常候选仍可选。
- **递归能力**：武器中新产生的单位节点改为即时递归能力数组，避免扩展顺序漏掉深层能力，稳定项身份和预算共用。

### 技术

- **自动检查**：准确本票隔离815项pytest、89项前端测试、类型检查与构建通过；8条相关Windows WebView2路径全部通过，全部输入起点与新增表单截图有当前证据，双轴独立审查无确定阻断。
- **游戏输出**：96个真实Workspace请求生成保存导出样本；基线结构化E0/W34、三项显式内联样本E0/W48，新增14条为两个BasicBulletType实例重复既有7类字段告警；原生日志各16条相同音乐错误另行研判，不代表音频通过。
- **交付边界**：第08票自动化完成。旧独立武器是编辑资料，保存和导出不自动展开引用；原版含非有限值的源展开明确拒绝。完整系统DPI、最终50轮组合回归及发行包仍由21/22集中验收。

---

## v0.4.0-alpha.10 (2026-10-06 03:30) — 上半 UI 重构：能力数组

### 新增

- **能力数组编辑**：15种既有能力接入配置驱动表单，新增使用旧默认值；同名能力按稳定项标识编辑、重排、删除和撤销，保存重开保留实际数据。
- **能力类型与引用**：类型切换保留其他字段，未知或缺类型的旧能力不自动改值；生成单位类能力的单位字段使用真实引用选择。

### 技术

- **共享状态**：能力类型族与数组节点注册到既有嵌套表单，复用基础/引用控件、唯一命令栈、预算保护及保存快照，不新增前端业务规则。
- **自动检查**：本票隔离完整pytest 782项、前端82项、类型检查与构建通过；5条相关真实宿主路径有当前通过证据，修正重开测试的加载/折叠时序，保留原失败记录。
- **游戏输出**：两类能力及重复项的真实编辑、重排、删除撤销、保存导出样本A4与本轮基线均结构化E0/W34；不代表全部15类都已做引擎专项验证。
- **交付边界**：第07票自动化完成，原生日志环境错误单独归档；系统DPI矩阵、最终50轮回归与发行包仍留21/22集中验收。

---

## v0.4.0-alpha.9 (2026-10-06 03:17) — 上半 UI 重构：资源字段与消耗

### 新增

- **资源列表与槽位**：物品/液体引用、数量、输出槽、列表增删重排接入真实工程；统一中英文候选与稳定项身份，清空槽位保存为既有null格式。
- **消耗编辑**：迁移既有物品、液体、电力、热量及加速选项，保留零值与未知字段；生产及战斗内容共用原会话命令、撤销和保存。

### 修复

- **数值校验**：数量边界与两位小数在Python校验；先检查精确十进制值再转浮点，拒绝极小值下溢和精度丢失绕过，失败不改变内容和历史。
- **资源界面**：补齐资源字段中文名和帮助，列表删除/移动后恢复焦点；共享递归表单扩展专用控件入口。

### 技术

- **自动检查**：本票隔离完整pytest 745项、前端82项、类型检查构建通过；真实Windows WebView2全34条路径通过，含资源保存重开、错误草稿、零值、空槽、加速开关、长候选与页面200%缩放。
- **游戏输出**：生产/战斗夹具基线A4零错误57条警告，真实编辑结果零错误55条（均指结构化报告）；两次原生日志均有16条相同音乐加载错误，未新增。既有heat/coolant表示的引擎限制独立记录，不冒充已支持游戏输出。
- **交付边界**：第09票自动化完成，研究/星球集合留10；完整系统DPI、最终50轮回归与发行包仍待21/22集中验收。

---

## v0.4.0-alpha.8 (2026-10-06 03:03) — 上半 UI 重构：多态与嵌套表单

### 新增

- **多态与递归表单**：迁移既有4种单位及5种子弹类型，字段组和嵌套对象由元数据/配置生成；未知类型保留原数据并明确反馈。
- **普通数组编辑**：新增、删除和重排使用会话项标识，重排后草稿、字段地址和焦点仍对应原项目；嵌套引用与基础字段复用现有控件。
- **统一历史**：类型、嵌套内容和数组修改进入原命令栈；保存、放弃和撤销一起恢复数据与表单状态，不新增磁盘格式或业务历史。

### 修复

- **中文与焦点**：修正标量数组项英文标签、已知基础类型误标未知，以及数组移动后按钮禁用造成的焦点丢失。

### 技术

- **自动检查**：本票隔离完整pytest 720项、前端77项、类型检查和构建通过；真实Windows WebView2全32条路径通过，包含本票类型/数组/未知值/引用/保存与撤销路径。
- **游戏输出**：真实服务编辑往返及同结构内联子弹样本A4零错误、33条结构化警告，较旧基线少1条且无结构化新增；原生日志另有1条保留字段height不属于Laser类型的提示，单列保留。独立武器导出当前不展开引用。
- **交付边界**：本票自动化实现完成；能力/武器专用数组分别留07/08，系统DPI矩阵、最终50轮组合回归与发行包仍待集中验收，不代表整个上半通过。

---

## v0.4.0-alpha.7 (2026-10-06 02:46) — 上半 UI 重构：贴图资源操作

### 新增

- **真实贴图操作**：资源面板迁移既有主体和附层命名，通过原生PNG选择器导入/明确替换及确认删除；取消不写盘，定位仅接受当前工程真实目标。
- **资源撤销**：PNG字节快照与文件写入进入现有会话命令栈，撤销/重做恢复真实文件，树节点和预览随实际磁盘刷新。
- **外部图片变化**：有界PNG观察更新预览及资源节点，切工程/关闭清理快照与轮询，旧会话迟到结果不能覆盖当前界面。

### 修复

- **资源失败保护**：验证真实PNG格式/CRC/解码及内存预算，临时文件原子替换；外部修改拒绝覆盖，失败撤销/重做保留历史以便恢复后重试。
- **原生验收定位**：分别识别文件/文件夹对话框输入控件，引用弹层测试明确点击顶栏，避免新增资源标题后的选择器歧义。

### 技术

- **自动检查**：准确本票隔离完整pytest 695项、前端69项、typecheck和build通过；完整真实WebView2运行28项通过，1项测试定位修正后独立补验通过，共覆盖29条路径。新增原生PNG取消/替换/删除/撤销/重做/损坏拒绝与外部刷新。
- **游戏输出**：真实资源命令及保存导出样本A4零错误、34条Warning与既有基线逐条一致，无新增；ZIP、文件字节、独立读回与预览像素交叉核对。
- **交付边界**：第16票完成，不含第17票贴图生成；完整系统DPI矩阵、最终50轮回归及发行包仍按21/22集中验收，不代表上半版本全部通过。

---

## v0.4.0-alpha.6 (2026-10-06 02:26) — 上半 UI 重构：统一引用选择

### 新增

- **引用选择**：基础引用字段接入Python真实类别候选，支持中英文检索、分类书签、未知已有值、空候选和明确清除；保存实际英文标识，候选读取不写脏。
- **键盘弹层**：迁移上下选择、Enter确认、Esc/外部点击取消、搜索清空和焦点返回；Tab可达弹层操作，窄栏使用独立弹层避免滚动容器裁切。

### 修复

- **撤销边界**：连续引用选择被文本合并规则吞并，保存后撤销也无法抵达已保存状态；现仅合并同段文本输入，离散选择及保存/撤销/重做切断合并。
- **异步检索**：迟到搜索结果与旧会话隔离，类别及输入校验仍由Python负责，不建立前端业务历史。

### 技术

- **自动检查**：本票隔离快照完整pytest 664项通过；工作区完整732项通过，含并行模块。前端69项（含并行资源模块5项）、typecheck、build通过；27条真实WebView2回归全部通过，含3条引用路径及全部输入起点测量。独立双轴审查发现的键盘及合并问题已修复。
- **游戏输出**：液体引用water→oil经真实编辑/撤销/保存导出后A4零错误、33条Warning；itemDrop样本及不经05修改的copper控制均触发验证器wallOres未初始化错误，按既有验证器缺口保留失败及归因，不称该引擎路径通过。
- **交付边界**：第05票功能自动化完成；完整Windows系统DPI矩阵在21集中验证，A4上述缺口单列。未宣布上半版本或发布包完成。

---

## v0.4.0-alpha.5 (2026-10-06 02:06) — 上半 UI 重构：基础字段与能力组

### 新增

- **基础字段**：数值、字符串、布尔、RGBA颜色经同一Python命令栈编辑和保存；默认展示不写脏，非法输入保留草稿与字段错误，颜色选择保留原透明度。
- **能力与字段组**：复用配置驱动表单计划、字段增删、锁定组、能力缓存及单向联动；能力开关与折叠独立，依赖不满足保留值并解释原因。
- **中文表单**：字段名称及帮助读取共享配置，马卡龙背景与饰条由集中令牌管理，保留20px复选框、14px勾和22px饰条。

### 修复

- **游戏别名**：类型归一化过早会丢失坦克等子类型，现以原始类型判定显隐与锁定，只归一化配置键。
- **草稿与操作协调**：异步响应只清理对应代次且文本未改变的草稿，中文组合期间不提交，保存与关闭统一等待合法草稿；非法颜色可由颜色选择恢复。
- **其他字段组**：聚合组没有配置级整体删除规则却显示删除入口，现由权威计划锁定整组，仍保留逐字段删除和撤销。

### 技术

- **验证**：本票隔离快照完整pytest 642项通过；58项前端测试、typecheck和build通过。23条完整真实WebView2回归加1条聚合组补验通过；浅深主题、100/125/150/200%原生页面缩放下测量全部输入起点。双轴审查发现的同一问题已修复并补红绿回归。
- **游戏输出**：真实请求编辑、撤销、保存后导出的基础字段样本通过A4，ERROR=0，33条Warning与既有报告原文一致且无新增；不以此代替宿主验证。
- **交付边界**：本票自动化完成；中文组合事件注入不等于系统输入法候选窗验收，页面缩放不等于Windows系统DPI矩阵。两项保留在集中人工/最终验收清单，未宣布上半整体交付或发布包验收完成。

---

## v0.4.0-alpha.4 (2026-10-06 01:22) — 上半 UI 重构：真实素材静态预览

### 新增

- **真实素材预览**：右侧Canvas通过当前Python工程读取真实PNG，迁移既有静态层次、PPU=4、Y方向、武器镜像与子类型过滤；支持鼠标中心缩放、拖动平移、适应、透明棋盘及网格。
- **异常恢复**：主体缺失或损坏时显示中文原因，可刷新恢复；附层失败保留可用图层及视口操作，切页后的迟到场景不会覆盖当前内容。

### 架构改进

- **受控资源**：PNG资源ID绑定当前工程与场景，校验归属、文件类型、CRC和解码尺寸；前后端限定累计像素预算，限制资源数、文件及编码缓存，并清理旧图片、计时器和监听。
- **只读边界**：预览复用串行桥接，不改变已打开文档、dirty、历史或磁盘数据；预览响应不进入业务结果缓存，防止旧图片跨场景滞留。

### 技术

- **验证**：后端563项、前端46项测试及类型检查、构建通过；15条真实WebView2整合路径通过。当前150%系统缩放下直接采样PNG像素、Canvas尺寸与实际滚轮锚点，并记录全部输入起点。双轴代码审查无必要返工项。
- **交付边界**：本票完成静态预览；完整窗口/DPI矩阵、图层编辑、动态预览及新发行包仍由后续票交付。本票不改变游戏输出，未重复运行A4。

---

## v0.4.0-alpha.3 (2026-10-06 00:58) — 上半 UI 重构：编辑、撤销与保存闭环

### 新增

- **真实编辑与历史**：单位生命值接入 Python CommandStack，同一会话负责撤销和重做，显示实际历史操作；按工程路径隔离同名内容，已关闭文档被历史操作影响时重新打开显示。
- **保存已打开内容**：按钮与 Ctrl+S 写入当前全部已打开内容，保留旧自动保存间隔设置；成功写盘后才清除对应未保存状态，部分失败保留未写成功项，不假装多文件事务。
- **关闭裁决**：关闭标签、切换工程和原生窗口关闭共用保存、放弃、取消流程；原生关闭先取消，再异步询问，保存失败留窗，批准退出后冻结新操作。

### 修复

- **异步请求隔离**：关闭全部后迟发读取可能重新进入保存范围，现以预期版本拒绝；晚到读取不抢回用户切换的标签。修改超时只查询原请求结果，确认前阻止继续修改。
- **错误反馈**：负数和非法生命值显示字段错误；保存前重新校验真实路径及文件类型，磁盘占用或路径变化不丢失内存修改。

### 技术

- **验证**：当前工作区后端560项、前端44项测试通过（包含并行第13票的19项后端及5项前端独立测试；预览代码未纳入本票提交）。类型检查、构建和12条真实WebView2路径通过，记录输入文本起点。A4最小样本真实修改保存后加载无错误，单位与方块各600tick通过，34条警告与既有基线逐项相同。
- **交付边界**：本票仅完成单字段编辑闭环；既有磁盘格式及会话级历史保持，未引入下半可靠保存体系。完整控件、多档DPI及新发布包仍由后续票交付。

---

## v0.4.0-alpha.2 (2026-10-06 00:26) — 上半 UI 重构：真实工程树与标签

### 新增

- **真实工程浏览**：欢迎页最近工程与原生目录选择接入现有 Python 会话；保留单位、方块虚拟分组、独立武器和贴图节点，支持中文显示名搜索、键盘导航、折叠恢复与品牌色选中条。
- **文档标签**：按会话与规范化路径区分同名内容，展示真实内容摘要；重复打开复用标签，支持关闭、关闭其他与关闭全部，页面视图独立保留。
- **受控桥接**：串行访问核心，限制待处理请求与结果缓存，重复请求不重复执行；打开超时后查询原操作结果，旧会话与已关闭页面的迟到响应不再覆盖当前界面。

### 修复

- **异常工程反馈**：损坏 JSON 保留可定位树节点；最近工程消失、名称类型异常、取消选择与路径越界均有对应处理，失败保留原工程。

### 技术

- **兼容核心入口**：新增明确类别路径读取与会话内文档缓存，旧裸名称接口保持兼容，不改变磁盘格式或提前引入下半文件核心。
- **验证边界**：514 项 pytest、36 项前端测试、类型检查和构建通过；6 条真实 WebView2 流程覆盖同名内容、搜索/键盘/标签、原生目录选择、超时结果恢复、迟到读取和失效路径，另补验搜索折叠恢复及全部输入起点。编辑保存和预览仍由后续票迁移，完整 DPI/发布包验收在末期完成。

---

## v0.4.0-alpha.1 (2026-10-05 23:49) — 上半 UI 重构：桌面壳与离线资料

### 新增

- **真实 Web 桌面入口**：React/TypeScript 三栏工作台通过 pywebview/WebView2 读取 Python 离线元数据，显示版本、类型与分类数量；保留旧 Qt 入口，不改变工程格式。
- **启动故障反馈**：桥接就绪等待、协议检查、并发读取合并、有限超时、损坏响应拒绝及手动重试；元数据缺失或损坏时显示中文错误，不回退为假数据。
- **宿主保护**：拒绝 pywebview 的 MSHTML 降级，加载超时关闭失败窗口并反馈；静态服务只暴露随包前端资源。

### 技术

- **可重复开发与打包**：锁定前端及 Windows Python 依赖，提供类型检查、单元测试、真实宿主测试和目录包测试入口；新目录包排除 Qt。
- **视觉规则**：集中 CSS 变量与 CSS Modules，保留三栏、浅色与深色令牌、品牌色及马卡龙类型配色；同步 Agent 的 Web 样式与宿主验证要求。
- **验证边界**：474 项 pytest、12 项前端测试、类型检查与构建通过；真实 WebView2 启动及元数据缺失修复重试 2 项通过，目录包在清理开发工具 PATH 后启动通过。尚未证明完整功能迁移、多档系统 DPI 或无开发环境机器验收；这是首票开发壳，不是上半正式交付。

---

## v0.3.0 (2026-10-05 20:00) — 批次 5：候选版验收收尾与动态预览精修

### 修复

- **原版字段语义对齐**：`Mathf.absin` 此前按正弦周期近似，导致 cell 脉动相位与真实引擎不符（残血红队初始色偏暗）。现按 Arc 的实现 `(sin(t/(2·scl))·mag + mag)/2` 计算，残血初始色由 `#230707` 修正为 `#851a1a`。
- **朝向角度基准**：四向角度以"右=0°"为基准，与 Mindustry 中 0° 指向上方不一致，渲染出的朝向整体偏转 90°。现改为"上=0°、右=90°、下=180°、左=270°"，并把默认朝向与下拉顺序统一为"上"开头。
- **枪口闪光落点**：闪光画在贴图顶部（头部）而非武器挂点，且没有武器时也会出现。现仅在有 `weapons` 时绘制，并按武器坐标逐个定位。
- **Research 未知字段丢失**：`as_research_object` 只保留七个已知字段，编辑 `parent` 等已支持字段时会静默丢弃模型未识别的键。现整体深拷贝原对象，只在 UI 层限制可编辑面；未知字段在撤销/重做中同样保留。
- **用户备注不入命令栈**：`$notes` 直接写 `data` 且不标记 dirty，无法撤销、保存状态不同步。现改为通过 `SetFieldCommand` / `DeleteFieldCommand` 写入并发出 `data_changed`。
- **武器坐标修改不可撤销**：图层树武器 x/y 直接改 dict，绕过命令栈。现由预览面板统一经命令栈写入，撤销/重做可回退到原值。

### 调整

- **动态预览控件改版**：入口由 `▶` / `Ⅱ` 符号改为"开始预览 / 结束预览"，新增独立"暂停帧 / 继续播放"，去掉 emoji 式图标并统一为纯中文。
- **控件排版与热区**：动态预览控件由两行横向布局改为网格布局并加中文标签，所有下拉与按钮固定宽度 82px；动态模式禁用视图拖拽，退出时恢复。
- **预览缩放不再被刷新重置**：`_refresh_preview(reset_zoom=False)` 默认保留用户当前缩放，仅在切换内容时重置。
- **停止自动开火**：动态预览不再在后坐和热量归零时自动补射，开火只由"开火一次"显式触发。

### 新增

- **动态预览示例**：`examples/dynamic_preview_demo/` 提供不依赖测试夹具的示范工程（中英双语 README、`run.bat`、`run_demo.py`），扫描本地参考模组并使用真实 `Project`/`ContentData`/`PreviewPanel` API 演示动态预览。

### 架构改进

- **预览面板依赖注入命令栈**：`PreviewPanel(command_stack=None)` 接收 `CommandStack`，未传入时自建；所有写回内容的操作统一走命令栈。

### 文档

- **CONTEXT.md**：新增"可解锁内容"和"Research（研究配置）"术语，明确 parent / Research / Produce 与 SectorComplete / OnSector / OnPlanet 的引用范围；修正 BulletType 说明，指向 ADR-011（v8 无独立 bullet content 解析器，必须内联）。
- **AGENTS.md**：新增 Skill 工作流与 Agent skills 章节（票据存 `.scratch/`、领域文档布局），提交范围由 `蓝钢-欢迎您/` 改为 `辅助项目/`。

### 技术

- **本地资料不入库**：`.gitignore` 增加 `.scratch/`、`Docs/验证反馈/`、`.vscode/settings.json`、`tools/draw_ui_mockups.py`，参考模组目录更名为 `辅助项目/`。

### 文件变更表

| 文件 | 变更 |
|:-----|:------|
| `app/core/preview_math.py` | 新增 `arc_absin`；朝向基准改为上=0°；cell 脉动按 Arc `absin` 计算 |
| `app/core/research_model.py` | `as_research_object` 保留未识别的 Research 键 |
| `app/ui/preview_panel.py` | 命令栈注入；控件网格布局与中文文案；暂停帧；保留缩放；枪口闪光定位 |
| `app/ui/editor_panel.py` | `$notes` 改为可撤销命令写入 |
| `app/ui/main_window.py` | `APP_VERSION` 同步为 `0.3.0-alpha.5`；向预览面板传入命令栈 |
| `examples/dynamic_preview_demo/` | **新增** — 动态预览示范工程 |
| `CONTEXT.md` | +2 术语；BulletType 说明指向 ADR-011 |
| `AGENTS.md` | +Skill 工作流、Agent skills；提交范围更新 |
| `.gitignore` | +`.scratch/`、`Docs/验证反馈/`、`.vscode/settings.json` |
| `tests/test_preview_math.py` | +`arc_absin` 与朝向断言 |
| `tests/test_preview_panel.py` | +暂停帧、控件宽度、武器坐标撤销、闪光定位 |
| `tests/test_editor_panel.py` | +Research 未知字段与 `$notes` 命令栈 |
| `tests/test_research_model.py` | 断言改为保留未知字段 |

---

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

> 用户反馈的 7 项 UI 问题全量修复（根因报告：`Docs/历史规格/v024-UI体验问题根因报告.md`）。

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
- 新增 `Docs/历史规格/v021-UI设计需求书.md`：B 阶段 UI 设计完整需求

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
| `Docs/历史规格/v021-UI设计需求书.md` | **新增** |
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
