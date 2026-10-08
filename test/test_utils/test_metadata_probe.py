"""Asking an installed package for its keywords, in a process of its own.

A package made for the test stands in for a framework: the probe is the same,
and what it must survive (printing as it is imported, failing, hanging) is
written into the stand-in. The three real frameworks are asked too, where they
are installed: that is the contract the profiles rely on.
"""
from __future__ import annotations

import ast
import importlib.util
import sys
from pathlib import Path

import pytest

from pybreeze.utils.exception.exceptions import LanguageServiceException
from pybreeze.utils.language_service.framework_profiles import PROFILES, FrameworkProfile
from pybreeze.utils.language_service.keyword_metadata import ParameterKind
from pybreeze.utils.language_service.metadata_probe import PROBE_SCRIPT, probe_command, read_metadata

FAKE = FrameworkProfile(
    framework="fake_runner", label="FakeRunner", document_key="fake_runner", executor_module="fake_runner.executor",
    distribution="fake_runner", keyword_prefix="FR_")

_EXECUTOR = '''from __future__ import annotations

import builtins
from inspect import getmembers, isbuiltin

print("fake_runner says hello as it is imported")


def FR_open(url: str, timeout: int = 30, *, retries=None, **options):
    """Open a page.

    And wait for it.
    """


def FR_close():
    pass


class _Wrapper:
    def click(self, x: int, y: int = 0):
        """Click somewhere."""


class Executor:
    def __init__(self):
        self.event_dict = {"FR_open": FR_open, "FR_close": FR_close, "FR_click": _Wrapper().click, "FR_table": {}}
        for name, function in getmembers(builtins, isbuiltin):
            self.event_dict[name] = function


executor = Executor()
'''


def _install(folder: Path, executor: str = _EXECUTOR) -> Path:
    """Write the stand-in package under *folder* and return the executor's file."""
    package = folder / "fake_runner"
    package.mkdir(parents=True)
    (package / "__init__.py").write_text("", encoding="utf-8")
    file = package / "executor.py"
    file.write_text(executor, encoding="utf-8")
    return file


@pytest.fixture
def installed(tmp_path, monkeypatch) -> Path:
    """The stand-in package, importable by a child interpreter; its executor's file."""
    file = _install(tmp_path / "site")
    monkeypatch.setenv("PYTHONPATH", str(tmp_path / "site"))
    return file


def _failing(tmp_path, monkeypatch, executor: str) -> None:
    _install(tmp_path / "site", executor)
    monkeypatch.setenv("PYTHONPATH", str(tmp_path / "site"))


# ----------------------------------------------------------------------
# What is read
# ----------------------------------------------------------------------

def test_a_packages_keywords_are_read_with_their_parameters(installed):
    metadata = read_metadata(FAKE)

    assert metadata.framework == "fake_runner"
    assert [keyword.name for keyword in metadata.own_keywords()] == ["FR_click", "FR_close", "FR_open"]
    opened = metadata.keyword("FR_open")
    assert opened.signature() == "FR_open(url: str, timeout: int = 30, retries=None, **options)"
    assert [(parameter.name, parameter.kind, parameter.required) for parameter in opened.parameters] == [
        ("url", ParameterKind.POSITIONAL_OR_KEYWORD, True),
        ("timeout", ParameterKind.POSITIONAL_OR_KEYWORD, False),
        ("retries", ParameterKind.KEYWORD_ONLY, False),
        ("options", ParameterKind.VAR_KEYWORD, False)]


def test_documentation_comes_as_python_cleans_it(installed):
    assert read_metadata(FAKE).keyword("FR_open").doc == "Open a page.\n\nAnd wait for it."
    assert read_metadata(FAKE).keyword("FR_close").doc == ""


def test_a_keyword_says_where_it_is_defined(installed):
    keyword = read_metadata(FAKE).keyword("FR_open")
    lines = installed.read_text(encoding="utf-8").splitlines()

    assert Path(keyword.source_file) == installed
    assert lines[keyword.source_line - 1].startswith("def FR_open(")


def test_a_method_is_described_without_its_self(installed):
    keyword = read_metadata(FAKE).keyword("FR_click")

    assert keyword.signature() == "FR_click(x: int, y: int = 0)"
    assert keyword.doc == "Click somewhere."


def test_pythons_built_ins_are_marked_and_what_is_not_callable_is_left_out(installed):
    metadata = read_metadata(FAKE)

    assert metadata.keyword("print").builtin and metadata.keyword("len").builtin
    assert not metadata.keyword("FR_open").builtin
    assert metadata.keyword("FR_table") is None


def test_a_package_that_is_not_a_distribution_has_no_version(installed):
    assert read_metadata(FAKE).version == ""


def test_what_a_package_prints_as_it_is_imported_does_not_spoil_the_answer(installed):
    # The stand-in prints a line as it is imported
    assert read_metadata(FAKE).keyword("FR_close") is not None


# ----------------------------------------------------------------------
# What it survives
# ----------------------------------------------------------------------

def test_a_package_that_is_not_installed_is_said_to_be(tmp_path, monkeypatch):
    monkeypatch.delenv("PYTHONPATH", raising=False)

    with pytest.raises(LanguageServiceException, match="fake_runner is not installed"):
        read_metadata(FAKE)


def test_a_package_in_the_folder_the_ide_is_in_is_not_the_one_asked(tmp_path, monkeypatch):
    _install(tmp_path)
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("PYTHONPATH", raising=False)

    with pytest.raises(LanguageServiceException, match="not installed"):
        read_metadata(FAKE)


def test_a_package_that_fails_to_import_is_named_by_the_failure_and_nothing_of_its_message(tmp_path, monkeypatch):
    _failing(tmp_path, monkeypatch, 'raise RuntimeError("C:/secret/place is broken")\n')

    with pytest.raises(LanguageServiceException) as caught:
        read_metadata(FAKE)

    assert str(caught.value) == "fake_runner could not list its keywords (RuntimeError)"


def test_a_module_without_an_executor_is_a_failure_too(tmp_path, monkeypatch):
    _failing(tmp_path, monkeypatch, "x = 1\n")

    with pytest.raises(LanguageServiceException, match=r"could not list its keywords \(AttributeError\)"):
        read_metadata(FAKE)


def test_a_package_that_hangs_is_given_up_on(tmp_path, monkeypatch):
    _failing(tmp_path, monkeypatch, "import time\ntime.sleep(60)\n")

    with pytest.raises(LanguageServiceException, match="took longer than 1 seconds"):
        read_metadata(FAKE, timeout_seconds=1)


def test_an_interpreter_that_is_not_there_is_a_failure_without_its_path(tmp_path):
    with pytest.raises(LanguageServiceException) as caught:
        read_metadata(FAKE, str(tmp_path / "no_such_python"))

    assert "could not list its keywords" in str(caught.value)
    assert str(tmp_path) not in str(caught.value)


def test_the_interpreter_asked_is_the_one_named(installed):
    assert read_metadata(FAKE, sys.executable).keyword("FR_open") is not None


# ----------------------------------------------------------------------
# The probe itself
# ----------------------------------------------------------------------

def test_the_probe_is_a_fixed_script_run_by_the_interpreter_named():
    command = probe_command(FAKE, "python-of-the-project")

    assert command[:3] == ["python-of-the-project", "-c", PROBE_SCRIPT]
    assert command[3:5] == ["fake_runner.executor", "fake_runner"]


def test_the_probe_needs_only_the_standard_library():
    imported = set()
    for node in ast.walk(ast.parse(PROBE_SCRIPT)):
        if isinstance(node, ast.Import):
            imported.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            imported.add((node.module or "").split(".")[0])

    assert imported <= {"builtins", "contextlib", "importlib", "inspect", "json", "sys"}


# ----------------------------------------------------------------------
# The three frameworks, where they are installed
# ----------------------------------------------------------------------

def _installed_or_skip(profile: FrameworkProfile):
    try:
        return read_metadata(profile)
    except LanguageServiceException as error:
        if "is not installed" in str(error):
            pytest.skip(f"{profile.framework} is not installed here")
        raise


@pytest.mark.parametrize("profile", PROFILES, ids=lambda profile: profile.framework)
def test_each_framework_lists_its_keywords_under_its_prefix(profile):
    metadata = _installed_or_skip(profile)

    own = metadata.own_keywords()
    assert own, f"{profile.framework} lists no keyword of its own"
    assert all(keyword.name.startswith(profile.keyword_prefix) for keyword in own)
    assert metadata.version
    assert metadata.can_locate()
    # The framework chooses which built-ins to expose; classification is covered
    # by the fake executor above without requiring a dependency to register print.


@pytest.mark.parametrize("profile", PROFILES, ids=lambda profile: profile.framework)
def test_each_frameworks_executor_reads_its_actions_from_the_key_the_profile_names(profile):
    # Found without importing the package: je_auto_control changes the process as it is imported
    package = importlib.util.find_spec(profile.framework)
    if package is None:
        pytest.skip(f"{profile.framework} is not installed here")
    module_path = Path(package.submodule_search_locations[0]).joinpath(
        *profile.executor_module.split(".")[1:]).with_suffix(".py")

    source = module_path.read_text(encoding="utf-8")

    assert f'.get("{profile.document_key}"' in source
    assert "event_dict" in source and "executor = Executor()" in source
