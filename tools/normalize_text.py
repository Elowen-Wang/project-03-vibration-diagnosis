"""仓库文本规范化工具（一次性整理，可重复执行）

用途
----
统一全仓库文本文件的编码与换行符，让 VS Code / GitHub 渲染一致：

1. 去掉 UTF-8 BOM —— `noise_log.csv` 原带 BOM，VS Code 里表头会显示成
   `﻿record_id`，用「编码 → 通过编码转换保存」时也会报错。
2. 换行符统一为 LF —— 仓库里 `.md/.csv/.py` 曾 CRLF、LF 混用，
   同一批文件在编辑器里反复被标记为「已修改」。
3. 修复 HTML 未自闭合标签 —— `盲测演示.html` 的 `<meta charset>` 缺 `/`，
   严格 XML 解析器（以及部分 VS Code 插件）会报 mismatched tag。

用法（仓库根目录执行）：
    python tools/normalize_text.py
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# 只处理纯文本；媒体文件（jpg/mp4/wav/png）一律不碰
TEXT_EXT = {".md", ".csv", ".py", ".svg", ".html", ".txt", ".json", ".gitattributes", ".gitignore"}


def fix_meta_tag(path: Path) -> bool:
    """把 HTML 里未自闭合的 <meta charset="utf-8"> 补成自闭合形式。"""
    raw = path.read_text(encoding="utf-8")
    old = '<meta charset="utf-8">'
    if old not in raw:
        return False
    path.write_text(raw.replace(old, '<meta charset="utf-8"/>'), encoding="utf-8", newline="\n")
    return True


def main() -> int:
    changed: list[str] = []
    for p in sorted(ROOT.rglob("*")):
        if not p.is_file() or ".git" in p.parts:
            continue
        if p.suffix.lower() not in TEXT_EXT and p.name not in {".gitattributes", ".gitignore"}:
            continue

        raw = p.read_bytes()
        orig = raw

        # 1) 去 BOM
        if raw.startswith(b"\xef\xbb\xbf"):
            raw = raw[3:]

        # 2) 换行符统一 LF（先转 CRLF/CR，再去掉残留 CR）
        raw = raw.replace(b"\r\n", b"\n").replace(b"\r", b"\n")

        if raw != orig:
            p.write_bytes(raw)
            changed.append(f"{p.relative_to(ROOT)}  (编码/换行)")

        # 3) HTML 标签修复
        if p.suffix.lower() == ".html" and fix_meta_tag(p):
            changed.append(f"{p.relative_to(ROOT)}  (meta 自闭合)")

    if changed:
        print("已规范化以下文件：")
        for c in changed:
            print("  -", c)
    else:
        print("所有文本文件已是规范状态，无需改动。")
    print(f"共检查 {len(TEXT_EXT)} 类文本扩展名。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
