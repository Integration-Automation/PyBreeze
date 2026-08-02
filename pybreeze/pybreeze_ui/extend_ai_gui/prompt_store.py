"""Where the editable prompt templates live, and how one is resolved.

Every template ships as a constant in the source tree and may be overridden by a
file the user edits. The file wins when it has content, so editing a prompt in the
editor changes what the review actually sends — which is the only reason the
editor is there.

The files sit under the user's own directory rather than the working one, so the
prompts someone has written are the same whichever folder the IDE was started
from, matching where the SSH known hosts and the prthinker settings are kept.
"""
from __future__ import annotations

from pathlib import Path

from pybreeze.utils.app_dirs import pybreeze_data_dir
from pybreeze.utils.logging.logger import pybreeze_logger

_PROMPT_DIR_NAME = "prompts"


def prompt_dir() -> Path:
    """Return the directory the editable prompt files live in.

    Reading and naming a prompt must not create anything: opening the editor to
    look at a built-in prompt should leave no directory behind. ``save_prompt_text``
    makes the directory when there is finally something to put in it.
    """
    return pybreeze_data_dir() / _PROMPT_DIR_NAME


def prompt_path(name: str) -> Path:
    """Return the file the prompt called *name* is edited in."""
    return prompt_dir() / name


def load_prompt(name: str, default: str) -> str:
    """Return the edited prompt *name*, or the built-in *default*.

    A file that is missing, empty or unreadable falls back to the built-in: an
    override that says nothing must not leave a review step with nothing to ask,
    and a file that cannot be read must not stop the review.

    :param name: the prompt's file name, e.g. ``linter.md``
    :param default: the template compiled into the source tree
    :return: the prompt text to use
    """
    path = prompt_path(name)
    if not path.is_file():
        return default
    try:
        edited = path.read_text(encoding="utf-8")
    except OSError as error:
        pybreeze_logger.error("Prompt %s could not be read: %r", name, error)
        return default
    return edited if edited.strip() else default
