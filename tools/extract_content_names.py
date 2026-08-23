"""从官方汉化包提取内容名总表（E-4 / ADR-013）。

读取 Mindustry 源码树的 bundle_zh_CN.properties，解析
`<category>.<content-name>.name = 中文名` 行，产出
`app/config/content_names_zh.json`（入库）。

结构：
    {
      "items":   { "copper": "铜", ... },
      "liquids": { "water": "水", ... },
      "blocks":  { "copper-wall": "铜墙", ... },
      "units":   { "dagger": "匕首", ... },
      "weapons": { "meltdown": "熔毁", ... },
      "status":  { "burning": "燃烧", ... }
    }

用法：
    python tools/extract_content_names.py \
        --bundle Mindustry-master/core/assets/bundles/bundle_zh_CN.properties \
        --out app/config/content_names_zh.json
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

# properties 键 → 输出分类名
_CATEGORY_MAP = {
    "block": "blocks",
    "unit": "units",
    "item": "items",
    "liquid": "liquids",
    "weapon": "weapons",
    "status": "status",
    "planet": "planets",
    "sector": "sectors",
}

# 匹配 `<type>.<name>.name = 中文`，name 为小写字母/数字/连字符
_ENTRY_RE = re.compile(
    r"^(block|unit|item|liquid|weapon|status|planet|sector)\.([A-Za-z0-9-]+)\.name\s*=\s*(.+)$"
)


def extract(bundle_path: Path) -> dict[str, dict[str, str]]:
    """解析汉化包，返回 {category: {name: zh}}。"""
    result: dict[str, dict[str, str]] = {
        "items": {}, "liquids": {}, "blocks": {},
        "units": {}, "weapons": {}, "status": {}, "planets": {}, "sectors": {},
    }
    lines = bundle_path.read_text(encoding="utf-8").splitlines()
    for line in lines:
        m = _ENTRY_RE.match(line.strip())
        if not m:
            continue
        cat_key, name, zh = m.group(1), m.group(2), m.group(3).strip()
        # 去掉 bundle 的标记颜色代码，如 [scarlet] 前缀
        zh = re.sub(r"^\[[^\]]*\]", "", zh).strip()
        if zh:
            result[_CATEGORY_MAP[cat_key]][name] = zh
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="提取内容名总表")
    parser.add_argument("--bundle", required=True, type=Path, help="汉化包路径")
    parser.add_argument("--out", required=True, type=Path, help="输出 JSON 路径")
    args = parser.parse_args()

    result = extract(args.bundle)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    total = sum(len(v) for v in result.values())
    print(f"已写入 {args.out}：{total} 条内容名")


if __name__ == "__main__":
    main()
