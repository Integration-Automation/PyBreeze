"""The import targets: each described once, and what each says it sends is what it writes."""
from __future__ import annotations

import ast
from pathlib import Path

import pytest

import pybreeze
from pybreeze.extend_multi_language.extend_english import pybreeze_english_word_dict
from pybreeze.utils.curl_import.curl_parser import CurlRequest, parse_curl
from pybreeze.utils.exception.exceptions import CurlParseException
from pybreeze.utils.import_targets.builtin_targets import IMPORT_TARGETS
from pybreeze.utils.import_targets.target_registry import (
    ImportTargetRegistry,
    RequestPart,
    TargetDescriptor,
    parts_of,
)

_URL = "https://x.example/api"
_TOOL_TABS = Path(pybreeze.__file__).parent / "pybreeze_ui" / "tools_gui"

# For each part: curl options that give a request that part alone, and text
# the generated output holds (in any case) only when it sends the part. A
# payload makes curl send a POST, which is a part of its own, so those samples
# name the method: curl then keeps it.
_PART_SAMPLES = {
    RequestPart.METHOD: ("-X DELETE", "delete"),
    RequestPart.HEADERS: ("-H 'X-Marker: mark-headers'", "mark-headers"),
    RequestPart.COOKIES: ("-b 'c=mark-cookies'", "mark-cookies"),
    RequestPart.BODY: ("-X GET -d 'mark-body=1'", "mark-body"),
    RequestPart.FORM_FIELDS: ("-X GET -F 'f=mark-form'", "mark-form"),
    RequestPart.FILE_UPLOAD: ("-X GET -F 'f=@mark-upload.bin'", "mark-upload"),
    RequestPart.BODY_FILE: ("-X GET -d @mark-bodyfile.bin", "mark-bodyfile"),
    RequestPart.COOKIE_FILE: ("-b mark-cookiefile.txt", "mark-cookiefile"),
    RequestPart.AUTH: ("-u mark-user:pw", "mark-user"),
    RequestPart.TIMEOUT: ("-m 7", "timeout"),
}


def _request_with(part: RequestPart) -> CurlRequest:
    return parse_curl(f"curl {_URL} {_PART_SAMPLES[part][0]}")


def _code_lines(output: str) -> str:
    """*output* in lower case without its comment lines: a comment names a part without sending it."""
    return "\n".join(line for line in output.lower().splitlines() if not line.lstrip().startswith("#"))


class TestPartsOf:
    def test_a_bare_get_has_none(self):
        assert parts_of(parse_curl(f"curl {_URL}?a=1")) == frozenset()

    def test_every_part_has_a_sample(self):
        assert set(_PART_SAMPLES) == set(RequestPart)

    @pytest.mark.parametrize("part", list(RequestPart))
    def test_each_part_is_found_alone(self, part):
        assert parts_of(_request_with(part)) == {part}

    def test_data_moved_to_the_query_is_not_a_body(self):
        # -G: curl sends the data in the URL, which every target carries
        assert parts_of(parse_curl(f"curl -G {_URL} -d a=1")) == frozenset()

    def test_a_form_of_text_and_a_file_is_both(self):
        request = parse_curl(f"curl {_URL} -F 'a=text' -F 'b=@up.bin'")

        assert parts_of(request) == {RequestPart.METHOD, RequestPart.FORM_FIELDS, RequestPart.FILE_UPLOAD}

    def test_a_header_left_to_requests_is_not_one_the_output_sends(self):
        # The form's own Content-Type is written by requests, with its boundary
        request = parse_curl(f"curl {_URL} -H 'Content-Type: multipart/form-data' -F 'a=text'")

        assert parts_of(request) == {RequestPart.METHOD, RequestPart.FORM_FIELDS}

    def test_a_payload_makes_the_request_a_post_which_is_a_part_too(self):
        assert parts_of(parse_curl(f"curl {_URL} -d a=1")) == {RequestPart.METHOD, RequestPart.BODY}

    def test_a_json_body_is_a_body(self):
        request = parse_curl(f"curl -X GET {_URL} -H 'Content-Type: application/json' -d '{{}}'")

        assert parts_of(request) == {RequestPart.HEADERS, RequestPart.BODY}

    def test_a_bearer_token_is_a_header(self):
        assert parts_of(parse_curl(f"curl {_URL} --oauth2-bearer t0ken")) == {RequestPart.HEADERS}


class TestBuiltinTargets:
    def test_every_label_is_in_the_dictionary(self):
        missing = [target.key for target in IMPORT_TARGETS.targets()
                   if target.label_key not in pybreeze_english_word_dict]

        assert missing == []

    def test_the_action_lists_are_json_and_the_rest_is_python(self):
        written_as = {target.key: (target.extension, target.single_basename, target.batch_basename)
                      for target in IMPORT_TARGETS.targets()}

        assert written_as.pop("apitestka_action") == ("json", "action", "actions")
        assert written_as.pop("webrunner_action") == ("json", "web_action", "web_actions")
        assert set(written_as.values()) == {("py", "request", "session")}

    def test_only_a_browser_cannot_make_another_method(self):
        without = [target.key for target in IMPORT_TARGETS.targets() if RequestPart.METHOD not in target.carries]

        assert without == ["webrunner_action"]

    @pytest.mark.parametrize("part", list(RequestPart))
    @pytest.mark.parametrize("target", IMPORT_TARGETS.targets(), ids=lambda target: target.key)
    def test_a_target_sends_the_parts_it_says_and_no_other(self, target, part):
        request = _request_with(part)
        marker = _PART_SAMPLES[part][1]
        carried = part in target.carries

        for generate in (lambda: target.generate_one(request), lambda: target.generate_many([request, request])):
            try:
                output = generate()
            except CurlParseException:
                # A target may refuse a part it cannot write, never one it says it sends
                assert not carried
                continue
            assert (marker in _code_lines(output)) is carried

    @pytest.mark.parametrize("part", list(RequestPart))
    @pytest.mark.parametrize("target", IMPORT_TARGETS.targets(), ids=lambda target: target.key)
    def test_unrepresented_names_what_is_left_out(self, target, part):
        expected = [] if part in target.carries else [part]

        assert target.unrepresented(_request_with(part)) == expected

    def test_unrepresented_lists_parts_in_their_declared_order(self):
        loaddensity = IMPORT_TARGETS.target("loaddensity_python")
        request = parse_curl(f"curl {_URL} -m 7 -u user:pw -d 'a=1' -H 'X-A: 1'")

        assert loaddensity.unrepresented(request) == [
            RequestPart.HEADERS, RequestPart.BODY, RequestPart.AUTH, RequestPart.TIMEOUT]


def test_no_tool_tab_names_a_target():
    # A tab that knows a target by name is a second place to change for every
    # new one: the tabs kept an `_JSON_TARGET` each to tell which wrote JSON
    keys = {target.key for target in IMPORT_TARGETS.targets()}
    named = []
    for source in sorted(_TOOL_TABS.glob("*.py")):
        tree = ast.parse(source.read_text(encoding="utf-8"), filename=str(source))
        named.extend(
            f"{source.name}:{node.lineno}" for node in ast.walk(tree)
            if isinstance(node, ast.Constant) and isinstance(node.value, str) and node.value in keys)

    assert named == []


def _target(key: str) -> TargetDescriptor:
    return TargetDescriptor(
        key=key, label_key=f"label_{key}", extension="txt",
        generate_one=lambda request: f"{key} one {request.url}",
        generate_many=lambda requests: f"{key} many {len(requests)}",
        carries=frozenset())


class TestRegistry:
    def test_targets_keep_their_registration_order(self):
        registry = ImportTargetRegistry()
        for key in ("b", "a", "c"):
            registry.register(_target(key))

        assert [target.key for target in registry.targets()] == ["b", "a", "c"]

    def test_a_key_registers_once(self):
        registry = ImportTargetRegistry()
        registry.register(_target("a"))

        with pytest.raises(ValueError, match="'a'"):
            registry.register(_target("a"))

    def test_an_unknown_key_gets_the_first_target(self):
        registry = ImportTargetRegistry()
        for key in ("first", "second"):
            registry.register(_target(key))

        assert registry.target("second").key == "second"
        assert registry.target("missing").key == "first"

    def test_an_empty_registry_has_no_target_to_give(self):
        with pytest.raises(LookupError):
            ImportTargetRegistry().target("anything")

    def test_nothing_to_write_is_an_empty_output(self):
        assert ImportTargetRegistry().generate("anything", []) == ""

    def test_one_request_is_written_in_the_single_form(self):
        registry = ImportTargetRegistry()
        registry.register(_target("a"))

        assert registry.generate("a", [CurlRequest(url=_URL)]) == f"a one {_URL}"

    def test_several_requests_are_written_in_the_batch_form(self):
        registry = ImportTargetRegistry()
        registry.register(_target("a"))

        assert registry.generate("a", [CurlRequest(url=_URL)] * 3) == "a many 3"

    def test_the_targets_list_is_a_copy(self):
        registry = ImportTargetRegistry()
        registry.register(_target("a"))
        registry.targets().clear()

        assert [target.key for target in registry.targets()] == ["a"]
