"""Translation review queue.

The plan's translation strategy is "词典 + 人工校对" (dictionary + human
review).  This module finds every term the automated dictionaries did not
cover, dumps them to a review file (TSV: 英文 term | 当前中文 | 待校对), and
merges the reviewed file back into the SQLite `translations` table so the
next build can consume it.

Workflow:
    1. python -m crawler.review_queue --dump data/review_queue.tsv
       (open in a spreadsheet, fill the 中文 column)
    2. python -m crawler.review_queue --import data/review_queue.tsv
       (merge reviewed terms into data/dbd_cn.db translations table)
    3. rebuild: python -m crawler.cli
"""

from __future__ import annotations

import argparse
import sqlite3
from pathlib import Path

from .db import connect
from .translate import EXTRA_DICTS, TERMS, looks_untranslated


def collect_untranslated(conn: sqlite3.Connection) -> list[tuple[str, str, str]]:
    """Return (kind, term_en, term_zh) rows that still look untranslated."""
    out: list[tuple[str, str, str]] = []
    for table, kind in (
        ("characters", "角色"),
        ("perks", "技能"),
        ("addons", "附加品"),
        ("maps", "地图"),
        ("realms", "领域"),
    ):
        for name_en, name_zh in conn.execute(
            f"SELECT name_en, name_zh FROM {table}"
        ):
            if looks_untranslated(name_zh or ""):
                out.append((kind, name_en, name_zh or ""))
    # translations table may hold reviewed but still-empty entries
    for term, zh in conn.execute(
        "SELECT term, zh FROM translations WHERE reviewed = 1"
    ):
        if looks_untranslated(zh or ""):
            out.append(("词表", term, zh or ""))
    return out


def dump_review(conn: sqlite3.Connection, out_path: str | Path) -> int:
    rows = collect_untranslated(conn)
    out_path = Path(out_path)
    lines = ["类型\t英文原词\t当前值(可改写中文)"]
    lines += ["\t".join(row) for row in rows]
    out_path.write_text("\n".join(lines), encoding="utf-8")
    return len(rows)


def import_review(conn: sqlite3.Connection, review_path: str | Path) -> int:
    """Import reviewed rows into the translations table (reviewed=1)."""
    review_path = Path(review_path)
    merged = 0
    cur = conn.cursor()
    for line in review_path.read_text(encoding="utf-8").splitlines()[1:]:
        if not line.strip():
            continue
        parts = line.split("\t")
        if len(parts) < 3:
            continue
        kind, term, zh = parts[0], parts[1], parts[2].strip()
        if not zh or looks_untranslated(zh):
            continue
        cur.execute(
            """INSERT INTO translations (term, zh, source, reviewed)
               VALUES (?,?,?,1)
               ON CONFLICT(term) DO UPDATE SET
                 zh=excluded.zh, source=excluded.source, reviewed=1""",
            (term, zh, f"review:{kind}"),
        )
        merged += 1
    conn.commit()
    return merged


def main() -> None:
    ap = argparse.ArgumentParser(prog="dbd-review", description="翻译校对队列")
    ap.add_argument("--db", default="data/dbd_cn.db")
    ap.add_argument("--dump", help="导出未翻译词表到 TSV")
    ap.add_argument("--import", dest="import_path", help="导入校对后的 TSV")
    args = ap.parse_args()
    conn = connect(args.db)

    if args.dump:
        n = dump_review(conn, args.dump)
        print(f"已导出 {n} 条待校对词条 -> {args.dump}")
    elif args.import_path:
        n = import_review(conn, args.import_path)
        print(f"已合并 {n} 条校对词条")
    else:
        rows = collect_untranslated(conn)
        print(f"未翻译词条总数: {len(rows)}")
        for kind, term, zh in rows[:30]:
            print(f"  [{kind}] {term} = {zh}")
        if len(rows) > 30:
            print(f"  ... 其余 {len(rows)-30} 条")
    conn.close()


if __name__ == "__main__":
    main()