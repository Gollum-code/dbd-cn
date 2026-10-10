"""Extract long-form content from rendered wiki pages.

The wiki stores numeric data in Lua datatables (parsed by lua_parser), but
descriptions, lore, powers and change logs only exist in the rendered HTML of
each page.  This module pulls them out with lxml.

Selectors are resilient: they target structural classes (.perkDesc,
.perkWrapper, the Overview/Lore/Change Log sections) and fall back to
heading-based section extraction when classes change.
"""

from __future__ import annotations

import re
from typing import Any

from lxml import etree, html

_TEXT_TAGS = ("p", "li", "dt", "dd", "td", "th", "h3", "h4")


def _clean_text(node: Any) -> str:
    """Text content of a node, collapsed and icon-links stripped."""
    # clone into an html fragment to avoid mutating the source tree
    frag = html.fragment_fromstring(
        html.tostring(node, encoding="unicode"), create_parent="div"
    )
    for el in frag.xpath(".//*[contains(@class,'tooltiptext')] | .//*[contains(@class,'iconLink')] | .//sup[contains(@class,'reference')]"):
        parent = el.getparent()
        if parent is not None:
            parent.remove(el)
    for el in frag.xpath(".//img"):
        parent = el.getparent()
        if parent is not None:
            parent.remove(el)
    text = " ".join((frag.text_content() or "").split())
    text = text.replace("\xa0", " ")
    return text


def _first(root: Any, xpath: str) -> Any | None:
    hit = root.xpath(xpath)
    return hit[0] if hit else None


# ---------------------------------------------------------------------------
# perk descriptions
# ---------------------------------------------------------------------------
def perk_description(html_source: str) -> str:
    """Extract the description block from a rendered perk page.

    Returns e.g. '"You are fuelled by unexpected energy..." Once the Exit
    Gates are powered, Adrenaline activates...'
    """
    root = html.fromstring(html_source)
    node = _first(root, "//div[contains(concat(' ', normalize-space(@class), ' '), ' perkDesc ')]")
    if node is not None:
        return _clean_text(node)
    # disambiguation stub (e.g. 'Left Behind may refer to')
    stub = " ".join((root.text_content() or "").split())
    if "may refer to" in stub and len(stub) < 400:
        return "（消歧义页面）" + stub[:200]
    # decommissioned perks show only a notice
    for div in root.xpath("//*[contains(@class,'notice')] | //table"):
        txt = (div.text_content() or "").strip()
        if "DECOMMISSIONED" in txt.upper() or "RETIRED" in txt.upper():
            return " ".join(txt.split())[:200]
    # fallback: paragraph(s) before the History heading
    h2 = _first(root, "//h2[contains(., 'History') or contains(., 'Change Log')]")
    if h2 is not None:
        parts = []
        for sib in h2.itersiblings():
            if sib.tag in _TEXT_TAGS:
                t = _clean_text(sib)
                if t:
                    parts.append(t)
        return " ".join(parts)
    return ""


def perk_page_titles(client, name: str) -> list[str]:
    """Return candidate wiki page titles for a perk, most specific first.

    wiki.gg disambiguates names shared with chapters/other pages, e.g. the
    perk "Left Behind" also matches the chapter "Left Behind".  The real perk
    lives at "Left Behind (Perk)".
    """
    return [f"{name} (Perk)", name]


# ---------------------------------------------------------------------------
# character lore / power
# ---------------------------------------------------------------------------
def _section_between(root: Any, start: str, end: str) -> str:
    """Text of all content between two <h2> headings (by rough text match)."""
    headings = root.xpath("//h2")
    collect = False
    parts: list[str] = []
    for h2 in headings:
        text = (h2.text_content() or "").strip().lower()
        if start.lower() in text:
            collect = True
            continue
        if collect and end.lower() in text:
            break
        if collect:
            for sib in h2.itersiblings(preceding=False):
                pass
    # simpler: gather siblings until heading matching end
    h2_start = None
    for h2 in root.xpath("//h2"):
        if start.lower() in (h2.text_content() or "").lower():
            h2_start = h2
            break
    if h2_start is None:
        return ""
    for h2 in h2_start.itersiblings():
        if h2.tag == "h2":
            if end.lower() in (h2.text_content() or "").lower():
                break
            continue
        if h2.tag in _TEXT_TAGS:
            t = _clean_text(h2)
            if t:
                parts.append(t)
    return " ".join(parts)


def character_lore(html_source: str) -> str:
    """Extract the Lore section of a character page."""
    root = html.fromstring(html_source)
    return _section_between(root, "Lore", "Load-out")


def character_power(html_source: str) -> str:
    """Extract the power name + intro from a killer page (Load-out section)."""
    root = html.fromstring(html_source)
    # power appears as 'Power: <Name>' in the Load-out section or overview
    m = re.search(r"Power:\s*([A-Za-z][^<]{1,60})", html_source)
    if m:
        return m.group(1).strip()
    # fallback: Overview paragraph mentioning the killer name
    ov = _section_between(root, "Overview", "Lore")
    if ov:
        return ov[:300]
    return ""


# ---------------------------------------------------------------------------
# addon effects
# ---------------------------------------------------------------------------
def addon_effect(html_source: str) -> str:
    """Extract the effect text of an addon page.

    Addon pages render a 'Description' cell inside a History table (tabber).
    The first table is sometimes a decommissioned-notice; we pick the first
    table whose header contains 'Description' and return its description cell.
    """
    root = html.fromstring(html_source)
    node = _first(root, "//div[contains(concat(' ', normalize-space(@class), ' '), ' loadoutDesc ')] | //div[contains(concat(' ', normalize-space(@class), ' '), ' itemDesc ')]")
    if node is not None:
        return _clean_text(node)
    decommissioned = ""
    for table in root.xpath("//table"):
        if "DECOMMISSIONED" in (table.text_content() or "").upper():
            notice = " ".join((table.text_content() or "").split())
            decommissioned = notice[:200]
            continue
        header_cells = [" ".join((th.text_content() or "").split()) for th in table.xpath(".//th")]
        if "Description" not in header_cells:
            continue
        for tr in table.xpath(".//tr"):
            tds = tr.xpath("./td")
            if not tds:
                continue
            txt = _clean_text(tds[0])
            if txt and txt != "Icon":
                return txt
    if decommissioned:
        return decommissioned
    return ""


# ---------------------------------------------------------------------------
# patch change notes
# ---------------------------------------------------------------------------
def patch_notes(html_source: str, patch: str) -> str:
    """Extract a specific patch's change-log bullets from a page.

    The Change Log uses <h3>Patch x.y.z</h3> headings followed by <ul> bullets.
    """
    root = html.fromstring(html_source)
    out: list[str] = []
    active = False
    for el in root.iter():
        if el.tag == "h3":
            t = (el.text_content() or "").strip()
            if patch in t:
                active = True
                continue
            elif active:
                break
        if active and el.tag == "li":
            t = _clean_text(el)
            if t and not t.startswith("["):  # skip sub-list noise
                out.append(t)
    return " | ".join(out[:12])