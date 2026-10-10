"""Parse Lua data tables embedded in wiki.gg module wikitext.

The wiki stores its structured data as Lua table literals inside
Module:Datatable and Module:Datatable/Loadout.  This module extracts
those literals and converts them into plain Python objects.

Only the subset of Lua used in these files is supported:
  * table constructors:  { ["key"] = value, [1] = value, key = value }
  * nested tables, strings ('' and ""), numbers, booleans
  * comments (-- and --[[ ]]--) are stripped before parsing
"""

from __future__ import annotations

import re
import logging
from typing import Any

log = logging.getLogger(__name__)

# A single Lua value: table, number, string, boolean, nil, or an identifier
# that (in data files) means true-ish or a previously defined constant.
_LUA_VALUE = re.compile(
    r"""
    \{                  # table constructor
    | \[.+?\]\s*=\s*\[  # keyed table with bracket-string key
    | -?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?   # number
    | ["']              # string quote
    | true|false|nil    # literal
    | [A-Za-z_][A-Za-z0-9_.]*   # identifier / constant ref
    """,
    re.VERBOSE,
)


unescape_map = {
    "\\": "\\",
    '"': '"',
    "'": "'",
    "n": "\n",
    "t": "\t",
    "r": "\r",
}


def strip_lua_comments(text: str) -> str:
    """Remove -- line comments and --[[ block ]] comments."""
    text = re.sub(r"--\[(=*)\[.*?\]\1\]", "", text, flags=re.DOTALL)
    text = re.sub(r"--[^\n]*", "", text)
    return text


def unquote(s: str) -> str:
    """Unescape a Lua string literal (without quotes)."""
    return (
        s.replace(r"\\", "\x00")
        .replace(r"\"", '"')
        .replace(r"\'", "'")
        .replace(r"\n", "\n")
        .replace(r"\t", "\t")
        .replace("\x00", "\\")
    )


class LuaParser:
    """Recursive-descent parser for Lua table literals."""

    def __init__(self, text: str) -> None:
        self.text = strip_lua_comments(text)
        self.pos = 0

    def parse(self) -> Any:
        self._skip_ws()
        if self._peek() == "{":
            return self._table()
        return self._value()

    # -- internals ----------------------------------------------------

    def _peek(self) -> str:
        return self.text[self.pos] if self.pos < len(self.text) else ""

    def _skip_ws(self) -> None:
        while self.pos < len(self.text) and self.text[self.pos].isspace():
            self.pos += 1

    def _table(self) -> dict[Any, Any]:
        assert self._peek() == "{"
        self.pos += 1
        out: dict[Any, Any] = {}
        index = 1
        while True:
            self._skip_ws()
            ch = self._peek()
            if ch == "}":
                self.pos += 1
                break
            if ch == "," or ch == ";":
                self.pos += 1
                continue
            key = None
            if self.text.startswith("[", self.pos):
                key = self._bracket_key()
            else:
                # bare identifier key
                m = re.match(r"[A-Za-z_][A-Za-z0-9_]*", self.text[self.pos:])
                if m and self.text[self.pos + m.end() :].lstrip().startswith("="):
                    key = m.group(0)
                    self.pos += m.end()
            self._skip_ws()
            if self._peek() == "=":
                self.pos += 1
            else:
                # sequential entry
                out[index] = self._value()
                index += 1
                continue
            value = self._value()
            if key is None:
                key = index
                index += 1
            out[key] = value
        return _compact_list(out) if _is_array(out) else out

    def _bracket_key(self) -> Any:
        assert self._peek() == "["
        self.pos += 1
        self._skip_ws()
        if self._peek() in ('"', "'"):
            val = self._string()
        else:
            num = re.match(r"-?\d+(?:\.\d+)?", self.text[self.pos:])
            if not num:
                raise ValueError(f"bad bracket key at pos {self.pos}")
            val = float(num.group(0))
            val = int(val) if val.is_integer() else val
            self.pos += num.end()
        self._skip_ws()
        assert self._peek() == "]"
        self.pos += 1
        return val

    def _value(self) -> Any:
        self._skip_ws()
        ch = self._peek()
        if ch == "{":
            return self._table()
        if ch in ('"', "'"):
            return self._string_concat()
        m = re.match(r"-?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?", self.text[self.pos:])
        if m:
            val = float(m.group(0))
            self.pos += m.end()
            return int(val) if val.is_integer() else val
        m = re.match(r"true|false|nil|[A-Za-z_][A-Za-z0-9_.]*", self.text[self.pos:])
        if m:
            word = m.group(0)
            self.pos += m.end()
            return {"true": True, "false": False, "nil": None}.get(word, word)
        raise ValueError(f"unexpected char {ch!r} at pos {self.pos}")

    def _string_concat(self) -> str:
        """Parse a string, joining operands joined by Lua's `..` operator."""
        parts: list[str] = []
        while True:
            self._skip_ws()
            if self._peek() in ('"', "'"):
                parts.append(self._string())
            else:
                m = re.match(r"[A-Za-z_][A-Za-z0-9_]*", self.text[self.pos:])
                if m:
                    # bare identifier (e.g. a local const like `br`): skip it
                    self.pos += m.end()
                else:
                    return "".join(parts)
            self._skip_ws()
            if not (self.text.startswith("..", self.pos)):
                break
            self.pos += 2
        return "".join(parts)

    def _string(self) -> str:
        quote = self._peek()
        self.pos += 1
        parts: list[str] = []
        while self.pos < len(self.text):
            ch = self.text[self.pos]
            if ch == "\\":
                esc = self.text[self.pos + 1 : self.pos + 2]
                parts.append(unescape_map.get(esc, esc))
                self.pos += 2
                continue
            if ch == quote:
                self.pos += 1
                return "".join(parts)
            parts.append(ch)
            self.pos += 1
        raise ValueError("unterminated string")


def _is_array(d: dict[Any, Any]) -> bool:
    """True when dict keys are contiguous positive ints 1..n."""
    if not d:
        return False
    return all(isinstance(k, int) and k >= 1 for k in d) and sorted(d) == list(range(1, len(d) + 1))


def _compact_list(d: dict[Any, Any]) -> list[Any]:
    return [d[i] for i in range(1, len(d) + 1)]


def parse_lua_value(text: str) -> Any:
    return LuaParser(text).parse()


def extract_table(
    source: str, name: str, *, kind: str = "p"
) -> dict[Any, Any] | None:
    """Extract a top-level Lua table from module source.

    Supports ``p.<name> = {...}`` (kind="p") and ``<name> = {...}`` (kind="bare").
    Returns None when the table is absent.
    """
    prefix = rf"\bp\.{re.escape(name)}" if kind == "p" else rf"\b{re.escape(name)}"
    m = re.search(prefix + r"\s*=\s*(?=\{)", source, flags=re.DOTALL)
    if m:
        try:
            return parse_lua_value(source[m.end() :])
        except ValueError:
            log.warning("failed to parse table %r", name)
            return None
    return None
