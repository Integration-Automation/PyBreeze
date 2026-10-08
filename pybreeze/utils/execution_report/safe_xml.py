"""Read an XML report without letting the file do anything but be read.

A report is a file from somewhere. XML can declare entities that expand to
gigabytes (the "billion laughs") or name files and URLs to be fetched; no
report needs either, so a document that declares a document type at all is
refused. What is left is read into a small tree, no deeper than
:data:`MAX_DEPTH` and with no more elements than :data:`MAX_ELEMENTS`.

Writing is the other half: :func:`write_xml` escapes everything it is given and
leaves out the characters XML 1.0 cannot hold, so that what is written can be
read back by any parser.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
# The parser rejects all DTD and entity declarations in parse_xml before expansion.
# nosemgrep: python.lang.security.use-defused-xml.use-defused-xml
from xml.parsers import expat
# These functions only escape output text and attributes, never parse input.
# nosemgrep: python.lang.security.use-defused-xml.use-defused-xml
from xml.sax.saxutils import escape, quoteattr  # nosec B406 - output escaping only

from pybreeze.utils.exception.exception_tags import report_xml_error
from pybreeze.utils.exception.exceptions import ExecutionReportException

MAX_DEPTH = 64
MAX_ELEMENTS = 500_000
# What XML 1.0 has no way to write: the control characters but tab, line feed
# and carriage return, the surrogates, and the two non-characters at the end of the plane
_NOT_XML = re.compile("[\x00-\x08\x0b\x0c\x0e-\x1f\ud800-\udfff￾￿]")


@dataclass
class XmlElement:
    """An element: its tag, its attributes, the text directly in it, and its child elements."""

    tag: str
    attributes: dict[str, str] = field(default_factory=dict)
    text: str = ""
    children: list[XmlElement] = field(default_factory=list)

    def child(self, tag: str) -> XmlElement | None:
        """The first child element called *tag*, or ``None``."""
        return next((each for each in self.children if each.tag == tag), None)

    def all(self, tag: str) -> list[XmlElement]:
        """The child elements called *tag*."""
        return [each for each in self.children if each.tag == tag]


class _Builder:
    """Builds the tree as the parser goes, and stops a document that is too deep, too large, or declares a type."""

    def __init__(self) -> None:
        self.root: XmlElement | None = None
        self._open: list[XmlElement] = []
        self._elements = 0

    def start(self, tag: str, attributes: dict[str, str]) -> None:
        self._elements += 1
        if len(self._open) >= MAX_DEPTH or self._elements > MAX_ELEMENTS:
            raise ExecutionReportException(report_xml_error)
        element = XmlElement(tag, dict(attributes))
        if self._open:
            self._open[-1].children.append(element)
        elif self.root is None:
            self.root = element
        self._open.append(element)

    def end(self, _tag: str) -> None:
        self._open.pop()

    def text(self, data: str) -> None:
        if self._open:
            self._open[-1].text += data

    @staticmethod
    def refuse(*_declaration) -> None:
        raise ExecutionReportException(report_xml_error)


def parse_xml(text: str) -> XmlElement:
    """The root element of the XML document *text*.

    :raises ExecutionReportException: when *text* is not well-formed XML,
        declares a document type or an entity, or is deeper or larger than a
        report is
    """
    builder = _Builder()
    # The text is already text: whatever encoding its declaration names, it is given as UTF-8
    parser = expat.ParserCreate("utf-8")
    parser.buffer_text = True
    parser.StartElementHandler = builder.start
    parser.EndElementHandler = builder.end
    parser.CharacterDataHandler = builder.text
    parser.StartDoctypeDeclHandler = builder.refuse
    parser.EntityDeclHandler = builder.refuse
    try:
        parser.Parse(text.encode("utf-8", "replace"), True)
    except expat.ExpatError as error:
        raise ExecutionReportException(report_xml_error) from error
    if builder.root is None:
        raise ExecutionReportException(report_xml_error)
    return builder.root


def xml_text(value: object) -> str:
    """*value* as text XML can hold: what it cannot is left out."""
    return _NOT_XML.sub("", str(value))


def _written(element: XmlElement, depth: int, lines: list[str]) -> None:
    indent = "  " * depth
    attributes = "".join(f" {name}={quoteattr(xml_text(value))}" for name, value in element.attributes.items())
    text = escape(xml_text(element.text))
    if not element.children and not text:
        lines.append(f"{indent}<{element.tag}{attributes}/>")
    elif not element.children:
        lines.append(f"{indent}<{element.tag}{attributes}>{text}</{element.tag}>")
    else:
        lines.append(f"{indent}<{element.tag}{attributes}>{text}")
        for child in element.children:
            _written(child, depth + 1, lines)
        lines.append(f"{indent}</{element.tag}>")


def write_xml(root: XmlElement) -> str:
    """*root* as an XML document, everything in it escaped.

    Tags and attribute names are the writer's own and are written as given;
    text and attribute values may be anything.
    """
    lines = ['<?xml version="1.0" encoding="UTF-8"?>']
    _written(root, 0, lines)
    return "\n".join(lines) + "\n"
