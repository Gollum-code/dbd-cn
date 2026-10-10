"""dbd-cn crawler package: wiki.gg -> 中文 SQLite."""

from .api import WikiClient, WikiApiError
from .db import connect
from .pipeline import build

__all__ = ["WikiClient", "WikiApiError", "connect", "build"]
__version__ = "0.1.0"
