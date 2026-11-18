import pytest

from paths import InvalidPathError, create_wildcard_file, normalize_new_filename, resolve_within_root


class TestResolveWithinRoot:
    def test_simple_relative_path(self, tmp_path):
        (tmp_path / "lighting.txt").touch()
        resolved = resolve_within_root(tmp_path, "lighting.txt")
        assert resolved == (tmp_path / "lighting.txt").resolve()

    def test_nested_relative_path(self, tmp_path):
        (tmp_path / "people").mkdir()
        resolved = resolve_within_root(tmp_path, "people/age.txt")
        assert resolved == (tmp_path / "people" / "age.txt").resolve()

    def test_empty_path_rejected(self, tmp_path):
        with pytest.raises(InvalidPathError):
            resolve_within_root(tmp_path, "")

    def test_blank_path_rejected(self, tmp_path):
        with pytest.raises(InvalidPathError):
            resolve_within_root(tmp_path, "   ")

    def test_absolute_path_rejected(self, tmp_path):
        with pytest.raises(InvalidPathError):
            resolve_within_root(tmp_path, "/etc/passwd")

    def test_traversal_rejected(self, tmp_path):
        with pytest.raises(InvalidPathError):
            resolve_within_root(tmp_path, "../outside.txt")

    def test_nested_traversal_rejected(self, tmp_path):
        with pytest.raises(InvalidPathError):
            resolve_within_root(tmp_path, "people/../../outside.txt")

    def test_symlink_escape_rejected(self, tmp_path):
        outside = tmp_path.parent / "outside_target"
        outside.mkdir(exist_ok=True)
        root = tmp_path / "wildcards"
        root.mkdir()
        link = root / "escape"
        link.symlink_to(outside)
        with pytest.raises(InvalidPathError):
            resolve_within_root(root, "escape/anything.txt")

    def test_symlink_within_root_allowed(self, tmp_path):
        root = tmp_path / "wildcards"
        real_dir = root / "real"
        real_dir.mkdir(parents=True)
        link = root / "linked"
        link.symlink_to(real_dir)
        resolved = resolve_within_root(root, "linked/file.txt")
        assert resolved == (real_dir / "file.txt").resolve()


class TestNormalizeNewFilename:
    def test_bare_name_gets_txt_appended(self):
        assert normalize_new_filename("lighting") == "lighting.txt"

    def test_name_with_txt_is_unchanged(self):
        assert normalize_new_filename("lighting.txt") == "lighting.txt"

    def test_does_not_double_append(self):
        assert normalize_new_filename("lighting.txt").endswith(".txt")
        assert not normalize_new_filename("lighting.txt").endswith(".txt.txt")

    def test_strips_surrounding_whitespace(self):
        assert normalize_new_filename("  lighting  ") == "lighting.txt"

    def test_empty_name_rejected(self):
        with pytest.raises(InvalidPathError):
            normalize_new_filename("")

    def test_blank_name_rejected(self):
        with pytest.raises(InvalidPathError):
            normalize_new_filename("   ")

    def test_none_rejected(self):
        with pytest.raises(InvalidPathError):
            normalize_new_filename(None)

    def test_forward_slash_rejected(self):
        with pytest.raises(InvalidPathError):
            normalize_new_filename("people/age")

    def test_backslash_rejected(self):
        with pytest.raises(InvalidPathError):
            normalize_new_filename("people\\age")

    def test_traversal_rejected(self):
        with pytest.raises(InvalidPathError):
            normalize_new_filename("..")

    def test_dotfile_rejected(self):
        with pytest.raises(InvalidPathError):
            normalize_new_filename(".hidden")

    def test_extension_only_rejected(self):
        with pytest.raises(InvalidPathError):
            normalize_new_filename(".txt")


class TestCreateWildcardFile:
    def test_creates_empty_utf8_file(self, tmp_path):
        created = create_wildcard_file(tmp_path, "lighting")
        assert created == (tmp_path / "lighting.txt").resolve()
        assert created.read_text(encoding="utf-8") == ""

    def test_does_not_overwrite_existing_file(self, tmp_path):
        existing = tmp_path / "lighting.txt"
        existing.write_text("keep me", encoding="utf-8")
        with pytest.raises(FileExistsError):
            create_wildcard_file(tmp_path, "lighting")
        assert existing.read_text(encoding="utf-8") == "keep me"

    def test_rejects_traversal(self, tmp_path):
        with pytest.raises(InvalidPathError):
            create_wildcard_file(tmp_path, "../escape.txt")

    def test_rejects_path_separator_in_name(self, tmp_path):
        with pytest.raises(InvalidPathError):
            create_wildcard_file(tmp_path, "sub/new.txt")
