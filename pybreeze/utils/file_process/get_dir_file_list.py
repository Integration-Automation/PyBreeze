from __future__ import annotations

from os import getcwd
from os import walk
from os.path import abspath
from os.path import join


def get_dir_files_as_list(dir_path: str | None = None, default_search_file_extension: str = ".json") -> list:
    """
    get dir file when end with default_search_file_extension
    :param dir_path: which dir we want to walk and get file list; defaults to the
        current working directory at call time when ``None``
    :param default_search_file_extension: which extension we want to search
        (matched case-insensitively)
    :return: [] if nothing searched or [file1, file2.... files] file was searched
    """
    if dir_path is None:
        dir_path = getcwd()
    extension = default_search_file_extension.lower()
    return [
        abspath(join(root, file)) for root, _dirs, files in walk(dir_path)
        for file in files
        if file.lower().endswith(extension)
    ]

