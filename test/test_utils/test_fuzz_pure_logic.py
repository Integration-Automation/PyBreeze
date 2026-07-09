"""Property-based fuzzing: pure-logic helpers must never crash on hostile input."""
from __future__ import annotations

from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from pybreeze.pybreeze_ui.connect_gui.ssh.ssh_file_viewer_widget import (
    format_size,
    natural_key,
    remote_join,
)
from pybreeze.pybreeze_ui.diagram_editor.diagram_mermaid_parser import parse_mermaid
from pybreeze.pybreeze_ui.diagram_editor.diagram_net_utils import (
    _is_text_content_type,
    _parse_content_length,
)
from pybreeze.utils.exception.exceptions import ITEJsonException
from pybreeze.utils.json_format.json_process import reformat_json
from pybreeze.utils.network.http_client import truncate_for_display
from pybreeze.utils.network.url_validation import _embedded_ipv4, _is_blocked_ip

_FUZZ = settings(max_examples=300, deadline=None, suppress_health_check=[HealthCheck.too_slow])


class TestParseMermaidNeverCrashes:
    @_FUZZ
    @given(st.text())
    def test_arbitrary_text(self, text):
        result = parse_mermaid(text)
        assert isinstance(result, dict)
        assert "nodes" in result and "connections" in result

    @_FUZZ
    @given(st.text(alphabet="ABCD-->.=<>|&()[]{}\"/\\ \n;", max_size=120))
    def test_diagram_like_text(self, text):
        result = parse_mermaid("graph TD\n" + text)
        # connections must only reference node indices that exist
        node_count = len(result["nodes"])
        for conn in result["connections"]:
            assert 0 <= conn["source"] < node_count
            assert 0 <= conn["target"] < node_count


class TestHelpersNeverCrash:
    @_FUZZ
    @given(st.text())
    def test_natural_key(self, name):
        key = natural_key(name)
        assert isinstance(key, list)

    @_FUZZ
    @given(st.integers())
    def test_format_size(self, num):
        assert isinstance(format_size(num), str)

    @_FUZZ
    @given(st.text(), st.text())
    def test_remote_join_always_absolute(self, directory, name):
        assert remote_join(directory, name).startswith("/")

    @_FUZZ
    @given(st.text(), st.integers(min_value=0, max_value=5000))
    def test_truncate_for_display(self, text, limit):
        out = truncate_for_display(text, limit=limit)
        assert isinstance(out, str)

    @_FUZZ
    @given(st.text())
    def test_reformat_json_only_raises_ite(self, text):
        # Must return a str or raise the documented ITEJsonException — never an
        # uncaught JSONDecodeError / ValueError / RecursionError.
        try:
            assert isinstance(reformat_json(text), str)
        except ITEJsonException:
            pass

    @_FUZZ
    @given(st.one_of(st.none(), st.text()))
    def test_parse_content_length(self, raw):
        result = _parse_content_length(raw)
        assert result is None or (isinstance(result, int) and result >= 0)

    @_FUZZ
    @given(st.text())
    def test_is_text_content_type(self, raw):
        assert isinstance(_is_text_content_type(raw), bool)


class TestSsrfLogicNeverCrashes:
    @_FUZZ
    @given(st.ip_addresses(v=4))
    def test_blocked_ipv4(self, ip):
        assert isinstance(_is_blocked_ip(ip), bool)

    @_FUZZ
    @given(st.ip_addresses(v=6))
    def test_blocked_ipv6(self, ip):
        # Covers the IPv4-mapped / 6to4 / Teredo / NAT64 extraction paths.
        assert isinstance(_is_blocked_ip(ip), bool)
        for embedded in _embedded_ipv4(ip):
            assert isinstance(_is_blocked_ip(embedded), bool)
