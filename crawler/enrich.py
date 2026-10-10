"""Long-form content enrichment: descriptions, lore, powers, patch notes.

After the datatable build fills the numeric/structure fields, this pass
fetches the rendered wiki page for every perk / addon / character / recent
patch and fills the prose fields (description, lore, power, effect, notes).

It is optional: `dbd-crawl --full` runs it; the weekly sync can skip it or
run it on a sample.  Fetching ~1400 pages is polite-throttled and takes a
few minutes.
"""

from __future__ import annotations

import json
import logging
import re
import sqlite3
from typing import Any, Callable

from .api import WikiClient
from .html_extract import (
    addon_effect,
    character_lore,
    character_power,
    patch_notes,
    perk_description,
    perk_page_titles,
)

log = logging.getLogger(__name__)

PAGE_LIMIT = 250  # safety: max pages fetched in one run


def _row_map(conn: sqlite3.Connection, table: str, id_col: str, name_col: str) -> dict[str, str]:
    """{id: name_en} for all rows."""
    return dict(conn.execute(f"SELECT {id_col}, {name_col} FROM {table}"))


def enrich_perks(client: WikiClient, conn: sqlite3.Connection, *, limit: int = PAGE_LIMIT) -> int:
    rows = conn.execute(
        "SELECT id, name_en FROM perks WHERE description IS NULL OR TRIM(description)=''"
    ).fetchall()
    updated = 0
    for i, (pid, name) in enumerate(rows[:limit]):
        # try the most specific title first (handles disambiguation pages)
        page = None
        for title in perk_page_titles(client, name):
            try:
                html = client.page_html(title)
            except Exception:  # noqa: BLE001
                continue
            text = perk_description(html)
            if text and not text.startswith("（消歧义页面）"):
                page = text
                break
        if page:
            conn.execute(
                "UPDATE perks SET description=? WHERE id=?",
                (page, pid),
            )
            updated += 1
        if i % 50 == 0:
            conn.commit()
    conn.commit()
    log.info("enriched %d/%d perks", updated, min(len(rows), limit))
    return updated


def enrich_characters(client: WikiClient, conn: sqlite3.Connection, *, limit: int = PAGE_LIMIT) -> int:
    """Fill lore (all) and power (killers) from rendered character pages."""
    rows = conn.execute(
        "SELECT id, name_en, name_zh, role, "
        "COALESCE(NULLIF(alternate, ''), name_en) "
        "FROM characters WHERE lore IS NULL OR TRIM(lore)=''"
    ).fetchall()
    updated = 0
    for i, (cid, name_en, name_zh, role, page_title) in enumerate(rows[:limit]):
        lore: str = ""
        power: str | None = None
        try:
            # multi-name killers (e.g. the Legion) use the group name as page title
            if "," in (page_title or ""):
                page_title = name_en
            page = client.page_html(page_title or name_en)
            lore = character_lore(page)
            if role == "killer":
                power = character_power(page)
            if not lore and name_zh and name_zh != name_en:
                try:
                    page = client.page_html(name_zh)
                    lore = lore or character_lore(page)
                    if role == "killer":
                        power = power or character_power(page)
                except Exception:  # noqa: BLE001   (Chinese mirror often 404s)
                    pass
            if lore or power:
                conn.execute(
                    "UPDATE characters SET lore=?, power=? WHERE id=?",
                    (lore or None, power or None, cid),
                )
                updated += 1
        except Exception as exc:  # noqa: BLE001
            log.warning("character %s: %s", page_title or name_en, exc)
        if i % 30 == 0:
            conn.commit()
    conn.commit()
    log.info("enriched %d/%d characters", updated, min(len(rows), limit))
    return updated


def enrich_addons(client: WikiClient, conn: sqlite3.Connection, *, limit: int = PAGE_LIMIT) -> int:
    rows = conn.execute(
        "SELECT id, name_en FROM addons WHERE effect IS NULL OR TRIM(effect)=''"
    ).fetchall()
    updated = 0
    for i, (aid, name) in enumerate(rows[:limit]):
        try:
            page = client.page_html(name)
            effect = addon_effect(page)
            if effect:
                conn.execute("UPDATE addons SET effect=? WHERE id=?", (effect, aid))
                updated += 1
        except Exception as exc:  # noqa: BLE001
            log.warning("addon %s: %s", name, exc)
        if i % 50 == 0:
            conn.commit()
    conn.commit()
    log.info("enriched %d/%d addons", updated, min(len(rows), limit))
    return updated


def enrich_patch_notes(client: WikiClient, conn: sqlite3.Connection, *, recent: int = 40) -> int:
    """Fill notes for the most recent patches from their dedicated pages.

    wiki.gg has one page per patch (e.g. 'Patch 10.2.0') whose Change Log
    lists every rework/buff/nerf.  We fetch that page and keep its bullet
    summary as the notes.
    """
    rows = conn.execute(
        "SELECT id, patch FROM patches ORDER BY id DESC LIMIT ?", (recent,)
    ).fetchall()
    if client is None:
        client = WikiClient()
    updated = 0
    for pid, patch in rows:
        try:
            page = client.page_html(f"Patch {patch}")
            notes = _patch_page_summary(page)
            if not notes:
                continue
            conn.execute("UPDATE patches SET notes=? WHERE id=?", (notes, pid))
            updated += 1
        except Exception as exc:  # noqa: BLE001
            log.warning("patch %s: %s", patch, exc)
    conn.commit()
    log.info("enriched %d patch notes", updated)
    return updated


def _patch_page_summary(page: str) -> str:
    """Summarise a rendered 'Patch x.y.z' page into a short notes string.

    The page has a 'Change Log' section whose bullet list holds every buff /
    nerf / rework line.  We take those bullets; if none are found we fall back
    to the page body.
    """
    from lxml import html as _lhtml
    from .html_extract import _clean_text

    root = _lhtml.fromstring(page)
    for toc in root.xpath("//div[contains(@class,'toc')]"):
        toc.getparent().remove(toc)

    bullets: list[str] = []
    collecting = False
    for el in root.iter():
        if el.tag in ("h2", "h3"):
            t = " ".join((el.text_content() or "").split())
            if "change log" in t.lower() or "变更" in t:
                collecting = True
                continue
            if collecting and el.tag == "h2":
                break
        if collecting and el.tag == "li":
            t = _clean_text(el)
            # skip sub-bullets and navigation noise
            if t and len(t) > 12:
                bullets.append(t)
            if len(bullets) >= 8:
                break
    if bullets:
        return " | ".join(bullets)
    # fallback: bullets mentioning change keywords anywhere on the page
    for li in root.xpath("//li"):
        t = _clean_text(li)
        if t and re.search(r"\b(Buff|Nerf|Rework|Added|Fixed|Adjusted|Removed)\b", t):
            bullets.append(t)
        if len(bullets) >= 8:
            break
    if bullets:
        return " | ".join(bullets)
    body = _clean_text(root)
    return body[:300]


def enrich_all(
    client: WikiClient | None = None,
    db_path: str = "data/dbd_cn.db",
    *,
    include_addons: bool = True,
    include_patches: bool = False,
) -> dict[str, int]:
    """Run the full enrichment pass."""
    from .db import connect

    client = client or WikiClient()
    conn = connect(db_path)
    out: dict[str, int] = {}
    out["perks"] = enrich_perks(client, conn)
    out["characters"] = enrich_characters(client, conn)
    if include_addons:
        out["addons"] = enrich_addons(client, conn)
    if include_patches:
        out["patches"] = enrich_patch_notes(client, conn)
    conn.close()
    return out