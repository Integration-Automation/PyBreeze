"""Settings and command building for the prthinker code review framework."""
from __future__ import annotations

import json

import pytest

from pybreeze.extend.prthinker_extend import prthinker_setting
from pybreeze.extend.prthinker_extend.prthinker_setting import (
    DEFAULT_SETTING, INSTALL_EXTRAS, SECRET_SETTINGS, SETTING_ENVIRONMENT,
    environment_for, extra_arguments, install_target, load_setting, loggable,
    review_file_arguments, review_pr_arguments, save_setting
)


@pytest.fixture()
def data_dir(tmp_path, monkeypatch):
    """Keep every test's settings file inside its own temporary directory."""
    monkeypatch.setattr(prthinker_setting, "pybreeze_data_dir", lambda: tmp_path)
    return tmp_path


class TestReadingAndWritingTheSettings:
    def test_nothing_stored_yields_the_defaults(self, data_dir):
        assert load_setting() == DEFAULT_SETTING

    def test_what_was_saved_comes_back(self, data_dir):
        assert save_setting({**DEFAULT_SETTING, "repository": "owner/name"})
        assert load_setting()["repository"] == "owner/name"

    def test_a_missing_field_falls_back_to_its_default(self, data_dir):
        (data_dir / "prthinker_setting.json").write_text(
            json.dumps({"repository": "owner/name"}), encoding="utf-8")
        setting = load_setting()
        assert setting["repository"] == "owner/name"
        assert setting["backend"] == DEFAULT_SETTING["backend"]

    def test_an_unknown_field_is_ignored(self, data_dir):
        (data_dir / "prthinker_setting.json").write_text(
            json.dumps({"nonsense": "value"}), encoding="utf-8")
        assert "nonsense" not in load_setting()

    def test_a_broken_file_does_not_stop_the_feature(self, data_dir):
        (data_dir / "prthinker_setting.json").write_text("{ not json", encoding="utf-8")
        assert load_setting() == DEFAULT_SETTING

    def test_saving_reports_failure_instead_of_raising(self, data_dir, monkeypatch):
        def refuse(*_args, **_kwargs):
            raise OSError("read-only")
        monkeypatch.setattr(
            prthinker_setting.Path, "write_text", refuse, raising=False)
        assert save_setting(DEFAULT_SETTING) is False


class TestTheEnvironmentGivenToTheChild:
    def test_a_filled_setting_becomes_its_variable(self):
        environment = environment_for({**DEFAULT_SETTING, "remote_url": "http://host"})
        assert environment["PRTHINKER_REMOTE_URL"] == "http://host"

    def test_a_blank_setting_is_left_out(self):
        # prthinker keeps its own default for anything not given.
        assert "PRTHINKER_MODEL_NAME" not in environment_for(DEFAULT_SETTING)

    def test_surrounding_spaces_are_dropped(self):
        environment = environment_for({**DEFAULT_SETTING, "repository": "  owner/name "})
        assert environment["GITHUB_REPOSITORY"] == "owner/name"

    def test_every_setting_that_travels_has_a_variable(self):
        # Anything in the table has to name a setting that actually exists.
        assert set(SETTING_ENVIRONMENT) <= set(DEFAULT_SETTING)


class TestTheCommandsAreBuilt:
    def test_reviewing_a_file_names_that_file(self):
        assert review_file_arguments("main.py", DEFAULT_SETTING) == \
            ["review-file", "main.py"]

    def test_reviewing_a_pull_request_carries_only_the_number(self):
        # The repository and the token travel as environment, never on the
        # command line, where a process list would show them.
        arguments = review_pr_arguments(
            7, {**DEFAULT_SETTING, "platform_token": "secret"})
        assert arguments == ["review-pr", "--pr-number", "7"]
        assert "secret" not in " ".join(arguments)

    def test_extra_arguments_are_appended(self):
        setting = {**DEFAULT_SETTING, "extra_arguments": "--step-plan adaptive"}
        assert review_file_arguments("main.py", setting) == \
            ["review-file", "main.py", "--step-plan", "adaptive"]

    def test_a_quoted_argument_stays_in_one_piece(self):
        setting = {**DEFAULT_SETTING, "extra_arguments": '--marker "a b"'}
        assert extra_arguments(setting) == ["--marker", "a b"]

    def test_an_unclosed_quote_costs_only_the_extra_arguments(self):
        setting = {**DEFAULT_SETTING, "extra_arguments": '--marker "unclosed'}
        assert extra_arguments(setting) == []
        assert review_file_arguments("main.py", setting) == ["review-file", "main.py"]


class TestInstallingFromSource:
    """prthinker is not on PyPI, so pip is pointed at a folder."""

    def test_a_real_folder_becomes_a_target_with_the_extras(self, tmp_path):
        assert install_target(str(tmp_path)) == f"{tmp_path}[{INSTALL_EXTRAS}]"

    def test_surrounding_spaces_are_dropped(self, tmp_path):
        assert install_target(f"  {tmp_path} ") == f"{tmp_path}[{INSTALL_EXTRAS}]"

    def test_nothing_chosen_is_no_target(self):
        assert install_target("") == ""

    def test_a_path_that_is_not_a_folder_is_no_target(self, tmp_path):
        a_file = tmp_path / "pyproject.toml"
        a_file.write_text("", encoding="utf-8")
        assert install_target(str(a_file)) == ""

    def test_the_source_folder_is_not_handed_to_prthinker_as_environment(self, tmp_path):
        # It says where to install from, which is nothing prthinker itself reads.
        assert "source_path" not in SETTING_ENVIRONMENT


class TestSecretsStayOutOfTheLog:
    @pytest.mark.parametrize("key", SECRET_SETTINGS)
    def test_a_secret_is_reduced_to_whether_it_is_set(self, key):
        covered = loggable({**DEFAULT_SETTING, key: "s3cr3t"})
        assert covered[key] == "(set)"

    def test_an_unset_secret_stays_empty(self):
        assert loggable(DEFAULT_SETTING)["platform_token"] == ""

    def test_the_rest_is_left_readable(self):
        assert loggable({**DEFAULT_SETTING, "repository": "owner/name"})["repository"] \
            == "owner/name"
