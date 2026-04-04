import pytest

from pybreeze.pybreeze_ui.jupyter_lab_gui.jupyter_lab_thread import find_free_port, JUPYTER_STARTUP_TIMEOUT


class TestFindFreePort:
    def test_returns_int(self):
        port = find_free_port()
        assert isinstance(port, int)

    def test_returns_valid_port_range(self):
        port = find_free_port()
        assert 1 <= port <= 65535

    def test_returns_different_ports(self):
        ports = {find_free_port() for _ in range(5)}
        # At least some should be different
        assert len(ports) >= 2


class TestConstants:
    def test_default_timeout(self):
        assert JUPYTER_STARTUP_TIMEOUT == 60
        assert isinstance(JUPYTER_STARTUP_TIMEOUT, int)
