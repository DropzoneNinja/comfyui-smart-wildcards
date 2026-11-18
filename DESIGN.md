# DESIGN.md — Smart Wildcards ComfyUI Node

This is the technical design for the node specified in [PROJECT.md](PROJECT.md). That document is authoritative for *requirements*; this document is authoritative for *how those requirements get implemented* — concrete data shapes, algorithms, and the resolution of choices PROJECT.md §12/§14 explicitly leaves open. Read PROJECT.md first.

Sections marked **Design decision** resolve something PROJECT.md leaves ambiguous or open. They are defaults, not mandates — flag disagreement before milestone work that depends on them (tracked in [TASKS.md](TASKS.md)).

## 1. Package layout

```
smart_wildcards/
  __init__.py            # NODE_CLASS_MAPPINGS, NODE_DISPLAY_NAME_MAPPINGS, WEB_DIRECTORY
  nodes.py                # SmartWildcards node class (INPUT_TYPES, FUNCTION, execute)
  paths.py                # resolve_within_root(), filename validation/normalization
  scanner.py               # recursive directory scan -> tree structure
  entries.py               # file -> parsed entry list, with mtime/size cache
  selection.py             # seeded deterministic random selection + selection-rule resolution
  prompt.py                # final prompt assembly from resolved per-file values
  state.py                 # persisted-state JSON schema, parsing/validation, reconciliation
  api_routes.py             # aiohttp route registration against PromptServer
  web/
    smart_wildcards.js      # app.registerExtension(...), DOM widget mount
    table.js                 # table/section/row rendering, drag-and-drop
    entry_picker.js           # entry popover component
    state_sync.js              # JS-side state object <-> hidden widget JSON
    style.css
  pyproject.toml
  README.md                  # written in Milestone 8
tests/
  test_paths.py
  test_scanner.py
  test_entries.py
  test_selection.py
  test_prompt.py
  test_state_reconciliation.py
  test_api_routes.py
```

## 2. Data model

### 2.1 Directory scan response (`GET /smart_wildcards/files`)

```json
{
  "root": "/basedir/wildcards",
  "tree": [
    {"type": "dir", "name": "people", "path": "people", "children": [
      {"type": "file", "path": "people/age.txt", "name": "age.txt",
       "entryCount": 12, "mtime": 1732000000.0, "status": "ok"}
    ]},
    {"type": "file", "path": "lighting.txt", "name": "lighting.txt",
     "entryCount": 0, "mtime": 1732000000.0, "status": "empty"}
  ],
  "errors": [{"path": "clothing/colour.txt", "message": "permission denied"}]
}
```

- `tree` is alphabetical, case-insensitive at every level — this is raw discovery order. Custom order is applied client-side (§2.3).
- `status` per file: `ok | empty | unreadable`. A directory never has `status`.
- Empty directories (no files, recursively) are omitted, per PROJECT.md §4.4.
- Hidden/dotfiles and dotdirs are skipped during the walk. Symlinks are only followed if `os.path.realpath(candidate)` stays under `os.path.realpath(root)`; anything else is skipped silently (not reported as an error — it's out of scope, not a user-facing fault).

### 2.2 Entries response (`GET /smart_wildcards/entries?file=<relpath>`)

```json
{"file": "people/age.txt", "entries": ["20s", "30s", "40s"], "mtime": 1732000000.0}
```

Error shape (used by all routes on failure):

```json
{"error": {"code": "not_found" | "invalid_path" | "exists" | "invalid_name" | "io_error", "message": "..."}}
```

### 2.3 Persisted node state (the hidden widget's JSON value — this is what the workflow file stores)

```json
{
  "version": 1,
  "randomEnabled": false,
  "files": {
    "lighting.txt": {"enabled": true, "mode": "auto", "entry": null},
    "people/age.txt": {"enabled": true, "mode": "entry", "entry": "30s"}
  },
  "order": {
    ".": ["lighting.txt", "camera.txt"],
    "people": ["age.txt", "hair.txt"]
  },
  "collapsed": ["clothing"],
  "missing": ["old_file.txt"]
}
```

**Design decision — order is scoped per directory, not a single flat list.** PROJECT.md's defaults table fixes *directory* ordering as always alphabetical/case-insensitive (not user-draggable), while only *file* ordering within a section is user-defined. Modeling `order` as `{dirPath: [filenames...]}` directly matches that split and satisfies §4.4's "preserve custom order... within directory sections" without needing a UI affordance for dragging a file across sections (which the spec never asks for). Section display order itself is always recomputed as alphabetical at render time — it is never stored.

**Design decision — selection is stored by entry *text*, not index.** Indices break silently if a line is inserted/removed/reordered in the file (edited externally, per §7). Storing the exact string lets execution check "does this text still exist in the current entries" and fall back to `auto` with a notice exactly as §7 requires. The cost (ambiguity if a file has duplicate lines) is acceptable — PROJECT.md explicitly preserves duplicates and doesn't require distinguishing which occurrence was picked.

**Design decision — `missing` is a persisted list of relpaths**, not a deletion. When reconciling (see §9), any file previously known (present in `files` or `order`) that is absent from a fresh scan is added to `missing` and its row is still shown (grayed, status "missing") rather than silently dropped — this is what "mark files that no longer exist as missing rather than silently applying their settings to another file" means in practice: the *key* a setting is attached to is the relpath, so a missing file simply can't be confused with any other file. If the file reappears (e.g., a different server, or the file was restored), it is removed from `missing` and its old `files`/`order` entry is reused automatically — this is what makes cross-instance workflow opening (§7's "another ComfyUI instance") degrade gracefully.

## 3. Path & filename validation (`paths.py`)

```
resolve_within_root(root, user_relpath) -> Path:
    reject if user_relpath is empty/blank
    reject if os.path.isabs(user_relpath)
    reject if any path segment == ".." 
    candidate = (root / user_relpath).resolve()
    reject unless candidate is root or a descendant of root.resolve()
    return candidate
```

Filename normalization for **Add File** (PROJECT.md §4.2):

```
normalize_new_filename(name) -> str:
    strip whitespace; reject if empty
    reject if name contains "/" or "\" (root-level only for v1, per §4.2.7)
    reject if name == ".." or starts with "."
    if name.lower().endswith(".txt"): base = name
    else: base = name + ".txt"
    reject if base, case-sensitively re-joined, resolves outside root (defense in depth)
    return base
```

Both functions reject rather than sanitize-and-continue — an invalid request is a 400 with a structured error, never a best-effort guess at what the user meant.

## 4. Directory scanning (`scanner.py`)

- `os.scandir` recursively, building the tree bottom-up so empty directories can be pruned (a directory is kept only if it or a descendant contains at least one `.txt` file).
- Sort each directory's immediate children alphabetically, case-insensitive, directories and files interleaved per PROJECT.md's example layout (§4.4 shows files and subsection headers both appearing at a level — sort key is just the name, dirs are visually distinguished by the frontend, not by sort order).
- Symlink handling: resolve and compare against the root's realpath per entry; a symlink pointing outside is skipped (not listed, not reported as an error, consistent with "ignore... unless explicitly required").
- Per-file `status` is `unreadable` if the file can't be opened (permission, I/O error) — scanning tolerates this and reports it in `errors`/`status` rather than aborting the whole scan, per §6's "one unreadable file should not cause the entire UI to become unusable."
- Result caching: an in-memory cache keyed by `root` realpath, invalidated on every `refresh` call and on every successful file creation. Not invalidated by a bare `GET /files` poll — the frontend controls when a rescan happens (PROJECT.md §9: "Scan on node initialisation... do not [poll] on every minor UI interaction").

## 5. Entry parsing (`entries.py`)

```
read_entries(path) -> list[str]:
    raw = path.read_bytes()
    text = raw.decode("utf-8-sig")   # transparently strips BOM if present
    lines = text.splitlines()         # handles CRLF and LF uniformly
    return [line.strip() for line in lines if line.strip()]
```

Cached per `(path, mtime, size)` so repeated picker opens on an unchanged file don't re-read/re-parse; a change in either invalidates that file's cache entry (PROJECT.md §9's "cache them with a sensible refresh strategy").

## 6. Deterministic seeded random selection (`selection.py`)

**Design decision — each file's random pick is independently sub-seeded, with no shared RNG sequence.**

```
pick_random_entry(seed: int, relpath: str, entries: list[str]) -> str:
    digest = hashlib.sha256(f"{seed}:{relpath}".encode("utf-8")).digest()
    sub_seed = int.from_bytes(digest[:8], "big")
    rng = random.Random(sub_seed)
    return entries[rng.randrange(len(entries))]
```

Using `hashlib` (not Python's built-in `hash()`, which is salted per-process by `PYTHONHASHSEED` unless disabled) guarantees the same `(seed, relpath, entries)` triple always yields the same pick, across processes and ComfyUI restarts. Keying each file's RNG independently off `(seed, relpath)` — rather than one shared `random.Random(seed)` consumed file-by-file — means the result for any one file never depends on how many *other* enabled files there are, their iteration order, or dict ordering. That removes an entire class of "reordering an unrelated row changed my selection" bugs.

Selection-rule resolution per file (PROJECT.md §4.6 table), applied uniformly whether the trigger is UI preview or execution:

```
resolve(file_state, random_enabled, entries, seed, relpath) -> str | None:
    if entries is empty: return None
    if file_state.mode == "entry" and file_state.entry in entries: return file_state.entry
    # mode == "auto", or a stale manual entry that no longer exists
    if random_enabled: return pick_random_entry(seed, relpath, entries)
    return entries[0]
```

## 7. Prompt assembly (`prompt.py`)

1. Compute display order: sections alphabetical (root first, by convention), files within each section per persisted `order[section]`, with any file not yet present in that list appended at the end (new/undragged files), per PROJECT.md §4.4.
2. For each file in that order: skip if disabled, skip if missing, skip if its resolved value (§6) is `None` (empty file).
3. Trim each resolved value's leading/trailing whitespace; join with `", "`.
4. Collect a parallel list of warnings (missing files that are enabled, unreadable files, stale-entry resets) for the status/preview surface.

## 8. Backend API (`api_routes.py`)

| Route | Method | Params | Success | Failure |
|---|---|---|---|---|
| `/smart_wildcards/files` | GET | — | tree (§2.1) | 500 io_error |
| `/smart_wildcards/entries` | GET | `file` (relpath) | entries (§2.2) | 400 invalid_path, 404 not_found, 500 io_error |
| `/smart_wildcards/files` | POST | `{"name": str}` | `{"path": "<relpath>"}` | 400 invalid_name/invalid_path, 409 exists, 500 io_error |
| `/smart_wildcards/refresh` | POST | — | tree (§2.1), bypasses scan cache | 500 io_error |

All routes resolve paths through `paths.resolve_within_root` before touching the filesystem — no route ever takes a server-absolute path from the client. Errors always return the structured `{"error": {...}}` shape with an HTTP status matching the error class, never a bare 500 with a stack trace.

## 9. Frontend architecture

- **Mount point:** `app.registerExtension` with `beforeRegisterNodeDef`/`nodeCreated` hooks on the SmartWildcards node type, adding a single DOM widget (ComfyUI's `addDOMWidget`) that owns the whole table UI. This needs to be confirmed against the installed ComfyUI frontend version per PROJECT.md §3/§14 — if `addDOMWidget` isn't available in the target version, fall back to the older canvas-widget approach and note that explicitly as a compatibility finding in Milestone 1.
- **Components:** `Header` (Add File button + inline name input, Random toggle, Refresh icon, seed display if not a separate graph input), `SectionHeader` (collapse caret + label), `FileRow` (drag handle, enabled checkbox, name, selected-entry button, status badge), `EntryPicker` (popover: search box for large files, scrollable list, "Automatic / Default" pinned at top, first real entry visually marked).
- **State:** one JS object mirroring §2.3's schema, held in the node's closure. Every mutation (toggle, drag, selection, collapse) synchronously writes the serialized JSON into the hidden widget's `value` so ComfyUI's existing workflow-serialization path persists it with no extra plumbing.
- **Drag-and-drop:** native HTML5 DnD, constrained to reordering within one section's row list (consistent with §2.3's per-section `order`); dropping is disabled across section boundaries.
- **Fetching:** file tree fetched on node creation and after Add File / manual Refresh, not on every render. Entries fetched lazily when a picker opens, cached client-side keyed by `(relpath, mtime)` from the last fetch; a picker reopened with a known-unchanged mtime (from the tree response) skips the network call.
- **Loading/error states:** a lightweight inline status line in the header area ("Loading files…", "N files — last scan failed: …") rather than a modal, so a backend hiccup never blocks the rest of the UI.

## 10. Workflow persistence & reconciliation (`state.py`)

- **Seed:** a standard ComfyUI `INT` widget (becomes a node input socket like any seed, so it can be wired from a shared seed elsewhere in the graph). No `control_after_generate` behavior is added for v1 — out of scope, the spec only requires the seed to be capable of changing the result, not of auto-incrementing.
- **On node `configure()` (workflow load):** parse the hidden widget's saved JSON (version-checked — unknown/missing `version` is treated as "no prior state", not an error) and reconcile it against a fresh scan:
  1. For every file in the fresh scan: if it's a known relpath (in saved `files`), keep its saved `enabled`/`mode`/`entry`; else it's new — default `enabled: false, mode: "auto", entry: null`, appended to the end of its section's `order` list.
  2. For every relpath in saved `files`/`order` that is *not* in the fresh scan: move it to `missing` (§2.3), keep its settings, don't delete them.
  3. For every file whose `mode == "entry"`: if its saved `entry` string is not present in a fresh read of that file's entries, reset to `mode: "auto", entry: null` and queue a non-blocking UI notice ("`people/age.txt`: selected entry no longer found, reset to Automatic").
  4. Collapsed-section state carries over unchanged (it's keyed by directory path, same reasoning as file settings).
- **Execution-time:** the Python `execute()` function re-runs step against a fresh scan every time (not the state captured at UI-render time), satisfying §4.2's "recompute the selection during every node execution."

## 11. Error/status taxonomy

| Condition | Row status | Execution behavior |
|---|---|---|
| File has ≥1 entry, readable | `ok` | Contributes per selection rules |
| File exists, zero non-blank lines | `empty` | Skipped, no warning (expected state) |
| File unreadable (permission/I/O) | `unreadable: <message>` | Skipped, warning emitted |
| File enabled but now missing | `missing` | Skipped, warning emitted |
| Saved manual entry no longer in file | (resets to `auto` first) | Contributes per `auto` rule, notice emitted |
| Wildcard root itself missing/inaccessible | node-level error banner | Execution raises a clear error (no silent empty output) — this is the one case treated as a hard failure, since it means the feature is fundamentally unavailable, not just one file |

The "useful execution preview/status" from PROJECT.md §5 is implemented as text returned via the node's `ui` return value (ComfyUI's standard mechanism for a node to show auxiliary text under itself) listing current warnings — **not** a second graph output socket, to keep the node's output interface to the single `prompt` STRING the spec requires.

## 12. Testing strategy

- **Backend (pytest), fully exercised without a running ComfyUI instance:** path validation (traversal, absolute paths, symlink escape, extension enforcement), scanner (nested dirs, empty-dir pruning, hidden files, symlink-outside-root), entry parsing (BOM, CRLF/LF, blank lines, duplicates), selection-rule table (all four combinations from §4.6), determinism (same seed+contents ⇒ same output across repeated calls; changed seed ⇒ different output), prompt assembly edge cases (all disabled, all empty, mixed missing), and state reconciliation (new/missing/stale-entry cases from §10).
- **API routes:** integration tests against the aiohttp routes directly (can be done with `aiohttp.test_utils` without a full ComfyUI server boot), covering each documented success/failure case in §8's table.
- **Frontend:** no JS unit-test harness is added for v1 — this is a deliberate scope decision given the project's size; the table/drag-and-drop/picker behavior is verified manually against PROJECT.md §11's acceptance criteria in a real ComfyUI instance (tracked as its own milestone in TASKS.md). Revisit if the frontend grows significantly past v1.

## 13. Packaging

- `__init__.py` exposes `NODE_CLASS_MAPPINGS`, `NODE_DISPLAY_NAME_MAPPINGS`, and `WEB_DIRECTORY = "web"` per standard custom-node conventions.
- No third-party Python dependencies are expected (stdlib `os`, `pathlib`, `hashlib`, `random`, `json`, `aiohttp` which ComfyUI already depends on) — `pyproject.toml`/`requirements.txt` should stay empty/minimal; add a dependency only if Milestone 1's inspection of the installed ComfyUI version turns up a reason to.
- Wildcard root stays `/basedir/wildcards` by default, matching PROJECT.md exactly. An optional, explicitly-documented env var override (e.g. `SMART_WILDCARDS_ROOT`) may be added as a stretch item — it does not violate "do not silently substitute a different wildcard directory" as long as the default is unchanged and any override is logged/surfaced in the UI, but it is **not required** by the spec and should not block v1.

## 14. Open items carried from PROJECT.md §12/§14

These are explicitly left to implementer judgment by the spec; this document's defaults (nested-directory flattening threshold not yet fixed, per-section drag-and-drop, text-based entry reference) are reasonable starting points but should be revisited once real wildcard trees (depth, file counts) are seen in Milestone 1's inspection:

- Exact presentation for deeply nested directories (indented hierarchy vs. flattened relative-path labels) — start with indented hierarchy, flatten only if a concrete tree makes it unreadable.
- Whether "Refresh" should also be auto-triggered on node focus/visibility — start with manual-only, per §9's "do not poll."
- Whether to add the optional env var root override from §13 — stretch, not required.
