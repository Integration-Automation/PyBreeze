"""The language service of an action script, from the keywords its framework has installed.

WebRunner, AutoControl and LoadDensity scripts have one shape, a JSON list of
``["keyword"]`` or ``["keyword", arguments]``, so one adapter serves all three:
given a framework's profile and the metadata its package gave
(``metadata_probe.py``), it answers the editor in the one way every language
service does (``service_adapter.py``).

- **Completion**: keywords where an action's name goes, a keyword's parameters
  where an argument's name goes, the framework's key at the top of an object.
- **Diagnostics**: a keyword the installed version does not have, a parameter
  the keyword does not take, a required one that is missing, a list of values
  of the wrong length, an action of the wrong shape, and text that is not JSON.
- **Hover**: a keyword's signature and documentation; a parameter's type and default.
- **Go to definition**: the file and line that define a keyword, where Python can tell.

Nothing here imports a framework, and nothing here is Qt.
"""
from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from difflib import get_close_matches
from pathlib import Path

from pybreeze.utils.language_service.framework_profiles import PROFILES, FrameworkProfile
from pybreeze.utils.language_service.json_scan import (
    ARRAY, OBJECT, STRING, CursorContext, Frame, LineIndex, Located, context_at, locate,
)
from pybreeze.utils.language_service.keyword_metadata import FrameworkMetadata, Keyword
from pybreeze.utils.language_service.service_adapter import (
    Capability, CompletionItem, Diagnostic, Hover, LanguageServiceAdapter, Location, Position, Range,
    TextDocument,
)

# A script that names the framework's key is that framework's, whatever else it holds
_KEY_SCORE = 1_000_000
# How many values an action's list holds at most: a keyword and its arguments
_ACTION_LENGTH = 2


def syntax_diagnostics(text: str, words: Mapping[str, str], source: str = "json") -> list[Diagnostic]:
    """One diagnostic where *text* stops being JSON; nothing for text that is JSON, or empty.

    What the frameworks' own ``json.load`` accepts is accepted here.
    """
    if not text.strip():
        return []
    try:
        json.loads(text)
    except json.JSONDecodeError as error:
        place = Position(max(error.lineno - 1, 0), max(error.colno - 1, 0))
    except (ValueError, RecursionError):
        place = Position(0, 0)
    else:
        return []
    return [Diagnostic(Range(place, Position(place.line, place.character + 1)),
                       words["language_service_json_syntax"], code="json-syntax", source=source)]


def action_list(root: Located | None, profile: FrameworkProfile) -> Located | None:
    """The value that holds *profile*'s actions in a script: the script itself, or what its key holds."""
    if root is None or root.kind == ARRAY:
        return root
    if root.kind != OBJECT:
        return None
    return next((value for key, value in root.members if key.value == profile.document_key), None)


def _action_names(actions: Located | None) -> list[str]:
    if actions is None or actions.kind != ARRAY:
        return []
    return [action.items[0].value for action in actions.items
            if action.kind == ARRAY and action.items and action.items[0].kind == STRING]


def script_score(root: Located | None, profile: FrameworkProfile, metadata: FrameworkMetadata | None) -> int:
    """How much the script at *root* looks like one of *profile*'s framework; 0 when not at all."""
    if root is None:
        return 0
    if root.kind == OBJECT:
        return _KEY_SCORE if any(key.value == profile.document_key for key, _value in root.members) else 0
    own = {keyword.name for keyword in metadata.own_keywords()} if metadata is not None else set()
    return sum(1 for name in _action_names(root) if name in own or name.startswith(profile.keyword_prefix))


def framework_of(text: str, metadata: Mapping[str, FrameworkMetadata]) -> FrameworkProfile | None:
    """Whose script *text* is, or ``None`` when it is nobody's (any other JSON file).

    :param text: the script; it need not be JSON yet
    :param metadata: the metadata at hand, by framework; a framework without any is told by its keywords' prefix
    """
    root = locate(text)
    scores = [(script_score(root, profile, metadata.get(profile.framework)), profile) for profile in PROFILES]
    best = max(scores, key=lambda scored: scored[0])
    return best[1] if best[0] > 0 else None


@dataclass(frozen=True)
class _Place:
    """Where in a script the cursor stands: where a keyword goes, or a parameter of *keyword*, or the framework's key."""

    kind: str
    keyword: str = ""
    given: tuple[str, ...] = ()


_KEYWORD_PLACE, _PARAMETER_PLACE, _KEY_PLACE = "keyword", "parameter", "key"


def _place(frames: tuple[Frame, ...], document_key: str) -> _Place | None:
    """What may be written where *frames* leave the cursor, or ``None`` when it is nothing this service knows."""
    if len(frames) == 1 and frames[0].kind == OBJECT and frames[0].key is None:
        return _Place(_KEY_PLACE, given=frames[0].keys)
    under_key = len(frames) > 1 and frames[0].kind == OBJECT and frames[0].key == document_key
    inside = frames[1:] if under_key else frames
    if not inside or any(frame.kind != ARRAY for frame in inside[:2]):
        return None
    if len(inside) == _ACTION_LENGTH and inside[1].index == 0:
        return _Place(_KEYWORD_PLACE)
    arguments = inside[2] if len(inside) == _ACTION_LENGTH + 1 else None
    if (arguments is not None and arguments.kind == OBJECT and arguments.key is None
            and inside[1].index == 1 and inside[1].first is not None):
        return _Place(_PARAMETER_PLACE, keyword=inside[1].first, given=arguments.keys)
    return None


class ActionLanguageAdapter(LanguageServiceAdapter):
    """Completion, diagnostics, hover and go-to-definition for one framework's action scripts.

    :param profile: the framework
    :param metadata: its keywords, as the installed package gave them
    :param words: the messages, by language key (a PyBreeze dictionary)
    """

    def __init__(self, profile: FrameworkProfile, metadata: FrameworkMetadata, words: Mapping[str, str]) -> None:
        self._profile = profile
        self._metadata = metadata
        self._words = words
        # The framework as a message names it: "WebRunner 0.0.66"
        self._name = f"{profile.label} {metadata.version}".strip()

    @property
    def framework(self) -> str:
        return self._profile.framework

    @property
    def metadata(self) -> FrameworkMetadata:
        """The keywords this adapter answers from."""
        return self._metadata

    def capabilities(self) -> frozenset[Capability]:
        found = {Capability.COMPLETION, Capability.DIAGNOSTICS, Capability.HOVER}
        if self._metadata.can_locate():
            found.add(Capability.DEFINITION)
        return frozenset(found)

    # ------------------------------------------------------------------
    # Completion
    # ------------------------------------------------------------------

    def complete(self, document: TextDocument, position: Position) -> list[CompletionItem]:
        offset = LineIndex(document.text).offset(position)
        context = context_at(document.text, offset)
        place = _place(context.frames, self._profile.document_key)
        if place is None:
            return []
        if place.kind == _KEY_PLACE:
            names = [] if self._profile.document_key in place.given else [self._profile.document_key]
            return [self._item(name, context) for name in names]
        if place.kind == _KEYWORD_PLACE:
            own = self._metadata.own_keywords()
            builtins = sorted((keyword for keyword in self._metadata.keywords.values() if keyword.builtin),
                              key=lambda keyword: keyword.name)
            return [self._item(keyword.name, context, keyword.signature(), keyword.doc)
                    for keyword in (*own, *builtins)]
        keyword = self._metadata.keyword(place.keyword)
        if keyword is None:
            return []
        given = {*place.given, *self._names_around(document.text, offset)}
        return [self._item(parameter.name, context, parameter.written())
                for parameter in keyword.named() if parameter.name not in given]

    def _names_around(self, text: str, offset: int) -> set[str]:
        """The names the action at *offset* gives anywhere, also after the cursor; not the one the cursor is in."""
        actions = action_list(locate(text), self._profile)
        for action in (actions.items if actions is not None and actions.kind == ARRAY else ()):
            if action.kind == ARRAY and action.holds(offset) and len(action.items) > 1:
                return {key.value for key, _value in action.items[1].members if not key.holds(offset)}
        return set()

    @staticmethod
    def _item(name: str, context: CursorContext, detail: str = "", documentation: str = "") -> CompletionItem:
        """*name* as a completion: as it is inside a string, in quotes where the string is still to be opened."""
        return CompletionItem(name if context.in_string else json.dumps(name), detail, documentation)

    # ------------------------------------------------------------------
    # Diagnostics
    # ------------------------------------------------------------------

    def diagnose(self, document: TextDocument) -> list[Diagnostic]:
        broken = syntax_diagnostics(document.text, self._words, self.framework)
        if broken:
            return broken
        root = locate(document.text)
        actions = action_list(root, self._profile)
        if actions is None:
            return []
        index = LineIndex(document.text)
        if actions.kind != ARRAY:
            return [self._diagnostic(index, actions, "actions-not-list", self._words[
                "language_service_actions_not_list"].format(key=self._profile.document_key))]
        found: list[Diagnostic] = []
        for action in actions.items:
            found.extend(self._check_action(index, action))
        return found

    def _diagnostic(self, index: LineIndex, where: Located, code: str, message: str) -> Diagnostic:
        return Diagnostic(index.span(where.start, where.end), message, code=code, source=self.framework)

    def _check_action(self, index: LineIndex, action: Located) -> list[Diagnostic]:
        """What is wrong with one action: its shape first, then its keyword, then its arguments."""
        words = self._words
        if action.kind != ARRAY:
            return [self._diagnostic(index, action, "action-shape", words["language_service_action_not_list"])]
        if not action.items or action.items[0].kind != STRING:
            return [self._diagnostic(index, action.items[0] if action.items else action, "action-shape",
                                     words["language_service_action_no_keyword"])]
        if len(action.items) > _ACTION_LENGTH:
            return [self._diagnostic(index, action.items[_ACTION_LENGTH], "action-shape",
                                     words["language_service_action_too_long"])]
        name = action.items[0]
        keyword = self._metadata.keyword(name.value)
        if keyword is None:
            return [self._diagnostic(index, name, "unknown-keyword", self._unknown(
                ("language_service_unknown_keyword", "language_service_unknown_keyword_suggestion"),
                name.value, list(self._metadata.keywords), name=name.value, framework=self._name))]
        arguments = action.items[1] if len(action.items) == _ACTION_LENGTH else None
        return self._check_arguments(index, keyword, name, arguments)

    def _unknown(self, keys: tuple[str, str], written: str, known: list[str], **fields: str) -> str:
        """That *written* is not known: the second message of *keys*, suggesting the nearest of *known*, when one is near."""
        plain, suggesting = keys
        near = get_close_matches(written, known, n=1)
        if near:
            return self._words[suggesting].format(suggestion=near[0], **fields)
        return self._words[plain].format(**fields)

    def _check_arguments(
            self, index: LineIndex, keyword: Keyword, name: Located, arguments: Located | None) -> list[Diagnostic]:
        if arguments is not None and arguments.kind not in (OBJECT, ARRAY):
            return [self._diagnostic(index, arguments, "action-shape",
                                     self._words["language_service_arguments_shape"])]
        if not keyword.signature_known:
            return []
        if arguments is not None and arguments.kind == ARRAY:
            return self._check_values(index, keyword, arguments)
        return self._check_names(index, keyword, name, arguments)

    def _check_names(
            self, index: LineIndex, keyword: Keyword, name: Located, arguments: Located | None) -> list[Diagnostic]:
        """An object of named values: each name is a parameter, and no required one is left out."""
        members = arguments.members if arguments is not None else ()
        found = []
        if not keyword.takes_any_name():
            known = [parameter.name for parameter in keyword.named()]
            found = [
                self._diagnostic(index, key, "unknown-parameter", self._unknown(
                    ("language_service_unknown_parameter", "language_service_unknown_parameter_suggestion"),
                    key.value, known, keyword=keyword.name, name=key.value))
                for key, _value in members if key.value not in known]
        missing = keyword.missing({key.value for key, _value in members})
        if missing:
            found.append(self._diagnostic(index, name, "missing-parameter", self._words[
                "language_service_missing_parameter"].format(keyword=keyword.name, names=", ".join(missing))))
        return found

    def _check_values(self, index: LineIndex, keyword: Keyword, values: Located) -> list[Diagnostic]:
        """A list of values: as many as the keyword takes in order, and none it needs by name."""
        least, most = keyword.positional_range()
        count = len(values.items)
        fields = {"keyword": keyword.name, "count": count}
        if most is not None and count > most:
            return [self._diagnostic(index, values.items[most], "too-many-values", self._words[
                "language_service_too_many_values"].format(most=most, **fields))]
        if count < least:
            return [self._diagnostic(index, values, "too-few-values", self._words[
                "language_service_too_few_values"].format(least=least, **fields))]
        by_name = keyword.needs_a_name()
        if by_name:
            return [self._diagnostic(index, values, "missing-parameter", self._words[
                "language_service_needs_names"].format(keyword=keyword.name, names=", ".join(by_name)))]
        return []

    # ------------------------------------------------------------------
    # Hover and go-to-definition
    # ------------------------------------------------------------------

    def _under(self, document: TextDocument, position: Position) -> tuple[Located, Keyword, Located | None] | None:
        """The string at *position*, the keyword of the action it is in, and its key when it is a parameter's name."""
        offset = LineIndex(document.text).offset(position)
        actions = action_list(locate(document.text), self._profile)
        for action in (actions.items if actions is not None and actions.kind == ARRAY else ()):
            if action.kind != ARRAY or not action.holds(offset) or not action.items:
                continue
            name = action.items[0]
            keyword = self._metadata.keyword(name.value) if name.kind == STRING else None
            if keyword is None:
                return None
            if name.holds(offset):
                return name, keyword, None
            arguments = action.items[1] if len(action.items) > 1 else None
            key = next((key for key, _value in (arguments.members if arguments is not None else ())
                        if key.holds(offset)), None)
            return (key, keyword, key) if key is not None else None
        return None

    def hover(self, document: TextDocument, position: Position) -> Hover | None:
        under = self._under(document, position)
        if under is None:
            return None
        where, keyword, key = under
        span = LineIndex(document.text).span(where.start, where.end)
        if key is None:
            return Hover("\n\n".join(part for part in (keyword.signature(), keyword.doc) if part), span)
        parameter = keyword.parameter(key.value)
        if parameter is None:
            return None
        need = self._words["language_service_parameter_required" if parameter.required
                           else "language_service_parameter_optional"]
        return Hover(f"{parameter.written()}\n\n{need}", span)

    def definition(self, document: TextDocument, position: Position) -> list[Location]:
        under = self._under(document, position)
        if under is None:
            return []
        _where, keyword, _key = under
        file = Path(keyword.source_file) if keyword.source_file else None
        if file is None or not file.is_absolute() or keyword.source_line < 1:
            return []
        line = Position(keyword.source_line - 1, 0)
        return [Location(file.as_uri(), Range(line, line))]
