# TASKS.md — Smart Wildcards implementation tracker

Tracks implementation progress against [PROJECT.md](PROJECT.md) (requirements) and [DESIGN.md](DESIGN.md) (how they're implemented). Check items off as completed; each milestone maps to PROJECT.md §13. Where useful, items reference the specific acceptance criterion (AC#) from PROJECT.md §11 they satisfy.

Milestones 1 and 2 are implemented at the repo root (not nested under a `smart_wildcards/` subfolder as DESIGN.md §1 literally draws it) — this repo IS the ComfyUI custom-node package, matching the standard convention where `ComfyUI/custom_nodes/<this-repo>/__init__.py` must sit directly at the clone root.

## Milestone 1 — Inspect & scaffold

- [x] Create package skeleton at repo root ([__init__.py](__init__.py), [nodes.py](nodes.py), [paths.py](paths.py), [scanner.py](scanner.py), [entries.py](entries.py), [web/](web/), [tests/](tests/))
- [x] Add `__init__.py` with `NODE_CLASS_MAPPINGS` / `NODE_DISPLAY_NAME_MAPPINGS` / `WEB_DIRECTORY` stub
- [x] Register a minimal `SmartWildcards` node (category, `STRING` output named `prompt`, placeholder execute) — satisfies AC1
- [x] Smoke-tested: package imports cleanly both as a ComfyUI-style package import (via `importlib.util.spec_from_file_location`, matching how ComfyUI's loader imports a custom-node directory) and as bare pytest modules — see `scanner.py`'s dual import fallback
- [ ] **Not independently verifiable in this environment — no ComfyUI installation was found on this machine (checked `which comfyui`, filesystem search).** The following still need checking against a real, running ComfyUI instance before relying on them:
  - Inspect the actual installed ComfyUI version and confirm `NODE_CLASS_MAPPINGS`/`WEB_DIRECTORY` conventions haven't changed
  - Confirm `addDOMWidget` is available in the installed frontend (DESIGN.md §9); note fallback if not
  - Confirm the `PromptServer.instance.routes` aiohttp registration pattern for the installed version (needed for Milestone 3)
  - Confirm the Docker deployment's actual mount point for `/basedir/wildcards`
  - Confirm the node loads with no errors and appears in a sensible node-menu category inside a running ComfyUI

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

- [ ] `GET /smart_wildcards/files` (DESIGN.md §8, §2.1)
- [ ] `GET /smart_wildcards/entries?file=<relpath>` (DESIGN.md §8, §2.2)
- [ ] `POST /smart_wildcards/files` create (DESIGN.md §8)
- [ ] `POST /smart_wildcards/refresh` — bypasses scan cache (DESIGN.md §4, §8)
- [ ] Structured JSON error responses with correct HTTP status for every failure case in DESIGN.md §8's table
- [ ] Integration tests covering each route's success and failure cases

## Milestone 4 — Frontend table shell

- [ ] Register JS extension + mount DOM widget on the node (DESIGN.md §9)
- [ ] Fetch and render file tree (sections + rows) on node creation
- [ ] Collapsible section headers with expand/collapse state — satisfies AC3
- [ ] Per-file enabled toggle, left-aligned per row — satisfies AC4, AC14
- [ ] Drag handle + within-section drag-and-drop reordering (DESIGN.md §9) — satisfies AC19
- [ ] Add File header control: inline input, client-side validation mirroring backend rules, calls create API, refreshes table, new row disabled by default — satisfies AC5, AC6, AC7, AC22
- [ ] Random toggle control
- [ ] Manual Refresh action that reconciles without discarding existing state
- [ ] Loading state and inline error surface for file-list fetch failures

## Milestone 5 — Entry selection

- [ ] Entry picker popover: fetch on open, client-side cache by `(relpath, mtime)`, search/scroll for large files (DESIGN.md §9)
- [ ] Visual distinction of the first/default entry in the picker
- [ ] "Automatic / Default" option that clears a manual override — satisfies AC10
- [ ] Selected-entry display in the row, truncated with full value on hover
- [ ] Reconciliation notice when a saved manual entry no longer exists in the file (reset to Automatic + non-blocking notice, DESIGN.md §10)
- [ ] Satisfies AC8, AC9

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
