"""Unit tests for the LLM translation module (offline, no API calls)."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from crawler.llm import _has_cjk, JOBS, MAX_CHARS, PARALLEL, _load_dotenv, cfg


class TestHelpers:
    def test_has_cjk(self):
        assert _has_cjk("这是中文")
        assert not _has_cjk("English only")
        assert not _has_cjk("")
        assert not _has_cjk(None)

    def test_jobs_cover_fields(self):
        keys = {f"{t}.{c}" for t, c, _ in JOBS}
        assert "perks.description" in keys
        assert "characters.lore" in keys
        assert "addons.effect" in keys
        assert "patches.notes" in keys

    def test_config_defaults(self):
        # cfg falls back to defaults when env is unset
        assert isinstance(cfg("LLM_MODEL_UNSET_XYZ", "fallback"), str)


class TestDotEnv:
    def test_load_dotenv_is_safe_without_file(self, tmp_path, monkeypatch):
        monkeypatch.setattr(
            "crawler.llm._DOT_ENV", tmp_path / "does-not-exist.env"
        )
        _load_dotenv()  # must not raise


class TestBatchParse:
    def test_batch_translate_parses_numbered_lines(self):
        # exercise the parsing logic without hitting the network by using a stub client
        from crawler.llm import LlmClient

        class Stub(LlmClient):
            def _chat(self, messages, max_tokens=1500):
                return "1: 译文一\n2: 译文二\n3: 译文三"

        stub = Stub(base_url="", api_key="x", model="x")
        out = stub.batch_translate(["a", "b", "c"])
        assert out == ["译文一", "译文二", "译文三"]

    def test_batch_translate_handles_empty(self):
        from crawler.llm import LlmClient

        class Stub(LlmClient):
            def _chat(self, messages, max_tokens=1500):
                return ""

        stub = Stub(base_url="", api_key="x", model="x")
        assert stub.batch_translate(["a", "b"]) == ["", ""]
        assert stub.batch_translate([]) == []
