"""Recursive wildcard-directory scanning. See DESIGN.md section 4."""

from __future__ import annotations

import os
import sys
from pathlib import Path

if __package__:
    from .entries import read_entries
else:
    # Imported as a bare module (e.g. under pytest, or by a ComfyUI loader
    # that doesn't treat this directory as a package) rather than as part
    # of a package -- fall back to a sibling import.
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from entries import read_entries


def scan_wildcards(root: Path) -> dict:
    """Scan `root` and return the tree structure described in DESIGN.md 2.1."""
    root = Path(root)
    errors: list[dict] = []

    if not root.is_dir():
        errors.append({"path": ".", "message": "wildcard root is missing or inaccessible"})
        return {"root": str(root), "tree": [], "errors": errors}

    root_real = root.resolve()
    tree = _scan_dir(root, root, root_real, errors)
    return {"root": str(root), "tree": tree, "errors": errors}


def flatten_files(tree: list[dict]) -> dict[str, dict]:
    """Flatten a scan_wildcards() "tree" value into {relpath: file_node}."""
    result: dict[str, dict] = {}
    for node in tree:
        if node["type"] == "file":
            result[node["path"]] = node
        else:
            result.update(flatten_files(node["children"]))
    return result


def _relpath(path: Path, root: Path) -> str:
    return path.relative_to(root).as_posix()


def _is_within(candidate_real: Path, root_real: Path) -> bool:
    try:
        candidate_real.relative_to(root_real)
        return True
    except ValueError:
        return False


def _scan_dir(current: Path, root: Path, root_real: Path, errors: list[dict]) -> list[dict]:
    try:
        children = list(os.scandir(current))
    except OSError as exc:
        errors.append({"path": _relpath(current, root), "message": str(exc)})
        return []

    children.sort(key=lambda e: e.name.lower())
    result: list[dict] = []

    for child in children:
        name = child.name
        if name.startswith("."):
            continue

        child_path = Path(child.path)

        if child.is_symlink():
            try:
                real = child_path.resolve()
            except OSError:
                continue
            if not _is_within(real, root_real):
                # Symlink escapes the wildcard root -- skip silently,
                # per DESIGN.md 4 ("not reported as an error... out of scope").
                continue

        if child.is_dir(follow_symlinks=True):
            sub = _scan_dir(child_path, root, root_real, errors)
            if sub:
                result.append({
                    "type": "dir",
                    "name": name,
                    "path": _relpath(child_path, root),
                    "children": sub,
                })
        elif child.is_file(follow_symlinks=True):
            if not name.lower().endswith(".txt"):
                continue
            result.append(_scan_file(child_path, root, errors))

    return result


def _scan_file(path: Path, root: Path, errors: list[dict]) -> dict:
    relpath = _relpath(path, root)
    base = {"type": "file", "name": path.name, "path": relpath}

    try:
        mtime = path.stat().st_mtime
    except OSError as exc:
        errors.append({"path": relpath, "message": str(exc)})
        return {**base, "entryCount": 0, "mtime": None, "status": "unreadable"}

    try:
        lines = read_entries(path)
    except OSError as exc:
        errors.append({"path": relpath, "message": str(exc)})
        return {**base, "entryCount": 0, "mtime": mtime, "status": "unreadable"}

    status = "ok" if lines else "empty"
    return {**base, "entryCount": len(lines), "mtime": mtime, "status": status}
