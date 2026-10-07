"""The language service of an action script: completion, diagnostics, hover and go-to-definition."""
from __future__ import annotations

import dataclasses
import json
from pathlib import Path

import pytest

from pybreeze.extend_multi_language.extend_english import pybreeze_english_word_dict as WORDS
from pybreeze.utils.language_service.action_adapter import (
    ActionLanguageAdapter,
    framework_of,
    syntax_diagnostics,
)
from pybreeze.utils.language_service.framework_profiles import PROFILES, profile_of
from pybreeze.utils.language_service.json_scan import LineIndex
from pybreeze.utils.language_service.keyword_metadata import (
    FrameworkMetadata,
    Keyword,
    KeywordParameter,
    ParameterKind,
    metadata_from_dict,
)
from pybreeze.utils.language_service.service_adapter import (
    Capability,
    LanguageService,
    Position,
    Severity,
    TextDocument,
)

FIXTURES = Path(__file__).parent / "fixtures" / "language_service"
METADATA = {
    profile.framework: metadata_from_dict(json.loads(
        (FIXTURES / f"{profile.framework}.metadata.json").read_text(encoding="utf-8")))
    for profile in PROFILES
}


def _adapter(framework: str = "je_web_runner", metadata: FrameworkMetadata | None = None) -> ActionLanguageAdapter:
    return ActionLanguageAdapter(profile_of(framework), metadata or METADATA[framework], WORDS)


def _document(text: str) -> TextDocument:
    return TextDocument("file:///script.json", text, 1)


def _marked(marked: str) -> tuple[TextDocument, Position]:
    """The document *marked* is without its ``|``, and the position of that ``|``."""
    text = marked.replace("|", "")
    return _document(text), LineIndex(text).position(marked.index("|"))


def _labels(marked: str, framework: str = "je_web_runner") -> list[str]:
    return [item.label for item in _adapter(framework).complete(*_marked(marked))]


def _found(text: str, framework: str = "je_web_runner", metadata: FrameworkMetadata | None = None):
    """Each diagnostic of *text* as (its code, the text it covers, its message)."""
    index = LineIndex(text)
    return [(found.code, text[index.offset(found.range.start):index.offset(found.range.end)], found.message)
            for found in _adapter(framework, metadata).diagnose(_document(text))]


def _codes(text: str, framework: str = "je_web_runner", metadata: FrameworkMetadata | None = None) -> list[str]:
    return [code for code, _covered, _message in _found(text, framework, metadata)]


# ----------------------------------------------------------------------
# Whose script it is
# ----------------------------------------------------------------------

@pytest.mark.parametrize(("text", "framework"), [
    ('[["WR_to_url", {"url": "x"}], ["WR_quit"]]', "je_web_runner"),
    ('[["AC_write", {"write_string": "x"}]]', "je_auto_control"),
    ('[["LD_generate_json"]]', "je_load_density"),
    ('{"webdriver_wrapper": []}', "je_web_runner"),
    ('{"auto_control": [["print", ["x"]]]}', "je_auto_control"),
    ('{"load_density": 5}', "je_load_density"),
    ('[["LD_', "je_load_density"),
    ('[["print"], ["AC_write"], ["WR_quit"], ["AC_hotkey"]]', "je_auto_control"),
])
def test_a_script_is_told_by_its_key_or_its_keywords(text, framework):
    assert framework_of(text, METADATA).framework == framework


@pytest.mark.parametrize("text", [
    "", "{}", "[]", "[1, 2, 3]", '{"name": "demo"}', '[["print", ["x"]]]', '"WR_quit"', '[["something"]]',
])
def test_any_other_json_is_nobodys_script(text):
    assert framework_of(text, METADATA) is None


def test_without_its_keywords_at_hand_a_script_is_told_by_their_prefix():
    assert framework_of('[["AC_anything_at_all"]]', {}).framework == "je_auto_control"


def test_a_keyword_the_installed_version_has_counts_whatever_its_prefix():
    metadata = FrameworkMetadata("je_web_runner", keywords={"open_page": Keyword("open_page")})

    assert framework_of('[["open_page"]]', {"je_web_runner": metadata}).framework == "je_web_runner"


# ----------------------------------------------------------------------
# Completion
# ----------------------------------------------------------------------

def test_where_an_actions_name_goes_the_frameworks_keywords_come_first_then_pythons():
    labels = _labels('[["WR_|')

    assert labels == ["WR_SaveTestObject", "WR_add_cookie", "WR_get_webdriver_manager", "WR_quit",
                      "WR_set_page_load_timeout", "WR_to_url", "len", "max", "print"]


def test_a_completion_carries_the_keywords_signature_and_documentation():
    item = next(item for item in _adapter().complete(*_marked('[["|')) if item.label == "WR_to_url")

    assert item.detail == "WR_to_url(url: str)"
    assert item.documentation == METADATA["je_web_runner"].keyword("WR_to_url").doc


def test_outside_a_string_a_keyword_is_offered_with_its_quotes():
    assert '"WR_quit"' in _labels('[[|')
    assert "WR_quit" not in _labels('[[|')


@pytest.mark.parametrize("marked", [
    '[["WR_quit"], ["|', '{"webdriver_wrapper": [["|', '[\n  ["WR_quit"],\n  ["W|"]\n]',
])
def test_keywords_are_offered_in_every_action_of_the_script(marked):
    assert "WR_to_url" in _labels(marked)


def test_where_an_arguments_name_goes_the_keywords_parameters_are_offered():
    assert _labels('[["WR_get_webdriver_manager", {"|') == ["webdriver_name", "options"]


def test_a_parameter_already_given_is_not_offered_again():
    assert _labels('[["WR_get_webdriver_manager", {"webdriver_name": "chrome", "|') == ["options"]


def test_a_parameter_given_after_the_cursor_is_not_offered_either():
    assert _labels('[["AC_click_mouse", {"|": 1, "y": 2}]]', "je_auto_control") == ["mouse_keycode", "x"]
    assert _labels('[["AC_click_mouse", {| "x": 1}]]', "je_auto_control") == ['"mouse_keycode"', '"y"']


def test_the_name_the_cursor_is_in_is_still_offered():
    assert _labels('[["AC_click_mouse", {"x|": 1, "y": 2}]]', "je_auto_control") == ["mouse_keycode", "x"]


def test_a_parameter_is_offered_with_its_type_and_default():
    items = _adapter("je_auto_control").complete(*_marked('[["AC_click_mouse", {"|'))

    assert [(item.label, item.detail) for item in items] == [
        ("mouse_keycode", "mouse_keycode: Union[int, str]"), ("x", "x: int = None"), ("y", "y: int = None")]


def test_the_frameworks_key_is_offered_at_the_top_of_an_object():
    assert _labels('{"|') == ["webdriver_wrapper"]
    assert _labels('{|') == ['"webdriver_wrapper"']
    assert _labels('{"webdriver_wrapper": [], "|') == []


@pytest.mark.parametrize("marked", [
    '|', '[|', '["|', '[["WR_to_url", {"url": "|', '[["WR_to_url", "|', '[["no_such_keyword", {"|',
    '[["WR_to_url", {"url": {"|', '[[["|', '{"other": [["|', '[["WR_to_url", {"url": "x"}, "|',
])
def test_nothing_is_offered_where_no_keyword_or_parameter_goes(marked):
    assert _labels(marked) == []


# ----------------------------------------------------------------------
# Diagnostics
# ----------------------------------------------------------------------

@pytest.mark.parametrize("text", [
    "",
    '[["WR_get_webdriver_manager", {"webdriver_name": "chrome"}], ["WR_to_url", {"url": "x"}], ["WR_quit"]]',
    '{"webdriver_wrapper": [["WR_quit"]]}',
    '[["WR_to_url", ["https://example.com"]]]',
    '[["print", ["hello"]], ["max", [1, 2]], ["max", {"whatever": 1}]]',
    '[["WR_SaveTestObject", {"test_object_name": "a", "anything": 1, "at_all": 2}]]',
    '{"name": "not a script of this framework"}',
])
def test_a_script_the_framework_would_run_has_nothing_wrong(text):
    assert _found(text) == []


def test_text_that_is_not_json_is_said_where_it_stops_being_json():
    found = _adapter().diagnose(_document('[\n  ["WR_quit"],\n  ["WR_to_url" {"url": "x"}]\n]'))

    assert [(each.code, each.range.start, each.severity) for each in found] == [
        ("json-syntax", Position(2, 15), Severity.ERROR)]
    assert found[0].message == WORDS["language_service_json_syntax"]
    assert found[0].source == "je_web_runner"


def test_a_keyword_the_installed_version_does_not_have_is_named_with_the_nearest_one():
    assert _found('[["WR_to_urll", {"url": "x"}]]') == [(
        "unknown-keyword", '"WR_to_urll"',
        "WR_to_urll is not a keyword of WebRunner 0.0.66. Did you mean WR_to_url?")]


def test_a_keyword_like_no_other_is_only_said_to_be_unknown():
    assert _found('[["zzzzzzzz"], ["WR_quit"]]') == [(
        "unknown-keyword", '"zzzzzzzz"', "zzzzzzzz is not a keyword of WebRunner 0.0.66")]


def test_a_parameter_the_keyword_does_not_take_is_named_with_the_nearest_one():
    assert _found('[["WR_to_url", {"url": "x", "urls": "y", "qqqq": 1}]]') == [
        ("unknown-parameter", '"urls"', "WR_to_url has no parameter named urls. Did you mean url?"),
        ("unknown-parameter", '"qqqq"', "WR_to_url has no parameter named qqqq")]


@pytest.mark.parametrize("text", ['[["WR_to_url"]]', '[["WR_to_url", {}]]', '[["WR_to_url", {"urls": 1}]]'])
def test_a_required_parameter_left_out_is_said_at_the_keyword(text):
    assert ("missing-parameter", '"WR_to_url"', "WR_to_url needs url") in _found(text)


def test_every_missing_parameter_is_named_in_order():
    assert _found('[["AC_set_mouse_position", {}]]', "je_auto_control") == [
        ("missing-parameter", '"AC_set_mouse_position"', "AC_set_mouse_position needs x, y")]


def test_a_list_with_too_many_values_is_said_at_the_first_one_too_many():
    assert _found('[["AC_set_mouse_position", [1, 2, 3, 4]]]', "je_auto_control") == [(
        "too-many-values", "3",
        "AC_set_mouse_position takes at most 2 values in a list, and this one gives 4")]


def test_a_list_with_too_few_values_is_said():
    assert _found('[["AC_set_mouse_position", [1]]]', "je_auto_control") == [(
        "too-few-values", "[1]", "AC_set_mouse_position needs at least 2 values in a list, and this one gives 1")]


def test_a_parameter_given_only_by_name_cannot_come_from_a_list():
    metadata = FrameworkMetadata("je_web_runner", "9", {"WR_new": Keyword("WR_new", (
        KeywordParameter("where"), KeywordParameter("mode", ParameterKind.KEYWORD_ONLY)))})

    assert _found('[["WR_new", ["here"]]]', metadata=metadata) == [(
        "missing-parameter", '["here"]',
        "WR_new takes mode by name only: give an object of named values, not a list")]
    assert _found('[["WR_new", {"where": 1, "mode": 2}]]', metadata=metadata) == []


@pytest.mark.parametrize(("text", "covered", "message_key"), [
    ('["WR_quit"]', '"WR_quit"', "language_service_action_not_list"),
    ('[["WR_quit"], 5]', "5", "language_service_action_not_list"),
    ('[["WR_quit"], []]', "[]", "language_service_action_no_keyword"),
    ('[["WR_quit"], [1, {}]]', "1", "language_service_action_no_keyword"),
    ('[["WR_to_url", {"url": "x"}, "extra"]]', '"extra"', "language_service_action_too_long"),
    ('[["WR_to_url", "https://example.com"]]', '"https://example.com"', "language_service_arguments_shape"),
    ('[["WR_to_url", 5]]', "5", "language_service_arguments_shape"),
])
def test_an_action_of_the_wrong_shape_is_said(text, covered, message_key):
    assert _found(text) == [("action-shape", covered, WORDS[message_key])]


def test_what_the_frameworks_key_holds_has_to_be_a_list():
    assert _found('{"webdriver_wrapper": {"WR_quit": 1}}') == [(
        "actions-not-list", '{"WR_quit": 1}', "webdriver_wrapper holds a list of actions")]


def test_every_action_is_checked_and_each_finding_is_an_error_of_the_framework():
    found = _adapter().diagnose(_document('[["WR_nope"], ["WR_to_url"], ["WR_quit", [1]]]'))

    assert [each.code for each in found] == ["unknown-keyword", "missing-parameter", "too-many-values"]
    assert {each.severity for each in found} == {Severity.ERROR}
    assert {each.source for each in found} == {"je_web_runner"}


def test_a_framework_without_a_version_is_named_without_one():
    metadata = dataclasses.replace(METADATA["je_web_runner"], version="")

    assert _found('[["zzzzzzzz"]]', metadata=metadata)[0][2] == "zzzzzzzz is not a keyword of WebRunner"


def test_positions_count_in_utf16_units():
    text = '[["WR_to_url", {"url": "\U0001F600"}], ["WR_nope"]]'

    found = _adapter().diagnose(_document(text))

    assert found[0].range.start == Position(0, text.index('"WR_nope"') + 1)


@pytest.mark.parametrize("text", ["", "  \n", "[]", '{"a": 1}'])
def test_json_that_is_json_has_no_syntax_diagnostic(text):
    assert syntax_diagnostics(text, WORDS) == []


@pytest.mark.parametrize("text", ["[", '{"a" 1}', "[1,]", "nope", "[" * 100000],
                         ids=["open", "no colon", "trailing comma", "a word", "nested too deep"])
def test_text_that_is_not_json_has_one(text):
    found = syntax_diagnostics(text, WORDS)

    assert [each.code for each in found] == ["json-syntax"]
    assert found[0].source == "json"


# ----------------------------------------------------------------------
# Hover and go-to-definition
# ----------------------------------------------------------------------

def test_a_keyword_under_the_cursor_shows_its_signature_and_documentation():
    document, position = _marked('[["WR_to|_url", {"url": "x"}]]')

    hover = _adapter().hover(document, position)

    keyword = METADATA["je_web_runner"].keyword("WR_to_url")
    assert hover.contents == f"WR_to_url(url: str)\n\n{keyword.doc}"
    assert (hover.range.start, hover.range.end) == (Position(0, 2), Position(0, 13))


@pytest.mark.parametrize(("marked", "expected"), [
    ('[["AC_click_mouse", {"mouse_|keycode": "mouse_left"}]]', "mouse_keycode: Union[int, str]\n\nrequired"),
    ('[["AC_click_mouse", {"mouse_keycode": "mouse_left", "x|": 1}]]', "x: int = None\n\noptional"),
])
def test_a_parameter_under_the_cursor_shows_its_type_and_whether_it_is_needed(marked, expected):
    assert _adapter("je_auto_control").hover(*_marked(marked)).contents == expected


@pytest.mark.parametrize("marked", [
    '[["WR_to_url", {"url": "x|"}]]', '[["WR_nope|"]]', '[  |["WR_quit"]]', '[["WR_to_url", {"url|s": 1}]]',
    '|', '{"other": [["WR_|quit"]]}', '[5|]',
])
def test_nothing_is_shown_for_what_is_not_a_keyword_or_a_parameter(marked):
    document, position = _marked(marked)

    assert _adapter().hover(document, position) is None
    assert _adapter().definition(document, position) == []


def test_a_keyword_leads_to_the_line_that_defines_it(tmp_path):
    source = tmp_path / "webdriver_wrapper.py"
    keyword = dataclasses.replace(METADATA["je_web_runner"].keyword("WR_quit"), source_file=str(source), source_line=40)
    metadata = FrameworkMetadata("je_web_runner", "0.0.66", {"WR_quit": keyword})

    found = _adapter(metadata=metadata).definition(*_marked('[["WR_|quit"]]'))

    assert [(location.uri, location.range.start) for location in found] == [(source.as_uri(), Position(39, 0))]


def test_a_keyword_that_does_not_say_where_it_is_defined_leads_nowhere():
    # The fixtures' paths are relative: no file can be named from them
    assert _adapter().definition(*_marked('[["WR_|quit"]]')) == []


# ----------------------------------------------------------------------
# What the adapter says it can do
# ----------------------------------------------------------------------

def test_definition_is_offered_only_when_a_keyword_says_where_it_is():
    everything = {Capability.COMPLETION, Capability.DIAGNOSTICS, Capability.HOVER, Capability.DEFINITION}
    unlocated = FrameworkMetadata("je_web_runner", "1", {"WR_quit": Keyword("WR_quit")})

    assert _adapter().capabilities() == everything
    assert _adapter(metadata=unlocated).capabilities() == everything - {Capability.DEFINITION}


@pytest.mark.parametrize("profile", PROFILES, ids=lambda profile: profile.framework)
def test_every_framework_is_served_by_the_same_adapter(profile):
    service = LanguageService(_adapter(profile.framework))
    name = METADATA[profile.framework].own_keywords()[0].name
    document, position = _marked(f'[["{name[:4]}|')

    assert service.framework == profile.framework
    assert name in [item.label for item in service.complete(document, position)]
    assert [each.code for each in service.diagnose(_document(f'[["{profile.keyword_prefix}no_such_keyword"]]'))] == [
        "unknown-keyword"]


def test_the_adapter_answers_from_the_metadata_it_was_given():
    assert _adapter().metadata is METADATA["je_web_runner"]
    assert _adapter().framework == "je_web_runner"
