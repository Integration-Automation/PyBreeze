"""A captured request as it is sent, whichever tool captured it.

The cURL parser and the HAR parser both fill a :class:`CurlRequest`, which is
the record of a parse: it holds what a command line said (``-G``, ``-I``,
whether ``-X`` named the method, form fragments in curl's own syntax, the
position of each ``@file`` among the data). What is *sent* has to be worked out
from it, and each generator did part of that working-out for itself.

A :class:`NormalizedRequest` is the result, worked out once: the method, the
whole URL, the headers and cookies that go out, one payload of one kind, the
credentials and the time limit. It is immutable, and nothing in it is curl's
or HAR's. A target written against it needs to know neither.

Pure data: normalising a request sends nothing.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from pybreeze.utils.curl_import.curl_parser import CurlRequest
from pybreeze.utils.curl_import.request_body import FormEntry, body_kind, form_entries, sent_headers

# The method a request has when nothing asks for another
DEFAULT_METHOD = "GET"


class PayloadKind(Enum):
    """What a request carries as its body."""

    NONE = "none"
    RAW = "raw"            # text, sent as it is
    JSON = "json"          # a JSON value the body parses to and comes back from unchanged
    FORM = "form"          # a multipart form: text fields, file uploads, or both
    FILES = "files"        # read from one or more files when the request is sent


@dataclass(frozen=True)
class Payload:
    """The body of a request, of one kind.

    :param kind: which of the fields below holds it
    :param text: the body's text (``RAW`` and ``JSON``)
    :param value: what the body parses to (``JSON``)
    :param fields: the form's entries as ``(name, is a file, value or file name)`` (``FORM``)
    :param files: the files the body is read from, in the order they are sent (``FILES``)
    """

    kind: PayloadKind = PayloadKind.NONE
    text: str = ""
    value: object = None
    fields: tuple[FormEntry, ...] = ()
    files: tuple[str, ...] = ()


@dataclass(frozen=True)
class NormalizedRequest:
    """One request as it goes out.

    :param method: the HTTP method, upper-case
    :param url: the whole URL, its query included
    :param headers: the headers a generated request sets, in order; one a client
        writes for itself (a form's ``Content-Type``) is not among them
    :param cookies: the cookies sent, as ``(name, value)``
    :param payload: the body
    :param username: the basic-auth user, or ``None``
    :param password: the basic-auth password; empty when a user is given without one
    :param timeout: the time limit in seconds, or ``None`` when there is none
    :param cookie_files: files the cookies were to be read from, which nothing here reads
    """

    method: str
    url: str
    headers: tuple[tuple[str, str], ...] = ()
    cookies: tuple[tuple[str, str], ...] = ()
    payload: Payload = Payload()
    username: str | None = None
    password: str = ""
    timeout: float | None = None
    cookie_files: tuple[str, ...] = ()


def _payload(request: CurlRequest) -> Payload:
    """The one payload *request* sends: a form first, then a body read from files, then an inline body.

    The order is the generators' (``request_codegen.payload_python_parts``):
    each writes only the first it finds.
    """
    if request.has_form:
        fields = tuple(form_entries(request))
        return Payload(PayloadKind.FORM, fields=fields) if fields else Payload()
    if request.data_file_refs:
        return Payload(PayloadKind.FILES, text=request.body, files=tuple(request.data_file_refs))
    kind = body_kind(request)
    if kind is None:
        return Payload()
    if kind[0] == "json":
        return Payload(PayloadKind.JSON, text=request.body, value=kind[1])
    return Payload(PayloadKind.RAW, text=request.body)


def normalize(request: CurlRequest) -> NormalizedRequest:
    """Work out what *request* sends.

    :param request: a parsed cURL command or HAR entry
    :return: the request as it goes out
    """
    return NormalizedRequest(
        method=request.method,
        url=request.full_url,
        headers=tuple(sent_headers(request).items()),
        cookies=tuple(request.cookies.items()),
        payload=_payload(request),
        username=request.username,
        password=request.password or "",
        # The parser has checked that it is a number
        timeout=None if request.timeout is None else float(request.timeout),
        cookie_files=tuple(request.cookie_files),
    )
