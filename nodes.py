"""SmartWildcards ComfyUI node registration.

Milestone 1 scope only: a minimal node with the required STRING output and
a placeholder execute(). Real discovery/selection/prompt-assembly wiring
lands in later milestones -- see TASKS.md and DESIGN.md sections 6-7.
"""

from __future__ import annotations

from pathlib import Path

WILDCARD_ROOT = Path("/basedir/wildcards")


class SmartWildcards:
    CATEGORY = "utils/wildcards"
    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("prompt",)
    FUNCTION = "execute"

    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {}}

    def execute(self):
        return ("",)


NODE_CLASS_MAPPINGS = {
    "SmartWildcards": SmartWildcards,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "SmartWildcards": "Smart Wildcards",
}
