"""A framework's keywords as data: what a signature says, and what is read back from another process."""
from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from pybreeze.utils.exception.exceptions import LanguageServiceException
from pybreeze.utils.language_service.framework_profiles import PROFILES, profile_of
from pybreeze.utils.language_service.keyword_metadata import (
    METADATA_SCHEMA,
    FrameworkMetadata,
    Keyword,
    KeywordParameter,
    ParameterKind,
    metadata_from_dict,
)

FIXTURES = Path(__file__).parent / "fixtures" / "language_service"


def _data(framework: str) -> dict:
    return json.loads((FIXTURES / f"{framework}.metadata.json").read_text(encoding="utf-8"))


def _metadata(framework: str) -> FrameworkMetadata:
    return metadata_from_dict(_data(framework))


# ----------------------------------------------------------------------
# The frameworks
# ----------------------------------------------------------------------

def test_the_three_frameworks_come_in_the_order_they_are_rolled_out():
    assert [profile.framework for profile in PROFILES] == ["je_web_runner", "je_auto_control", "je_load_density"]


def test_each_framework_has_its_own_key_and_prefix():
    assert len({profile.document_key for profile in PROFILES}) == len(PROFILES)
    assert len({profile.keyword_prefix for profile in PROFILES}) == len(PROFILES)


def test_a_profile_is_found_by_the_packages_import_name():
    assert profile_of("je_auto_control").label == "AutoControl"
    assert profile_of("requests") is None


@pytest.mark.parametrize("profile", PROFILES, ids=lambda profile: profile.framework)
def test_the_fixture_of_each_framework_is_read(profile):
    metadata = _metadata(profile.framework)

    assert metadata.framework == profile.framework
    assert metadata.version
    assert metadata.own_keywords()
    assert all(keyword.name.startswith(profile.keyword_prefix) for keyword in metadata.own_keywords())


# ----------------------------------------------------------------------
# What a signature says
# ----------------------------------------------------------------------

@pytest.mark.parametrize(("parameter", "written"), [
    (KeywordParameter("url", annotation="str"), "url: str"),
    (KeywordParameter("image"), "image"),
    (KeywordParameter("timeout", required=False, default="30", annotation="int"), "timeout: int = 30"),
    (KeywordParameter("x", required=False, default="None"), "x=None"),
    (KeywordParameter("args", ParameterKind.VAR_POSITIONAL, required=False), "*args"),
    (KeywordParameter("kwargs", ParameterKind.VAR_KEYWORD, required=False), "**kwargs"),
])
def test_a_parameter_is_written_as_python_writes_it(parameter, written):
    assert parameter.written() == written


def test_a_keyword_is_written_as_a_call():
    keyword = _metadata("je_web_runner").keyword("WR_get_webdriver_manager")

    assert keyword.signature() == "WR_get_webdriver_manager(webdriver_name: str, options: List[str] = None, **kwargs)"


def test_a_keyword_python_cannot_describe_says_so():
    keyword = _metadata("je_web_runner").keyword("max")

    assert not keyword.signature_known
    assert keyword.signature() == "max(...)"


def test_a_keyword_knows_which_names_it_takes():
    keyword = _metadata("je_auto_control").keyword("AC_click_mouse")

    assert [parameter.name for parameter in keyword.named()] == ["mouse_keycode", "x", "y"]
    assert keyword.parameter("x").annotation == "int"
    assert keyword.parameter("z") is None
    assert not keyword.takes_any_name()
    assert _metadata("je_web_runner").keyword("WR_get_webdriver_manager").takes_any_name()


def test_a_keyword_knows_what_a_call_still_has_to_give():
    keyword = _metadata("je_auto_control").keyword("AC_set_mouse_position")

    assert keyword.missing(set()) == ["x", "y"]
    assert keyword.missing({"y"}) == ["x"]
    assert keyword.missing({"x", "y"}) == []


@pytest.mark.parametrize(("parameters", "expected"), [
    ((), (0, 0)),
    ((KeywordParameter("a"), KeywordParameter("b", required=False, default="1")), (1, 2)),
    ((KeywordParameter("a"), KeywordParameter("rest", ParameterKind.VAR_POSITIONAL, required=False)), (1, None)),
    ((KeywordParameter("a", ParameterKind.POSITIONAL_ONLY), KeywordParameter("k", ParameterKind.KEYWORD_ONLY)),
     (1, 1)),
])
def test_a_keyword_knows_how_many_values_a_list_may_give(parameters, expected):
    assert Keyword("k", parameters).positional_range() == expected


def test_a_required_keyword_only_parameter_cannot_come_from_a_list():
    keyword = Keyword("k", (KeywordParameter("a"), KeywordParameter("mode", ParameterKind.KEYWORD_ONLY),
                            KeywordParameter("flag", ParameterKind.KEYWORD_ONLY, required=False, default="1")))

    assert keyword.needs_a_name() == ["mode"]
    assert [parameter.name for parameter in keyword.named()] == ["a", "mode", "flag"]


def test_a_positional_only_parameter_is_not_given_by_name():
    keyword = Keyword("k", (KeywordParameter("a", ParameterKind.POSITIONAL_ONLY),))

    assert keyword.named() == ()
    assert keyword.missing(set()) == ["a"]


def test_the_frameworks_own_keywords_leave_pythons_built_ins_out():
    metadata = _metadata("je_web_runner")

    assert "print" in metadata.keywords and metadata.keyword("print").builtin
    assert [keyword.name for keyword in metadata.own_keywords()] == sorted(
        name for name in metadata.keywords if name.startswith("WR_"))


def test_metadata_says_whether_any_keyword_can_be_found():
    assert _metadata("je_web_runner").can_locate()
    assert not FrameworkMetadata("x", keywords={"k": Keyword("k")}).can_locate()


# ----------------------------------------------------------------------
# Across the process boundary
# ----------------------------------------------------------------------

@pytest.mark.parametrize("profile", PROFILES, ids=lambda profile: profile.framework)
def test_metadata_written_and_read_back_is_the_same(profile):
    metadata = _metadata(profile.framework)

    assert metadata_from_dict(json.loads(json.dumps(metadata.to_dict()))) == metadata
    assert metadata.to_dict()["schema"] == METADATA_SCHEMA


def _broken(change) -> dict:
    data = copy.deepcopy(_data("je_load_density"))
    change(data)
    return data


@pytest.mark.parametrize("data", [
    None, [], "je_web_runner", {},
    _broken(lambda data: data.pop("framework")),
    _broken(lambda data: data.update(framework="")),
    _broken(lambda data: data.update(framework=7)),
    _broken(lambda data: data.update(schema=METADATA_SCHEMA + 1)),
    _broken(lambda data: data.pop("schema")),
    _broken(lambda data: data.update(keywords={"a": 1})),
    _broken(lambda data: data.update(keywords=["LD_start_test"])),
    _broken(lambda data: data["keywords"][0].pop("name")),
    _broken(lambda data: data["keywords"][0].update(parameters="x")),
    _broken(lambda data: data["keywords"][0]["parameters"].append({"kind": "VAR_KEYWORD"})),
    _broken(lambda data: data["keywords"][0]["parameters"][0].update(kind="SOMETHING_ELSE")),
], ids=lambda data: type(data).__name__)
def test_what_is_not_metadata_is_refused(data):
    with pytest.raises(LanguageServiceException, match="not in a form"):
        metadata_from_dict(data)


def test_the_refusal_names_the_framework_when_it_is_known():
    with pytest.raises(LanguageServiceException, match="je_load_density"):
        metadata_from_dict(_broken(lambda data: data.update(keywords=None)))


def test_fields_a_package_left_out_get_their_defaults():
    metadata = metadata_from_dict({"schema": METADATA_SCHEMA, "framework": "je_x", "keywords": [
        {"name": "X_go", "parameters": [{"name": "where"}]}]})

    keyword = metadata.keyword("X_go")
    assert metadata.version == ""
    assert keyword.signature_known and not keyword.builtin and keyword.doc == ""
    assert keyword.parameters == (KeywordParameter("where"),)


@pytest.mark.parametrize("line", [-3, 0, "12", True, None, 1.5])
def test_a_line_that_is_not_a_line_number_is_no_line(line):
    metadata = metadata_from_dict({"schema": METADATA_SCHEMA, "framework": "je_x", "keywords": [
        {"name": "X_go", "source_file": "x.py", "source_line": line}]})

    assert metadata.keyword("X_go").source_line == 0
    assert not metadata.can_locate()
