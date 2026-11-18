# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Current state

This repository is currently **empty of implementation code**. It contains only [PROJECT.md](PROJECT.md), the full specification for a ComfyUI custom node called **Smart Wildcards**. There is no git history, no README, no build tooling, and no test suite yet — all of that needs to be created as part of implementing the spec.

Because there's no code yet, there are no build/lint/test commands to list. Once a Python package and frontend extension exist, update this file with the actual commands (e.g. how to install the node into a ComfyUI instance, run Python tests, lint the JS, etc.) rather than leaving this section placeholder-only.

## Read PROJECT.md, DESIGN.md, and TASKS.md before implementing anything

- [PROJECT.md](PROJECT.md) is the authoritative spec — read it completely before writing code. It is long and detailed; the summary below only orients you to the shape of the system and the easy-to-miss invariants. It does not substitute for the full document, which also contains exact column layouts, API route suggestions, default values, and acceptance criteria.
- [DESIGN.md](DESIGN.md) resolves PROJECT.md's open implementation choices into concrete data shapes and algorithms (persisted-state JSON schema, path validation, scan/parse algorithms, seeded random selection, reconciliation logic). Treat its "Design decision" call-outs as the defaults to implement unless the user says otherwise.
- [TASKS.md](TASKS.md) is the progress tracker, grouped by the milestones in PROJECT.md §13 and cross-referenced to PROJECT.md §11's acceptance criteria. Keep it current as work proceeds — check items off, don't let it drift from actual progress.

## What is being built

A ComfyUI custom node providing a table-based UI to select/combine entries from wildcard `.txt` files under `/basedir/wildcards`, producing one combined prompt string (`STRING` output). Key architectural split mandated by the spec:

- **Python backend is authoritative** for filesystem access (scanning, reading entries, creating files, generating the final prompt). It must be a standard ComfyUI custom-node package (Python node + registration) — do not modify ComfyUI core files.
- **JS frontend extension** renders the interactive table and talks to the backend **only through custom API routes** the extension registers (e.g. `GET /smart_wildcards/files`, `GET /smart_wildcards/entries?file=...`, `POST /smart_wildcards/files`, `POST /smart_wildcards/refresh` — illustrative, not fixed names). The frontend must never assume direct filesystem access.
- Before writing code, inspect the actually-installed ComfyUI version and its current custom-node/frontend-extension conventions rather than assuming an API shape.

## Invariants that are easy to get wrong

These are called out repeatedly in the spec because naive implementations tend to violate them:

- **Random vs. manual precedence**: a manually selected entry always wins over random mode, file by file. Random mode only fills in files still set to `auto`. See the precedence table in PROJECT.md §4.6.
- **Random selection is seeded and resolved server-side at execution time**, not in the frontend and not frozen at UI-render time. Same seed + same file contents ⇒ same selection; a changed seed ⇒ a new deterministic combination; re-executing must re-resolve randomness.
- **New files (created via "Add File" or newly discovered on disk) are disabled by default** and must not alter an existing generated prompt until explicitly enabled.
- **Directories are section dividers only** — never selectable wildcards themselves. They support collapse/expand without affecting child rows' enabled/selected state.
- **User-defined drag-and-drop row order is authoritative once set**; alphabetical, case-insensitive order is only the *initial* order for files not yet positioned. Refreshes/rescans must not reset custom order; newly discovered files append to the end of their section.
- **Path safety**: all user-supplied filenames/paths must be resolved and validated against `/basedir/wildcards` server-side — reject absolute paths, `../` traversal, symlinks escaping the root, and non-`.txt` extensions. Never let the frontend pass arbitrary server paths. Never overwrite an existing file on create.
- **Reconciliation on refresh**: when files change on disk, preserve saved state for files that still exist, mark missing files as missing (never silently reassign their settings to another file), and reset a selection to `auto` with a non-blocking notice if its specific entry no longer exists.
- **Workflow persistence**: random enabled/disabled, per-file enabled/disabled, per-file selection mode (`auto` vs specific entry), the seed/seed-input config, custom row order, and (if practical) section collapse state must all round-trip through ComfyUI workflow save/reload — don't rely on transient browser state.
- **Parsing**: UTF-8, strip BOM, handle both CRLF and LF, one non-empty line = one entry, blank lines ignored, duplicates preserved (they affect random weighting intentionally).
- **Prompt output**: one entry per enabled file, in table/custom order, joined with `, `, skipping disabled/empty files, no filenames or extra punctuation added, each entry trimmed but internal whitespace preserved.
- Scope discipline: this is not a general file manager — only the narrowly defined wildcard list/read/create/refresh operations in PROJECT.md §8 should be exposed via the API.

## Confirmed decisions vs. open implementation choices

PROJECT.md §12 lists product decisions that are already confirmed and must not be re-litigated (disabled-by-default new files, seeded random, no in-node text editor, drag-and-drop ordering persisted, random resolved in the Python execution function). Everything else not explicitly pinned down (nested-directory presentation depth, exact refresh triggers, exact error-skip behavior per file) is intentionally left to implementer judgment — see the end of §12 and §14 for the explicit list of what's open.
