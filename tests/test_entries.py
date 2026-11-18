import time

from entries import invalidate_cache, read_entries


def test_basic_lines_in_order(tmp_path):
    f = tmp_path / "lighting.txt"
    f.write_text("cinematic\nsoft\nharsh\n", encoding="utf-8")
    assert read_entries(f) == ["cinematic", "soft", "harsh"]


def test_blank_lines_ignored(tmp_path):
    f = tmp_path / "lighting.txt"
    f.write_text("cinematic\n\n\nsoft\n   \nharsh\n", encoding="utf-8")
    assert read_entries(f) == ["cinematic", "soft", "harsh"]


def test_duplicate_lines_preserved(tmp_path):
    f = tmp_path / "lighting.txt"
    f.write_text("soft\nsoft\nharsh\n", encoding="utf-8")
    assert read_entries(f) == ["soft", "soft", "harsh"]


def test_crlf_line_endings(tmp_path):
    f = tmp_path / "lighting.txt"
    f.write_bytes(b"cinematic\r\nsoft\r\nharsh\r\n")
    assert read_entries(f) == ["cinematic", "soft", "harsh"]


def test_mixed_line_endings(tmp_path):
    f = tmp_path / "lighting.txt"
    f.write_bytes(b"cinematic\r\nsoft\nharsh\r\n")
    assert read_entries(f) == ["cinematic", "soft", "harsh"]


def test_utf8_bom_stripped(tmp_path):
    f = tmp_path / "lighting.txt"
    f.write_bytes(b"\xef\xbb\xbfcinematic\nsoft\n")
    assert read_entries(f) == ["cinematic", "soft"]


def test_entries_are_stripped_of_surrounding_whitespace(tmp_path):
    f = tmp_path / "lighting.txt"
    f.write_text("  cinematic  \n\tsoft\t\n", encoding="utf-8")
    assert read_entries(f) == ["cinematic", "soft"]


def test_empty_file_returns_empty_list(tmp_path):
    f = tmp_path / "empty.txt"
    f.write_text("", encoding="utf-8")
    assert read_entries(f) == []


def test_cache_returns_same_result_for_unchanged_file(tmp_path):
    f = tmp_path / "lighting.txt"
    f.write_text("cinematic\nsoft\n", encoding="utf-8")
    first = read_entries(f)
    second = read_entries(f)
    assert first == second == ["cinematic", "soft"]


def test_cache_invalidated_when_file_changes(tmp_path):
    f = tmp_path / "lighting.txt"
    f.write_text("cinematic\n", encoding="utf-8")
    assert read_entries(f) == ["cinematic"]

    time.sleep(0.01)
    f.write_text("cinematic\nharsh\n", encoding="utf-8")
    assert read_entries(f) == ["cinematic", "harsh"]


def test_invalidate_cache_forces_reread(tmp_path):
    f = tmp_path / "lighting.txt"
    f.write_text("cinematic\n", encoding="utf-8")
    assert read_entries(f) == ["cinematic"]

    invalidate_cache(f)
    f.write_text("harsh\n", encoding="utf-8")
    assert read_entries(f) == ["harsh"]
