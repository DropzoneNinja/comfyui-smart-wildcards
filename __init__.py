import sys

from .nodes import NODE_CLASS_MAPPINGS, NODE_DISPLAY_NAME_MAPPINGS, WILDCARD_ROOT

WEB_DIRECTORY = "web"

# "server" is only present in sys.modules when we're actually being loaded
# by a running ComfyUI process (main.py imports/instantiates PromptServer
# before loading custom nodes). This keeps the package importable -- e.g.
# by pytest, which imports this __init__.py as part of collecting tests/
# since this directory has to be a real package for ComfyUI's loader.
if "server" in sys.modules:
    from server import PromptServer

    from .api_routes import register_routes

    register_routes(PromptServer.instance.routes, WILDCARD_ROOT)

__all__ = ["NODE_CLASS_MAPPINGS", "NODE_DISPLAY_NAME_MAPPINGS", "WEB_DIRECTORY"]
