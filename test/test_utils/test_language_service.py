"""The language-service contract: one way to ask every framework, and a failing one costs nothing else."""
from __future__ import annotations

import logging

import pytest
from hypothesis import given
from hypothesis import strategies as st

from pybreeze.utils.language_service.service_adapter import (
    Capability,
    CompletionItem,
    Diagnostic,
    Hover,
    LanguageService,
    LanguageServiceAdapter,
    LanguageServiceRegistry,
    Location,
    Position,
    Range,
    Severity,
    TextDocument,
    index_at,
    utf16_offset,
)

_DOCUMENT = TextDocument(uri="file:///actions.json", text='[["WR_to_url", {}]]', version=3)
_PLACE = Position(line=0, character=3)
_STRETCH = Range(Position(0, 3), Position(0, 12))
_EVERYTHING = frozenset(Capability)


class _Adapter(LanguageServiceAdapter):
    """An adapter that answers everything and records what it was asked."""

    def __init__(self, framework: str = "je_web_runner", capabilities: frozenset = _EVERYTHING) -> None:
        self._framework = framework
        self.can = capabilities
        self.asked: list[str] = []

    @property
    def framework(self) -> str:
        return self._framework

    def capabilities(self) -> frozenset[Capability]:
        return self.can

    def complete(self, document, position):
        self.asked.append("complete")
        return [CompletionItem(label="WR_to_url", detail="(url)")]

    def diagnose(self, document):
        self.asked.append("diagnose")
        return [Diagnostic(range=_STRETCH, message="unknown keyword", source=self._framework)]

    def hover(self, document, position):
        self.asked.append("hover")
        return Hover(contents="Open a URL", range=_STRETCH)

    def definition(self, document, position):
        self.asked.append("definition")
        return [Location(uri="file:///executor.py", range=_STRETCH)]


class _MinimalAdapter(LanguageServiceAdapter):
    """Only what every adapter must provide."""

    @property
    def framework(self) -> str:
        return "je_load_density"

    def capabilities(self) -> frozenset[Capability]:
        return _EVERYTHING

    def complete(self, document, position):
        return []

    def diagnose(self, document):
        return []


class _BrokenAdapter(_Adapter):
    """An adapter whose every answer raises."""

    def complete(self, document, position):
        raise RuntimeError("the framework's metadata could not be read")

    def diagnose(self, document):
        raise KeyError("event_dict")

    def hover(self, document, position):
        raise ImportError("je_web_runner")

    def definition(self, document, position):
        raise OSError("source file gone")


class TestTheContract:
    def test_an_adapter_must_say_its_framework_and_do_the_minimum(self):
        with pytest.raises(TypeError, match="abstract"):
            LanguageServiceAdapter()

    def test_hover_and_definition_are_optional(self):
        adapter = _MinimalAdapter()

        assert adapter.hover(_DOCUMENT, _PLACE) is None
        assert adapter.definition(_DOCUMENT, _PLACE) == []

    def test_severities_carry_the_protocols_numbers(self):
        assert [severity.value for severity in Severity] == [1, 2, 3, 4]

    def test_a_diagnostic_is_an_error_unless_it_says_otherwise(self):
        assert Diagnostic(range=_STRETCH, message="x").severity is Severity.ERROR


class TestService:
    def test_it_gives_the_adapters_answers(self):
        service = LanguageService(_Adapter())

        assert service.framework == "je_web_runner"
        assert service.capabilities() == _EVERYTHING
        assert service.complete(_DOCUMENT, _PLACE) == [CompletionItem(label="WR_to_url", detail="(url)")]
        assert service.diagnose(_DOCUMENT)[0].message == "unknown keyword"
        assert service.hover(_DOCUMENT, _PLACE) == Hover(contents="Open a URL", range=_STRETCH)
        assert service.definition(_DOCUMENT, _PLACE) == [Location(uri="file:///executor.py", range=_STRETCH)]

    def test_it_asks_only_for_what_the_adapter_can_do(self):
        adapter = _Adapter(capabilities=frozenset({Capability.COMPLETION, Capability.DIAGNOSTICS}))
        service = LanguageService(adapter)

        assert service.hover(_DOCUMENT, _PLACE) is None
        assert service.definition(_DOCUMENT, _PLACE) == []
        assert service.complete(_DOCUMENT, _PLACE) != []
        assert service.diagnose(_DOCUMENT) != []
        assert adapter.asked == ["complete", "diagnose"]

    def test_what_the_adapter_can_do_is_asked_every_time(self):
        # The framework was upgraded, or uninstalled, while the IDE ran
        adapter = _Adapter(capabilities=frozenset())
        service = LanguageService(adapter)

        assert service.complete(_DOCUMENT, _PLACE) == []
        adapter.can = frozenset({Capability.COMPLETION})

        assert service.complete(_DOCUMENT, _PLACE) != []

    def test_a_failing_adapter_gives_nothing_and_is_logged(self, caplog):
        service = LanguageService(_BrokenAdapter())

        with caplog.at_level(logging.ERROR):
            assert service.complete(_DOCUMENT, _PLACE) == []
            assert service.diagnose(_DOCUMENT) == []
            assert service.hover(_DOCUMENT, _PLACE) is None
            assert service.definition(_DOCUMENT, _PLACE) == []

        failures = [record.getMessage() for record in caplog.records]
        assert len(failures) == 4
        assert all("je_web_runner" in failure for failure in failures)
        assert "completion" in failures[0]
        assert "could not be read" in failures[0]

    def test_an_adapter_that_cannot_say_what_it_can_do_is_asked_nothing(self, caplog):
        adapter = _Adapter()
        adapter.capabilities = lambda: 1 / 0
        service = LanguageService(adapter)

        with caplog.at_level(logging.ERROR):
            assert service.capabilities() == frozenset()
            assert service.complete(_DOCUMENT, _PLACE) == []

        assert adapter.asked == []
        assert "capabilities" in caplog.records[0].getMessage()

    def test_each_empty_answer_is_its_own_list(self):
        service = LanguageService(_Adapter(capabilities=frozenset()))

        first = service.complete(_DOCUMENT, _PLACE)
        first.append(CompletionItem(label="added by the caller"))

        assert service.complete(_DOCUMENT, _PLACE) == []


class TestRegistry:
    def test_a_framework_gets_its_service(self):
        registry = LanguageServiceRegistry()
        registry.register(_Adapter("je_web_runner"))
        registry.register(_Adapter("je_auto_control"))

        assert registry.frameworks() == ["je_web_runner", "je_auto_control"]
        assert registry.service_for("je_auto_control").framework == "je_auto_control"

    def test_a_framework_without_one_has_none(self):
        assert LanguageServiceRegistry().service_for("je_load_density") is None

    def test_a_framework_has_one_service(self):
        registry = LanguageServiceRegistry()
        registry.register(_Adapter("je_web_runner"))

        with pytest.raises(ValueError, match="je_web_runner"):
            registry.register(_Adapter("je_web_runner"))


class TestUtf16Positions:
    # "a", an emoji (two UTF-16 code units), "b"
    _LINE = "a\U0001f600b"

    @pytest.mark.parametrize(("index", "offset"), [(0, 0), (1, 1), (2, 3), (3, 4)])
    def test_an_index_as_a_position(self, index, offset):
        assert utf16_offset(self._LINE, index) == offset

    @pytest.mark.parametrize(("offset", "index"), [(0, 0), (1, 1), (3, 2), (4, 3)])
    def test_a_position_as_an_index(self, offset, index):
        assert index_at(self._LINE, offset) == index

    def test_an_offset_inside_a_character_is_that_character(self):
        assert index_at(self._LINE, 2) == 1

    def test_an_offset_past_the_end_is_the_end(self):
        assert index_at(self._LINE, 99) == 3
        assert utf16_offset(self._LINE, 99) == 4

    def test_an_offset_before_the_start_is_the_start(self):
        assert index_at(self._LINE, -1) == 0
        assert utf16_offset(self._LINE, -1) == 0

    def test_half_a_character_counts_as_one_unit(self):
        assert utf16_offset("\ud83dx", 1) == 1

    @given(line=st.text(max_size=20), data=st.data())
    def test_a_position_made_from_an_index_leads_back_to_it(self, line, data):
        index = data.draw(st.integers(min_value=0, max_value=len(line)))

        assert index_at(line, utf16_offset(line, index)) == index

    @given(line=st.text(max_size=20))
    def test_the_end_of_a_line_is_its_length_as_qt_counts_it(self, line):
        assert utf16_offset(line, len(line)) == len(line.encode("utf-16-le")) // 2
