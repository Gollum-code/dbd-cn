"""End-to-end integration test: sample data -> SQLite -> static Wiki.

Uses a small in-memory fixture (no network) to verify the whole pipeline:
crawler.db schema, pipeline normalisers, and wiki generator all compose.
"""

from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest

from crawler.db import connect
from crawler.pipeline import (
    _seed_default_builds,
    load_into_db,
    normalise_addons,
    normalise_characters,
    normalise_maps,
    normalise_patches,
    normalise_perks,
    normalise_realms,
)


@pytest.fixture()
def sample():
    """Tiny but structurally-complete dataset mirroring the real shapes."""
    killers = [{
        "id": 1, "name": "Trapper", "realName": "Evan MacMillan",
        "gender": "Man", "origin": "American", "realm": 1,
        "speed": 4.6, "radius": 32, "height": "T", "diff": 1,
    }]
    survivors = [{
        "id": 1, "name": "Dwight Fairfield", "gender": "Man",
        "role": "Nervous Leader", "origin": "American",
    }]
    realms = [{
        "id": 1, "name": "The MacMillan Estate", "abbr": "Ind",
        "location": "Washington State, United States", "palette": "Blue",
        "color": "4982a2",
    }]
    maps = [{"id": 1, "name": "Coal Tower", "realm": 1,
             "variations": [{"size": 132, "release": "1.0.0"}]}]
    perks = {"Agitation": {
        "id": 51, "values": {1: 14, 2: 16, 3: 18}, "units": {1: "metres"},
        "character": 1, "charType": "K", "level": 40, "prestige": 3,
        "tags": {"Carrying", "TerrorRadius"}, "patch": "10.2.0",
    }}
    addons = {"Tar Bottle": {
        "id": 5, "rarity": 2, "killer": 1, "tags": {"TrapDisguise"},
    }}
    patches = [{"id": 1, "patch": "10.2.0", "rDate": "06.10.2026"}]
    return {
        "characters": normalise_characters(killers, survivors, realms),
        "perks": normalise_perks(perks),
        "addons": normalise_addons(addons),
        "maps": normalise_maps(maps),
        "realms": normalise_realms(realms),
        "patches": normalise_patches(patches),
    }


def test_pipeline_to_db(sample, tmp_path):
    """load_into_db persists every entity and upserts correctly."""
    db_path = tmp_path / "e2e.db"
    conn = connect(db_path)
    counts = load_into_db(
        conn,
        characters=sample["characters"],
        perks=sample["perks"],
        addons=sample["addons"],
        maps=sample["maps"],
        realms=sample["realms"],
        patches=sample["patches"],
    )
    assert counts["characters"] == 2
    assert counts["perks"] == 1
    assert counts["addons"] == 1
    assert counts["maps"] == 1
    assert counts["realms"] == 1
    assert counts["patches"] == 1

    # spot-check a persisted killer row
    row = conn.execute(
        "SELECT id, name_en, name_zh, speed, realm_id, alternate "
        "FROM characters WHERE id='K01'"
    ).fetchone()
    assert row[0] == "K01"
    assert row[1] == "Trapper"
    assert row[2] == "设陷者"       # translated by the dictionary
    assert row[3] == pytest.approx(4.6)  # speed stored as REAL
    assert row[5] == "Evan MacMillan"  # realName persisted as alternate

    # perk tiers are JSON
    tiers = json.loads(
        conn.execute("SELECT tiers FROM perks WHERE id='agitation'").fetchone()[0]
    )
    assert tiers["1"] == 14

    conn.close()


def test_addon_owner_links_to_killer(sample):
    """Add-ons use the wiki's `killer = <id>` field (not charType/character)."""
    addon = sample["addons"][0]
    assert addon["owner"] == "K01"
    assert addon["name_zh"] == "焦油瓶"


def test_unowned_item_addon():
    """Item add-ons (no killer field) keep an empty owner."""
    from crawler.pipeline import normalise_addons

    out = normalise_addons({"Flashlight": {"id": 1, "rarity": 1}})
    assert out[0]["owner"] == ""


def test_db_to_wiki_full_render(sample, tmp_path):
    """The wiki generator renders a full site from the sample database."""
    from wiki.generate import render_site

    db_path = tmp_path / "e2e.db"
    conn = connect(db_path)
    load_into_db(
        conn,
        characters=sample["characters"],
        perks=sample["perks"],
        addons=sample["addons"],
        maps=sample["maps"],
        realms=sample["realms"],
        patches=sample["patches"],
    )
    _seed_default_builds(conn)
    conn.close()

    out_dir = tmp_path / "site"
    counts = render_site(str(db_path), str(out_dir))

    assert counts["pages"] >= 5
    index = (out_dir / "index.html").read_text(encoding="utf-8")
    assert "黎明杀机" in index

    perk_page = out_dir / "perk" / "agitation.html"
    assert perk_page.exists()
    assert "焦躁" in perk_page.read_text(encoding="utf-8")

    char_page = out_dir / "character" / "K01.html"
    assert char_page.exists()

    sitemap = (out_dir / "sitemap.xml").read_text(encoding="utf-8")
    assert "agitation.html" in sitemap
