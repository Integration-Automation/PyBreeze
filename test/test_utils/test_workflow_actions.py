"""Workflow steps pin their actions to commits, only a job that pushes keeps its token, publish tools are locked.

A tag such as ``@v4`` can be moved to other code at any time (the 2025
tj-actions/changed-files compromise rewrote tags), so each ``uses:`` names a
full 40-hex commit and carries the release it corresponds to as a comment,
which Dependabot reads and updates. Pinning also keeps Node 20 actions from
lingering unseen: GitHub removed Node 20 from its runners on 2026-09-23.

The same holds for what ``pip`` installs in the two jobs that are given the
PyPI token: an unpinned ``pip install build twine`` runs whatever PyPI serves
that minute next to the token, so those jobs install from
``.github/requirements/publish.txt``, where every package is a version and a
hash.

The build backend is one of those packages. ``python -m build`` alone builds
in an isolated environment and downloads the newest ``setuptools`` into it as
the job runs, so the jobs pass ``--no-isolation`` and the build imports the
``setuptools`` the lock installed.

The whole suite runs on Windows. Each workflow also runs the platform smoke
tests on Linux and macOS (the ``platform-smoke`` job), and no job waits for
that one: a system that is still being brought up must not hold a release.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest
from packaging.requirements import Requirement  # pytest needs packaging, so it is there
from packaging.utils import canonicalize_name

_ROOT = Path(__file__).resolve().parents[2]
_WORKFLOWS = sorted((_ROOT / ".github" / "workflows").glob("*.yml"))
_USES = re.compile(r"^\s*(?:-\s*)?uses:\s*(\S+)(.*)$")
_PINNED = re.compile(r"^[\w.-]+/[\w./-]+@[0-9a-f]{40}$")
_VERSION_COMMENT = re.compile(r"^\s+#\s*v\d+(\.\d+)*\s*$")
_REQUIREMENTS = _ROOT / ".github" / "requirements"
_PUBLISH_JOBS = ("dev.yml:publish-dev", "stable.yml:publish")
_LOCKED_INSTALL = "python -m pip install --require-hashes --only-binary :all: -r .github/requirements/publish.txt"
_JOB = re.compile(r"^  ([\w-]+):[ \t]*$", re.MULTILINE)
_INSTALL = re.compile(r"\bpip[x3]?\b.*\binstall\b")
_LOCKED_PACKAGE = re.compile(r"^([a-z0-9][a-z0-9._-]*)==(\S+) \\$")
_METADATA = ("pyproject.toml", "dev.toml")  # what a publish job can build from
_SMOKE_JOB = "platform-smoke"
_SMOKE_SYSTEMS = ["ubuntu-latest", "macos-latest"]  # Windows runs the whole suite
_BUILD_REQUIRES = re.compile(r"^\[build-system\]\n(?:[^\[\n].*\n|\n)*?requires\s*=\s*\[([^\]]*)\]", re.MULTILINE)


def _uses(path: Path) -> list[tuple[int, str, str]]:
    """``(line number, action reference, rest of the line)`` for each ``uses:`` of another repository."""
    found = []
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        match = _USES.match(line)
        if match and not match.group(1).startswith("./"):
            found.append((number, match.group(1), match.group(2)))
    return found


def _checkout_steps(path: Path) -> list[tuple[int, str]]:
    """``(line number, step text)`` for each ``actions/checkout`` step."""
    lines = path.read_text(encoding="utf-8").splitlines()
    steps = []
    for index, line in enumerate(lines):
        if not re.search(r"uses:\s*actions/checkout@", line):
            continue
        column = line.index("uses:")
        body = [line]
        for following in lines[index + 1:]:
            indent = len(following) - len(following.lstrip())
            if following.strip() and (indent < column or following.lstrip().startswith("- ")):
                break
            body.append(following)
        steps.append((index + 1, "\n".join(body)))
    return steps


def _jobs_given_the_pypi_token() -> dict[str, str]:
    """``workflow:job`` and the text of the job, for each job that is given the PyPI token."""
    given = {}
    for workflow in _WORKFLOWS:
        parts = _JOB.split(workflow.read_text(encoding="utf-8").split("\njobs:\n", 1)[1])
        for name, body in zip(parts[1::2], parts[2::2]):
            if "secrets.PYPI_API_TOKEN" in body:
                given[f"{workflow.name}:{name}"] = body
    return given


def _requirement_lines(name: str) -> list[str]:
    """The lines of a file in ``.github/requirements`` that are neither blank nor a comment."""
    return [line for line in (_REQUIREMENTS / name).read_text(encoding="utf-8").splitlines()
            if line.strip() and not line.lstrip().startswith("#")]


def _locked_versions() -> dict[str, str]:
    """Each package of the lock and the version it is pinned to."""
    return {match.group(1): match.group(2)
            for match in map(_LOCKED_PACKAGE.match, _requirement_lines("publish.txt")) if match}


def _build_requires(metadata: str) -> list[Requirement]:
    """What ``[build-system]`` requires in a metadata file. Read as text: Python 3.10 has no ``tomllib``."""
    text = (_ROOT / metadata).read_text(encoding="utf-8")
    return [Requirement(item) for item in re.findall(r'"([^"]+)"', _BUILD_REQUIRES.search(text).group(1))]


def _backend() -> set[str]:
    """The packages a build needs, by the name the lock gives them."""
    return {canonicalize_name(requirement.name) for metadata in _METADATA for requirement in _build_requires(metadata)}


def test_there_are_workflows():
    assert _WORKFLOWS


@pytest.mark.parametrize("workflow", _WORKFLOWS, ids=lambda path: path.name)
def test_every_action_is_pinned_to_a_commit_with_its_version(workflow):
    unpinned = [f"{workflow.name}:{number} {ref}{rest}" for number, ref, rest in _uses(workflow)
                if not (_PINNED.match(ref) and _VERSION_COMMENT.match(rest))]
    assert unpinned == []


def test_one_version_per_action():
    # The same action at two commits is an upgrade done halfway
    commits: dict[str, set[str]] = {}
    for workflow in _WORKFLOWS:
        for _number, ref, _rest in _uses(workflow):
            action, _, commit = ref.partition("@")
            commits.setdefault(action, set()).add(commit)
    assert {action: found for action, found in commits.items() if len(found) > 1} == {}


def test_dependabot_keeps_the_pins_current_on_dev():
    # A pinned commit stays current only if something bumps it; every update
    # goes to dev, because every push to main publishes. Read as text: PyYAML
    # is not a test dependency.
    text = (_ROOT / ".github" / "dependabot.yml").read_text(encoding="utf-8")
    blocks = re.split(r"^\s*-\s*package-ecosystem:", text, flags=re.MULTILINE)[1:]
    ecosystems = {block.split()[0].strip("\"'") for block in blocks}
    assert {"pip", "github-actions"} <= ecosystems
    assert all(re.search(r"^\s*target-branch:\s*\"dev\"", block, re.MULTILINE) for block in blocks)


def test_dependabot_waits_a_week_before_proposing_a_release():
    # A compromised release is usually found and yanked within days.
    # Dependabot's own default wait is 3 days, and zizmor's dependabot-cooldown
    # audit asks for 7. The wait never delays security updates.
    text = (_ROOT / ".github" / "dependabot.yml").read_text(encoding="utf-8")
    blocks = re.split(r"^\s*-\s*package-ecosystem:", text, flags=re.MULTILINE)[1:]
    days = [re.search(r"^\s*default-days:\s*(\d+)", block, re.MULTILINE) for block in blocks]
    assert blocks
    assert all(match and int(match.group(1)) >= 7 for match in days)


@pytest.mark.parametrize("workflow", _WORKFLOWS, ids=lambda path: path.name)
def test_every_checkout_decides_whether_it_keeps_the_token(workflow):
    # actions/checkout leaves the job's token in .git/config unless told not
    # to, where every later step can read it. Only a job that pushes keeps it,
    # and says so.
    undecided = [f"{workflow.name}:{number}" for number, step in _checkout_steps(workflow)
                 if not re.search(r"^\s*persist-credentials:\s*(true|false)\b", step, re.MULTILINE)]
    assert undecided == []


def test_only_the_job_that_publishes_keeps_the_token():
    kept = [f"{workflow.name}:{number}" for workflow in _WORKFLOWS
            for number, step in _checkout_steps(workflow)
            if re.search(r"^\s*persist-credentials:\s*true\b", step, re.MULTILINE)]
    assert [place.split(":")[0] for place in kept] == ["stable.yml"]


def test_the_pypi_token_reaches_the_two_publish_jobs_only():
    assert tuple(sorted(_jobs_given_the_pypi_token())) == _PUBLISH_JOBS


@pytest.mark.parametrize("job", _PUBLISH_JOBS)
def test_a_publish_job_installs_nothing_but_the_locked_tools(job):
    # One install, from the lock: no `--upgrade pip` before it and no second,
    # unpinned install after it. Either would run next to the PyPI token.
    # The command is quoted: `:all: ` holds a colon and a space, which YAML
    # reads as a key in an unquoted value, and the workflow no longer loads.
    installs = [line.strip() for line in _jobs_given_the_pypi_token()[job].splitlines()
                if _INSTALL.search(line) and not line.lstrip().startswith("#")]
    assert installs == [f'run: "{_LOCKED_INSTALL}"']


def test_the_lock_names_every_package_by_version_and_hash():
    # pip refuses an entry without a hash, but only once the job runs, and the
    # stable job runs after the merge into main. This says so on dev.
    lines = _requirement_lines("publish.txt")
    packages = [line for line in lines if not line.startswith(" ")]
    unhashed = [line for line, following in zip(lines, lines[1:] + [""])
                if not line.startswith(" ") and not following.startswith("    --hash=sha256:")]
    assert packages
    assert [line for line in packages if not _LOCKED_PACKAGE.match(line)] == []
    assert unhashed == []


def test_the_lock_is_made_from_the_tools_the_publish_jobs_run():
    # A tool a job starts running has to be added to publish.in, and a tool no
    # job runs any more has to leave it. The build backend is no module a job
    # names: `python -m build --no-isolation` imports it from the job's
    # environment, so it is listed beside the tools.
    run = {module for job in _jobs_given_the_pypi_token().values()
           for module in re.findall(r"python -m ([\w.]+)", job)} - {"pip"}
    assert _backend()
    assert set(_requirement_lines("publish.in")) == run | _backend()
    assert run | _backend() <= set(_locked_versions())


@pytest.mark.parametrize("job", _PUBLISH_JOBS)
def test_a_publish_job_builds_with_the_locked_backend(job):
    # `python -m build` alone makes an isolated environment and downloads the
    # newest setuptools into it: outside the lock, next to the PyPI token.
    builds = [line.split(" #")[0].split() for line in _jobs_given_the_pypi_token()[job].splitlines()
              if "python -m build" in line and not line.lstrip().startswith("#")]
    assert builds
    assert [command for command in builds if "--no-isolation" not in command] == []


@pytest.mark.parametrize("metadata", _METADATA)
def test_the_locked_backend_is_one_the_metadata_accepts(metadata):
    # --no-isolation checks [build-system] requires against what is installed
    # and installs nothing. Dependabot raises the floor in pyproject.toml; with
    # the lock left as it was the build would fail in the publish job, the
    # stable one after the merge into main. This says so on dev.
    locked = _locked_versions()
    required = {canonicalize_name(requirement.name): requirement for requirement in _build_requires(metadata)}
    assert required
    assert [str(requirement) for name, requirement in required.items()
            if name not in locked or not requirement.specifier.contains(locked[name])] == []


def test_dependabot_reads_the_lock_of_the_publish_jobs():
    # A directory reaches its own manifests and those one folder down; the lock
    # is two folders below the root, so the pip entry names its folder too.
    text = (_ROOT / ".github" / "dependabot.yml").read_text(encoding="utf-8")
    blocks = re.split(r"^\s*-\s*package-ecosystem:", text, flags=re.MULTILINE)[1:]
    pip = [block for block in blocks if block.split()[0].strip("\"'") == "pip"]
    assert len(pip) == 1
    assert re.findall(r"^\s*-\s*\"(/[^\"]*)\"\s*$", pip[0], re.MULTILINE) == ["/", "/.github/requirements"]


def _jobs(workflow: Path) -> dict[str, str]:
    """Each job of *workflow* and its text."""
    parts = _JOB.split(workflow.read_text(encoding="utf-8").split("\njobs:\n", 1)[1])
    return dict(zip(parts[1::2], parts[2::2]))


@pytest.mark.parametrize("workflow", _WORKFLOWS, ids=lambda path: path.name)
def test_the_smoke_tests_run_on_linux_and_macos(workflow):
    job = _jobs(workflow).get(_SMOKE_JOB)
    assert job is not None
    systems = re.search(r"^\s*os:\s*\[([^\]]*)\]\s*$", job, re.MULTILINE)
    assert systems is not None
    assert [system.strip() for system in systems.group(1).split(",")] == _SMOKE_SYSTEMS
    assert "pytest test/test_utils/test_platform_smoke.py" in job
    # No display on a runner: the tests ask for the offscreen platform themselves,
    # and the job says it too, for anything else a step starts
    assert re.search(r"^\s*QT_QPA_PLATFORM:\s*offscreen\s*$", job, re.MULTILINE)


@pytest.mark.parametrize("workflow", _WORKFLOWS, ids=lambda path: path.name)
def test_linux_smoke_has_an_x11_display_for_the_automation_dependency(workflow):
    job = _jobs(workflow)[_SMOKE_JOB]
    assert "xvfb xauth" in job
    assert "if: runner.os == 'Linux'" in job
    assert "xvfb-run --auto-servernum python -m pytest" in job
    assert "if: runner.os != 'Linux'" in job


@pytest.mark.parametrize("workflow", _WORKFLOWS, ids=lambda path: path.name)
def test_no_job_waits_for_the_smoke_tests(workflow):
    # A system still being brought up must not hold the tests' other consumers:
    # the scan, and the two jobs that publish
    waiting = [name for name, job in _jobs(workflow).items()
               if any(_SMOKE_JOB in needs for needs in re.findall(r"^\s*needs:\s*(.+?)\s*$", job, re.MULTILINE))]
    assert waiting == []
