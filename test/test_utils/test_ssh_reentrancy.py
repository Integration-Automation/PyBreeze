"""Re-clicking Connect must tear down the prior SSH session, not leak it."""
from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from unittest.mock import MagicMock

from pybreeze.pybreeze_ui.connect_gui.ssh import ssh_command_widget as mod


def _widget_with_valid_inputs():
    widget = mod.SSHCommandWidget.__new__(mod.SSHCommandWidget)
    widget.word_dict = {}
    login = MagicMock()
    login.host_edit.text.return_value = "host"
    login.user_edit.text.return_value = "user"
    login.port_spin.value.return_value = 22
    login.use_key_check.isChecked.return_value = False
    login.key_edit.text.return_value = ""
    login.pass_edit.text.return_value = "pw"
    widget.login_widget = login
    return widget


class TestConnectReentrancy:
    def test_cleanup_runs_before_new_session(self, monkeypatch):
        widget = _widget_with_valid_inputs()
        order = []
        widget._cleanup = lambda: order.append("cleanup")
        widget._start_shell = lambda *args: order.append("start_shell")
        monkeypatch.setattr(mod.paramiko, "SSHClient", lambda: MagicMock())
        monkeypatch.setattr(mod, "apply_host_key_policy", lambda client, parent: None)

        widget.connect_ssh()

        # The prior session is torn down before a new client/shell is created,
        # so re-connecting cannot leak the old client or orphan its reader.
        assert order == ["cleanup", "start_shell"]
