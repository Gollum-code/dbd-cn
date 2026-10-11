"""Icon downloader.

Fetches perk / addon / character icon images from wiki.gg and records their
local paths in the SQLite `icon` columns.

Licensing: all images belong to Behaviour Interactive (see the wiki's
{{Copyright Game}} notice); this project is a non-commercial fan project and
keeps that attribution on every page that renders an icon.

Strategy
--------
Most icon files follow a deterministic naming scheme:
  perks      IconPerks_<camelSlug>.png
  addons     IconAddon_<camelSlug>.png
  killers    K<NN>_The<Name>_Portrait.png
  survivors  S<NN><Name>_Portrait.png

Some names deviate (apostrophes, short-hands, legacy art).  For those we
fall back to extracting the real image URL from the rendered page HTML.
"""

from __future__ import annotations

import logging
import re
from pathlib import Path

import requests

from .api import USER_AGENT, WikiClient

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# name -> file candidates
# ---------------------------------------------------------------------------
def _camel(slug: str) -> str:
    """'aNurseSCalling' -> 'aNursesCalling' style normalisation attempts.

    Returns the original first; callers try several variants.
    """
    # collapse repeated capitals (SS -> Ss), strip apostrophes
    out = re.sub(r"([a-z])([A-Z][A-Z])", lambda m: m.group(1) + m.group(2)[0] + m.group(2)[1].lower(), slug)
    return out


def perk_file_candidates(name: str, slug: str) -> list[str]:
    bare = re.sub(r"[^A-Za-z0-9]+", "", name)  # 'Barbecue & Chilli' -> 'BarbecueChilli'
    first = bare[:1].lower() + bare[1:]         # camelCase lowercase-first
    return list(dict.fromkeys([
        f"IconPerks_{slug}.png",
        f"IconPerks_{_camel(slug)}.png",
        f"IconPerks_{bare}.png",
        f"IconsPerks_{first}.png",
        f"T_UI_iconsPerks_{bare}.png",
    ]))


def addon_file_candidates(name: str, slug: str) -> list[str]:
    bare = re.sub(r"[^A-Za-z0-9]+", "", name)
    first = bare[:1].lower() + bare[1:]
    return list(dict.fromkeys([
        f"IconAddon_{slug}.png",
        f"FulliconAddon_{slug}.png",
        f"IconAddon_{bare}.png",
        f"IconAddon_{first}.png",
        f"T_UI_iconAddon_{bare}.png",
    ]))


def character_file_candidates(role: str, num: int, name: str) -> list[str]:
    """Portrait file candidates.  `name` is the wiki page name e.g. 'The Trapper'."""
    prefix = "K" if role == "killer" else "S"
    tag = f"{prefix}{num:02d}"
    bare = re.sub(r"[^A-Za-z0-9]+", "", name)
    out = [
        f"{tag}_The{bare}_Portrait.png",
        f"{tag}_{bare}_Portrait.png",
        f"{bare}_Portrait_Render.png",
    ]
    return list(dict.fromkeys(out))


# ---------------------------------------------------------------------------
# existence + download
# ---------------------------------------------------------------------------
def _imageinfo_urls(client: WikiClient, filenames: list[str]) -> dict[str, str]:
    """Batch imageinfo lookup.

    Returns candidate -> full download URL for every file that exists.
    MediaWiki canonicalises names (spaces/underscores, case of first letter,
    and resolves redirects), so the returned URL is always the real file.
    """
    if not filenames:
        return {}
    titles = "|".join("File:" + f for f in filenames[:50])
    data = client.query(titles=titles, prop="imageinfo", iiprop="url")
    by_title: dict[str, str] = {}
    for p in data["query"].get("pages", []):
        if p.get("missing"):
            continue
        ii = p.get("imageinfo") or [{}]
        url = (ii[0] or {}).get("url", "")
        if not url:
            continue
        # MediaWiki normalises File titles with spaces; our candidates use
        # underscores, so compare on a space-free lowercase key.
        key = p["title"].removeprefix("File:").replace(" ", "_").lower()
        by_title[key] = url
    out: dict[str, str] = {}
    for f in filenames:
        out[f] = by_title.get(f.lower(), "")
    return out


def _first_existing(client: WikiClient, candidates: list[str]) -> str | None:
    urls = _imageinfo_urls(client, candidates)
    for f in candidates:
        if urls.get(f):
            return urls[f]
    return None


def download_icon(url: str, dest: Path) -> bool:
    """Download an image file.  Returns True on success."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    try:
        resp = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=30)
        resp.raise_for_status()
        dest.write_bytes(resp.content)
        return True
    except requests.RequestException as exc:
        log.warning("download failed %s: %s", url, exc)
        return False


def fetch_icons(
    client: WikiClient | None = None,
    db_path: str = "data/dbd_cn.db",
    icons_dir: str = "data/icons",
) -> dict[str, int]:
    """Resolve + download every icon, then update the DB icon columns."""
    from .db import connect

    client = client or WikiClient()
    icons_dir = Path(icons_dir)
    conn = connect(db_path)
    counts = {"perks": 0, "addons": 0, "characters": 0}

    def _need(icon: str | None, dest: Path) -> bool:
        """True when the icon is missing from the DB or absent on disk.

        Checking both matters on fresh CI checkouts, where the DB may already
        reference icons that were never downloaded into this working tree.
        """
        if icon and dest.exists():
            return False
        return True

    # -- perks -----------------------------------------------------------
    rows = conn.execute("SELECT id, name_en, icon FROM perks").fetchall()
    rows = [(i, n, ic) for i, n, ic in rows if _need(ic, icons_dir / "perks" / f"{i}.png")]
    for i, (pid, name, _icon) in enumerate(rows):
        url = _first_existing(client, perk_file_candidates(name, pid))
        if not url:
            url = _extract_from_page(client, name, "IconPerks")
        if not url:
            continue
        rel = f"icons/perks/{pid}.png"
        if download_icon(url, icons_dir / "perks" / f"{pid}.png"):
            conn.execute("UPDATE perks SET icon=? WHERE id=?", (rel, pid))
            counts["perks"] += 1
        if i % 25 == 0:
            conn.commit()

    # -- addons ----------------------------------------------------------
    rows = conn.execute("SELECT id, name_en, icon FROM addons").fetchall()
    rows = [(i, n, ic) for i, n, ic in rows if _need(ic, icons_dir / "addons" / f"{i}.png")]
    for i, (aid, name, _icon) in enumerate(rows):
        url = _first_existing(client, addon_file_candidates(name, aid))
        if not url:
            url = _extract_from_page(client, name, "IconAddon")
        if not url:
            continue
        rel = f"icons/addons/{aid}.png"
        if download_icon(url, icons_dir / "addons" / f"{aid}.png"):
            conn.execute("UPDATE addons SET icon=? WHERE id=?", (rel, aid))
            counts["addons"] += 1
        if i % 25 == 0:
            conn.commit()

    # -- characters ------------------------------------------------------
    rows = conn.execute(
        "SELECT id, name_en, role, icon FROM characters ORDER BY id"
    ).fetchall()
    rows = [(i, n, r, ic) for i, n, r, ic in rows if _need(ic, icons_dir / "characters" / f"{i}.png")]
    num_by_id = {r[0]: int(r[0][1:]) for r in rows}
    for i, (cid, name_en, role, _icon) in enumerate(rows):
        num = num_by_id[cid]
        url = _first_existing(client, character_file_candidates(role, num, name_en))
        if not url:
            url = _extract_from_page(client, name_en, "Portrait")
        if not url:
            continue
        rel = f"icons/characters/{cid}.png"
        if download_icon(url, icons_dir / "characters" / f"{cid}.png"):
            conn.execute("UPDATE characters SET icon=? WHERE id=?", (rel, cid))
            counts["characters"] += 1
        if i % 10 == 0:
            conn.commit()

    conn.commit()
    conn.close()
    log.info("icons fetched: %s", counts)
    return counts


def _extract_from_page(client: WikiClient, title: str, needle: str) -> str | None:
    """Pull the first image URL matching `needle` from a rendered page.

    Handles the icon prefixes seen on the wiki:
      IconPerks_ / IconAddon_            (classic)
      IconsPerks_ / IconsAddon_          (variant, plural 's')
      T_UI_iconsPerks_ / T_UI_iconAddon_ (newer art, lowercase 'i')
    """
    import re as _re

    try:
        html_source = client.page_html(title)
    except Exception:  # noqa: BLE001
        return None
    core = needle[4:] if needle.startswith("Icon") else needle  # 'Perks'/'Addon'
    variants = [needle, "Icons" + core, "icons" + core, "Icon" + core.lower(),
                "T_UI_icon" + core.lower()]
    for v in variants:
        m = _re.search(r'src="([^"]*' + _re.escape(v) + r'[^"]*)"', html_source)
        if not m:
            continue
        url = m.group(1)
        if "/images/" in url:
            return url if url.startswith("http") else "https://deadbydaylight.wiki.gg" + url
    return None
