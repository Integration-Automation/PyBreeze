"""Release helper for the dev channel, ``pybreeze_dev`` on PyPI.

The ``publish-dev`` job of ``.github/workflows/dev.yml`` runs it once the tests pass:

* ``python scripts/dev_release.py prepare`` writes ``pyproject.toml`` from ``dev.toml`` with the
  next version: one patch above the newest ``X.Y.Z`` release on PyPI, or above the version in
  ``dev.toml`` when that is higher. Nothing is committed back, so the version in ``dev.toml`` is a
  floor, raised by hand only when PyPI refuses a number (a deleted release keeps its number).
* ``python scripts/dev_release.py changed dist`` compares the wheel in ``dist`` with the newest
  published one and writes ``changed=true`` or ``changed=false`` to ``$GITHUB_OUTPUT``, so a push
  that ships nothing new publishes nothing.
"""
from __future__ import annotations

import hashlib
import io
import json
import os
import re
import sys
import zipfile
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import urlopen

Version = tuple[int, int, int]

PYPI_JSON = "https://pypi.org/pypi/{name}/json"
TRUSTED_PREFIXES = ("https://pypi.org/", "https://files.pythonhosted.org/")
NAME_LINE = re.compile(r'^name\s*=\s*"([^"]+)"', re.MULTILINE)
VERSION_LINE = re.compile(r'^(version\s*=\s*)"(\d+)\.(\d+)\.(\d+)"', re.MULTILINE)
RELEASE = re.compile(r"^(\d+)\.(\d+)\.(\d+)$")
DIST_INFO = re.compile(r"^[^/]+\.dist-info/")
METADATA_VERSION = re.compile(rb"^Version: .*\r?\n", re.MULTILINE)
# Members that differ between two builds of the same sources.
VOLATILE = ("dist-info/RECORD", "dist-info/WHEEL")


def fetch(url: str) -> bytes:
    """Return the body of a PyPI URL; any other host is refused."""
    if not url.startswith(TRUSTED_PREFIXES):
        raise ValueError(f"refusing to fetch {url}")
    # The prefix check above leaves only https URLs on PyPI's two hosts.
    with urlopen(url, timeout=60) as response:  # nosec B310
        return response.read()


def as_version(parts: tuple[str, ...]) -> Version:
    """Turn the three captured number strings of a version into a comparable tuple."""
    major, minor, patch = (int(part) for part in parts)
    return major, minor, patch


def published(name: str) -> dict[Version, str | None]:
    """Map each ``X.Y.Z`` release of ``name`` on PyPI to its wheel URL, ``None`` without one."""
    try:
        releases = json.loads(fetch(PYPI_JSON.format(name=name)))["releases"]
    except HTTPError as error:
        if error.code == 404:  # not on PyPI yet: the first release
            return {}
        raise
    found: dict[Version, str | None] = {}
    for version, files in releases.items():
        match = RELEASE.match(version)
        if match and files:
            wheels = [item["url"] for item in files if item["packagetype"] == "bdist_wheel"]
            found[as_version(match.groups())] = wheels[0] if wheels else None
    return found


def next_version(floor: Version, released: dict[Version, str | None]) -> str:
    """Return one patch above the highest of ``floor`` and the released versions."""
    major, minor, patch = max([floor, *released])
    return f"{major}.{minor}.{patch + 1}"


def prepare(root: Path) -> str:
    """Write ``pyproject.toml`` from ``dev.toml`` with the next version and return that version."""
    text = (root / "dev.toml").read_text(encoding="utf-8")
    name, floor = NAME_LINE.search(text), VERSION_LINE.search(text)
    if name is None or floor is None:
        raise SystemExit("dev.toml needs a name and an X.Y.Z version")
    version = next_version(as_version(floor.groups()[1:]), published(name.group(1)))
    project = VERSION_LINE.sub(rf'\g<1>"{version}"', text, count=1)
    (root / "pyproject.toml").write_text(project, encoding="utf-8", newline="\n")
    return version


def fingerprint(wheel: bytes) -> dict[str, str]:
    """Map each wheel member to its SHA-256, leaving out what only a new version number changes."""
    members: dict[str, str] = {}
    with zipfile.ZipFile(io.BytesIO(wheel)) as archive:
        for member in archive.namelist():
            name = DIST_INFO.sub("dist-info/", member)
            if name in VOLATILE:
                continue
            data = archive.read(member)
            if name == "dist-info/METADATA":
                data = METADATA_VERSION.sub(b"", data, count=1)
            members[name] = hashlib.sha256(data).hexdigest()
    return members


def changed(dist: Path) -> bool:
    """Tell whether the wheel in ``dist`` ships anything the newest published wheel does not."""
    built = next(dist.glob("*.whl"))
    released = published(built.name.split("-")[0])
    latest = released[max(released)] if released else None
    if latest is None:
        return True
    return fingerprint(built.read_bytes()) != fingerprint(fetch(latest))


def main(argv: list[str]) -> int:
    """Run ``prepare`` or ``changed <dist directory>``; return the process exit code."""
    if argv == ["prepare"]:
        print(f"version={prepare(Path.cwd())}")
        return 0
    if len(argv) == 2 and argv[0] == "changed":
        line = f"changed={str(changed(Path(argv[1]))).lower()}"
        print(line)
        output = os.environ.get("GITHUB_OUTPUT")
        if output:
            with open(output, "a", encoding="utf-8") as handle:
                handle.write(line + "\n")
        return 0
    print(__doc__, file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
