from prompt import assemble_prompt, compute_order


class TestAssemblePrompt:
    def test_joins_with_comma_space(self):
        assert assemble_prompt(["a", "b", "c"]) == "a, b, c"

    def test_skips_none_and_empty(self):
        assert assemble_prompt(["a", "", None, "b"]) == "a, b"

    def test_trims_whitespace_preserving_internal(self):
        assert assemble_prompt(["  a b  ", "c\t"]) == "a b, c"

    def test_empty_list_returns_empty_string(self):
        assert assemble_prompt([]) == ""

    def test_all_blank_returns_empty_string(self):
        assert assemble_prompt(["", "   ", None]) == ""


def _file(name, path=None):
    return {"type": "file", "name": name, "path": path or name}


def _dir(name, path, children):
    return {"type": "dir", "name": name, "path": path, "children": children}


class TestComputeOrder:
    def test_root_files_alphabetical_by_default(self):
        tree = [_file("lighting.txt"), _file("camera.txt")]
        assert compute_order(tree, {}) == ["camera.txt", "lighting.txt"]

    def test_case_insensitive_alphabetical(self):
        tree = [_file("Zebra.txt"), _file("apple.txt")]
        assert compute_order(tree, {}) == ["apple.txt", "Zebra.txt"]

    def test_custom_order_is_respected(self):
        tree = [_file("lighting.txt"), _file("camera.txt")]
        order = compute_order(tree, {".": ["lighting.txt", "camera.txt"]})
        assert order == ["lighting.txt", "camera.txt"]

    def test_new_file_appended_at_end_of_known_order(self):
        tree = [_file("lighting.txt"), _file("camera.txt"), _file("ambient.txt")]
        order = compute_order(tree, {".": ["lighting.txt", "camera.txt"]})
        assert order == ["lighting.txt", "camera.txt", "ambient.txt"]

    def test_order_entries_for_removed_files_are_ignored(self):
        tree = [_file("lighting.txt")]
        order = compute_order(tree, {".": ["ghost.txt", "lighting.txt"]})
        assert order == ["lighting.txt"]

    def test_nested_directories_depth_first_after_own_files(self):
        tree = [
            _file("lighting.txt"),
            _dir("people", "people", [_file("age.txt", "people/age.txt")]),
        ]
        assert compute_order(tree, {}) == ["lighting.txt", "people/age.txt"]

    def test_directories_ordered_alphabetically_not_user_orderable(self):
        tree = [
            _dir("zeta", "zeta", [_file("a.txt", "zeta/a.txt")]),
            _dir("alpha", "alpha", [_file("b.txt", "alpha/b.txt")]),
        ]
        assert compute_order(tree, {}) == ["alpha/b.txt", "zeta/a.txt"]

    def test_per_directory_custom_order_is_independent(self):
        tree = [
            _dir(
                "people",
                "people",
                [_file("age.txt", "people/age.txt"), _file("hair.txt", "people/hair.txt")],
            ),
        ]
        order = compute_order(tree, {"people": ["hair.txt", "age.txt"]})
        assert order == ["people/hair.txt", "people/age.txt"]
