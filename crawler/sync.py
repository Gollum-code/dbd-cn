"""Weekly incremental sync (per the project plan, runs unattended).

`dbd-sync` calls the pipeline and records sync metadata so we know how stale
the local copy is.  In normal use this is scheduled (cron / Task Scheduler)
once a week.
"""

from __future__ import annotations

import argparse
import logging
import sys

from .pipeline import build

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")


def main() -> None:
    ap = argparse.ArgumentParser(prog="dbd-sync", description="每周同步 DBD 数据")
    ap.add_argument("--db", default="data/dbd_cn.db")
    args = ap.parse_args()
    try:
        counts = build(db_path=args.db)
    except Exception as exc:  # noqa: BLE001
        logging.getLogger(__name__).exception("sync failed")
        sys.exit(1)
    print("同步完成:", counts)


if __name__ == "__main__":
    main()