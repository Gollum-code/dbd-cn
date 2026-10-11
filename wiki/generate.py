"""Static wiki generator.

Reads the db-cn SQLite database and renders a full static HTML site
(Jinja2 templates) that can be hosted on GitHub Pages / any static host.

Pages:
  index.html           首页：版本信息、角色/技能导航
  roster/killers.html    杀手列表
  roster/survivors.html  逃生者列表
  character/{id}.html    角色详情
  perks.html             技能列表
  perk/{id}.html         技能详情
  addons.html            附加品列表
  maps.html              地图/领域
  changelog.html         更新日志
  builds.html            社区构筑
  sitemap.xml            站点地图（--sitemap）
  robots.txt             爬虫协议（--sitemap）
"""

from __future__ import annotations

import argparse
import json
import shutil
import sqlite3
from pathlib import Path
from urllib.parse import quote

from jinja2 import Environment, FileSystemLoader, select_autoescape

SCRIPT = "dbd-cn/0.1 (+https://github.com/dbd-cn; contact=dbd-cn@example.org)"
SITE_URL = "https://dbd-cn.github.io/dbd-cn/"

try:
    from crawler.db import connect
except ImportError:  # allow running as `python wiki/generate.py`
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from crawler.db import connect


def _rows(conn: sqlite3.Connection, sql: str, params=()) -> list[dict]:
    return [dict(r) for r in conn.execute(sql, params)]


def _jsonld(obj: dict) -> str:
    """Serialise a JSON-LD block, safe to embed inside a <script> tag."""
    return json.dumps(obj, ensure_ascii=False).replace("<", "\\u003c")


def _jsonld_website(base: str) -> str:
    return _jsonld({
        "@context": "https://schema.org",
        "@type": "WebSite",
        "name": "黎明杀机中文 Wiki",
        "url": base,
        "inLanguage": "zh-CN",
        "potentialAction": {
            "@type": "SearchAction",
            "target": base + "search.html?q={search_term_string}",
            "query-input": "required name=search_term_string",
        },
    })


def _jsonld_character(ch: dict, base: str) -> str:
    return _jsonld({
        "@context": "https://schema.org",
        "@type": "VideoGameCharacter",
        "name": ch.get("name_zh") or ch.get("name_en"),
        "alternateName": ch.get("name_en"),
        "url": base + "character/" + ch["id"] + ".html",
        "inLanguage": "zh-CN",
    })


def _jsonld_perk(p: dict, base: str) -> str:
    return _jsonld({
        "@context": "https://schema.org",
        "@type": "Thing",
        "name": p.get("name_zh") or p.get("name_en"),
        "alternateName": p.get("name_en"),
        "url": base + "perk/" + p["id"] + ".html",
        "description": (p.get("description") or "")[:300],
        "inLanguage": "zh-CN",
    })


def _base_url(p: Path, out_dir: Path) -> str:
    """Relative path prefix from a generated page back to the site root.

    e.g. index.html / addons-2.html -> ""  (already at root)
         character/K01.html          -> "../"
    """
    rel = p.relative_to(out_dir)
    return "../" * (len(rel.parts) - 1)


def _seo(title: str, desc: str, keywords: str = "", canonical: str = "") -> dict:
    return {
        "page_title": title,
        "description": desc,
        "keywords": keywords,
        "canonical": canonical,
    }


def render_site(
    db_path: str,
    out_dir: str,
    templates_dir: str | None = None,
    *,
    site_url: str = "https://dbd-cn.github.io/dbd-cn/",
    write_seo: bool = True,
) -> dict:
    db_path = Path(db_path)
    out_dir = Path(out_dir)
    templates_dir = Path(templates_dir) if templates_dir else Path(__file__).parent / "templates"

    conn = connect(db_path)
    env = Environment(
        loader=FileSystemLoader(templates_dir),
        autoescape=select_autoescape(["html", "xml"]),
    )

    def load_json(raw: str | None, default=None):
        if not raw:
            return default if default is not None else {}
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return default if default is not None else {}

    env.filters["fromjson"] = load_json

    def icon_url(icon: str | None, base: str = "") -> str:
        """Map a DB icon path (icons/x/y.png) to its site-relative URL."""
        if not icon:
            return ""
        return (base or "") + "static/" + icon.lstrip("/")

    env.filters["icon_url"] = icon_url

    try:
        from crawler.pipeline import parse_stated_values
    except ImportError:  # pragma: no cover - standalone import path
        def parse_stated_values(raw):  # type: ignore[misc]
            return []

    env.filters["states"] = parse_stated_values

    killers = _rows(conn, "SELECT * FROM characters WHERE role='killer' ORDER BY id")
    survivors = _rows(conn, "SELECT * FROM characters WHERE role='survivor' ORDER BY id")
    perks = _rows(conn, "SELECT * FROM perks ORDER BY name_en")
    addons = _rows(conn, "SELECT * FROM addons ORDER BY name_en")
    maps = _rows(conn, "SELECT * FROM maps ORDER BY name_en")
    realms = _rows(conn, "SELECT * FROM realms ORDER BY id")
    patches = _rows(conn, "SELECT * FROM patches ORDER BY id DESC")
    builds = _rows(conn, "SELECT * FROM builds ORDER BY rating DESC")
    sync = dict(conn.execute("SELECT key,value FROM sync_meta").fetchall())
    char_by_id = {c["id"]: c for c in killers + survivors}

    sitemap: list[str] = []

    # index
    page = out_dir / "index.html"
    _w(page, env.get_template("index.html").render(
        killers=killers, survivors=survivors, perks=perks, maps=maps, realms=realms,
        patches=patches, sync=sync, base=_base_url(page, out_dir),
        jsonld=_jsonld_website(SITE_URL),
        **_seo("黎明杀机中文Wiki - 角色/技能/附加品/地图资料站",
               "黎明杀机（Dead by Daylight）中文资料站：杀手与逃生者图鉴、技能大全、附加品、地图领域、构筑推荐。每周自动同步官方数据。",
               "黎明杀机,黎明杀机wiki,DBD,Dead by Daylight,杀手,逃生者,技能,附加品,地图",
               SITE_URL)))
    sitemap.append(page)

    # roster
    for role, rows, name in (("killer", killers, "杀手"), ("survivor", survivors, "逃生者")):
        page = out_dir / f"roster/{role}s.html"
        _w(page, env.get_template("roster.html").render(
            role=role, title=f"{name}图鉴", chars=rows, sync=sync,
            base=_base_url(page, out_dir),
            **_seo(f"{name}图鉴 - 黎明杀机中文Wiki",
                   f"黎明杀机『{name}』全角色图鉴：难度/移速/恐惧范围/背景故事与专属技能。",
                   "黎明杀机,DBD,杀手,逃生者,角色图鉴",
                   SITE_URL + f"roster/{role}s.html")))
        sitemap.append(page)

# character detail
    universal = {
        "killer": [p for p in perks if p["owner"] == "K00"],
        "survivor": [p for p in perks if p["owner"] == "S00"],
    }
    for ch in killers + survivors:
        owner = ch["id"]
        owned_perks = [p for p in perks if p["owner"] == owner]
        owned_addons = [a for a in addons if a["owner"] == owner]
        realm = next((r for r in realms if r["id"] == ch.get("realm_id")), None)
        name = ch["name_zh"] or ch["name_en"]
        page = out_dir / "character" / f"{ch['id']}.html"
        _w(page, env.get_template("character.html").render(
            ch=ch, perks=owned_perks, addons=owned_addons, realm=realm, sync=sync,
            universal_perks=universal[ch["role"]],
            base=_base_url(page, out_dir),
            jsonld=_jsonld_character(ch, SITE_URL),
            **_seo(f"{name} - 黎明杀机中文Wiki",
                   f"黎明杀机角色『{name}』资料：{'背景故事、能力与' if ch['role']=='killer' else ''}专属技能、附加品。",
                   canonical=SITE_URL + "character/" + ch["id"] + ".html")) )
        sitemap.append(page)

    # perks list + detail
    page = out_dir / "perks.html"
    _w(page, env.get_template("perks.html").render(
        perks=perks, killers=killers, survivors=survivors, sync=sync, base=_base_url(page, out_dir),
        **_seo("技能大全 - 黎明杀机中文Wiki",
               "黎明杀机全部技能中文资料：技能描述、三档数值、所属角色。支持中文检索。",
               "黎明杀机,DBD,技能,技能大全,技能图鉴",
               SITE_URL + "perks.html")))
    sitemap.append(page)
    for p in perks:
        pname = p["name_zh"] or p["name_en"]
        page = out_dir / f"perk/{p['id']}.html"
        _w(page, env.get_template("perk.html").render(
            p=p, owner=char_by_id.get(p["owner"]), sync=sync, base=_base_url(page, out_dir),
            jsonld=_jsonld_perk(p, SITE_URL),
            **_seo(f"{pname} - 黎明杀机中文Wiki",
                   f"黎明杀机技能『{pname}』（{p['name_en']}）：效果描述与三档数值。",
                   canonical=SITE_URL + "perk/" + p["id"] + ".html")))
        sitemap.append(page)

    # addons list (paginated: addons.html, addons-2.html, ...)
    _write_paginated_addons(out_dir, addons, killers, survivors, sitemap)
    for a in addons:
        owner = char_by_id.get(a["owner"])
        page = out_dir / "addon" / f"{a['id']}.html"
        _w(page, env.get_template("addon.html").render(
            a=a, owner=owner, sync=sync, base=_base_url(page, out_dir),
            **_seo("{} - 附加品 - DBD 中文 Wiki".format(a.get("name_zh") or a["name_en"]),
                   "{}：中文效果、稀有度与所属角色。".format(a.get("name_zh") or a["name_en"]),
                   canonical=SITE_URL + "addon/" + a["id"] + ".html")))
        sitemap.append(page)

    # maps
    page = out_dir / "maps.html"
    _w(page, env.get_template("maps.html").render(
        maps=maps, realms=realms, sync=sync, base=_base_url(page, out_dir),
        **_seo("地图与领域 - 黎明杀机中文Wiki",
               "黎明杀机地图与领域资料：钩点、图腾点、地图尺寸版本变化。",
               canonical=SITE_URL + "maps.html")))
    sitemap.append(page)

    # 404 page
    page = out_dir / "404.html"
    _w(page, env.get_template("404.html").render(
        sync=sync, base=_base_url(page, out_dir),
        **_seo("页面不存在 - DBD 中文 Wiki", "页面不存在。", canonical=SITE_URL + "404.html")))

    # 站内搜索（索引单独成文件，便于缓存/并行加载）
    search_index = _build_search_index(killers + survivors, perks, addons, maps, realms)
    index_path = out_dir / "static" / "search-index.json"
    index_path.parent.mkdir(parents=True, exist_ok=True)
    index_path.write_text(
        json.dumps(search_index, ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8",
    )
    page = out_dir / "search.html"
    _w(page, env.get_template("search.html").render(
        index={"total": len(search_index)},
        index_url=_base_url(page, out_dir) + "static/search-index.json",
        sync=sync, base=_base_url(page, out_dir),
        **_seo("搜索 - DBD 中文 Wiki",
               "在黎明杀机中文 Wiki 中搜索角色、技能、附加品与地图，支持中文效果关键词。",
               canonical=SITE_URL + "search.html")))
    sitemap.append(page)

    # changelog (patches) - paginated
    _write_paginated_changelog(out_dir, patches, sitemap, per_page=50)

    # builds (from DB; community section)
    page = out_dir / "builds.html"
    _w(page, env.get_template("builds.html").render(
        builds=builds, char_by_id=char_by_id, sync=sync, base=_base_url(page, out_dir),
        **_seo("构筑推荐 - 黎明杀机中文Wiki",
               "黎明杀机社区构筑推荐：杀手/逃生者主流玩法技能搭配。",
               canonical=SITE_URL + "builds.html")))
    sitemap.append(page)

    # assets
    static = Path(__file__).parent / "static"
    if static.exists():
        shutil.copytree(static, out_dir / "static", dirs_exist_ok=True)

    # icons (from data/icons, referenced by DB icon column as icons/...)
    icons_src = Path(db_path).parent / "icons"
    if icons_src.exists():
        shutil.copytree(icons_src, out_dir / "static" / "icons", dirs_exist_ok=True)

    # SEO extras
    if write_seo:
        _write_sitemap(out_dir, sitemap, site_url)
        _write_robots(out_dir)

    conn.close()
    counts = {"pages": sum(1 for _ in out_dir.rglob("*.html")),
              "characters": len(killers) + len(survivors), "perks": len(perks)}
    return counts


def _body(text: str | None, cap: int = 200) -> str:
    """Collapse + cap a long body so the embedded index stays small."""
    if not text:
        return ""
    return " ".join(text.split())[:cap]


def _build_search_index(chars, perks, addons, maps, realms) -> list[list[str]]:
    """Client-side search index as compact arrays.

    Row shape: ``[kind, id, name_zh, name_en, body, url]``.  The full body text
    is kept so a keyword late in a long description still matches; the compact
    array layout (instead of objects with named keys) roughly halves the file.
    """
    rows: list[list[str]] = []
    for c in chars:
        rows.append([
            "角色", c["id"], c.get("name_zh") or "", c.get("name_en") or "",
            " ".join(x for x in [c.get("lore"), c.get("power")] if x),
            f"character/{c['id']}.html",
        ])
    for p in perks:
        rows.append([
            "技能", p["id"], p.get("name_zh") or "", p.get("name_en") or "",
            p.get("description") or "",
            f"perk/{p['id']}.html",
        ])
    for a in addons:
        rows.append([
            "附加品", a["id"], a.get("name_zh") or "", a.get("name_en") or "",
            a.get("effect") or "",
            f"addon/{a['id']}.html",
        ])
    for m in maps:
        rows.append(["地图", m["id"], m.get("name_zh") or "", m.get("name_en") or "", "", "maps.html"])
    for r in realms:
        rows.append([
            "领域", str(r["id"]), r.get("name_zh") or "", r.get("name_en") or "",
            r.get("location") or "", "maps.html",
        ])
    return rows


def _page_name(stem: str, n: int) -> str:
    """File name for page n of a paginated section (page 1 has no suffix)."""
    return f"{stem}.html" if n == 1 else f"{stem}-{n}.html"


def _write_paginated_changelog(out_dir: Path, patches, sitemap, per_page: int = 50):
    """Render the patch changelog split across pages."""
    templates_dir = Path(__file__).parent / "templates"
    env = Environment(
        loader=FileSystemLoader(templates_dir),
        autoescape=select_autoescape(["html", "xml"]),
    )
    total = len(patches)
    pages = max(1, (total + per_page - 1) // per_page)
    for n in range(1, pages + 1):
        chunk = patches[(n - 1) * per_page : n * per_page]
        page = out_dir / ("changelog.html" if n == 1 else f"changelog-{n}.html")
        base = _base_url(page, out_dir)
        page_links = [
            {
                "n": i,
                "url": base + ("changelog.html" if i == 1 else f"changelog-{i}.html"),
                "current": i == n,
            }
            for i in range(1, pages + 1)
        ]
        _w(page, env.get_template("changelog.html").render(
            page_patches=chunk,
            total=total,
            page=n,
            pages=pages,
            page_links=page_links,
            prev_url=(base + _page_name("changelog", n - 1) if n > 1 else ""),
            next_url=(base + _page_name("changelog", n + 1) if n < pages else ""),
            base=base,
            sync={},
        ))
        sitemap.append(page)


def _write_paginated_addons(out_dir: Path, addons, killers, survivors, sitemap, per_page: int = 150):
    """Render the addons list split across pages to keep each file small."""
    templates_dir = Path(__file__).parent / "templates"
    env = Environment(
        loader=FileSystemLoader(templates_dir),
        autoescape=select_autoescape(["html", "xml"]),
    )

    def icon_url(icon, base=""):
        if not icon:
            return ""
        return (base or "") + "static/" + icon.lstrip("/")

    env.filters["icon_url"] = icon_url
    total = len(addons)
    pages = max(1, (total + per_page - 1) // per_page)
    for n in range(1, pages + 1):
        chunk = addons[(n - 1) * per_page : n * per_page]
        page = out_dir / ("addons.html" if n == 1 else f"addons-{n}.html")
        base = _base_url(page, out_dir)
        page_links = [
            {
                "n": i,
                "url": base + ("addons.html" if i == 1 else f"addons-{i}.html"),
                "current": i == n,
            }
            for i in range(1, pages + 1)
        ]
        _w(page, env.get_template("addons.html").render(
            page_addons=chunk,
            killers=killers,
            survivors=survivors,
            total=total,
            page=n,
            pages=pages,
            page_links=page_links,
            prev_url=(base + _page_name("addons", n - 1) if n > 1 else ""),
            next_url=(base + _page_name("addons", n + 1) if n < pages else ""),
            base=base,
            sync={},
        ))
        sitemap.append(page)


def _write_sitemap(out_dir: Path, pages: list[Path], site_url: str) -> None:
    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">',
    ]
    root = site_url.rstrip("/")
    for p in pages:
        rel = p.relative_to(out_dir).as_posix()
        url = f"{root}/{quote(rel)}"
        lines.append(f"  <url><loc>{url}</loc></url>")
    lines.append("</urlset>")
    _w(out_dir / "sitemap.xml", "\n".join(lines) + "\n")


def _write_robots(out_dir: Path) -> None:
    _w(out_dir / "robots.txt",
       "User-agent: *\nAllow: /\n\nSitemap: https://dbd-cn.github.io/dbd-cn/sitemap.xml\n")


def _w(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def main() -> None:
    ap = argparse.ArgumentParser(prog="dbd-wiki", description="从 SQLite 生成静态中文 Wiki")
    ap.add_argument("--db", default="data/dbd_cn.db")
    ap.add_argument("--out", default="site")
    ap.add_argument("--templates", default=None)
    ap.add_argument("--sitemap", action="store_true", help="额外生成 sitemap.xml 与 robots.txt")
    args = ap.parse_args()
    counts = render_site(args.db, args.out, args.templates, write_seo=args.sitemap)
    print("站点已生成:", counts)


if __name__ == "__main__":
    main()
