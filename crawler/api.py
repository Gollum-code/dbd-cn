"""wiki.gg MediaWiki API client.

Handles the mediawiki REST endpoints used by the Dead by Daylight wiki
(https://deadbydaylight.wiki.gg), including pagination, retries and a
polite User-Agent (wiki.gg rejects requests without one).
"""

from __future__ import annotations

import logging
import threading
import time
from typing import Any

import requests

log = logging.getLogger(__name__)

WIKI_BASE = "https://deadbydaylight.wiki.gg"
API_ENDPOINT = f"{WIKI_BASE}/api.php"
USER_AGENT = (
    "dbd-cn/0.1 (+https://github.com/dbd-cn; data pipeline bot) "
    "contact=dbd-cn@example.org"
)
MAX_RETRIES = 5
BACKOFF_BASE = 2.0  # seconds
MIN_INTERVAL = 0.35  # seconds between requests (polite to wiki.gg)


class WikiApiError(RuntimeError):
    """Raised when the MediaWiki API rejects or fails a request."""


class WikiClient:
    """Small wrapper around the MediaWiki action API."""

    def __init__(self, endpoint: str = API_ENDPOINT, timeout: float = 30.0) -> None:
        self.endpoint = endpoint
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers["User-Agent"] = USER_AGENT
        self._lock = threading.Lock()
        self._last_request = 0.0

    def _throttle(self) -> None:
        """Enforce a minimum gap between requests (wiki.gg rate limits)."""
        with self._lock:
            wait = self._last_request + MIN_INTERVAL - time.monotonic()
            if wait > 0:
                time.sleep(wait)
            self._last_request = time.monotonic()

    def _request(self, params: dict[str, Any]) -> dict[str, Any]:
        """Perform a GET with retries and backoff."""
        params = dict(params)
        params.setdefault("format", "json")
        params.setdefault("formatversion", "2")
        last_err: Exception | None = None
        for attempt in range(MAX_RETRIES):
            self._throttle()
            try:
                resp = self.session.get(
                    self.endpoint, params=params, timeout=self.timeout
                )
                if resp.status_code == 429:
                    raise requests.RequestException("rate limited (429)")
                resp.raise_for_status()
                data = resp.json()
                if "error" in data:
                    raise WikiApiError(data["error"])
                return data
            except (requests.RequestException, ValueError) as exc:
                last_err = exc
                wait = BACKOFF_BASE * (2**attempt)
                log.warning("request failed (attempt %d): %s; retrying in %.1fs",
                            attempt + 1, exc, wait)
                time.sleep(wait)
        raise WikiApiError(f"request failed after {MAX_RETRIES} attempts: {last_err}")

    def query(self, **params: Any) -> dict[str, Any]:
        """Fire an action=query request, following 'continue' pagination."""
        params["action"] = "query"
        out: dict[str, Any] = {"query": {}}
        while True:
            data = self._request(params)
            q = data.get("query", {})
            out["query"].setdefault("pages", [])
            out["query"].get("pages", []).extend(q.get("pages", []))
            out["query"].setdefault("allcategories", [])
            out["query"].get("allcategories", []).extend(q.get("allcategories", []))
            cont = data.get("continue")
            if not cont:
                break
            params.update(cont)
        return out

    def page_content(self, title: str) -> str:
        """Return the current wikitext of a single page."""
        data = self._request({
            "action": "query",
            "titles": title,
            "prop": "revisions",
            "rvprop": "content",
            "rvslots": "main",
        })
        pages = data.get("query", {}).get("pages", [])
        if not pages:
            raise WikiApiError(f"page not found: {title!r}")
        page = pages[0]
        if page.get("missing"):
            raise WikiApiError(f"page not found: {title!r}")
        return page["revisions"][0]["slots"]["main"]["content"]

    def page_html(self, title: str) -> str:
        """Return the fully rendered HTML of a page, following redirects."""
        data = self._request({
            "action": "parse",
            "page": title,
            "prop": "text",
            "formatversion": "2",
            "redirects": "1",
        })
        return data["parse"]["text"]

    def category_members(self, category: str, *, namespace: int = 0) -> list[str]:
        """List page titles in a wiki category."""
        data = self.query(
            list="categorymembers",
            cmtitle=f"Category:{category}",
            cmlimit=500,
            cmnamespace=namespace,
        )
        return [p["title"] for p in data["query"].get("pages", [])]

    def all_pages_in_namespace(self, namespace: int) -> list[str]:
        """List every page title in a MediaWiki namespace."""
        data = self.query(list="allpages", apnamespace=namespace, aplimit=500)
        return [p["title"] for p in data["query"].get("pages", [])]
