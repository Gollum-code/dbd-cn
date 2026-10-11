"""Unit tests for rendered-HTML content extraction (html_extract)."""

from __future__ import annotations

from crawler.html_extract import (
    addon_effect,
    character_lore,
    character_power,
    patch_notes,
    perk_description,
)

PERK_HTML = """
<div class="mw-content-ltr mw-parser-output">
<p><b>Adrenaline</b> is a <span class="luaClr clr clrorange">Unique</span> Perk.</p>
<div class="perkWrapper displayF">
  <div class="perkDesc divTableCel">
    "You are fuelled by unexpected energy when on the verge of escape."
    <p>Once the Exit Gates are powered, Adrenaline activates.</p>
    <ul><li>Heals you to the next Health State.</li></ul>
  </div>
</div>
<h2>History</h2>
<h3>Patch 10.1.0</h3>
<ul><li>Buff: increased duration.</li></ul>
</div>
"""

CHAR_HTML = """
<div class="mw-content-ltr mw-parser-output">
<h2>Overview</h2>
<p>An area-control Killer.</p>
<h2>Lore</h2>
<p><i>Evan MacMillan idolised his father.</i></p>
<h2>Load-out</h2>
<h3>Power: Bear Trap</h3>
</div>
"""

ADDON_HTML = """
<div class="mw-content-ltr mw-parser-output">
<p>Stitched Bag is a Very Rare Add-on for Bear Trap.</p>
<table class="wikitable">
<tr><th>Icon</th><th>Description</th></tr>
<tr><th><img src="x"></th>
<td>Start with 2 additional Bear Traps.</td></tr>
</table>
</div>
"""


class TestPerkExtraction:
    def test_perk_description(self):
        out = perk_description(PERK_HTML)
        assert "fuelled by unexpected energy" in out
        assert "Heals you" in out

    def test_patch_notes(self):
        out = patch_notes(PERK_HTML, "10.1.0")
        assert "Buff" in out
        assert "duration" in out

    def test_perk_description_returns_empty_on_unrelated(self):
        assert perk_description("<div>no perk here</div>") in ("", "（消歧义页面）")


class TestCharacterExtraction:
    def test_lore(self):
        out = character_lore(CHAR_HTML)
        assert "Evan MacMillan idolised" in out

    def test_power(self):
        out = character_power(CHAR_HTML)
        assert "Bear Trap" in out


class TestAddonExtraction:
    def test_addon_effect(self):
        out = addon_effect(ADDON_HTML)
        assert "2 additional Bear Traps" in out

    def test_addon_decommissioned_fallback(self):
        html = """
        <table class="wikitable">
        <tr><th>Icon</th><th>Description</th><th>Cost</th></tr>
        <tr><td></td><td>THIS ADD-ON WAS DECOMMISSIONED (retired).</td><td>4,000</td></tr>
        </table>
        """
        out = addon_effect(html)
        assert "DECOMMISSIONED" in out
