from pathlib import Path

import pytest
from aiohttp import web

import api_routes
import entries


@pytest.fixture(autouse=True)
def _clear_caches():
    api_routes._tree_cache.clear()
    entries.invalidate_cache()
    yield
    api_routes._tree_cache.clear()
    entries.invalidate_cache()


@pytest.fixture
def app_factory(tmp_path):
    def make_app(root: Path = tmp_path):
        routes = web.RouteTableDef()
        api_routes.register_routes(routes, root)
        app = web.Application()
        app.add_routes(routes)
        return app

    return make_app


async def test_get_files_empty_root(aiohttp_client, app_factory, tmp_path):
    client = await aiohttp_client(app_factory(tmp_path))
    resp = await client.get("/smart_wildcards/files")
    assert resp.status == 200
    body = await resp.json()
    assert body["tree"] == []
    assert body["errors"] == []


async def test_get_files_lists_created_file(aiohttp_client, app_factory, tmp_path):
    (tmp_path / "lighting.txt").write_text("a\nb\n", encoding="utf-8")
    client = await aiohttp_client(app_factory(tmp_path))
    resp = await client.get("/smart_wildcards/files")
    body = await resp.json()
    assert body["tree"][0]["name"] == "lighting.txt"
    assert body["tree"][0]["entryCount"] == 2


async def test_get_files_missing_root_is_io_error(aiohttp_client, app_factory, tmp_path):
    missing = tmp_path / "does_not_exist"
    client = await aiohttp_client(app_factory(missing))
    resp = await client.get("/smart_wildcards/files")
    # scan_wildcards tolerates a missing root (empty tree + errors list),
    # not an HTTP-level failure -- confirm that behavior end-to-end.
    assert resp.status == 200
    body = await resp.json()
    assert body["tree"] == []
    assert body["errors"]


async def test_get_entries_happy_path(aiohttp_client, app_factory, tmp_path):
    (tmp_path / "lighting.txt").write_text("cinematic\nsoft\n", encoding="utf-8")
    client = await aiohttp_client(app_factory(tmp_path))
    resp = await client.get("/smart_wildcards/entries", params={"file": "lighting.txt"})
    assert resp.status == 200
    body = await resp.json()
    assert body["entries"] == ["cinematic", "soft"]
    assert body["file"] == "lighting.txt"


async def test_get_entries_missing_query_param(aiohttp_client, app_factory):
    client = await aiohttp_client(app_factory())
    resp = await client.get("/smart_wildcards/entries")
    assert resp.status == 400
    body = await resp.json()
    assert body["error"]["code"] == "invalid_path"


async def test_get_entries_traversal_rejected(aiohttp_client, app_factory):
    client = await aiohttp_client(app_factory())
    resp = await client.get("/smart_wildcards/entries", params={"file": "../outside.txt"})
    assert resp.status == 400
    body = await resp.json()
    assert body["error"]["code"] == "invalid_path"


async def test_get_entries_absolute_path_rejected(aiohttp_client, app_factory):
    client = await aiohttp_client(app_factory())
    resp = await client.get("/smart_wildcards/entries", params={"file": "/etc/passwd"})
    assert resp.status == 400
    body = await resp.json()
    assert body["error"]["code"] == "invalid_path"


async def test_get_entries_not_found(aiohttp_client, app_factory, tmp_path):
    client = await aiohttp_client(app_factory(tmp_path))
    resp = await client.get("/smart_wildcards/entries", params={"file": "missing.txt"})
    assert resp.status == 404
    body = await resp.json()
    assert body["error"]["code"] == "not_found"


async def test_post_create_file_bare_name_appends_txt(aiohttp_client, app_factory, tmp_path):
    client = await aiohttp_client(app_factory(tmp_path))
    resp = await client.post("/smart_wildcards/files", json={"name": "lighting"})
    assert resp.status == 200
    body = await resp.json()
    assert body["path"] == "lighting.txt"
    assert (tmp_path / "lighting.txt").exists()


async def test_post_create_file_does_not_double_append_txt(aiohttp_client, app_factory, tmp_path):
    client = await aiohttp_client(app_factory(tmp_path))
    resp = await client.post("/smart_wildcards/files", json={"name": "lighting.txt"})
    body = await resp.json()
    assert body["path"] == "lighting.txt"


async def test_post_create_file_rejects_existing(aiohttp_client, app_factory, tmp_path):
    (tmp_path / "lighting.txt").write_text("keep me", encoding="utf-8")
    client = await aiohttp_client(app_factory(tmp_path))
    resp = await client.post("/smart_wildcards/files", json={"name": "lighting"})
    assert resp.status == 409
    body = await resp.json()
    assert body["error"]["code"] == "exists"
    assert (tmp_path / "lighting.txt").read_text(encoding="utf-8") == "keep me"


async def test_post_create_file_rejects_traversal(aiohttp_client, app_factory, tmp_path):
    client = await aiohttp_client(app_factory(tmp_path))
    resp = await client.post("/smart_wildcards/files", json={"name": "../escape.txt"})
    assert resp.status == 400
    body = await resp.json()
    assert body["error"]["code"] == "invalid_name"


async def test_post_create_file_rejects_missing_name(aiohttp_client, app_factory, tmp_path):
    client = await aiohttp_client(app_factory(tmp_path))
    resp = await client.post("/smart_wildcards/files", json={})
    assert resp.status == 400
    body = await resp.json()
    assert body["error"]["code"] == "invalid_name"


async def test_post_create_file_rejects_non_json_body(aiohttp_client, app_factory, tmp_path):
    client = await aiohttp_client(app_factory(tmp_path))
    resp = await client.post("/smart_wildcards/files", data="not json")
    assert resp.status == 400
    body = await resp.json()
    assert body["error"]["code"] == "invalid_name"


async def test_get_files_is_cached_until_refresh(aiohttp_client, app_factory, tmp_path):
    client = await aiohttp_client(app_factory(tmp_path))

    resp = await client.get("/smart_wildcards/files")
    assert (await resp.json())["tree"] == []

    # Created on disk directly (bypassing the API), so the cached GET
    # /files response should still be stale...
    (tmp_path / "lighting.txt").write_text("a\n", encoding="utf-8")
    resp = await client.get("/smart_wildcards/files")
    assert (await resp.json())["tree"] == []

    # ...until an explicit refresh.
    resp = await client.post("/smart_wildcards/refresh")
    body = await resp.json()
    assert body["tree"][0]["name"] == "lighting.txt"

    resp = await client.get("/smart_wildcards/files")
    assert (await resp.json())["tree"][0]["name"] == "lighting.txt"


async def test_create_file_invalidates_tree_cache(aiohttp_client, app_factory, tmp_path):
    client = await aiohttp_client(app_factory(tmp_path))

    resp = await client.get("/smart_wildcards/files")
    assert (await resp.json())["tree"] == []

    await client.post("/smart_wildcards/files", json={"name": "lighting"})

    resp = await client.get("/smart_wildcards/files")
    body = await resp.json()
    assert body["tree"][0]["name"] == "lighting.txt"
