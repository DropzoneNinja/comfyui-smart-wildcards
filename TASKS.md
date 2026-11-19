# TASKS.md — Smart Wildcards implementation tracker

Tracks implementation progress against [PROJECT.md](PROJECT.md) (requirements) and [DESIGN.md](DESIGN.md) (how they're implemented). Check items off as completed; each milestone maps to PROJECT.md §13. Where useful, items reference the specific acceptance criterion (AC#) from PROJECT.md §11 they satisfy.

Milestones 1 and 2 are implemented at the repo root (not nested under a `smart_wildcards/` subfolder as DESIGN.md §1 literally draws it) — this repo IS the ComfyUI custom-node package, matching the standard convention where `ComfyUI/custom_nodes/<this-repo>/__init__.py` must sit directly at the clone root.

## Milestone 1 — Inspect & scaffold

- [x] Create package skeleton at repo root ([__init__.py](__init__.py), [nodes.py](nodes.py), [paths.py](paths.py), [scanner.py](scanner.py), [entries.py](entries.py), [web/](web/), [tests/](tests/))
- [x] Add `__init__.py` with `NODE_CLASS_MAPPINGS` / `NODE_DISPLAY_NAME_MAPPINGS` / `WEB_DIRECTORY` stub
- [x] Register a minimal `SmartWildcards` node (category, `STRING` output named `prompt`, placeholder execute) — satisfies AC1
- [x] Smoke-tested: package imports cleanly both as a ComfyUI-style package import (via `importlib.util.spec_from_file_location`, matching how ComfyUI's loader imports a custom-node directory) and as bare pytest modules — see `scanner.py`'s dual import fallback
Verified 2026-11-19 against the local instance at `/Volumes/Data/ComfyUI/ComfyUI/ComfyUI` (ComfyUI v0.46.0, `comfyui-frontend-package` 1.59.6, Python 3.13.12, desktop/standalone build):

- [x] Inspected the installed ComfyUI version and confirmed `NODE_CLASS_MAPPINGS` + `WEB_DIRECTORY` are still the conventions checked first by `load_custom_node` in `nodes.py` (a newer `comfy_entrypoint`/`ComfyExtension`/`io.Schema` API also exists and is now used by the shipped `example_node.py.example` template, but only as an `elif` fallback when `NODE_CLASS_MAPPINGS` is absent — our approach is correct and not legacy-only)
- [x] Confirmed `addDOMWidget` exists in the bundled frontend JS (`comfyui_frontend_package`'s `core-*.js`/`app-*.js`) — no fallback needed for Milestone 4
- [x] Confirmed the exact `PromptServer.instance.routes` aiohttp registration pattern from the shipped `custom_nodes/example_node.py.example` (`from server import PromptServer; @PromptServer.instance.routes.get(...)`) — matches DESIGN.md §8 as written
- [x] Symlinked this repo into `custom_nodes/comfyui-smart-wildcards` and ran `python main.py --quick-test-for-ci --cpu` (full custom-node load path, no GPU/model init) — our module appears in the "Import times for custom nodes" log with no error and no `IMPORT FAILED` entry; process exits 0
- [x] Started the real server (`python main.py --cpu --listen 127.0.0.1 --port 8198`) and queried `GET /object_info/SmartWildcards` directly — confirmed it's registered exactly as intended: `"display_name": "Smart Wildcards"`, `"category": "utils/wildcards"`, single `STRING` output named `"prompt"`. Server stopped afterward.
- [ ] **Still open — out of scope for this local (non-Docker) instance:** confirming the actual Docker deployment's bind-mount path for `/basedir/wildcards`. Needs checking against the real Docker deployment when available.

## Milestone 2 — Backend discovery

- [x] Implement `paths.resolve_within_root` and `normalize_new_filename` (DESIGN.md §3) — [paths.py](paths.py)
- [x] Implement file creation: validation, no-overwrite, UTF-8 write, `.txt`-only — `create_wildcard_file` in [paths.py](paths.py), satisfies AC5, AC6, AC7
- [x] Implement `scanner.py` recursive tree scan: nesting, metadata, empty-dir pruning, hidden-file/dotdir skip, symlink-outside-root skip (DESIGN.md §4) — satisfies AC2, AC3
- [x] Implement `entries.py` parsing with BOM strip, CRLF/LF handling, blank-line skip, duplicate preservation, mtime/size cache (DESIGN.md §5) — satisfies AC8, AC15
- [x] Unit tests: path validation — traversal, absolute paths, symlink escape, extension enforcement ([tests/test_paths.py](tests/test_paths.py), 20 cases)
- [x] Unit tests: scanner — nested dirs, empty-dir omission, hidden files, symlink escape ([tests/test_scanner.py](tests/test_scanner.py), 15 cases)
- [x] Unit tests: entry parser — BOM, CRLF vs LF, blank lines, duplicate lines preserved ([tests/test_entries.py](tests/test_entries.py), 11 cases)
- [x] Full suite passes: `50 passed` (run with a local `.venv`; see below)

Running the tests locally:

```
python3 -m venv .venv
.venv/bin/pip install pytest
.venv/bin/python -m pytest -q
```

## Milestone 3 — Backend API routes

- [x] `GET /smart_wildcards/files` (DESIGN.md §8, §2.1) — [api_routes.py](api_routes.py)
- [x] `GET /smart_wildcards/entries?file=<relpath>` (DESIGN.md §8, §2.2)
- [x] `POST /smart_wildcards/files` create (DESIGN.md §8)
- [x] `POST /smart_wildcards/refresh` — bypasses the in-memory tree cache and invalidates the entry-parse cache (DESIGN.md §4, §8)
- [x] Structured JSON error responses with correct HTTP status for every failure case in DESIGN.md §8's table
- [x] Integration tests covering each route's success and failure cases ([tests/test_api_routes.py](tests/test_api_routes.py), 16 cases, via `aiohttp.test_utils`/`pytest-aiohttp` against a bare `web.Application()` — no PromptServer needed)
- [x] `register_routes` wired into [__init__.py](__init__.py) against the real `PromptServer.instance.routes`, gated on `"server" in sys.modules` so the package stays importable outside ComfyUI (needed because pytest's own package-collection semantics require importing `__init__.py` — see commit history)
- [x] Verified live against the local ComfyUI instance: all four routes respond with the correct status/body for both success and error cases (traversal, missing query param, missing root handled as a 200 with an `errors` entry rather than a 500, per DESIGN.md's error taxonomy)

Dev dependencies for the test suite are listed in [requirements-dev.txt](requirements-dev.txt) (`pip install -r requirements-dev.txt` into `.venv`).

## Milestone 4 — Frontend table shell

Implemented in [web/smart_wildcards.js](web/smart_wildcards.js) (extension registration, header controls, fetch/load) and [web/table.js](web/table.js) (tree rendering). State lives **in-memory only** on the node instance for now (`node._smartWildcards.state`) — it is not yet written to a serialized widget, so it does not survive a workflow save/reload. That persistence wiring (the hidden state widget + Python-side parsing) is explicitly Milestone 6/7's job, not pulled forward here.

- [x] Register JS extension + mount DOM widget on the node (DESIGN.md §9) — confirmed `addDOMWidget`, `beforeRegisterNodeDef`, `nodeCreated`/`onNodeCreated` all exist in the installed frontend bundle (`comfyui_frontend_package` 1.59.6)
- [x] Fetch and render file tree (sections + rows) on node creation
- [x] Collapsible section headers with expand/collapse state, arbitrary nesting depth (indented hierarchy per DESIGN.md §14's default) — satisfies AC3
- [x] Per-file enabled toggle, left-aligned per row — satisfies AC4, AC14
- [x] Drag handle + within-section drag-and-drop reordering (native HTML5 DnD, constrained to same `dirPath`, DESIGN.md §9) — satisfies AC19
- [x] Add File header control: inline input, calls create API, refreshes table, new row disabled by default (relies on the backend's validation/error messages rather than duplicating the rules client-side) — satisfies AC5, AC6, AC7, AC22
- [x] Random toggle control (UI state only — nothing consumes it server-side yet; that's Milestone 6)
- [x] Manual Refresh action (calls `POST /refresh`, re-renders without resetting `state.order`/`state.collapsed`/`state.files`)
- [x] Loading state and inline error surface (header status text) for file-list fetch failures

## Milestone 5 — Entry selection

Implemented in [web/entry_picker.js](web/entry_picker.js).

- [x] Entry picker popover: fetch on open via `GET /entries`, client-side cache by `(relpath, mtime)`, search box, scrollable list, viewport-aware positioning (DESIGN.md §9)
- [x] Visual distinction of the first/default entry in the picker (bold)
- [x] "Automatic / Default" option pinned at the top that clears a manual override — satisfies AC10
- [x] Selected-entry display in the row, truncated via CSS ellipsis with full value in the `title` tooltip; an `auto` row additionally previews the resolved first entry once entries have been fetched at least once
- [x] Reconciliation notice when a saved manual entry no longer exists in the freshly-fetched entries (reset to Automatic + a non-blocking banner) — exercised every time the picker opens, which is the same code path Milestone 7 will reuse at workflow-load time
- [x] Satisfies AC8, AC9

**Frontend verification performed:** all four JS files pass `node --check` (ES module syntax), and — against the real local ComfyUI instance — `GET /extensions` lists all three top-level modules under `/extensions/comfyui-smart-wildcards/...`, and fetching `smart_wildcards.js`/`style.css` returns 200 with byte-identical content to the source and correct content types. **Not verified:** actual in-browser rendering, click/drag interaction, and visual appearance — this session has no browser automation tool available, so the DOM/event-wiring logic was verified by careful code review and static checks only, not by driving a real browser. Worth an actual click-through in ComfyUI's UI before relying on this for real use.

## Milestone 6 — Prompt execution (Python)

- [ ] Hidden state widget (`serialize: true`) holding the JSON schema from DESIGN.md §2.3; frontend state writes sync to it on every mutation
- [ ] Seed `INT` widget/input on the node
- [ ] `selection.py`: per-file seeded deterministic random pick (hashlib sub-seed, DESIGN.md §6) — satisfies AC12, AC17, AC18
- [ ] `selection.py`: selection-rule resolution for all four auto/manual × random-on/off combinations — satisfies AC11, AC13
- [ ] `prompt.py`: ordered assembly, comma-space join, skip disabled/empty/missing, trim — satisfies AC16
- [ ] Execution-time per-file error handling: skip missing/unreadable files with a warning rather than failing the whole node — satisfies AC21
- [ ] Execution status/preview text (warnings list) surfaced via the node's `ui` return value, not a second output socket (DESIGN.md §11)
- [ ] Unit tests: full selection-rule table
- [ ] Unit tests: determinism (same seed+contents → same output repeatedly; changed seed → different output)
- [ ] Unit tests: prompt assembly edge cases (all disabled, all empty, mixed missing)

## Milestone 7 — Persistence, reconciliation & validation

- [ ] Node `configure()` handler: parse saved JSON state on workflow load, reconcile against a fresh scan per DESIGN.md §10
- [ ] Unit tests: state reconciliation (new file appears disabled at end of section; removed file → `missing`, settings preserved, not reassigned; stale manual entry → reset to auto + notice)
- [ ] Manual test: full save → reload round-trip preserves Random mode, seed, per-file enabled, per-file selection, custom order, collapse state — satisfies AC20
- [ ] Manual test: delete a wildcard file on disk, refresh, confirm it's marked missing and other files' settings are untouched
- [ ] Manual test: add a file on disk outside the UI, refresh, confirm it appears disabled at the end of its section without disturbing existing order
- [ ] Manual penetration test: path traversal and symlink-escape attempts against all four API routes
- [ ] Manual test: open the same saved workflow against a server with a different `/basedir/wildcards` contents; confirm graceful reconciliation (document the result as the "cross-instance" limitation)
- [ ] Satisfies AC21, AC23

## Milestone 8 — Documentation & packaging

- [ ] `README.md`: installation (Docker + manual), usage walkthrough, troubleshooting, the cross-instance limitation
- [ ] `pyproject.toml` / manifest metadata suitable for the target ComfyUI custom-node manager, if applicable
- [ ] Document the workflow JSON state format (DESIGN.md §2.3) for future debugging
- [ ] Walk every item in PROJECT.md §11 (AC1–AC24) explicitly and confirm pass/fail
- [ ] Confirm no ComfyUI core files were modified — satisfies AC24
- [ ] Record any known limitations or decisions still needing user input

## Stretch / explicitly deferred (not required for v1)

- [ ] Optional `SMART_WILDCARDS_ROOT` env var override, documented, default unchanged (DESIGN.md §13)
- [ ] JS unit-test harness for the frontend table/picker (DESIGN.md §12 — deferred, revisit only if frontend complexity grows)
- [ ] Flattened-path presentation for very deep directory nesting, if an indented hierarchy proves unreadable in practice (DESIGN.md §14)
