"""Say what the chosen import target leaves out of the requests it is given.

A target may not be able to send everything a captured request holds: a
LoadDensity run drives a URL, a WebRunner action visits a page. Each target
declares what its output sends (``TargetDescriptor.carries``), and the cURL and
HAR tabs show this line under the output, so a header or a body that did not
make it into the script is named before the script is run instead of being
found missing afterwards.
"""
from __future__ import annotations

from je_editor import language_wrapper

from pybreeze.utils.curl_import.curl_parser import CurlRequest
from pybreeze.utils.import_targets.target_registry import RequestPart, TargetDescriptor

# Each part and the language key of its name
_PART_WORDS: dict[RequestPart, str] = {
    RequestPart.METHOD: "request_part_method",
    RequestPart.HEADERS: "request_part_headers",
    RequestPart.COOKIES: "request_part_cookies",
    RequestPart.BODY: "request_part_body",
    RequestPart.FORM_FIELDS: "request_part_form_fields",
    RequestPart.FILE_UPLOAD: "request_part_file_upload",
    RequestPart.BODY_FILE: "request_part_body_file",
    RequestPart.COOKIE_FILE: "request_part_cookie_file",
    RequestPart.AUTH: "request_part_auth",
    RequestPart.TIMEOUT: "request_part_timeout",
}
# Between two parts in the line: the same in every language, where a comma would not be
_BETWEEN_PARTS = " · "


def gaps_text(target: TargetDescriptor, requests: list[CurlRequest]) -> str:
    """The line naming what *target* does not send of *requests*; empty when it sends all of it.

    Each part is named once however many of the requests have it, in the order
    ``RequestPart`` lists them.

    :param target: the target the output is generated for
    :param requests: the requests the output was generated from
    """
    missing = {part for request in requests for part in target.unrepresented(request)}
    if not missing:
        return ""
    word = language_wrapper.language_word_dict
    names = [word.get(_PART_WORDS[part]) for part in RequestPart if part in missing]
    return word.get("import_target_gaps_note").format(parts=_BETWEEN_PARTS.join(names))
