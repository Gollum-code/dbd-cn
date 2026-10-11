"""SQLite schema for the dbd-cn single source of truth.

Mirrors the tables designed in the project plan (characters, perks, addons,
maps, builds, translations), extended with killer/survivor stats and
weekly-sync metadata.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS characters (
    id          TEXT PRIMARY KEY,        -- 'K01_TheTrapper' / 'S01_DwightFairfield'
    name_en     TEXT NOT NULL,
    name_zh     TEXT,
    role        TEXT NOT NULL,           -- 'killer' | 'survivor'
    difficulty  TEXT,
    lore        TEXT,
    power       TEXT,
    icon        TEXT,
    gender      TEXT,
    origin      TEXT,
    apt         REAL,                    -- killer agility / survivor role flavor
    speed       REAL,                    -- killer movement speed (m/s)
    terror_radius REAL,                  -- killer terror radius (m)
    height      TEXT,
    realm_id    INTEGER,
    dlc         TEXT,
    actor       TEXT,
    alternate   TEXT,                    -- realName (killer page title)
    updated_at  TEXT
);

CREATE TABLE IF NOT EXISTS perks (
    id          TEXT PRIMARY KEY,        -- slug, e.g. 'barbecueAndChilli'
    name_en     TEXT NOT NULL,
    name_zh     TEXT,
    owner       TEXT,                    -- character id
    role        TEXT,
    tiers       TEXT,                    -- JSON: {1: 28, 2: 30, 3: 32}
    units       TEXT,                    -- JSON: {1: 'metres'}
    description TEXT,
    tags        TEXT,                    -- JSON array (中文标签)
    tags_en     TEXT,                    -- JSON array (原始英文标签)
    icon        TEXT,
    patch       TEXT,
    updated_at  TEXT
);

CREATE TABLE IF NOT EXISTS addons (
    id          TEXT PRIMARY KEY,
    name_en     TEXT NOT NULL,
    name_zh     TEXT,
    owner       TEXT,
    rarity      TEXT,                    -- zh rarity name
    rarity_en   TEXT,
    effect      TEXT,
    tags        TEXT,                    -- JSON array (中文标签)
    tags_en     TEXT,                    -- JSON array (原始英文标签)
    icon        TEXT,
    updated_at  TEXT
);

CREATE TABLE IF NOT EXISTS maps (
    id          TEXT PRIMARY KEY,
    name_en     TEXT NOT NULL,
    name_zh     TEXT,
    realm       TEXT,
    realm_id    INTEGER,
    variations  TEXT,                    -- JSON: [{size:..., release:...}]
    hooks       TEXT,
    totems      TEXT
);

CREATE TABLE IF NOT EXISTS realms (
    id          INTEGER PRIMARY KEY,
    name_en     TEXT NOT NULL,
    name_zh     TEXT,
    abbr        TEXT,
    location    TEXT,
    palette     TEXT,
    color       TEXT
);

CREATE TABLE IF NOT EXISTS builds (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    character   TEXT,
    role        TEXT,
    perks       TEXT,                    -- JSON: [4 perk ids]
    addons      TEXT,                    -- JSON
    playstyle   TEXT,
    rating      REAL,
    source      TEXT DEFAULT 'user'      -- 'default' | 'user'
);

CREATE TABLE IF NOT EXISTS translations (
    term        TEXT PRIMARY KEY,
    zh          TEXT,
    source      TEXT DEFAULT '',
    reviewed    INTEGER DEFAULT 0        -- 1 = 人工校对过
);

CREATE TABLE IF NOT EXISTS sync_meta (
    key         TEXT PRIMARY KEY,
    value       TEXT
);

CREATE TABLE IF NOT EXISTS patches (
    id          INTEGER PRIMARY KEY,
    patch       TEXT NOT NULL,           -- '10.2.0'
    rdate       TEXT,                    -- '06.10.2026'
    ptb         INTEGER DEFAULT 0,       -- 1 = 测试服
    notes       TEXT                     -- 变更说明（中文，人工/词典）
);
"""


def connect(db_path: str | Path) -> sqlite3.Connection:
    """Open the database, applying the schema."""
    db_path = Path(db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    _migrate(conn)
    conn.commit()
    return conn


def _migrate(conn: sqlite3.Connection) -> None:
    """Additive migrations for databases created by older versions."""
    cols = {row[1] for row in conn.execute("PRAGMA table_info(builds)")}
    if "source" not in cols:
        conn.execute(
            "ALTER TABLE builds ADD COLUMN source TEXT DEFAULT 'user'"
        )
        conn.execute(
            "UPDATE builds SET source = 'default' WHERE id IN "
            "(SELECT id FROM builds ORDER BY id LIMIT 2)"
        )
    char_cols = {row[1] for row in conn.execute("PRAGMA table_info(characters)")}
    if "alternate" not in char_cols:
        conn.execute("ALTER TABLE characters ADD COLUMN alternate TEXT")
    for tbl in ("perks", "addons"):
        cols = {row[1] for row in conn.execute(f"PRAGMA table_info({tbl})")}
        if "tags_en" not in cols:
            conn.execute(f"ALTER TABLE {tbl} ADD COLUMN tags_en TEXT")
