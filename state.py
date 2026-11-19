"""Persisted node-state JSON parsing and defaults. See DESIGN.md section 2.3."""

from __future__ import annotations

import json

DEFAULT_STATE = {
    "version": 1,
    "randomEnabled": False,
    "files": {},
    "order": {},
    "collapsed": [],
    "missing": [],
}

DEFAULT_STATE_JSON = json.dumps(DEFAULT_STATE)


def parse_state(raw: str) -> dict:
    """Parse the saved state JSON.

    Tolerates missing/invalid data entirely -- treated as "no prior
    state" rather than an error, per DESIGN.md section 10 ("unknown/
    missing version is treated as no prior state, not an error").
    """
    try:
        data = json.loads(raw) if raw else {}
    except (TypeError, ValueError):
        data = {}

    if not isinstance(data, dict):
        data = {}

    return {
        "randomEnabled": bool(data.get("randomEnabled", False)),
        "files": data.get("files") if isinstance(data.get("files"), dict) else {},
        "order": data.get("order") if isinstance(data.get("order"), dict) else {},
        "collapsed": data.get("collapsed") if isinstance(data.get("collapsed"), list) else [],
        "missing": data.get("missing") if isinstance(data.get("missing"), list) else [],
    }


def serialize_state(state: dict) -> str:
    return json.dumps(
        {
            "version": 1,
            "randomEnabled": bool(state.get("randomEnabled", False)),
            "files": state.get("files", {}),
            "order": state.get("order", {}),
            "collapsed": state.get("collapsed", []),
            "missing": state.get("missing", []),
        }
    )
