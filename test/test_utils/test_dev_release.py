"""``scripts/dev_release.py`` numbers and gates the ``pybreeze_dev`` releases CI publishes.

A wrong version is refused by PyPI (a number is never reused) and a wrong comparison either
publishes on every push or never again, so both are pinned here without touching the network.
"""
from __future__ import annotations

import importlib.util
import io
import re
import zipfile
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[2]
_SCRIPT = _ROOT / "scripts" / "dev_release.py"
_WORKFLOW = _ROOT / ".github" / "workflows" / "dev.yml"
_FILES = "https://files.pythonhosted.org/"


def _load_script():
    spec = importlib.util.spec_from_file_location("dev_release", _SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


dev_release = _load_script()


def _wheel(version: str, source: str = "VALUE = 1\n", requires: str = "PySide6==6.11.2") -> bytes:
    info = f"pybreeze_dev-{version}.dist-info"
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("pybreeze/__init__.py", source)
        archive.writestr(f"{info}/METADATA",
                         f"Name: pybreeze_dev\nVersion: {version}\nRequires-Dist: {requires}\n")
        archive.writestr(f"{info}/RECORD", f"pybreeze/__init__.py,sha256={version}\n")
        archive.writestr(f"{info}/WHEEL", f"Generator: setuptools ({version})\n")
        archive.writestr(f"{info}/licenses/LICENSE", "MIT\n")
    return buffer.getvalue()


@pytest.mark.parametrize("floor, released, expected", [
    ((1, 0, 14), {(1, 0, 14): None, (1, 0, 13): None}, "1.0.15"),
    ((1, 0, 14), {(1, 0, 20): None}, "1.0.21"),
    ((1, 1, 0), {(1, 0, 20): None}, "1.1.1"),
    ((1, 0, 14), {}, "1.0.15"),
])
def test_next_version_is_one_patch_above_the_floor_and_every_release(floor, released, expected):
    assert dev_release.next_version(floor, released) == expected


def test_published_keeps_plain_releases_and_their_wheels(monkeypatch):
    payload = (
        b'{"releases": {'
        b'"1.0.13": [{"packagetype": "sdist", "url": "https://files.pythonhosted.org/a.tar.gz"}],'
        b'"1.0.14": [{"packagetype": "sdist", "url": "https://files.pythonhosted.org/b.tar.gz"},'
        b' {"packagetype": "bdist_wheel", "url": "https://files.pythonhosted.org/b.whl"}],'
        b'"1.0.15.dev1": [{"packagetype": "bdist_wheel", "url": "https://files.pythonhosted.org/c.whl"}],'
        b'"1.0.12": []}}'
    )
    monkeypatch.setattr(dev_release, "fetch", lambda url: payload)
    assert dev_release.published("pybreeze_dev") == {
        (1, 0, 13): None,
        (1, 0, 14): _FILES + "b.whl",
    }


def test_fetch_refuses_a_host_that_is_not_pypi():
    with pytest.raises(ValueError, match="refusing to fetch"):
        dev_release.fetch("https://example.com/pybreeze_dev.whl")


def test_prepare_writes_pyproject_from_dev_toml_with_the_next_version(tmp_path, monkeypatch):
    dev_toml = (_ROOT / "dev.toml").read_text(encoding="utf-8")
    (tmp_path / "dev.toml").write_text(dev_toml, encoding="utf-8")
    asked = []
    monkeypatch.setattr(dev_release, "published", lambda name: asked.append(name) or {(9, 9, 9): None})

    assert dev_release.prepare(tmp_path) == "9.9.10"

    written = (tmp_path / "pyproject.toml").read_text(encoding="utf-8")
    assert asked == ["pybreeze_dev"]
    assert written == dev_release.VERSION_LINE.sub(r'\g<1>"9.9.10"', dev_toml, count=1)
    assert written.count('version = "9.9.10"') == 1


def test_fingerprint_ignores_what_only_the_version_number_changes():
    assert dev_release.fingerprint(_wheel("1.0.14")) == dev_release.fingerprint(_wheel("1.0.15"))


@pytest.mark.parametrize("difference", [{"source": "VALUE = 2\n"}, {"requires": "PySide6==6.11.3"}])
def test_fingerprint_sees_changed_code_and_changed_metadata(difference):
    assert dev_release.fingerprint(_wheel("1.0.14")) != dev_release.fingerprint(_wheel("1.0.15", **difference))


@pytest.mark.parametrize("latest, expected", [
    ({}, True),
    ({"source": "VALUE = 0\n"}, True),
    ({"source": "VALUE = 1\n"}, False),
])
def test_changed_compares_the_built_wheel_with_the_newest_published_one(
        tmp_path, monkeypatch, latest, expected):
    (tmp_path / "pybreeze_dev-1.0.15-py3-none-any.whl").write_bytes(_wheel("1.0.15"))
    url = _FILES + "pybreeze_dev-1.0.14-py3-none-any.whl"
    released = {(1, 0, 13): _FILES + "old.whl", (1, 0, 14): url} if latest else {}
    monkeypatch.setattr(dev_release, "published", lambda name: released)
    monkeypatch.setattr(dev_release, "fetch", lambda asked: _wheel("1.0.14", **latest) if asked == url else b"")

    assert dev_release.changed(tmp_path) is expected


def test_changed_publishes_when_the_newest_release_has_no_wheel(tmp_path, monkeypatch):
    (tmp_path / "pybreeze_dev-1.0.15-py3-none-any.whl").write_bytes(_wheel("1.0.15"))
    monkeypatch.setattr(dev_release, "published", lambda name: {(1, 0, 14): None})

    assert dev_release.changed(tmp_path) is True


def test_main_writes_the_result_where_the_workflow_reads_it(tmp_path, monkeypatch):
    output = tmp_path / "github_output"
    monkeypatch.setenv("GITHUB_OUTPUT", str(output))
    monkeypatch.setattr(dev_release, "changed", lambda dist: False)

    assert dev_release.main(["changed", str(tmp_path)]) == 0
    assert output.read_text(encoding="utf-8") == "changed=false\n"
    assert dev_release.main(["publish"]) == 2


def _publish_job() -> str:
    text = _WORKFLOW.read_text(encoding="utf-8")
    return re.split(r"^  publish-dev:\s*$", text, maxsplit=1, flags=re.MULTILINE)[1]


def test_the_workflow_publishes_only_a_tested_push_to_dev():
    # The SonarCloud job is skipped on a push to dev, and a skipped dependency
    # would skip the publish job with it: only the tests are needed.
    job = _publish_job()
    assert re.findall(r"^\s*needs:\s*(.+?)\s*$", job, re.MULTILINE) == ["unit-tests"]
    assert "if: github.event_name == 'push' && github.ref == 'refs/heads/dev'" in job
    assert "runs-on: ubuntu-latest" in job


def test_the_workflow_uploads_only_a_changed_build_and_keeps_no_credentials():
    job = _publish_job()
    upload = job.index("twine upload")
    assert job.index("dev_release.py prepare") < job.index("python -m build") < upload
    assert job.index("dev_release.py changed dist") < upload
    assert job.index("git ls-remote origin refs/heads/dev") < upload
    assert "if: steps.compare.outputs.changed == 'true' && steps.tip.outputs.current == 'true'" in job
    assert "persist-credentials: false" in job
