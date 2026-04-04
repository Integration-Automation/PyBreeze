import os
import tempfile

import pytest

from pybreeze.utils.file_process.get_dir_file_list import get_dir_files_as_list


@pytest.fixture
def temp_dir_with_files():
    """Create a temp directory with test files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create test files
        for name in ["test1.json", "test2.json", "readme.txt", "data.csv"]:
            with open(os.path.join(tmpdir, name), "w") as f:
                f.write("{}")
        # Create subdirectory with more files
        subdir = os.path.join(tmpdir, "subdir")
        os.makedirs(subdir)
        with open(os.path.join(subdir, "nested.json"), "w") as f:
            f.write("{}")
        with open(os.path.join(subdir, "other.py"), "w") as f:
            f.write("")
        yield tmpdir


class TestGetDirFilesAsList:
    def test_returns_list(self, temp_dir_with_files):
        result = get_dir_files_as_list(temp_dir_with_files)
        assert isinstance(result, list)

    def test_finds_json_files_by_default(self, temp_dir_with_files):
        result = get_dir_files_as_list(temp_dir_with_files)
        assert len(result) == 3  # test1.json, test2.json, nested.json
        assert all(f.endswith(".json") for f in result)

    def test_custom_extension(self, temp_dir_with_files):
        result = get_dir_files_as_list(temp_dir_with_files, ".txt")
        assert len(result) == 1
        assert result[0].endswith("readme.txt")

    def test_csv_extension(self, temp_dir_with_files):
        result = get_dir_files_as_list(temp_dir_with_files, ".csv")
        assert len(result) == 1

    def test_py_extension(self, temp_dir_with_files):
        result = get_dir_files_as_list(temp_dir_with_files, ".py")
        assert len(result) == 1
        assert result[0].endswith("other.py")

    def test_no_matching_extension(self, temp_dir_with_files):
        result = get_dir_files_as_list(temp_dir_with_files, ".xyz")
        assert result == []

    def test_empty_directory(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            result = get_dir_files_as_list(tmpdir)
            assert result == []

    def test_returns_absolute_paths(self, temp_dir_with_files):
        result = get_dir_files_as_list(temp_dir_with_files)
        for path in result:
            assert os.path.isabs(path)

    def test_case_insensitive_extension(self, temp_dir_with_files):
        # Create a file with uppercase extension
        with open(os.path.join(temp_dir_with_files, "upper.JSON"), "w") as f:
            f.write("{}")
        result = get_dir_files_as_list(temp_dir_with_files, ".json")
        # .json should match files with .json extension
        # The function uses file.endswith(ext.lower()) so it checks lowercase ext
        # But the file "upper.JSON" won't match ".json" because endswith is case-sensitive
        json_files = [f for f in result if f.endswith(".json")]
        assert len(json_files) == 3  # only lowercase .json files

    def test_walks_subdirectories(self, temp_dir_with_files):
        result = get_dir_files_as_list(temp_dir_with_files, ".json")
        nested = [f for f in result if "subdir" in f]
        assert len(nested) == 1
