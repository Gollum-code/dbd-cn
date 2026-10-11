"""Unit tests for the DBD中文项目计划 crawler/mapping pipeline."""

from __future__ import annotations

from crawler.lua_parser import (
    extract_table,
    parse_lua_value,
    strip_lua_comments,
)


class TestLuaParser:
    def test_simple_string(self):
        assert parse_lua_value('{["a"] = "hello"}') == {"a": "hello"}

    def test_number_and_boolean(self):
        assert parse_lua_value("{id = 1, specialAttack = false}") == {
            "id": 1,
            "specialAttack": False,
        }

    def test_nested_array_compacts_to_list(self):
        assert parse_lua_value('{{id = 1}, {id = 2}}') == [
            {"id": 1},
            {"id": 2},
        ]

    def test_alt_name_array(self):
        val = parse_lua_value('{altName = {"Banshee", "Bob"}}')
        assert val == {"altName": ["Banshee", "Bob"]}

    def test_semicolon_separator(self):
        val = parse_lua_value('{["Power Range"] = {tags = {"A"; "B"}}}')
        assert val == {"Power Range": {"tags": ["A", "B"]}}

    def test_concat_operator(self):
        val = parse_lua_value('{g = "Men (" .. "Julie)"}')
        assert val == {"g": "Men (Julie)"}

    def test_killers_row(self):
        src = (
            '{id = 1, name = "Trapper", realName = "Evan MacMillan", '
            'gender = "Man", realm = 1, specialAttack = true, speed = 4.6, '
            "radius = 32, height = 'T', diff = 1}"
        )
        assert parse_lua_value(src) == {
            "id": 1,
            "name": "Trapper",
            "realName": "Evan MacMillan",
            "gender": "Man",
            "realm": 1,
            "specialAttack": True,
            "speed": 4.6,
            "radius": 32,
            "height": "T",
            "diff": 1,
        }

    def test_comments_stripped(self):
        src = "--line\n--[[\n block ]] killers = { --tail\n {id = 1}, --row\n}"
        assert "killers" in strip_lua_comments(src)

    def test_extract_bare_table(self):
        src = "killers = {\n{id = 1, name = \"Trapper\"},\n{id = 2, name = \"Wraith\"},\n}"
        assert extract_table(src, "killers", kind="bare") == [
            {"id": 1, "name": "Trapper"},
            {"id": 2, "name": "Wraith"},
        ]

    def test_extract_p_table(self):
        src = 'p.perks = { ["Adrenaline"] = {id = 42, values = {60, 50, 40}} }'
        assert extract_table(src, "perks") == {
            "Adrenaline": {"id": 42, "values": [60, 50, 40]}
        }


class TestPipelineNormalisation:
    def test_character_ids(self):
        from crawler.pipeline import normalise_characters

        killers = [{"id": 1, "name": "Trapper", "gender": "Man"}]
        survivors = [{"id": 1, "name": "Dwight Fairfield"}]
        out = normalise_characters(killers, survivors, [])
        assert out[0]["id"] == "K01"
        assert out[1]["id"] == "S01"
        assert out[0]["role"] == "killer"
        assert out[1]["role"] == "survivor"

    def test_translation_hits_dictionary(self):
        from crawler.pipeline import normalise_characters

        out = normalise_characters([{"id": 1, "name": "Trapper"}], [], [])
        assert out[0]["name_zh"] == "设陷者"

    def test_slugify(self):
        from crawler.pipeline import _slugify

        assert _slugify("A Nurse's Calling") == "aNurseSCalling"
        assert _slugify("Ace in the Hole") == "aceInTheHole"

    def test_json_safe_serialises_lists(self):
        from crawler.pipeline import _json_safe

        assert _json_safe([1, 2]) == "[1, 2]"
        assert _json_safe("plain") == "plain"
        assert _json_safe(None) is None


class TestTranslator:
    def test_known_terms(self):
        from crawler.translate import translate_term

        assert translate_term("Trapper") == "设陷者"
        assert translate_term("Common") == "常见"
        assert translate_term("The MacMillan Estate") == "麦克米伦庄园"

    def test_unknown_passthrough(self):
        from crawler.translate import translate_term

        assert translate_term("Some New Realm") == "Some New Realm"
        assert translate_term("") == ""
        assert translate_term(None) == ""

    def test_untranslated_detector(self):
        from crawler.translate import looks_untranslated

        assert looks_untranslated("Coal Tower")
        assert not looks_untranslated("麦克米伦庄园")
