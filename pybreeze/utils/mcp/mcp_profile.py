"""The MCP servers a user has set up, and where they are kept.

An MCP server over the standard transport is a program the client starts and
talks to on its standard input and output. A :class:`McpServerProfile` is what
it takes to start one: a name, the command, the environment variables it needs
(where its keys and tokens go) and the folder it starts in, with what the user
has decided about it: how long a request may take, and which of its tools may
be called without being asked each time.

Profiles are the user's own and are kept in ``~/.pybreeze/mcp_servers.json``,
written for the owner alone: a profile's environment holds secrets. The file
uses the ``mcpServers`` layout other MCP clients write (a name, then
``command``, ``args``, ``env``), so a list made elsewhere can be read in.

A project may bring such a file too (``.mcp.json``). Those servers are *found*,
never started on being found: a file in a folder someone opened names a
command, and running it is the user's decision (:func:`discovered_profiles`).

Pure logic: nothing here starts a process.
"""
from __future__ import annotations

import json
import math
from collections.abc import Mapping
from dataclasses import dataclass, field, replace
from pathlib import Path

from pybreeze.utils.app_dirs import pybreeze_data_dir, pybreeze_data_path
from pybreeze.utils.exception.exception_tags import mcp_profile_command_error, mcp_profile_file_error
from pybreeze.utils.exception.exceptions import McpException
from pybreeze.utils.file_process.read_capped import read_text_capped
from pybreeze.utils.file_process.replace_file import replace_text
from pybreeze.utils.logging.logger import pybreeze_logger

PROFILES_FILE = "mcp_servers.json"
# The file a project brings, in the layout MCP clients share
PROJECT_FILE = ".mcp.json"
# The key the servers are under, in both
_SERVERS_KEY = "mcpServers"
DEFAULT_TIMEOUT_SECONDS = 30.0
# A request is given at least this long and at most this long, whatever a file says
_TIMEOUT_RANGE = (1.0, 3600.0)
# A file larger than this is not a list of servers
_MAX_FILE_BYTES = 1024 * 1024


@dataclass(frozen=True)
class McpServerProfile:
    """What it takes to start an MCP server, and what the user decided about it.

    :param name: what the user calls it; unique among the profiles
    :param command: the program and its arguments, as an argument list (never a shell line)
    :param environment: variables added to the server's environment; secrets go here, never in *command*
    :param working_directory: the folder it starts in; the IDE's own when empty
    :param timeout_seconds: how long one request may take
    :param trusted_tools: the tools the user said may be called without being asked each time
    """

    name: str
    command: tuple[str, ...]
    environment: Mapping[str, str] = field(default_factory=dict)
    working_directory: str = ""
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS
    trusted_tools: frozenset[str] = frozenset()

    def __post_init__(self) -> None:
        if not self.command or not all(isinstance(part, str) for part in self.command) or not self.command[0].strip():
            raise McpException(mcp_profile_command_error.format(name=self.name))

    def secrets(self) -> list[str]:
        """The values given to the server as environment variables: what must not reach a log or a report."""
        return list(self.environment.values())

    def trusting(self, tool: str) -> McpServerProfile:
        """This profile with *tool* among those called without being asked."""
        return replace(self, trusted_tools=self.trusted_tools | {tool})

    def to_entry(self) -> dict:
        """The profile as its entry in the file: ``command``, ``args``, ``env`` and PyBreeze's own fields."""
        entry: dict = {"command": self.command[0], "args": list(self.command[1:])}
        if self.environment:
            entry["env"] = dict(self.environment)
        if self.working_directory:
            entry["cwd"] = self.working_directory
        if self.timeout_seconds != DEFAULT_TIMEOUT_SECONDS:
            entry["timeout"] = self.timeout_seconds
        if self.trusted_tools:
            entry["trustedTools"] = sorted(self.trusted_tools)
        return entry


def _texts(value: object) -> list[str] | None:
    """*value* as a list of strings, or ``None`` when it is not one."""
    if isinstance(value, list) and all(isinstance(item, str) for item in value):
        return list(value)
    return None


def _timeout(value: object) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        return DEFAULT_TIMEOUT_SECONDS
    return float(min(max(value, _TIMEOUT_RANGE[0]), _TIMEOUT_RANGE[1]))


def profile_from_entry(name: str, entry: object) -> McpServerProfile | None:
    """The profile one entry of a servers file describes, or ``None`` when it describes none.

    The file may have been written by hand or by another program: an entry
    without a usable command is passed over rather than failing the list, and a
    field of the wrong type takes its default.
    """
    if not isinstance(entry, dict) or not isinstance(entry.get("command"), str) or not entry["command"].strip():
        return None
    arguments = _texts(entry.get("args", [])) or []
    environment = entry.get("env")
    variables = {key: value for key, value in environment.items()
                 if isinstance(key, str) and isinstance(value, str)} if isinstance(environment, dict) else {}
    folder = entry.get("cwd")
    return McpServerProfile(
        name=name, command=(entry["command"], *arguments), environment=variables,
        working_directory=folder if isinstance(folder, str) else "",
        timeout_seconds=_timeout(entry.get("timeout", DEFAULT_TIMEOUT_SECONDS)),
        trusted_tools=frozenset(_texts(entry.get("trustedTools")) or ()))


def profiles_from_text(text: str) -> list[McpServerProfile]:
    """The profiles a servers file's *text* holds, in the file's order.

    :raises McpException: when *text* is not a servers file at all
    """
    try:
        data = json.loads(text)
    except (ValueError, RecursionError) as error:
        raise McpException(mcp_profile_file_error) from error
    servers = data.get(_SERVERS_KEY) if isinstance(data, dict) else None
    if not isinstance(servers, dict):
        raise McpException(mcp_profile_file_error)
    found = (profile_from_entry(name, entry) for name, entry in servers.items() if isinstance(name, str) and name)
    return [profile for profile in found if profile is not None]


def profiles_to_text(profiles: list[McpServerProfile]) -> str:
    """*profiles* as the text of a servers file."""
    return json.dumps({_SERVERS_KEY: {profile.name: profile.to_entry() for profile in profiles}},
                      indent=2, ensure_ascii=False) + "\n"


def load_profiles() -> list[McpServerProfile]:
    """The user's own servers; none when the file is not there.

    :raises McpException: when the file is there and is not a servers file
    :raises OSError: when it cannot be read
    """
    file = pybreeze_data_path() / PROFILES_FILE
    if not file.is_file():
        return []
    return profiles_from_text(read_text_capped(file, max_bytes=_MAX_FILE_BYTES))


def save_profiles(profiles: list[McpServerProfile]) -> None:
    """Keep *profiles* as the user's own servers, readable by the user alone.

    :raises OSError: when the file cannot be written; the one there is left as it was
    """
    replace_text(pybreeze_data_dir() / PROFILES_FILE, profiles_to_text(profiles), private=True)


def discovered_profiles(folder: Path) -> list[McpServerProfile]:
    """The servers a project's ``.mcp.json`` in *folder* names; none when it has no such file, or not a usable one.

    They are found, not trusted: nothing here starts one, and none carries a
    trusted tool whatever the file says.
    """
    file = folder / PROJECT_FILE
    try:
        if not file.is_file():
            return []
        found = profiles_from_text(read_text_capped(file, max_bytes=_MAX_FILE_BYTES))
    except (OSError, UnicodeDecodeError, McpException) as error:
        # A project's file is not the user's to be told about: it is passed over
        pybreeze_logger.debug("mcp_profile.py %s not read as a servers file: %r", PROJECT_FILE, error)
        return []
    return [replace(profile, trusted_tools=frozenset()) for profile in found]
