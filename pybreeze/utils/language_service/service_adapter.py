"""What a framework's language service gives an editor, in one shape for every framework.

AutoControl, WebRunner and LoadDensity each have their own keywords, their own
parameters and their own way of saying what a script may hold. An editor that
asked each of them in its own way would hold three language features. A
:class:`LanguageServiceAdapter` is the one way it asks: completion and
diagnostics from every adapter, hover and go-to-definition from those whose
framework has the metadata for it. An adapter says which it can do
(:meth:`LanguageServiceAdapter.capabilities`), and says it each time it is
asked, because the answer depends on the framework version installed.

The editor never calls an adapter directly. It goes through a
:class:`LanguageService`, which asks only for what the adapter says it can do
and keeps a failing adapter to itself: a framework's mistake costs a
completion list, not the IDE.

The types are the Language Server Protocol's, so an adapter can sit behind a
real language server later without the editor's side changing. Pure logic: no
Qt, and no framework is imported here.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum
from typing import TypeVar

from pybreeze.utils.logging.logger import pybreeze_logger

_Answer = TypeVar("_Answer")

# Above this code point a character takes two UTF-16 code units
_LAST_BMP_CODE_POINT = 0xFFFF


class Capability(Enum):
    """Something a language service may be able to do."""

    COMPLETION = "completion"
    DIAGNOSTICS = "diagnostics"
    HOVER = "hover"
    DEFINITION = "definition"


class Severity(Enum):
    """How serious a diagnostic is, numbered as the protocol numbers them."""

    ERROR = 1
    WARNING = 2
    INFORMATION = 3
    HINT = 4


@dataclass(frozen=True)
class Position:
    """A place in a document.

    :param line: the line, from 0
    :param character: the offset in that line, from 0, in UTF-16 code units:
        the protocol's default, and what Qt's text cursor counts in. A
        character outside the Basic Multilingual Plane (an emoji) is two;
        :func:`utf16_offset` and :func:`index_at` convert to and from a
        Python index
    """

    line: int
    character: int


@dataclass(frozen=True)
class Range:
    """A stretch of a document, from *start* up to but not including *end*."""

    start: Position
    end: Position


@dataclass(frozen=True)
class TextDocument:
    """The text a service is asked about.

    :param uri: what names the document (a file URI, or any stable name for an unsaved one)
    :param text: its whole text
    :param version: a number that grows with every change, so an answer can be matched to the text it was for
    """

    uri: str
    text: str
    version: int = 0


@dataclass(frozen=True)
class Diagnostic:
    """Something wrong with a stretch of a document.

    :param range: where it is
    :param message: what is wrong
    :param severity: how serious it is
    :param code: the rule's stable name, when it has one
    :param source: who found it: the framework's import name
    """

    range: Range
    message: str
    severity: Severity = Severity.ERROR
    code: str = ""
    source: str = ""


@dataclass(frozen=True)
class CompletionItem:
    """One thing that may be written at a position.

    :param label: what the list shows, and what is inserted when *insert_text* is not given
    :param detail: a short note beside the label (a signature)
    :param documentation: what it does
    :param insert_text: the text to insert, when it is not the label
    """

    label: str
    detail: str = ""
    documentation: str = ""
    insert_text: str | None = None


@dataclass(frozen=True)
class Hover:
    """What to show for the thing at a position.

    :param contents: the text to show
    :param range: the stretch it is about, when the service knows
    """

    contents: str
    range: Range | None = None


@dataclass(frozen=True)
class Location:
    """A stretch of some document: where a keyword is defined."""

    uri: str
    range: Range


def utf16_offset(line: str, index: int) -> int:
    """The :attr:`Position.character` of the character at *index* of *line*."""
    return sum(2 if ord(character) > _LAST_BMP_CODE_POINT else 1 for character in line[:max(index, 0)])


def index_at(line: str, character: int) -> int:
    """The index in *line* of the character at the UTF-16 offset *character*.

    :return: an offset past the end gives ``len(line)``; one that falls inside
        a character gives that character
    """
    units = 0
    for index, each in enumerate(line):
        units += 2 if ord(each) > _LAST_BMP_CODE_POINT else 1
        if units > character:
            return index
    return len(line)


class LanguageServiceAdapter(ABC):
    """One framework's language service.

    Completion and diagnostics are what every adapter provides; hover and
    go-to-definition are for those whose framework can tell.
    """

    @property
    @abstractmethod
    def framework(self) -> str:
        """The framework's package, by its import name (``je_web_runner``)."""

    @abstractmethod
    def capabilities(self) -> frozenset[Capability]:
        """What this adapter can do with the framework as it is installed now.

        Asked before every request: a framework that is missing, or older than
        the metadata an answer needs, gives fewer.
        """

    @abstractmethod
    def complete(self, document: TextDocument, position: Position) -> list[CompletionItem]:
        """What may be written at *position* of *document*."""

    @abstractmethod
    def diagnose(self, document: TextDocument) -> list[Diagnostic]:
        """What is wrong with *document*."""

    def hover(self, document: TextDocument, position: Position) -> Hover | None:
        """What to show for the thing at *position* of *document*; ``None`` when there is nothing."""
        return None

    def definition(self, document: TextDocument, position: Position) -> list[Location]:
        """Where the thing at *position* of *document* is defined."""
        return []


class LanguageService:
    """An adapter as the editor sees it: asked only for what it can do, its failures kept here.

    :param adapter: the framework's adapter
    """

    def __init__(self, adapter: LanguageServiceAdapter) -> None:
        self._adapter = adapter
        self.framework = adapter.framework

    def capabilities(self) -> frozenset[Capability]:
        """What the adapter can do now; nothing when it cannot even say."""
        return self._guarded(self._adapter.capabilities, frozenset(), "capabilities")

    def complete(self, document: TextDocument, position: Position) -> list[CompletionItem]:
        """What may be written at *position*; nothing from an adapter without completion."""
        return self._ask(Capability.COMPLETION, lambda: self._adapter.complete(document, position), [])

    def diagnose(self, document: TextDocument) -> list[Diagnostic]:
        """What is wrong with *document*; nothing from an adapter without diagnostics."""
        return self._ask(Capability.DIAGNOSTICS, lambda: self._adapter.diagnose(document), [])

    def hover(self, document: TextDocument, position: Position) -> Hover | None:
        """What to show at *position*; ``None`` from an adapter without hover."""
        return self._ask(Capability.HOVER, lambda: self._adapter.hover(document, position), None)

    def definition(self, document: TextDocument, position: Position) -> list[Location]:
        """Where the thing at *position* is defined; nothing from an adapter without go-to-definition."""
        return self._ask(Capability.DEFINITION, lambda: self._adapter.definition(document, position), [])

    def _ask(self, capability: Capability, call: Callable[[], _Answer], nothing: _Answer) -> _Answer:
        """*call*'s answer when the adapter has *capability*, else *nothing*."""
        if capability not in self.capabilities():
            return nothing
        return self._guarded(call, nothing, capability.value)

    def _guarded(self, call: Callable[[], _Answer], nothing: _Answer, asked_for: str) -> _Answer:
        """*call*'s answer, or *nothing* when it raises."""
        try:
            return call()
        except Exception as error:  # noqa: BLE001 — an adapter runs a framework's code and the editor must outlive it
            pybreeze_logger.error(
                "language service for %s failed at %s: %r", self.framework, asked_for, error)
            return nothing


class LanguageServiceRegistry:
    """The language services on offer, one per framework."""

    def __init__(self) -> None:
        self._services: dict[str, LanguageService] = {}

    def register(self, adapter: LanguageServiceAdapter) -> None:
        """Offer *adapter* as its framework's language service.

        :raises ValueError: when that framework has one already
        """
        service = LanguageService(adapter)
        if service.framework in self._services:
            raise ValueError(f"{service.framework!r} has a language service already")
        self._services[service.framework] = service

    def frameworks(self) -> list[str]:
        """The frameworks that have a service, in registration order."""
        return list(self._services)

    def service_for(self, framework: str) -> LanguageService | None:
        """The service of *framework*, or ``None`` when it has none."""
        return self._services.get(framework)
