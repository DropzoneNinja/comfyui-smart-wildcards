import json

import pytest

import nodes


def _state(files=None, order=None, random_enabled=False):
    return json.dumps(
        {
            "version": 1,
            "randomEnabled": random_enabled,
            "files": files or {},
            "order": order or {},
            "collapsed": [],
            "missing": [],
        }
    )


def test_execute_builds_prompt_from_enabled_files_only(tmp_path, monkeypatch):
    monkeypatch.setattr(nodes, "WILDCARD_ROOT", tmp_path)
    (tmp_path / "lighting.txt").write_text("cinematic\nharsh\n", encoding="utf-8")
    (tmp_path / "camera.txt").write_text("portrait\n", encoding="utf-8")

    state = _state(
        files={
            "lighting.txt": {"enabled": True, "mode": "auto", "entry": None},
            "camera.txt": {"enabled": False, "mode": "auto", "entry": None},
        }
    )

    result = nodes.SmartWildcards().execute(seed=1, wildcards_state=state)
    assert result["result"] == ("cinematic",)


def test_execute_disabled_files_do_not_contribute(tmp_path, monkeypatch):
    monkeypatch.setattr(nodes, "WILDCARD_ROOT", tmp_path)
    (tmp_path / "lighting.txt").write_text("cinematic\n", encoding="utf-8")

    state = _state(files={"lighting.txt": {"enabled": False, "mode": "auto", "entry": None}})
    result = nodes.SmartWildcards().execute(seed=1, wildcards_state=state)
    assert result["result"] == ("",)


def test_execute_manual_entry_wins_even_with_random_on(tmp_path, monkeypatch):
    monkeypatch.setattr(nodes, "WILDCARD_ROOT", tmp_path)
    (tmp_path / "lighting.txt").write_text("a\nb\nc\n", encoding="utf-8")

    state = _state(
        files={"lighting.txt": {"enabled": True, "mode": "entry", "entry": "b"}},
        random_enabled=True,
    )
    result = nodes.SmartWildcards().execute(seed=123, wildcards_state=state)
    assert result["result"] == ("b",)


def test_execute_respects_custom_order(tmp_path, monkeypatch):
    monkeypatch.setattr(nodes, "WILDCARD_ROOT", tmp_path)
    (tmp_path / "lighting.txt").write_text("cinematic\n", encoding="utf-8")
    (tmp_path / "camera.txt").write_text("portrait\n", encoding="utf-8")

    state = _state(
        files={
            "lighting.txt": {"enabled": True, "mode": "auto", "entry": None},
            "camera.txt": {"enabled": True, "mode": "auto", "entry": None},
        },
        order={".": ["camera.txt", "lighting.txt"]},
    )
    result = nodes.SmartWildcards().execute(seed=1, wildcards_state=state)
    assert result["result"] == ("portrait, cinematic",)


def test_execute_is_deterministic_for_same_seed(tmp_path, monkeypatch):
    monkeypatch.setattr(nodes, "WILDCARD_ROOT", tmp_path)
    (tmp_path / "lighting.txt").write_text("\n".join(f"e{i}" for i in range(20)) + "\n", encoding="utf-8")

    state = _state(files={"lighting.txt": {"enabled": True, "mode": "auto", "entry": None}}, random_enabled=True)
    node = nodes.SmartWildcards()

    first = node.execute(seed=5, wildcards_state=state)["result"]
    second = node.execute(seed=5, wildcards_state=state)["result"]
    assert first == second


def test_execute_changed_seed_can_change_result(tmp_path, monkeypatch):
    monkeypatch.setattr(nodes, "WILDCARD_ROOT", tmp_path)
    (tmp_path / "lighting.txt").write_text("\n".join(f"e{i}" for i in range(20)) + "\n", encoding="utf-8")

    state = _state(files={"lighting.txt": {"enabled": True, "mode": "auto", "entry": None}}, random_enabled=True)
    node = nodes.SmartWildcards()

    results = {node.execute(seed=s, wildcards_state=state)["result"] for s in range(10)}
    assert len(results) > 1


def test_execute_missing_file_skipped_with_warning(tmp_path, monkeypatch):
    monkeypatch.setattr(nodes, "WILDCARD_ROOT", tmp_path)
    state = _state(files={"ghost.txt": {"enabled": True, "mode": "auto", "entry": None}})

    result = nodes.SmartWildcards().execute(seed=1, wildcards_state=state)
    assert result["result"] == ("",)
    assert "ghost.txt" in result["ui"]["text"][0]


def test_execute_empty_file_contributes_nothing_without_warning(tmp_path, monkeypatch):
    monkeypatch.setattr(nodes, "WILDCARD_ROOT", tmp_path)
    (tmp_path / "blank.txt").write_text("", encoding="utf-8")
    state = _state(files={"blank.txt": {"enabled": True, "mode": "auto", "entry": None}})

    result = nodes.SmartWildcards().execute(seed=1, wildcards_state=state)
    assert result["result"] == ("",)
    assert "blank.txt" not in result["ui"]["text"][0]


def test_execute_stale_manual_entry_falls_back_with_warning(tmp_path, monkeypatch):
    monkeypatch.setattr(nodes, "WILDCARD_ROOT", tmp_path)
    (tmp_path / "lighting.txt").write_text("a\nb\n", encoding="utf-8")

    state = _state(files={"lighting.txt": {"enabled": True, "mode": "entry", "entry": "zzz"}})
    result = nodes.SmartWildcards().execute(seed=1, wildcards_state=state)

    assert result["result"] == ("a",)
    assert "lighting.txt" in result["ui"]["text"][0]


def test_execute_unknown_file_not_in_state_is_treated_as_disabled(tmp_path, monkeypatch):
    # A file that exists on disk but was never added to the saved state
    # (e.g. discovered for the first time) must not contribute, same as an
    # explicitly disabled file -- "new files are disabled by default".
    monkeypatch.setattr(nodes, "WILDCARD_ROOT", tmp_path)
    (tmp_path / "lighting.txt").write_text("cinematic\n", encoding="utf-8")

    result = nodes.SmartWildcards().execute(seed=1, wildcards_state=_state())
    assert result["result"] == ("",)
    assert "lighting.txt" not in result["ui"]["text"][0]


def test_execute_missing_file_does_not_affect_other_files_settings(tmp_path, monkeypatch):
    # A missing file's entry is looked up by relpath, so it can never be
    # confused with -- or silently reassign its settings onto -- another
    # file. See DESIGN.md section 2.3.
    monkeypatch.setattr(nodes, "WILDCARD_ROOT", tmp_path)
    (tmp_path / "camera.txt").write_text("portrait\nlandscape\n", encoding="utf-8")

    state = _state(
        files={
            "lighting.txt": {"enabled": True, "mode": "entry", "entry": "harsh"},  # missing
            "camera.txt": {"enabled": True, "mode": "entry", "entry": "landscape"},
        }
    )
    result = nodes.SmartWildcards().execute(seed=1, wildcards_state=state)

    assert result["result"] == ("landscape",)
    assert "lighting.txt" in result["ui"]["text"][0]


def test_execute_missing_root_raises(tmp_path, monkeypatch):
    monkeypatch.setattr(nodes, "WILDCARD_ROOT", tmp_path / "does_not_exist")
    with pytest.raises(RuntimeError):
        nodes.SmartWildcards().execute(seed=1, wildcards_state=_state())


def test_execute_invalid_state_json_falls_back_to_defaults(tmp_path, monkeypatch):
    monkeypatch.setattr(nodes, "WILDCARD_ROOT", tmp_path)
    (tmp_path / "lighting.txt").write_text("a\n", encoding="utf-8")

    result = nodes.SmartWildcards().execute(seed=1, wildcards_state="not json")
    assert result["result"] == ("",)


def test_execute_no_warnings_reports_contribution_count(tmp_path, monkeypatch):
    monkeypatch.setattr(nodes, "WILDCARD_ROOT", tmp_path)
    (tmp_path / "lighting.txt").write_text("a\n", encoding="utf-8")
    state = _state(files={"lighting.txt": {"enabled": True, "mode": "auto", "entry": None}})

    result = nodes.SmartWildcards().execute(seed=1, wildcards_state=state)
    assert result["ui"]["text"][0] == "1 file(s) contributed"
