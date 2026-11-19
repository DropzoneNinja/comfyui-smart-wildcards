"""Seeded deterministic random selection and selection-rule resolution.

See DESIGN.md section 6 and PROJECT.md section 4.6's precedence table.
"""

from __future__ import annotations

import hashlib
import random


def pick_random_entry(seed: int, relpath: str, entries: list[str]) -> str:
    """Deterministically pick an entry for one file.

    Each file is sub-seeded independently from `(seed, relpath)` via
    hashlib (not Python's salted built-in hash()), so a given file's pick
    never depends on any other file's state or on iteration order.
    """
    digest = hashlib.sha256(f"{seed}:{relpath}".encode("utf-8")).digest()
    sub_seed = int.from_bytes(digest[:8], "big")
    rng = random.Random(sub_seed)
    return entries[rng.randrange(len(entries))]


def resolve_selection(
    file_state: dict,
    random_enabled: bool,
    entries: list[str],
    seed: int,
    relpath: str,
) -> str | None:
    """Resolve one enabled file's contributed value, or None if it has no entries.

    A manually selected entry (mode "entry") always wins, even when
    random_enabled is True and even if that exact value happens to be
    present. A stale manual entry (no longer in `entries`) is treated the
    same as "auto".
    """
    if not entries:
        return None

    if file_state.get("mode") == "entry":
        entry = file_state.get("entry")
        if entry in entries:
            return entry

    if random_enabled:
        return pick_random_entry(seed, relpath, entries)

    return entries[0]
