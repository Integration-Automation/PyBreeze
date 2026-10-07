"""The frameworks whose action scripts have a language service, and what tells one's script from another's.

WebRunner, AutoControl and LoadDensity run the same kind of script: a JSON list
of actions, ``["keyword"]`` or ``["keyword", arguments]``, either as the whole
file or under the framework's own key. What differs is the key, the module that
holds the keywords, and the keywords themselves, which are read from the
installed package (``metadata_probe.py``). A profile is the little that has to
be known before the package is asked.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class FrameworkProfile:
    """What is known of a framework without importing it.

    :param framework: the package's import name
    :param label: the name people call it
    :param document_key: the key its action list goes under when the script is an object
    :param executor_module: the module whose ``executor.event_dict`` maps keywords to functions
    :param distribution: the name the package is installed under, for its version
    :param keyword_prefix: how its own keywords start; tells whose script a file is
        while the package itself cannot be asked
    """

    framework: str
    label: str
    document_key: str
    executor_module: str
    distribution: str
    keyword_prefix: str


# In the order the roadmap brings them in
PROFILES: tuple[FrameworkProfile, ...] = (
    FrameworkProfile(
        framework="je_web_runner", label="WebRunner", document_key="webdriver_wrapper",
        executor_module="je_web_runner.utils.executor.action_executor", distribution="je_web_runner",
        keyword_prefix="WR_"),
    FrameworkProfile(
        framework="je_auto_control", label="AutoControl", document_key="auto_control",
        executor_module="je_auto_control.utils.executor.action_executor", distribution="je_auto_control",
        keyword_prefix="AC_"),
    FrameworkProfile(
        framework="je_load_density", label="LoadDensity", document_key="load_density",
        executor_module="je_load_density.utils.executor.action_executor", distribution="je_load_density",
        keyword_prefix="LD_"),
)


def profile_of(framework: str) -> FrameworkProfile | None:
    """The profile of the framework imported as *framework*, or ``None``."""
    return next((profile for profile in PROFILES if profile.framework == framework), None)
