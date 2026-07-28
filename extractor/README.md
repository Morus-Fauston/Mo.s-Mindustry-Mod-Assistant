# Metadata Extractor

Java 一次性工具，通过反射从 Mindustry 中提取元数据，输出结构化 JSON 目录供 Python 编辑器使用。

## 前置条件

- JDK 17+
- 网络连接（首次构建时从 JitPack 拉取 Mindustry core 依赖）

## 使用方法

```bash
cd extractor

# 方式一：直接运行（输出到 ../metadata/）
gradle run

# 方式二：指定输出目录
gradle run --args="--output D:/path/to/metadata"

# 方式三：打包为 fat jar 后运行
gradle jar
java -jar build/libs/metadata-extractor.jar --output ../metadata
```

## 输出结构

```
metadata/
├── manifest.json              ← 总索引
├── classes/
│   ├── UnitType.json          ← 类的字段定义
│   ├── Block.json
│   ├── Wall.json
│   ├── ItemTurret.json
│   ├── Weapon.json
│   └── BulletType.json
├── instances/
│   ├── UnitTypes/
│   │   ├── dagger.json        ← 原版单位的完整属性值
│   │   ├── mace.json
│   │   └── ...
│   ├── Blocks/
│   │   ├── duo.json
│   │   └── ...
│   ├── Items/
│   ├── Liquids/
│   └── StatusEffects/
└── docs/
    └── field_docs.json        ← 字段注释（预留，v1 为空）
```

## 目标版本

锁定 Mindustry **v159**。JitPack 依赖坐标：`com.github.Anuken.Mindustry:core:v159`

如果 JitPack 拉取失败（超时），手动下载 Mindustry 的 `core.jar` 放到 `libs/` 目录，并修改 `build.gradle`：

```groovy
dependencies {
    implementation files('libs/core.jar')
    implementation 'com.google.code.gson:gson:2.11.0'
}
```

## 何时需要重新运行

- Mindustry 发布新大版本时
- 编辑器需要支持新的 Content 类型时（修改 `ClassExtractor.TARGET_CLASSES`）
- 需要导出更多实例字段时（修改 `InstanceExtractor.FIELD_WHITELIST`）

## 已知风险

| 风险 | 说明 | 缓解 |
|------|------|------|
| Headless 初始化失败 | Mindustry 的 `ContentLoader` 在无窗口环境下可能缺少依赖 | 捕获异常，输出警告，class 提取不受影响 |
| JitPack 构建超时 | JitPack 对大型仓库偶尔超时 | 手动下载 JAR 作为兜底 |
| 反射访问被限制 | JDK 17 的模块系统可能阻止 `setAccessible` | 运行时加 `--add-opens` 参数 |

如果遇到反射访问问题，在 `build.gradle` 的 `run` task 中添加：

```groovy
tasks.named('run') {
    jvmArgs = [
        '--add-opens', 'java.base/java.lang=ALL-UNNAMED',
        '--add-opens', 'java.base/java.lang.reflect=ALL-UNNAMED'
    ]
}
```

## 扩展指南

### 添加新的 Content 类

在 `ClassExtractor.java` 中：

```java
private static final List<Class<?>> TARGET_CLASSES = List.of(
    UnitType.class,
    Block.class,
    Weapon.class,
    BulletType.class,
    // 新增：
    mindustry.type.ItemStack.class
);
```

### 添加新的实例分类

在 `InstanceExtractor.java` 中：

```java
private static final Map<String, ContentType> CATEGORIES = new LinkedHashMap<>(Map.of(
    // ...existing...
    "Sounds", ContentType.sound  // 新增
));
```

### 添加更多实例字段

在 `InstanceExtractor.FIELD_WHITELIST` 中对应分类的 Set 里加字段名即可。
