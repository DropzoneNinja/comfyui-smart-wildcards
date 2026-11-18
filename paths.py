"""Path and filename validation for the wildcard root.

Every function here is defense against a hostile or malformed relative path
coming from the frontend. See DESIGN.md section 3.
"""

from __future__ import annotations

import os
from pathlib import Path


class InvalidPathError(ValueError):
    """Raised when a user-supplied path/filename fails validation."""


def resolve_within_root(root: Path, user_relpath: str) -> Path:
    """Resolve `user_relpath` against `root`, raising if it escapes root.

    Rejects empty input, absolute paths, and any ".." segment before ever
    touching the filesystem, then re-checks the resolved real path against
    root's real path to also catch symlink escapes.
    """
    if not user_relpath or not user_relpath.strip():
        raise InvalidPathError("path must not be empty")

    if os.path.isabs(user_relpath):
        raise InvalidPathError("absolute paths are not allowed")

    parts = Path(user_relpath).parts
    if any(part == ".." for part in parts):
        raise InvalidPathError("path traversal is not allowed")

    root_real = root.resolve()
    candidate_real = (root / user_relpath).resolve()

    try:
        candidate_real.relative_to(root_real)
    except ValueError:
        raise InvalidPathError("path escapes the wildcard root") from None

    return candidate_real


def normalize_new_filename(name: str) -> str:
    """Normalize a user-supplied filename for file creation.

    Appends ".txt" if missing, never doubles it, and rejects anything that
    is not a plain root-level filename (no separators, no traversal).
    """
    if name is None:
        raise InvalidPathError("filename must not be empty")

    candidate = name.strip()
    if not candidate:
        raise InvalidPathError("filename must not be empty")

    if "/" in candidate or "\\" in candidate:
        raise InvalidPathError("filename must not contain a path separator")

    if candidate in (".", ".."):
        raise InvalidPathError("filename must not be '.' or '..'")

    if candidate.startswith("."):
        raise InvalidPathError("filename must not start with '.'")

    if candidate.lower().endswith(".txt"):
        base = candidate
    else:
        base = candidate + ".txt"

    if base.lower() == ".txt":
        raise InvalidPathError("filename must not be empty")

    return base


def create_wildcard_file(root: Path, name: str) -> Path:
    """Create a new empty UTF-8 wildcard file at the root, never overwriting.

    Returns the resolved path of the created file. Raises InvalidPathError
    if the name is invalid or resolves outside root, and FileExistsError if
    the file already exists.
    """
    filename = normalize_new_filename(name)
    target = resolve_within_root(root, filename)

    if target.exists():
        raise FileExistsError(f"{filename} already exists")

    target.parent.mkdir(parents=True, exist_ok=True)
    # "x" mode atomically fails with FileExistsError on a TOCTOU race
    # instead of silently overwriting a file created between the check above
    # and this call.
    with open(target, "x", encoding="utf-8"):
        pass

    return target
