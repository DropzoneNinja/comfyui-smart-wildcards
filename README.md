# Smart Wildcards

A ComfyUI custom node providing a table-based UI for selecting and combining wildcard text files into a single prompt string, as an alternative to typing wildcard references by hand.

- Discovers `.txt` wildcard files under a fixed root, `/basedir/wildcards`, including in subdirectories (shown as collapsible sections).
- Each file can be enabled/disabled, dragged into a custom order within its section, and set to a specific entry or left on "Automatic".
- A global Random toggle, combined with a seed input, deterministically randomizes any file still set to Automatic at execution time — a manually chosen entry always wins over randomization.
- New files can be created from the node itself ("+ Add File"); they're added disabled so they never silently change an existing prompt.
- All of this is persisted in the workflow JSON, so it survives save/reload.

See [PROJECT.md](PROJECT.md) for the full behavioral specification and [DESIGN.md](DESIGN.md) for the technical design (data shapes, algorithms, and the decisions made to resolve things the spec leaves open). [TASKS.md](TASKS.md) tracks implementation progress milestone by milestone, including exactly what has and hasn't been verified against a real ComfyUI instance.

## Installation

### Docker

1. Mount your wildcards directory into the container at `/basedir/wildcards`, readable and writable by the ComfyUI process (it needs to create new `.txt` files there). This path is fixed, not configurable — the node deliberately never substitutes a different directory if this one is missing.
2. Clone this repository into `custom_nodes/` inside your ComfyUI installation:
   ```
   git clone https://github.com/DropzoneNinja/comfyui-smart-wildcards custom_nodes/comfyui-smart-wildcards
   ```
3. Restart ComfyUI. No ComfyUI core files are modified by this install.

### Manual / non-Docker

Same as above, minus the container step — just make sure `/basedir/wildcards` exists on the machine running ComfyUI and is readable/writable by that process. There's no setting to point it elsewhere; see "Known limitations" below if you need a different path for local testing.

## Usage

Add the **Smart Wildcards** node (category `utils/wildcards`). Its table lists every `.txt` file found under the wildcard root:

- **Enabled checkbox** — whether this file contributes to the output prompt.
- **Drag handle** — reorder files within their section; this order becomes the prompt's word order. Section order itself (and a new file's initial position) is always alphabetical; only the order *within* a section is user-defined.
- **Selected-entry button** — opens a popover listing the file's non-empty lines in order, with a search box for long files and an "Automatic / Default" option pinned at the top. Automatic means: use the first entry when Random is off, or a seeded random entry when Random is on.
- **Status** — entry count, `empty`, or `error` (with the reason in a tooltip) for a file ComfyUI couldn't read.

Header controls:
- **+ Add File** — creates a new root-level `.txt` file (appends `.txt` if you didn't type it; rejects anything that isn't a plain filename). It appears in the table disabled, ready for you to populate externally in a text editor.
- **Random** — global toggle. A file left on Automatic is randomly selected when this is on; a file with a specific entry chosen is never affected by it.
- **⟳ Refresh** — re-scans the wildcard root without discarding your current enabled/order/selection state. Use after editing files outside ComfyUI, or after adding/removing files directly on disk.

The node also exposes a standard **seed** input. Random selection is resolved fresh on every execution from `(seed, file path, file contents)` — the same seed and file contents always produce the same picks; changing the seed can produce a different combination.

Connect the node's `prompt` output (a `STRING`) to any normal text/prompt input downstream.

## How state is stored in the workflow

Everything except the `seed` widget is stored as JSON in a second widget, `wildcards_state`, which the frontend hides but which still serializes with the workflow like any other widget value:

```json
{
  "version": 1,
  "randomEnabled": false,
  "files": {
    "lighting.txt": {"enabled": true, "mode": "auto", "entry": null},
    "people/age.txt": {"enabled": true, "mode": "entry", "entry": "30s"}
  },
  "order": {".": ["lighting.txt", "camera.txt"], "people": ["age.txt", "hair.txt"]},
  "collapsed": ["clothing"],
  "missing": []
}
```

- `files` is keyed by the file's path relative to the wildcard root, so a setting can never be silently reassigned to a different file.
- `order` is per-directory (`"."` for the root): directory/section order is always alphabetical and not user-orderable, so only each section's own file order needs to be stored.
- A manually selected `entry` is stored as its literal text, not an index or line number, so it survives lines being added/removed elsewhere in the file; if that exact text no longer exists the next time the file is read, the file resets to `"mode": "auto"` and a brief notice is shown.
- Files that were previously configured but no longer exist under the wildcard root are listed in `missing` and shown as a separate, grayed-out section in the table — their settings are kept, not discarded, and are reapplied automatically if the file reappears (including, for example, when the same workflow is reopened against a different server whose wildcard directory happens to contain it again).

## Known limitations

- **No automated browser/UI testing.** The frontend (`web/*.js`) was verified by code review, by a one-off Node script exercising the pure state-reconciliation logic, and by confirming it loads and serves correctly from a real ComfyUI instance — but no actual clicking, dragging, or popover interaction was driven through a real browser during development. Click through the table yourself before relying on it for anything important, especially drag-and-drop reordering and the entry picker's popover positioning.
- **Opening a saved workflow on a different server reconciles against that server's files.** If the wildcard directory's contents differ from where the workflow was saved, files missing on the new server show up in the "missing" section (settings preserved, nothing silently reassigned); files new to this server appear disabled at the end of their section. This is inherent to the file list being server-side, not a bug.
- **The wildcard root is not configurable.** `/basedir/wildcards` is fixed in `nodes.py`'s `WILDCARD_ROOT` constant, deliberately, so the node never silently substitutes a different directory. Changing it for local development means editing that constant.
- **The actual Docker bind-mount path was not independently verified** during development — testing here used a local, non-Docker ComfyUI desktop install (v0.46.0) since no Docker environment was available. Confirm `/basedir/wildcards` is correctly mounted and permissioned in your real deployment.
- **No license has been chosen yet** for this repository.

## Troubleshooting

| Symptom | Likely cause |
|---|---|
| Table shows "Wildcard root unavailable: …" | `/basedir/wildcards` is missing or unreadable by the ComfyUI process — check the mount/permissions. |
| Node execution fails with "wildcard root is missing or inaccessible" | Same as above; this is a deliberate hard failure (not a silently empty prompt) so you notice. |
| A row's entry picker says "No entries in this file" | The file exists but has no non-blank lines yet — populate it in a text editor. |
| A row appears grayed out under "Missing files" | It was previously configured but no longer exists under the wildcard root; its settings are kept and will be reused automatically if the file comes back. |
| "+ Add File" rejects a name | Filenames must be a plain, root-level name ending in `.txt` (it's appended for you if omitted) — no `/`, no `..`, no overwriting an existing file. |
| A manual entry selection quietly reverted to "Automatic" | That exact line no longer exists in the file (edited externally) — a brief notice explains which file. |

## Development

```
python3 -m venv .venv
.venv/bin/pip install -r requirements-dev.txt
.venv/bin/python -m pytest -q
```

See [TASKS.md](TASKS.md) for exactly what's been verified where (unit tests vs. live-instance checks vs. acknowledged gaps), and [DESIGN.md](DESIGN.md) for the algorithms and data shapes behind all of the above.
