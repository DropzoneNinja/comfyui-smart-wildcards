from scanner import scan_wildcards


def _find(tree, path):
    for node in tree:
        if node["path"] == path:
            return node
        if node["type"] == "dir":
            found = _find(node["children"], path)
            if found is not None:
                return found
    return None


def test_missing_root_reports_error_and_empty_tree(tmp_path):
    missing = tmp_path / "does_not_exist"
    result = scan_wildcards(missing)
    assert result["tree"] == []
    assert result["errors"]


def test_root_level_files_are_listed(tmp_path):
    (tmp_path / "lighting.txt").write_text("a\n", encoding="utf-8")
    (tmp_path / "camera.txt").write_text("b\n", encoding="utf-8")

    result = scan_wildcards(tmp_path)
    names = [n["name"] for n in result["tree"]]
    assert names == ["camera.txt", "lighting.txt"]  # alphabetical, case-insensitive


def test_case_insensitive_sort(tmp_path):
    (tmp_path / "Zebra.txt").write_text("a\n", encoding="utf-8")
    (tmp_path / "apple.txt").write_text("b\n", encoding="utf-8")

    result = scan_wildcards(tmp_path)
    names = [n["name"] for n in result["tree"]]
    assert names == ["apple.txt", "Zebra.txt"]


def test_non_txt_files_are_ignored(tmp_path):
    (tmp_path / "notes.md").write_text("ignore me", encoding="utf-8")
    (tmp_path / "lighting.txt").write_text("a\n", encoding="utf-8")

    result = scan_wildcards(tmp_path)
    names = [n["name"] for n in result["tree"]]
    assert names == ["lighting.txt"]


def test_hidden_files_are_ignored(tmp_path):
    (tmp_path / ".hidden.txt").write_text("a\n", encoding="utf-8")
    (tmp_path / "lighting.txt").write_text("a\n", encoding="utf-8")

    result = scan_wildcards(tmp_path)
    names = [n["name"] for n in result["tree"]]
    assert names == ["lighting.txt"]


def test_hidden_directories_are_ignored(tmp_path):
    hidden = tmp_path / ".cache"
    hidden.mkdir()
    (hidden / "inside.txt").write_text("a\n", encoding="utf-8")

    result = scan_wildcards(tmp_path)
    assert result["tree"] == []


def test_nested_directory_becomes_a_dir_node(tmp_path):
    people = tmp_path / "people"
    people.mkdir()
    (people / "age.txt").write_text("20s\n30s\n", encoding="utf-8")

    result = scan_wildcards(tmp_path)
    assert len(result["tree"]) == 1
    dir_node = result["tree"][0]
    assert dir_node["type"] == "dir"
    assert dir_node["name"] == "people"
    assert dir_node["children"][0]["path"] == "people/age.txt"


def test_empty_directory_is_omitted(tmp_path):
    (tmp_path / "empty_dir").mkdir()
    (tmp_path / "lighting.txt").write_text("a\n", encoding="utf-8")

    result = scan_wildcards(tmp_path)
    names = [n["name"] for n in result["tree"]]
    assert "empty_dir" not in names


def test_directory_with_only_empty_subdirs_is_omitted(tmp_path):
    nested_empty = tmp_path / "outer" / "inner"
    nested_empty.mkdir(parents=True)

    result = scan_wildcards(tmp_path)
    assert result["tree"] == []


def test_file_entry_count_and_status_ok(tmp_path):
    (tmp_path / "lighting.txt").write_text("a\nb\nc\n", encoding="utf-8")

    result = scan_wildcards(tmp_path)
    node = _find(result["tree"], "lighting.txt")
    assert node["entryCount"] == 3
    assert node["status"] == "ok"


def test_empty_file_status_is_empty(tmp_path):
    (tmp_path / "blank.txt").write_text("", encoding="utf-8")

    result = scan_wildcards(tmp_path)
    node = _find(result["tree"], "blank.txt")
    assert node["entryCount"] == 0
    assert node["status"] == "empty"


def test_relative_paths_use_forward_slashes(tmp_path):
    people = tmp_path / "people"
    people.mkdir()
    (people / "age.txt").write_text("20s\n", encoding="utf-8")

    result = scan_wildcards(tmp_path)
    node = _find(result["tree"], "people/age.txt")
    assert node is not None


def test_symlinked_file_escaping_root_is_skipped(tmp_path):
    outside = tmp_path.parent / "outside_file.txt"
    outside.write_text("secret\n", encoding="utf-8")
    root = tmp_path / "wildcards"
    root.mkdir()
    (root / "escape.txt").symlink_to(outside)
    (root / "lighting.txt").write_text("a\n", encoding="utf-8")

    result = scan_wildcards(root)
    names = [n["name"] for n in result["tree"]]
    assert names == ["lighting.txt"]


def test_symlinked_dir_escaping_root_is_skipped(tmp_path):
    outside = tmp_path.parent / "outside_dir"
    outside.mkdir()
    (outside / "inside.txt").write_text("secret\n", encoding="utf-8")
    root = tmp_path / "wildcards"
    root.mkdir()
    (root / "escape").symlink_to(outside)
    (root / "lighting.txt").write_text("a\n", encoding="utf-8")

    result = scan_wildcards(root)
    names = [n["name"] for n in result["tree"]]
    assert names == ["lighting.txt"]
