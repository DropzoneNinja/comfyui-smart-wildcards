"""SmartWildcards ComfyUI node registration and execution.

See DESIGN.md sections 6-7 for the selection/prompt-assembly design and
section 11 for the error/status taxonomy implemented in execute() below.
"""

from __future__ import annotations

import sys
from pathlib import Path

if __package__:
    from .entries import read_entries
    from .prompt import assemble_prompt, compute_order
    from .scanner import flatten_files, scan_wildcards
    from .selection import resolve_selection
    from .state import DEFAULT_STATE_JSON, parse_state
else:
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from entries import read_entries
    from prompt import assemble_prompt, compute_order
    from scanner import flatten_files, scan_wildcards
    from selection import resolve_selection
    from state import DEFAULT_STATE_JSON, parse_state

WILDCARD_ROOT = Path("/basedir/wildcards")


class SmartWildcards:
    CATEGORY = "utils/wildcards"
    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("prompt",)
    FUNCTION = "execute"
    # Lets the node show a text preview of its own status (DESIGN.md 11)
    # even though its real output is a normal, connectable STRING socket.
    OUTPUT_NODE = True

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "seed": ("INT", {"default": 0, "min": 0, "max": 0xFFFFFFFFFFFFFFFF}),
                "wildcards_state": ("STRING", {"default": DEFAULT_STATE_JSON, "multiline": True}),
            }
        }

    def execute(self, seed: int, wildcards_state: str):
        state = parse_state(wildcards_state)

        scan = scan_wildcards(WILDCARD_ROOT)
        if any(err["path"] == "." for err in scan["errors"]):
            raise RuntimeError(f"wildcard root is missing or inaccessible: {WILDCARD_ROOT}")

        files_by_path = flatten_files(scan["tree"])
        order = compute_order(scan["tree"], state["order"])

        parts: list[str] = []
        warnings: list[str] = []

        # `order` only contains relpaths that exist in the live scan -- any
        # enabled file the saved state refers to that no longer exists on
        # disk has to be caught separately.
        for relpath, fstate in state["files"].items():
            if fstate.get("enabled") and relpath not in files_by_path:
                warnings.append(f"{relpath}: file is missing, skipped")

        for relpath in order:
            fstate = state["files"].get(relpath)
            if not fstate or not fstate.get("enabled"):
                continue

            file_info = files_by_path[relpath]
            if file_info["status"] == "unreadable":
                warnings.append(f"{relpath}: unreadable, skipped")
                continue

            try:
                file_entries = read_entries(WILDCARD_ROOT / relpath)
            except OSError:
                warnings.append(f"{relpath}: unreadable, skipped")
                continue

            if fstate.get("mode") == "entry" and fstate.get("entry") not in file_entries:
                warnings.append(f"{relpath}: selected entry no longer found, used Automatic")

            value = resolve_selection(fstate, state["randomEnabled"], file_entries, seed, relpath)
            if value is not None:
                parts.append(value)

        prompt = assemble_prompt(parts)
        status_text = "; ".join(warnings) if warnings else f"{len(parts)} file(s) contributed"
        return {"ui": {"text": (status_text,)}, "result": (prompt,)}


NODE_CLASS_MAPPINGS = {
    "SmartWildcards": SmartWildcards,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "SmartWildcards": "Smart Wildcards",
}
