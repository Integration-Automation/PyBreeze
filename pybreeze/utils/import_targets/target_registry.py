"""The targets a captured request can be written for, each described once.

A cURL command or a HAR entry is parsed into a :class:`CurlRequest`; a *target*
is one thing that request can be generated as: a ``requests`` script, a pytest
test, an APITestka action. Each target used to be a row in three tables keyed
by the same string (its label, its single-request generator, its
several-request generator), and each tool tab kept a fourth of its own to know
which one wrote JSON. A :class:`TargetDescriptor` says all of it in one place
and an :class:`ImportTargetRegistry` holds them, so a tab asks the registry and
a new target is one registration.

A target also says which parts of a request its output sends
(:attr:`TargetDescriptor.carries`), so what it leaves out can be told before
the output is used rather than found missing afterwards.

Pure logic: nothing here sends the request it describes.
"""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum

from pybreeze.utils.curl_import.curl_parser import CurlRequest
from pybreeze.utils.curl_import.request_body import form_entries, sent_headers


class RequestPart(Enum):
    """A part of a captured request that not every target can write.

    The method, the URL and its query are not here: every target carries them.
    """

    HEADERS = "headers"
    COOKIES = "cookies"
    BODY = "body"
    FORM_FIELDS = "form_fields"
    FILE_UPLOAD = "file_upload"
    BODY_FILE = "body_file"
    COOKIE_FILE = "cookie_file"
    AUTH = "auth"
    TIMEOUT = "timeout"


def _payload_parts(request: CurlRequest) -> set[RequestPart]:
    """The parts *request*'s payload is made of, read as the generators read it.

    A form comes first, then a body read from a file, then an inline body:
    ``request_codegen.payload_python_parts`` writes only the first it finds.
    """
    if request.has_form:
        uploads = [is_file for _name, is_file, _value in form_entries(request)]
        parts: set[RequestPart] = set()
        if any(uploads):
            parts.add(RequestPart.FILE_UPLOAD)
        if not all(uploads):
            parts.add(RequestPart.FORM_FIELDS)
        return parts
    if request.data_file_refs:
        return {RequestPart.BODY_FILE}
    return {RequestPart.BODY} if request.body else set()


def parts_of(request: CurlRequest) -> frozenset[RequestPart]:
    """The parts *request* has, of those a target may not carry.

    :param request: the parsed request
    :return: its parts; empty for a bare ``GET`` of a URL
    """
    present = {
        RequestPart.HEADERS: bool(sent_headers(request)),
        RequestPart.COOKIES: bool(request.cookies),
        RequestPart.COOKIE_FILE: bool(request.cookie_files),
        RequestPart.AUTH: request.username is not None,
        RequestPart.TIMEOUT: request.timeout is not None,
    }
    return frozenset({part for part, has_it in present.items() if has_it} | _payload_parts(request))


@dataclass(frozen=True)
class TargetDescriptor:
    """One thing a captured request can be generated as.

    :param key: the target's stable name: what a selector stores and a caller asks for
    :param label_key: the language-dictionary key of the name shown for it
    :param extension: the extension of a file holding the output, without the dot
    :param generate_one: writes a single request
    :param generate_many: writes several requests into one output, in capture order
    :param carries: the request parts the output sends
    :param single_basename: the name suggested for a file holding one request
    :param batch_basename: the name suggested for a file holding several
    """

    key: str
    label_key: str
    extension: str
    generate_one: Callable[[CurlRequest], str]
    generate_many: Callable[[list[CurlRequest]], str]
    carries: frozenset[RequestPart]
    single_basename: str = "request"
    batch_basename: str = "session"

    def unrepresented(self, request: CurlRequest) -> list[RequestPart]:
        """The parts of *request* this target's output does not send.

        The generator either leaves such a part out or refuses the request;
        which of the two is its own business, and asking here first tells
        either before the output is used.

        :param request: the parsed request
        :return: the missing parts, in the order :class:`RequestPart` lists them
        """
        missing = parts_of(request) - self.carries
        return [part for part in RequestPart if part in missing]


class ImportTargetRegistry:
    """The targets on offer, in the order they were registered; the first is the default."""

    def __init__(self) -> None:
        self._targets: dict[str, TargetDescriptor] = {}

    def register(self, target: TargetDescriptor) -> None:
        """Add *target* after those already registered.

        :raises ValueError: when a target of that key is registered already;
            replacing it would change what an existing selector entry generates
        """
        if target.key in self._targets:
            raise ValueError(f"an import target named {target.key!r} is registered already")
        self._targets[target.key] = target

    def targets(self) -> list[TargetDescriptor]:
        """Every registered target, in registration order."""
        return list(self._targets.values())

    def target(self, key: str) -> TargetDescriptor:
        """The target named *key*, or the default one when none has that name.

        :raises LookupError: when nothing is registered at all
        """
        found = self._targets.get(key)
        if found is not None:
            return found
        if not self._targets:
            raise LookupError("no import target is registered")
        return next(iter(self._targets.values()))

    def generate(self, key: str, requests: list[CurlRequest]) -> str:
        """Generate the output of the target named *key* for *requests*.

        One request is written as the target's single form whichever tool
        asks, so the cURL and HAR importers agree on it.

        :param key: a registered target's key; an unknown one gets the default target
        :param requests: the requests to write, in capture order
        :return: the generated text, or an empty string when there is nothing to write
        """
        if not requests:
            return ""
        target = self.target(key)
        if len(requests) == 1:
            return target.generate_one(requests[0])
        return target.generate_many(requests)
