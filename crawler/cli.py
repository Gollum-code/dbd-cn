"""CLI entry point: dbd-crawl / dbd-sync."""

from __future__ import annotations

import argparse
import logging

from .enrich import enrich_all
from .icons import fetch_icons
from .pipeline import build

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")


def main() -> None:
    ap = argparse.ArgumentParser(prog="dbd-crawl", description="抓取 wiki.gg 数据并生成中文 SQLite")
    ap.add_argument("--db", default="data/dbd_cn.db", help="SQLite 输出路径")
    ap.add_argument(
        "--full",
        action="store_true",
        help="抓数据后补充描述/背景/效果（较慢，数千次请求）",
    )
    ap.add_argument(
        "--icons",
        action="store_true",
        help="抓取角色/技能/附加品图标（约 1500 张小图，需几分钟）",
    )
    ap.add_argument(
        "--translate",
        action="store_true",
        help="LLM 翻译长文本（技能描述/背景/效果/补丁说明，需配置 .env）",
    )
    args = ap.parse_args()
    counts = build(db_path=args.db)
    print("完成:", counts)
    if args.full:
        enriched = enrich_all(db_path=args.db, include_patches=True)
        print("已补充内容:", enriched)
    if args.icons:
        icons = fetch_icons(db_path=args.db)
        print("已抓取图标:", icons)
    if args.translate:
        from .llm import translate_all_fields
        print("LLM 翻译开始…", flush=True)
        translated = translate_all_fields(db_path=args.db)
        print("翻译完成:", translated)


if __name__ == "__main__":
    main()
