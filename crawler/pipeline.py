"""The data pipeline: fetch wiki.gg modules -> parse -> load SQLite.

Entry point for the weekly sync.  Reads `Module:Datatable` and
`Module:Datatable/Loadout` (the wiki's structured data), normalises them into
the db-cn schema and upserts into the local SQLite database.
"""

from __future__ import annotations

import datetime as _dt
import json
import logging
import re
from pathlib import Path
from typing import Any

from . import translate as tr
from .api import WikiClient
from .db import connect
from .lua_parser import extract_table
from .translate import translate_all

log = logging.getLogger(__name__)

LATEST_PATCH = "unknown"
_own_slug_cache: dict[str, str] = {}


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------
def _slugify(name: str) -> str:
    slug = re.sub(r"[^A-Za-z0-9]+", " ", name).strip()
    slug = "".join(w.capitalize() for w in slug.split())
    if not slug:
        slug = "unknown"
    return slug[:1].lower() + slug[1:] if len(slug) > 1 else slug.lower() or "unknown"


def _ts() -> str:
    return _dt.datetime.now(_dt.timezone.utc).isoformat(timespec="minutes")


def _char_id(role: str, num: int) -> str:
    return f"{'K' if role == 'killer' else 'S'}{num:02d}"


def _norm_list(obj: Any) -> list[Any]:
    if obj is None:
        return []
    if isinstance(obj, list):
        return obj
    if isinstance(obj, (set, tuple)):
        return list(obj)
    if isinstance(obj, dict):
        return list(obj.values())
    return [obj]


def _tags_zh(obj: Any) -> str:
    """Translate a Lua tag list into a JSON array of Chinese labels.

    Unknown tags keep their original English name so nothing is lost.
    """
    tags = tr.EXTRA_DICTS.get("tags_zh", {})
    out = []
    for t in _norm_list(obj):
        if not isinstance(t, str):
            continue
        out.append(tags.get(t, t))
    return json.dumps(out, ensure_ascii=False)


# ---------------------------------------------------------------------------
# fetch
# ---------------------------------------------------------------------------
def fetch_module(client: WikiClient, title: str) -> str:
    log.info("fetching %s", title)
    return client.page_content(title)


# ---------------------------------------------------------------------------
# normalisers
# ---------------------------------------------------------------------------
def _json_safe(value: Any) -> Any:
    """Serialise Lua dict/list structures into a JSON string."""
    if value is None or isinstance(value, (str, int, float)):
        return value
    return json.dumps(value, ensure_ascii=False)


def parse_stated_values(raw: Any) -> list[dict]:
    """Parse a killer's speed / terror_radius into [{label, value}] forms.

    Handles three shapes coming from the wiki datatables:
      4.6                                  -> single unnamed form
      [4.6, "Uncloaked"]                   -> {形态: Uncloaked, 数值: 4.6}
      [[32, "Stalker Mode"], [16, "Pursuer"]] -> several labelled forms

    Returns an empty list when there is nothing to show.
    """

    def num(v: float) -> float | int:
        return int(v) if float(v).is_integer() else v

    if raw is None or raw == "":
        return []
    data: Any = raw
    if isinstance(raw, str):
        text = raw.strip()
        if not text:
            return []
        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            try:
                return [{"label": "", "value": num(float(text))}]
            except ValueError:
                return []
    if isinstance(data, (int, float)):
        return [{"label": "", "value": num(float(data))}]
    forms: list[dict] = []
    if isinstance(data, list):
        if len(data) == 2 and isinstance(data[0], (int, float)) and isinstance(data[1], str):
            return [{"label": data[1], "value": num(float(data[0]))}]
        for item in data:
            if isinstance(item, list) and len(item) == 2 and isinstance(item[0], (int, float)):
                forms.append({"label": str(item[1]), "value": num(float(item[0]))})
            elif isinstance(item, (int, float)):
                forms.append({"label": "", "value": num(float(item))})
    return forms


def normalise_characters(
    killers: list[dict], survivors: list[dict], realms: list[dict]
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    realm_map = {r.get("id"): r.get("name", "") for r in realms}
    for role, rows in (
        ("killer", killers),
        ("survivor", survivors),
    ):
        for row in rows:
            ch_id = _char_id("k", row.get("id", 0)) if role == "killer" else _char_id("s", row.get("id", 0))
            if role == "killer":
                ch_id = f"K{row.get('id', 0):02d}"
            else:
                ch_id = f"S{row.get('id', 0):02d}"
            name_en = row.get("name", "")
            out.append({
                "id": ch_id,
                "name_en": name_en,
                "name_zh": translate_all(name_en),
                "role": role,
                "difficulty": str(row.get("diff", "")) if role == "killer" else "",
                "speed": _json_safe(row.get("speed")) if role == "killer" else None,
                "terror_radius": _json_safe(row.get("radius")) if role == "killer" else None,
                "height": row.get("height") if role == "killer" else None,
                "gender": tr.translate_term(row.get("gender", "")),
                "origin": tr.translate_term(row.get("origin", "")),
                "realm_id": row.get("realm") if role == "killer" else None,
                "realm_name": realm_map.get(row.get("realm"), "") if role == "killer" else "",
                "dlc": str(row.get("dlc", "") or ""),
                "actor": _json_safe(row.get("actor")),
                "role_flavor": row.get("role", "") if role == "survivor" else "",
                "alternate": row.get("realName", ""),
            })
    return out


def normalise_perks(perks: dict[str, dict]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for name_en, row in perks.items():
        owner_num = row.get("character", 0)
        role = "K" if str(row.get("charType", "")).upper() == "K" else "S"
        owner = f"{role}{owner_num:02d}"
        out.append({
            "id": _slugify(name_en),
            "name_en": name_en,
            "name_zh": translate_all(name_en),
            "owner": owner,
            "role": "killer" if row.get("charType") == "K" else "survivor",
            "tiers": json.dumps(_norm_dict(row.get("values"))),
            "units": json.dumps(_norm_dict(row.get("units"))),
            "tags": _tags_zh(row.get("tags")),
            "tags_en": json.dumps(_norm_list(row.get("tags"))),
            "patch": row.get("patch", ""),
            "level": row.get("level", ""),
            "prestige": row.get("prestige", ""),
        })
    return out


def normalise_addons(addons: dict[str, dict]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for name_en, row in addons.items():
        if row.get("unused"):
            continue
        rarity_en = tr.RARITY_BY_LEVEL.get(row.get("rarity", 0), "Common")
        # Killers' add-ons are keyed by `killer = <killer id>` in the wiki
        # datatable (there is no charType/character column).  Survivor item
        # add-ons carry no owner at all.
        killer_id = row.get("killer")
        owner = f"K{killer_id:02d}" if isinstance(killer_id, int) else ""
        out.append({
            "id": _slugify(name_en),
            "name_en": name_en,
            "name_zh": translate_all(name_en),
            "owner": owner,
            "rarity": tr.translate_term(rarity_en),
            "rarity_en": rarity_en,
            "effect": "",
            "tags": _tags_zh(row.get("tags")),
            "tags_en": json.dumps(_norm_list(row.get("tags"))),
            "power": row.get("power", ""),
        })
    return out


def normalise_powers(powers: dict[str, dict]) -> dict[str, dict]:
    return {k: v for k, v in powers.items()}


def _load_landmarks() -> dict[str, dict]:
    """Load curated hook/totem counts for maps from dictionaries/landmarks.json."""
    path = Path(__file__).parent / "dictionaries" / "landmarks.json"
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data.get("maps", {})
    except (json.JSONDecodeError, OSError):
        return {}


def normalise_maps(maps: list[dict]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    landmarks = _load_landmarks()
    for row in maps:
        name = row.get("name", "")
        lm = landmarks.get(name, {})
        out.append({
            "id": str(row.get("id", 0)),
            "name_en": name,
            "name_zh": translate_all(name),
            "realm_id": row.get("realm"),
            "variations": json.dumps(row.get("variations", [])),
            "hooks": json.dumps(lm.get("hooks")) if lm.get("hooks") else None,
            "totems": json.dumps(lm.get("totems")) if lm.get("totems") else None,
        })
    return out


def normalise_realms(realms: list[dict]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for row in realms:
        out.append({
            "id": row.get("id", 0),
            "name_en": row.get("name", ""),
            "name_zh": translate_all(row.get("name", "")),
            "abbr": row.get("abbr", ""),
            "location": tr.translate_term(row.get("location", "")),
            "palette": row.get("palette", ""),
            "color": row.get("color", ""),
        })
    return out


def _norm_dict(obj: Any) -> dict:
    if isinstance(obj, dict):
        return obj
    if isinstance(obj, list):
        return {i + 1: v for i, v in enumerate(obj)}
    return {}


# ---------------------------------------------------------------------------
# loader
# ---------------------------------------------------------------------------
def normalise_patches(patches: list[dict]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for row in patches:
        out.append({
            "id": row.get("id", 0),
            "patch": row.get("patch", ""),
            "rdate": row.get("rDate", ""),
            "ptb": 1 if row.get("ptb") else 0,
            "notes": "",
        })
    return out


def load_into_db(conn, *, characters, perks, addons, maps, realms, patches=None):
    cur = conn.cursor()
    for ch in characters:
        cur.execute(
            """INSERT INTO characters
               (id,name_en,name_zh,role,difficulty,speed,terror_radius,height,
                gender,origin,realm_id,dlc,actor,alternate,updated_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
               ON CONFLICT(id) DO UPDATE SET
                 name_en=excluded.name_en,name_zh=excluded.name_zh,
                 role=excluded.role,difficulty=excluded.difficulty,
                 speed=excluded.speed,terror_radius=excluded.terror_radius,
                 height=excluded.height,gender=excluded.gender,
                 origin=excluded.origin,realm_id=excluded.realm_id,
                 actor=excluded.actor,alternate=excluded.alternate,
                 updated_at=excluded.updated_at""",
            (ch["id"], ch["name_en"], ch["name_zh"], ch["role"], ch["difficulty"],
             ch.get("speed"), ch.get("terror_radius"), ch.get("height"),
             ch.get("gender"), ch.get("origin"), ch.get("realm_id"),
             ch.get("dlc"), ch.get("actor"), ch.get("alternate"), _ts()),
        )
    for p in perks:
        cur.execute(
            """INSERT INTO perks
               (id,name_en,name_zh,owner,role,tiers,units,tags,tags_en,patch,updated_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?)
               ON CONFLICT(id) DO UPDATE SET
                 name_en=excluded.name_en,name_zh=excluded.name_zh,
                 owner=excluded.owner,role=excluded.role,tiers=excluded.tiers,
                 units=excluded.units,tags=excluded.tags,tags_en=excluded.tags_en,
                 patch=excluded.patch,updated_at=excluded.updated_at""",
            (p["id"], p["name_en"], p["name_zh"], p["owner"], p["role"],
             p["tiers"], p["units"], p["tags"], p.get("tags_en", "[]"),
             p.get("patch", ""), _ts()),
        )
    for a in addons:
        cur.execute(
            """INSERT INTO addons
               (id,name_en,name_zh,owner,rarity,rarity_en,tags,tags_en,icon,updated_at)
               VALUES (?,?,?,?,?,?,?,?,?,?)
               ON CONFLICT(id) DO UPDATE SET
                 name_en=excluded.name_en,name_zh=excluded.name_zh,
                 owner=excluded.owner,rarity=excluded.rarity,
                 rarity_en=excluded.rarity_en,tags=excluded.tags,
                 tags_en=excluded.tags_en,icon=COALESCE(excluded.icon, addons.icon),
                 updated_at=excluded.updated_at""",
            (a["id"], a["name_en"], a["name_zh"], a.get("owner", ""),
             a.get("rarity", ""), a.get("rarity_en", ""), a.get("tags", "[]"),
             a.get("tags_en", "[]"), a.get("icon"), _ts()),
        )
    for m_ in maps:
        cur.execute(
            """INSERT INTO maps (id,name_en,name_zh,realm_id,variations,hooks,totems)
               VALUES (?,?,?,?,?,?,?)
               ON CONFLICT(id) DO UPDATE SET
                 name_en=excluded.name_en,name_zh=excluded.name_zh,
                 realm_id=excluded.realm_id,variations=excluded.variations,
                 hooks=excluded.hooks,totems=excluded.totems""",
            (m_["id"], m_["name_en"], m_["name_zh"], m_.get("realm_id"),
             m_.get("variations", "[]"), m_.get("hooks"), m_.get("totems")),
        )
    for r in realms:
        cur.execute(
            """INSERT INTO realms (id,name_en,name_zh,abbr,location,palette,color)
               VALUES (?,?,?,?,?,?,?)
               ON CONFLICT(id) DO UPDATE SET
                 name_en=excluded.name_en,name_zh=excluded.name_zh,
                 abbr=excluded.abbr,location=excluded.location,
                 palette=excluded.palette,color=excluded.color""",
            (r["id"], r["name_en"], r["name_zh"], r.get("abbr", ""),
             r.get("location", ""), r.get("palette", ""), r.get("color", "")),
        )
    for p in patches or []:
        cur.execute(
            """INSERT INTO patches (id,patch,rdate,ptb,notes)
               VALUES (?,?,?,?,?)
               ON CONFLICT(id) DO UPDATE SET
                 patch=excluded.patch,rdate=excluded.rdate,
                 ptb=excluded.ptb,notes=excluded.notes""",
            (p["id"], p["patch"], p.get("rdate"), p.get("ptb", 0),
             p.get("notes", "")),
        )
    conn.commit()
    counts = {"characters": len(characters), "perks": len(perks),
              "addons": len(addons), "maps": len(maps), "realms": len(realms)}
    if patches is not None:
        counts["patches"] = len(patches)
    return counts


def build(client: WikiClient | None = None, db_path: str = "data/dbd_cn.db"):
    """Full pipeline: fetch -> parse -> load."""
    client = client or WikiClient()
    datatable = fetch_module(client, "Module:Datatable")
    loadout = fetch_module(client, "Module:Datatable/Loadout")

    killers = extract_table(datatable, "killers", kind="bare") or []
    survivors = extract_table(datatable, "survivors", kind="bare") or []
    realms = extract_table(datatable, "realms", kind="bare") or []
    maps_tbl = extract_table(datatable, "maps", kind="bare") or []
    patches_tbl = extract_table(datatable, "patches", kind="bare") or []
    perks = extract_table(loadout, "perks") or {}
    addons = extract_table(loadout, "addons") or {}
    # NOTE: the datatable also exposes a `powers` table (ability stats); it is
    # not persisted because the wiki carries the same info on each character
    # page (captured into characters.power by enrich.py).

    characters = normalise_characters(killers, survivors, realms)
    perks_out = normalise_perks(perks)
    addons_out = normalise_addons(addons)
    maps_out = normalise_maps(maps_tbl)
    realms_out = normalise_realms(realms)
    patches_out = normalise_patches(patches_tbl)

    conn = connect(db_path)
    counts = load_into_db(
        conn,
        characters=characters,
        perks=perks_out,
        addons=addons_out,
        maps=maps_out,
        realms=realms_out,
        patches=patches_out,
    )
    _seed_default_builds(conn)
    conn.execute(
        "INSERT OR REPLACE INTO sync_meta (key,value) VALUES ('last_sync',?)",
        (_ts(),),
    )
    conn.execute(
        "INSERT OR REPLACE INTO sync_meta (key,value) VALUES ('source','deadbydaylight.wiki.gg')",
    )
    conn.commit()
    conn.close()
    log.info("build complete: %s", counts)
    return counts


DEFAULT_BUILDS = [
    ("K01", "killer", '["brutalStrength","agitation","ironGrasp","monstrousShrine"]',
     '["stichedBag","rustedJaws"]', "控场流：熊夹封锁必经路线，配合高恐惧范围压制逃生者。", 4.6),
    ("S01", "survivor", '["bond","proveThyself","weWillMakeIt","leader"]',
     "[]", "团队辅助流：报点+加速修机+快速治疗，适合车队开黑。", 4.2),
    ("K02", "killer", '["hexRuin","hexUndying","hexRetribution","hexDevourHope"]',
     '["boneClapper","coxscomb"]', "图腾流：图腾叠 buff，利用咒术体系压制修机节奏。", 4.5),
    ("S04", "survivor", '["ironWill","sprintBurst","deadHard","decisiveStrike"]',
     "[]", "硬核遛鬼流：位移+反制，配合打击技能拖延杀手。", 4.4),
    ("K11", "killer", '["discordance","barbecueAndChilli","noWayOut","bloodWarden"]',
     '["darkTint","yellowBottle"]', "信息流：高频获取逃生者位置，利用终局技能收割。", 4.3),
    ("S06", "survivor", '["kindred","openHanded","windowsOfOpportunity","resilience"]',
     "[]", "侦查辅助流：报点+窗框视野+加速修理，稳扎稳打。", 4.0),
    ("K04", "killer", '["barbecueAndChilli","nursesCalling","agitation","ironGrasp"]',
     '["rustedJaws","serratedJaws"]', "追猎控制流：高频击倒+范围视野压制。", 4.2),
    ("S02", "survivor", '["sprintBurst","ironWill","endurance","perseverance"]',
     "[]", "逃生核心流：受伤加速+长时间自摸，极限逃生。", 4.1),
    ("K06", "killer", '["hexRuin","hexUndying","hexThrillOfTheHunt","hexDevourHope"]',
     '["boneClapper","coxscomb"]', "图腾献祭流：图腾buff+修复放缓，干扰修机节奏。", 4.4),
    ("S07", "survivor", '["alert","spineChill","resilience","situationalAwareness"]',
     "[]", "警觉生存流：提前感知杀手动向，避免危险位置。", 3.8),
]


def _seed_default_builds(conn) -> None:
    """Refresh default builds per character; user-added builds are preserved."""
    cur = conn.cursor()
    for char, role, perks, addons, play, rating in DEFAULT_BUILDS:
        cur.execute(
            "DELETE FROM builds WHERE character = ? AND role = ? AND source = 'default'",
            (char, role),
        )
        cur.execute(
            "INSERT INTO builds (character, role, perks, addons, playstyle,"
            " rating, source) VALUES (?,?,?,?,?,?, 'default')",
            (char, role, perks, addons, play, rating),
        )
    conn.commit()
