import sys
from os import getcwd
from os import walk
from os.path import abspath
from os.path import join

from PySide6.QtWidgets import QFileDialog, QMainWindow


def get_dir_files_as_list(dir_path: str = getcwd(), default_search_file_extension: str = ".json") -> list:
    """
    get dir file when end with default_search_file_extension
    :param dir_path: which dir we want to walk and get file list
    :param default_search_file_extension: which extension we want to search
    :return: [] if nothing searched or [file1, file2.... files] file was searched
    """
    return [
        abspath(join(dir_path, file)) for root, dirs, files in walk(dir_path)
        for file in files
        if file.endswith(default_search_file_extension.lower())
    ]


def ask_and_get_dir_files_as_list(main_window: QMainWindow, default_search_file_extension: str = ".json") -> list:
    choose_dir = QFileDialog(parent=main_window).getExistingDirectory()
    if choose_dir is not None and choose_dir != "":
        return get_dir_files_as_list(choose_dir, default_search_file_extension)
    else:
        print("Not select any dir", file=sys.stderr)
