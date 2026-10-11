"""Unit tests for patches, landmarks and the translation review queue."""

from __future__ import annotations

from crawler.db import connect
from crawler.pipeline import normalise_patches
from crawler.review_queue import collect_untranslated, dump_review, import_review


class TestPatches:
    def test_normalise_patches(self):
        patches = [
            {"id": 398, "patch": "10.2.0", "rDate": "06.10.2026"},
            {"id": 396, "patch": "10.2.0", "rDate": "15.09.2026", "ptb": True},
        ]
        out = normalise_patches(patches)
        assert out[0]["patch"] == "10.2.0"
        assert out[0]["ptb"] == 0
        assert out[1]["ptb"] == 1


class TestMapsLandmarks:
    def test_normalise_maps_with_landmarks(self):
        from crawler.pipeline import normalise_maps

        rows = normalise_maps([{"id": 1, "name": "Coal Tower", "realm": 1}])
        assert rows[0]["name_zh"] == "煤塔"
        assert rows[0]["hooks"] == "10"
        assert rows[0]["totems"] == "5"

    def test_untranslated_languages(self):
        from crawler.translate import translate_all

        assert translate_all("Coal Tower") == "煤塔"
        assert translate_all("Gas Heaven") == "天堂加油站"


class TestReviewQueue:
    def test_collect_untranslated_and_import(self, tmp_path):
        db = connect(tmp_path / "t.db")
        db.execute(
            "INSERT OR REPLACE INTO perks (id, name_en, name_zh, owner, role, "
            "tiers, units, tags, updated_at) VALUES "
            "('x1','Cut Thru U Single','Cut Thru U Single','K30','killer',"
            "'{}','{}','[]','now')"
        )
        db.commit()

        rows = collect_untranslated(db)
        assert any(term == "Cut Thru U Single" for _, term, _ in rows)

        tsv = tmp_path / "review.tsv"
        n = dump_review(db, tsv)
        assert n >= 1
        reviewed = tmp_path / "reviewed.tsv"
        lines = [line for line in tsv.read_text(encoding="utf-8").splitlines()]
        header = lines[0]
        assert "类型" in header
        # fill in a Chinese value for the first data row
        filled = [header]
        for line in lines[1:]:
            if "Cut Thru U Single" in line:
                filled.append("\t".join(line.split("\t")[:2] + ["空刀无力"]))
            else:
                filled.append(line)
        reviewed.write_text("\n".join(filled), encoding="utf-8")

        merged = import_review(db, reviewed)
        assert merged >= 1
        zh = db.execute(
            "SELECT zh FROM translations WHERE term='Cut Thru U Single'"
        ).fetchone()[0]
        assert zh == "空刀无力"
        db.close()


class TestExtraDicts:
    def test_dict_files_load(self):
        from crawler.translate import EXTRA_DICTS

        assert "perks_zh" in EXTRA_DICTS
        assert "maps_zh" in EXTRA_DICTS
        assert "addons_zh" in EXTRA_DICTS
        assert len(EXTRA_DICTS["perks_zh"]) > 300


class TestLandmarksFile:
    def test_all_maps_covered(self, tmp_path):
        import json
        from pathlib import Path

        lm_path = Path("crawler/dictionaries/landmarks.json")
        if not lm_path.exists():
            return
        data = json.loads(lm_path.read_text(encoding="utf-8"))["maps"]
        assert len(data) == 46


class TestBuildsSeed:
    def test_default_builds_refresh(self, tmp_path):
        from crawler.pipeline import DEFAULT_BUILDS, _seed_default_builds

        db = connect(tmp_path / "b.db")
        _seed_default_builds(db)
        rows = db.execute(
            "SELECT character, source FROM builds ORDER BY id"
        ).fetchall()
        assert len(rows) == len(DEFAULT_BUILDS)
        assert all(r[1] == "default" for r in rows)
        # second call should not duplicate
        _seed_default_builds(db)
        rows2 = db.execute("SELECT COUNT(*) FROM builds").fetchone()[0]
        assert rows2 == len(DEFAULT_BUILDS)
        db.close()
