"""Final display order and prompt-string assembly. See DESIGN.md section 7.

compute_order mirrors web/table.js's rendering order exactly (sections
alphabetical, files within a section per the saved order with unlisted
files appended alphabetically) so the prompt's file order always matches
what the user sees in the table.
"""

from __future__ import annotations


def _apply_order(names: list[str], order_list: list[str]) -> list[str]:
    known = [n for n in order_list if n in names]
    rest = sorted((n for n in names if n not in order_list), key=str.lower)
    return known + rest


def compute_order(tree: list[dict], order_state: dict[str, list[str]]) -> list[str]:
    """Flatten `tree` (scanner.scan_wildcards()'s "tree" value) into the
    final ordered list of file relpaths for prompt assembly."""
    result: list[str] = []
    _walk(tree, ".", order_state, result)
    return result


def _walk(children: list[dict], dir_path: str, order_state: dict, result: list[str]) -> None:
    files = [c for c in children if c["type"] == "file"]
    dirs = sorted((c for c in children if c["type"] == "dir"), key=lambda d: d["name"].lower())

    names = [f["name"] for f in files]
    order = _apply_order(names, order_state.get(dir_path, []))
    by_name = {f["name"]: f for f in files}
    for name in order:
        result.append(by_name[name]["path"])

    for d in dirs:
        _walk(d["children"], d["path"], order_state, result)


def assemble_prompt(parts: list[str]) -> str:
    """Join resolved per-file values into the final prompt string."""
    return ", ".join(p.strip() for p in parts if p and p.strip())
