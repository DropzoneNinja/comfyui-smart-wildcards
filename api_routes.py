"""Custom API routes for the frontend. See DESIGN.md section 8.

`register_routes` is a plain function so it can be exercised directly in
tests against a bare aiohttp app, independent of a running ComfyUI/
PromptServer instance -- see tests/test_api_routes.py.
"""

from __future__ import annotations

import sys
from pathlib import Path

from aiohttp import web

if __package__:
    from .entries import invalidate_cache as invalidate_entry_cache
    from .entries import read_entries
    from .paths import InvalidPathError, create_wildcard_file, resolve_within_root
    from .scanner import scan_wildcards
else:
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from entries import invalidate_cache as invalidate_entry_cache
    from entries import read_entries
    from paths import InvalidPathError, create_wildcard_file, resolve_within_root
    from scanner import scan_wildcards

_tree_cache: dict[str, dict] = {}


def _error(code: str, message: str, status: int) -> web.Response:
    return web.json_response({"error": {"code": code, "message": message}}, status=status)


def _get_tree(root: Path, *, bypass_cache: bool) -> dict:
    key = str(root)
    if bypass_cache or key not in _tree_cache:
        _tree_cache[key] = scan_wildcards(root)
    return _tree_cache[key]


def invalidate_tree_cache(root: Path) -> None:
    _tree_cache.pop(str(root), None)


def register_routes(routes: web.RouteTableDef, root: Path) -> None:
    """Register the smart_wildcards routes on `routes`.

    `routes` is any aiohttp RouteTableDef -- in production this is
    `PromptServer.instance.routes`; in tests it's a fresh one added to a
    throwaway `web.Application()`.
    """

    @routes.get("/smart_wildcards/files")
    async def get_files(request: web.Request) -> web.Response:
        try:
            tree = _get_tree(root, bypass_cache=False)
        except OSError as exc:
            return _error("io_error", str(exc), 500)
        return web.json_response(tree)

    @routes.get("/smart_wildcards/entries")
    async def get_entries(request: web.Request) -> web.Response:
        file_param = request.query.get("file")
        if not file_param:
            return _error("invalid_path", "missing 'file' query parameter", 400)

        try:
            resolved = resolve_within_root(root, file_param)
        except InvalidPathError as exc:
            return _error("invalid_path", str(exc), 400)

        if not resolved.is_file():
            return _error("not_found", f"{file_param} does not exist", 404)

        try:
            lines = read_entries(resolved)
            mtime = resolved.stat().st_mtime
        except OSError as exc:
            return _error("io_error", str(exc), 500)

        return web.json_response({"file": file_param, "entries": lines, "mtime": mtime})

    @routes.post("/smart_wildcards/files")
    async def post_create_file(request: web.Request) -> web.Response:
        try:
            body = await request.json()
        except Exception:
            return _error("invalid_name", "request body must be JSON", 400)

        name = body.get("name") if isinstance(body, dict) else None
        if not isinstance(name, str):
            return _error("invalid_name", "'name' must be a string", 400)

        try:
            created = create_wildcard_file(root, name)
        except InvalidPathError as exc:
            return _error("invalid_name", str(exc), 400)
        except FileExistsError as exc:
            return _error("exists", str(exc), 409)
        except OSError as exc:
            return _error("io_error", str(exc), 500)

        invalidate_tree_cache(root)
        relpath = created.relative_to(root.resolve()).as_posix()
        return web.json_response({"path": relpath})

    @routes.post("/smart_wildcards/refresh")
    async def post_refresh(request: web.Request) -> web.Response:
        invalidate_entry_cache()
        try:
            tree = _get_tree(root, bypass_cache=True)
        except OSError as exc:
            return _error("io_error", str(exc), 500)
        return web.json_response(tree)
