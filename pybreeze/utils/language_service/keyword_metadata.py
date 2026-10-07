"""What a framework says about its keywords: their names, parameters, documentation and where each is defined.

None of it is written down in PyBreeze. It is read from the package that is
installed (``metadata_probe.py``), so the editor's answers are those of the
version that will run the script, and a keyword a release adds or renames is
known the day that release is installed.

The shapes here are what crosses from the process that imports the framework
to the one that answers the editor: plain data, written and read as JSON.
"""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import Enum

from pybreeze.utils.exception.exception_tags import language_metadata_shape_error
from pybreeze.utils.exception.exceptions import LanguageServiceException

# The version of the shape written by to_dict(); a reader refuses one it does not know
METADATA_SCHEMA = 1


class ParameterKind(Enum):
    """How a parameter is passed, named as ``inspect.Parameter`` names them."""

    POSITIONAL_ONLY = "POSITIONAL_ONLY"
    POSITIONAL_OR_KEYWORD = "POSITIONAL_OR_KEYWORD"
    VAR_POSITIONAL = "VAR_POSITIONAL"
    KEYWORD_ONLY = "KEYWORD_ONLY"
    VAR_KEYWORD = "VAR_KEYWORD"


# Parameters an action's object of named values can give
_NAMED = frozenset({ParameterKind.POSITIONAL_OR_KEYWORD, ParameterKind.KEYWORD_ONLY})
# Parameters an action's list of values can give, one each
_POSITIONAL = frozenset({ParameterKind.POSITIONAL_ONLY, ParameterKind.POSITIONAL_OR_KEYWORD})


@dataclass(frozen=True)
class KeywordParameter:
    """One parameter of a keyword.

    :param name: its name
    :param kind: how it is passed
    :param required: whether a call must give it
    :param default: its default as Python writes it (``'chrome'``, ``None``); empty when it has none
    :param annotation: its type as the package wrote it; empty when it gave none
    """

    name: str
    kind: ParameterKind = ParameterKind.POSITIONAL_OR_KEYWORD
    required: bool = True
    default: str = ""
    annotation: str = ""

    def written(self) -> str:
        """The parameter as a signature writes it: ``url: str``, ``timeout: int = 30``, ``**kwargs``."""
        stars = {ParameterKind.VAR_POSITIONAL: "*", ParameterKind.VAR_KEYWORD: "**"}.get(self.kind, "")
        text = f"{stars}{self.name}"
        if self.annotation:
            text += f": {self.annotation}"
        if not self.required and not stars:
            text += f" = {self.default}" if self.annotation else f"={self.default}"
        return text


@dataclass(frozen=True)
class Keyword:
    """One name an action may start with, and the function behind it.

    :param name: the keyword (``WR_to_url``)
    :param parameters: its parameters, in order
    :param signature_known: ``False`` when Python cannot tell the function's
        parameters (some built-ins): nothing is then said about its arguments
    :param doc: its documentation, as the package wrote it
    :param source_file: the file that defines it; empty when Python cannot tell
    :param source_line: the line it is defined on, from 1; 0 when unknown
    :param builtin: one of Python's built-in functions, which every framework's executor also offers
    """

    name: str
    parameters: tuple[KeywordParameter, ...] = ()
    signature_known: bool = True
    doc: str = ""
    source_file: str = ""
    source_line: int = 0
    builtin: bool = False

    def signature(self) -> str:
        """The keyword as a call is written: ``WR_to_url(url: str)``; ``name(...)`` when the parameters are unknown."""
        if not self.signature_known:
            return f"{self.name}(...)"
        return f"{self.name}({', '.join(parameter.written() for parameter in self.parameters)})"

    def named(self) -> tuple[KeywordParameter, ...]:
        """The parameters an object of named values can give."""
        return tuple(parameter for parameter in self.parameters if parameter.kind in _NAMED)

    def parameter(self, name: str) -> KeywordParameter | None:
        """The parameter given by the name *name*, or ``None``."""
        return next((parameter for parameter in self.named() if parameter.name == name), None)

    def takes_any_name(self) -> bool:
        """Whether it takes named values it does not list (``**kwargs``)."""
        return any(parameter.kind is ParameterKind.VAR_KEYWORD for parameter in self.parameters)

    def missing(self, given: set[str]) -> list[str]:
        """The parameters a call giving the names *given* must still give, in order."""
        return [parameter.name for parameter in self.parameters
                if parameter.required and parameter.kind in _NAMED | {ParameterKind.POSITIONAL_ONLY}
                and parameter.name not in given]

    def positional_range(self) -> tuple[int, int | None]:
        """How few and how many values a list of values may hold; no upper limit is ``None``."""
        positional = [parameter for parameter in self.parameters if parameter.kind in _POSITIONAL]
        least = sum(1 for parameter in positional if parameter.required)
        unlimited = any(parameter.kind is ParameterKind.VAR_POSITIONAL for parameter in self.parameters)
        return least, None if unlimited else len(positional)

    def needs_a_name(self) -> list[str]:
        """The required parameters a list of values cannot give (keyword-only ones)."""
        return [parameter.name for parameter in self.parameters
                if parameter.required and parameter.kind is ParameterKind.KEYWORD_ONLY]


@dataclass(frozen=True)
class FrameworkMetadata:
    """The keywords of one framework, as the installed package gives them.

    :param framework: the package's import name (``je_web_runner``)
    :param version: the installed version; empty when the package does not say
    :param keywords: every name its executor runs, by name
    """

    framework: str
    version: str = ""
    keywords: Mapping[str, Keyword] = field(default_factory=dict)

    def keyword(self, name: str) -> Keyword | None:
        """The keyword called *name*, or ``None``."""
        return self.keywords.get(name)

    def own_keywords(self) -> list[Keyword]:
        """The framework's own keywords, without Python's built-ins, in name order."""
        return sorted((keyword for keyword in self.keywords.values() if not keyword.builtin),
                      key=lambda keyword: keyword.name)

    def can_locate(self) -> bool:
        """Whether any keyword says where it is defined."""
        return any(keyword.source_file and keyword.source_line for keyword in self.keywords.values())

    def to_dict(self) -> dict:
        """The metadata as JSON-ready data (:func:`metadata_from_dict` reads it back)."""
        return {
            "schema": METADATA_SCHEMA,
            "framework": self.framework,
            "version": self.version,
            "keywords": [
                {
                    "name": keyword.name,
                    "signature_known": keyword.signature_known,
                    "doc": keyword.doc,
                    "source_file": keyword.source_file,
                    "source_line": keyword.source_line,
                    "builtin": keyword.builtin,
                    "parameters": [
                        {"name": parameter.name, "kind": parameter.kind.value, "required": parameter.required,
                         "default": parameter.default, "annotation": parameter.annotation}
                        for parameter in keyword.parameters],
                }
                for keyword in self.keywords.values()],
        }


def _parameter(data: object) -> KeywordParameter:
    if not isinstance(data, dict) or not isinstance(data.get("name"), str):
        raise ValueError("a parameter without a name")
    return KeywordParameter(
        name=data["name"], kind=ParameterKind(data.get("kind", ParameterKind.POSITIONAL_OR_KEYWORD.value)),
        required=bool(data.get("required", True)), default=str(data.get("default", "")),
        annotation=str(data.get("annotation", "")))


def _keyword(data: object) -> Keyword:
    if not isinstance(data, dict) or not isinstance(data.get("name"), str):
        raise ValueError("a keyword without a name")
    parameters = data.get("parameters", [])
    if not isinstance(parameters, list):
        raise ValueError("a keyword whose parameters are not a list")
    line = data.get("source_line", 0)
    return Keyword(
        name=data["name"], parameters=tuple(_parameter(parameter) for parameter in parameters),
        signature_known=bool(data.get("signature_known", True)), doc=str(data.get("doc", "")),
        source_file=str(data.get("source_file", "")),
        source_line=line if isinstance(line, int) and not isinstance(line, bool) and line > 0 else 0,
        builtin=bool(data.get("builtin", False)))


def metadata_from_dict(data: object) -> FrameworkMetadata:
    """Read what :meth:`FrameworkMetadata.to_dict` wrote.

    The data comes from another process, which imported a package PyBreeze did
    not write: every field is checked, and nothing in it is trusted to be there.

    :raises LanguageServiceException: when *data* is not such metadata, or is of
        a schema this version does not read
    """
    framework = data.get("framework") if isinstance(data, dict) else None
    try:
        if not isinstance(framework, str) or not framework or data.get("schema") != METADATA_SCHEMA:
            raise ValueError("no framework, or another schema")
        keywords = data.get("keywords")
        if not isinstance(keywords, list):
            raise ValueError("keywords that are not a list")
        read = [_keyword(keyword) for keyword in keywords]
    except ValueError as error:
        raise LanguageServiceException(
            language_metadata_shape_error.format(framework=framework if isinstance(framework, str) else "?")
        ) from error
    return FrameworkMetadata(
        framework=framework, version=str(data.get("version", "")),
        keywords={keyword.name: keyword for keyword in read})
