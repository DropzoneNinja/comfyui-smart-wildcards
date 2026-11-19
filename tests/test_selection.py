from selection import pick_random_entry, resolve_selection


class TestPickRandomEntry:
    def test_deterministic_for_same_seed(self):
        entries = ["a", "b", "c", "d"]
        first = pick_random_entry(42, "lighting.txt", entries)
        second = pick_random_entry(42, "lighting.txt", entries)
        assert first == second
        assert first in entries

    def test_changes_across_seeds(self):
        entries = [f"entry{i}" for i in range(20)]
        results = {pick_random_entry(seed, "lighting.txt", entries) for seed in range(10)}
        assert len(results) > 1

    def test_differs_by_relpath_for_same_seed(self):
        entries = [f"entry{i}" for i in range(20)]
        results = {pick_random_entry(7, f"file{i}.txt", entries) for i in range(10)}
        assert len(results) > 1

    def test_independent_of_unrelated_state(self):
        # Calling it repeatedly for the same (seed, relpath, entries) must
        # always agree -- nothing external (other files, call order) may
        # influence a single file's pick. See DESIGN.md section 6.
        entries = ["a", "b", "c"]
        results = {pick_random_entry(7, "lighting.txt", entries) for _ in range(20)}
        assert len(results) == 1


class TestResolveSelection:
    def test_empty_entries_returns_none(self):
        assert resolve_selection({"mode": "auto"}, False, [], 1, "f.txt") is None

    def test_random_off_auto_uses_first_entry(self):
        assert resolve_selection({"mode": "auto"}, False, ["x", "y"], 1, "f.txt") == "x"

    def test_random_off_specific_uses_specific_entry(self):
        result = resolve_selection({"mode": "entry", "entry": "y"}, False, ["x", "y"], 1, "f.txt")
        assert result == "y"

    def test_random_on_auto_uses_random_entry(self):
        entries = ["x", "y", "z"]
        result = resolve_selection({"mode": "auto"}, True, entries, 1, "f.txt")
        assert result in entries

    def test_random_on_specific_uses_specific_entry_unchanged(self):
        result = resolve_selection({"mode": "entry", "entry": "y"}, True, ["x", "y"], 1, "f.txt")
        assert result == "y"

    def test_stale_specific_entry_falls_back_to_auto_rule_random_off(self):
        result = resolve_selection({"mode": "entry", "entry": "missing"}, False, ["x", "y"], 1, "f.txt")
        assert result == "x"

    def test_stale_specific_entry_falls_back_to_auto_rule_random_on(self):
        entries = ["x", "y"]
        result = resolve_selection({"mode": "entry", "entry": "missing"}, True, entries, 1, "f.txt")
        assert result in entries

    def test_determinism_same_seed_same_result(self):
        entries = [f"e{i}" for i in range(15)]
        a = resolve_selection({"mode": "auto"}, True, entries, 99, "f.txt")
        b = resolve_selection({"mode": "auto"}, True, entries, 99, "f.txt")
        assert a == b

    def test_changed_seed_can_change_result(self):
        entries = [f"e{i}" for i in range(15)]
        results = {resolve_selection({"mode": "auto"}, True, entries, seed, "f.txt") for seed in range(10)}
        assert len(results) > 1
