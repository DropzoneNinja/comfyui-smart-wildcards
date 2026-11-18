"""Wildcard file entry parsing, with a cache keyed by (path, mtime, size).

See DESIGN.md section 5.
"""

from __future__ import annotations

from pathlib import Path

_cache: dict[str, tuple[float, int, list[str]]] = {}


def read_entries(path: Path) -> list[str]:
    """Return the non-blank, stripped lines of a wildcard file, in order.

    Handles a UTF-8 BOM and both CRLF and LF line endings. Blank lines are
    dropped; duplicate lines are preserved. Cached per (path, mtime, size)
    so repeated reads of an unchanged file are free.
    """
    path = Path(path)
    stat = path.stat()
    key = str(path)
    cached = _cache.get(key)
    if cached is not None and cached[0] == stat.st_mtime and cached[1] == stat.st_size:
        return cached[2]

    raw = path.read_bytes()
    text = raw.decode("utf-8-sig")
    lines = [line.strip() for line in text.splitlines() if line.strip()]

    _cache[key] = (stat.st_mtime, stat.st_size, lines)
    return lines


def invalidate_cache(path: Path | None = None) -> None:
    """Drop cached entries for `path`, or the whole cache if `path` is None."""
    if path is None:
        _cache.clear()
    else:
        _cache.pop(str(Path(path)), None)
