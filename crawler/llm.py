"""LLM-assisted translation of long-form content (descriptions, lore, effects).

The numeric/short fields are covered by the curated dictionaries; the long
texts (perk descriptions, character lore/power, addon effects, patch notes)
are translated here using the configured OpenAI-compatible chat API.

Config is read from `crawler/llm.py` env / `.env`:
  LLM_BASE_URL  (default https://api.inferaiapi.com/v1)
  LLM_API_KEY
  LLM_MODEL     (default deepseek-v4-pro)

The pipeline is checkpointed: every translated row is written to the DB
immediately, and rows that already contain CJK are skipped, so a re-run only
fills the remainder.
"""

from __future__ import annotations

import logging
import os
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import requests

log = logging.getLogger(__name__)

_DOT_ENV = Path(__file__).resolve().parent.parent / ".env"

SYSTEM_PROMPT = (
    "你是《黎明杀机》(Dead by Daylight) 中文资料站的专业翻译。"
    "将用户提供的英文游戏文本翻译成简体中文。"
    "要求：1) 术语使用玩家熟悉的译名（设陷者/幽灵/逃生者/技能/附加品等）；"
    "2) 保留数字、百分比、状态效果名（如 Exhausted 疲惫/ Haste 急速）的准确对应；"
    "3) 专有名词（人名、公司名、地名、作品名）采用通行音译或保留原文，不要生造译名；"
    "4) 输出纯中文翻译正文，不要任何解释、注释或 JSON 包装。"
)

# translation job spec: (table, column, chunk_label)
JOBS: list[tuple[str, str, str]] = [
    ("perks", "description", "技能描述"),
    ("characters", "lore", "角色背景"),
    ("characters", "power", "角色能力"),
    ("addons", "effect", "附加品效果"),
    ("patches", "notes", "补丁说明"),
]

MAX_CHARS = 1500        # per request input size
PARALLEL = 3            # concurrent requests (api is rate-limited; keep low)
MAX_ROUNDS = 8          # retry rounds for failures


# ---------------------------------------------------------------------------
# config
# ---------------------------------------------------------------------------
def _load_dotenv() -> None:
    if not _DOT_ENV.exists():
        return
    for line in _DOT_ENV.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, _, v = line.partition("=")
        os.environ.setdefault(k.strip(), v.strip())


def cfg(name: str, default: str) -> str:
    _load_dotenv()
    return os.environ.get(name) or default


BASE_URL = cfg("LLM_BASE_URL", "https://api.inferaiapi.com/v1").rstrip("/")
API_KEY = cfg("LLM_API_KEY", "")
MODEL = cfg("LLM_MODEL", "deepseek-v4-pro")


# ---------------------------------------------------------------------------
# chat client
# ---------------------------------------------------------------------------
class LlmClient:
    def __init__(self, base_url: str = BASE_URL, api_key: str = API_KEY,
                 model: str = MODEL, timeout: int = 180) -> None:
        self.base_url = base_url
        self.api_key = api_key
        self.model = model
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers["Authorization"] = f"Bearer {api_key}"
        self.session.headers["Content-Type"] = "application/json"

    def _chat(self, messages: list[dict], max_tokens: int = 1500) -> str:
        """One chat completion call with retries/backoff for 429."""
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": 0.3,
            "max_tokens": max_tokens,
        }
        for attempt in range(5):
            try:
                resp = self.session.post(
                    f"{self.base_url}/chat/completions",
                    json=payload,
                    timeout=self.timeout,
                )
                if resp.status_code == 429:
                    wait = 15 * (attempt + 1)
                    log.warning("rate limited, retry %d (sleep %ds)", attempt + 1, wait)
                    time.sleep(wait)
                    continue
                resp.raise_for_status()
                data = resp.json()
                return (data["choices"][0]["message"]["content"] or "").strip()
            except (requests.RequestException, KeyError, ValueError) as exc:
                log.warning("LLM call failed (attempt %d): %s", attempt + 1, exc)
                if attempt == 4:
                    raise
                time.sleep(10 * (attempt + 1))
        return ""

    def translate(self, text: str) -> str:
        """Translate a single block of game text; returns Chinese."""
        if not text or not text.strip():
            return ""
        if not self.api_key:
            raise RuntimeError("LLM_API_KEY 未配置（见 crawler/llm.py / .env）")
        return self._chat([
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": text[:MAX_CHARS]},
        ])

    def batch_translate(self, texts: list[str]) -> list[str]:
        """Translate several texts in ONE request.

        The model is asked to reply line-by-line ("1: 译文") so we can split
        reliably.  Entries that fail to parse are left empty (None-safe).
        """
        if not texts:
            return []
        if not self.api_key:
            raise RuntimeError("LLM_API_KEY 未配置（见 crawler/llm.py / .env）")
        body = "\n".join(f"{i + 1}. {t[:MAX_CHARS]}" for i, t in enumerate(texts))
        user = (
            "每条文本之间用单独的换行分隔，先输出序号再输出中文翻译，"
            "例如：\n1: 翻译一\n2: 翻译二\n仅输出该格式，不要加任何其他文字。\n\n"
            + body
        )
        raw = self._chat([
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user},
        ], max_tokens=3000)
        out: list[str] = [""] * len(texts)
        if not raw:
            return out
        for line in raw.splitlines():
            mm = re.match(r"^(\d+)\s*[.:、]\s*(.*)$", line)
            if mm:
                idx = int(mm.group(1)) - 1
                if 0 <= idx < len(texts):
                    out[idx] = mm.group(2).strip()
        return out


# ---------------------------------------------------------------------------
# worker
# ---------------------------------------------------------------------------
def _has_cjk(text: str) -> bool:
    return bool(re.search(r"[\u4e00-\u9fff]", text or ""))


def _iter_pending(conn, table: str, column: str):
    """Yield (id, text) rows that are untranslated and non-empty."""
    cur = conn.execute(
        f"SELECT id, {column} FROM {table} "
        f"WHERE {column} IS NOT NULL AND TRIM({column}) != ''"
    )
    for row in cur.fetchall():
        rid, text = row
        if not _has_cjk(text):
            yield rid, text


def translate_table_batch(client: LlmClient, conn, table: str, column: str,
                          batch: int = 6, workers: int = 3, max_rounds: int = 10) -> int:
    """Translate all pending rows using multi-text batches (fewer requests).

    Each batch sends several texts in one chat call; ~6x fewer requests than
    translate_table, which matters when the API rate-limits aggressively.
    """
    updated = 0
    for round_no in range(1, max_rounds + 1):
        pending = list(_iter_pending(conn, table, column))
        if not pending:
            break
        log.info("[%s.%s] 批量第 %d 轮: %d 条待翻译", table, column, round_no, len(pending))
        batches = [pending[i:i + batch] for i in range(0, len(pending), batch)]

        def _do(grp: list) -> list:
            texts = [t for _, t in grp]
            return client.batch_translate(texts)

        with ThreadPoolExecutor(max_workers=workers) as ex:
            futures = {ex.submit(_do, grp): grp for grp in batches}
            for fut in as_completed(futures):
                grp = futures[fut]
                results = fut.result()
                for (rid, _text), zh in zip(grp, results, strict=False):
                    if zh and _has_cjk(zh):
                        conn.execute(
                            f"UPDATE {table} SET {column}=? WHERE id=?", (zh, rid)
                        )
                        updated += 1
            conn.commit()
        log.info("[%s.%s] 批量第 %d 轮完成，累计 %d 条", table, column, round_no, updated)
    log.info("[%s.%s] 批量全部完成: 共翻译 %d 条", table, column, updated)
    return updated


def translate_table(client: LlmClient, conn, table: str, column: str,
                    workers: int = PARALLEL) -> int:
    """Translate all pending rows of one field concurrently, retrying
    failures (rate-limits / transient errors) for several rounds.

    SQLite writes stay on the main thread; only the HTTP calls run in the
    pool, so we never hit "database is locked".
    """
    updated = 0
    for round_no in range(1, MAX_ROUNDS + 1):
        pending = list(_iter_pending(conn, table, column))
        if not pending:
            break
        log.info("[%s.%s] 第 %d 轮: %d 条待翻译（%d 并发）",
                 table, column, round_no, len(pending), workers)

        def _do(text: str) -> str:
            try:
                return client.translate(text[:MAX_CHARS])
            except Exception as exc:  # noqa: BLE001
                log.warning("翻译调用失败: %s", exc)
                return ""

        with ThreadPoolExecutor(max_workers=workers) as ex:
            futures = {ex.submit(_do, text): (rid, text) for rid, text in pending}
            for fut in as_completed(futures):
                rid, _ = futures[fut]
                zh = fut.result()
                if zh and _has_cjk(zh):
                    conn.execute(
                        f"UPDATE {table} SET {column}=? WHERE id=?", (zh, rid)
                    )
                    updated += 1
            conn.commit()
        log.info("[%s.%s] 第 %d 轮完成，累计 %d 条", table, column, round_no, updated)
    log.info("[%s.%s] 全部完成: 共翻译 %d 条", table, column, updated)
    return updated


def translate_all_fields(db_path: str = "data/dbd_cn.db",
                         fields: list[str] | None = None) -> dict[str, int]:
    """Run the full long-text translation pass.

    fields: subset of ('perks.description','characters.lore',
    'characters.power','addons.effect','patches.notes').  None = all.
    """
    from .db import connect

    client = LlmClient()
    conn = connect(db_path)
    wanted = set(fields) if fields else None
    out: dict[str, int] = {}
    for table, column, label in JOBS:
        key = f"{table}.{column}"
        if wanted and key not in wanted:
            continue
        print(f"翻译 {label} …", flush=True)
        out[key] = translate_table(client, conn, table, column)
    conn.close()
    return out
