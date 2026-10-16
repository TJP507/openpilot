"""
Copyright (c) 2021-, Haibin Wen, sunnypilot, and a number of other contributors.

This file is part of sunnypilot and is licensed under the MIT License.
See the LICENSE.md file in the root directory for more details.

Tests for the TylerPilot fork version scheme
(`sunnypilot/common/version_scheme.py`) and its runtime/CLI consumers.
"""
import subprocess
import sys
from pathlib import Path

from openpilot.sunnypilot.common import version_scheme
from openpilot.system.version import get_version

REPO_ROOT = Path(__file__).resolve().parents[3]


def _write_version(root: Path, value: str) -> None:
  version_dir = root / "sunnypilot" / "common"
  version_dir.mkdir(parents=True, exist_ok=True)
  (version_dir / "version.h").write_text(f'#define SUNNYPILOT_VERSION "{value}"\n')


class TestVersionScheme:
  def test_is_base(self):
    assert version_scheme.is_base("2026.002.029")
    assert not version_scheme.is_base("2026.002.029-tp.1")
    assert not version_scheme.is_base("2026.002.029-tp.dev")

  def test_is_full_version(self):
    assert version_scheme.is_full_version("2026.002.029-tp.1")
    assert version_scheme.is_full_version("2026.002.029-tp.42")
    assert not version_scheme.is_full_version("2026.002.029")
    assert not version_scheme.is_full_version("2026.002.029-tp.dev")

  def test_compose(self):
    assert version_scheme.dev_version("2026.002.029") == "2026.002.029-tp.dev"
    assert version_scheme.ci_version("2026.002.029", 1) == "2026.002.029-tp.1"
    assert version_scheme.ci_tag("2026.002.029", 1) == "ci/2026.002.029-tp.1"

  def test_ci_number_from_tag(self):
    base = "2026.002.029"
    assert version_scheme.ci_number_from_tag("ci/2026.002.029-tp.7", base) == 7
    assert version_scheme.ci_number_from_tag("ci/2026.002.030-tp.7", base) is None
    assert version_scheme.ci_number_from_tag("ci/2026.002.029-tp.dev", base) is None
    assert version_scheme.ci_number_from_tag("v2026.002.029", base) is None

  def test_next_ci_number(self):
    base = "2026.002.029"
    assert version_scheme.next_ci_number(base, []) == 1
    assert version_scheme.next_ci_number(base, ["ci/2026.002.029-tp.1"]) == 2
    assert version_scheme.next_ci_number(base, ["ci/2026.002.029-tp.1", "ci/2026.002.029-tp.3"]) == 4
    assert version_scheme.next_ci_number(base, ["ci/2026.002.030-tp.9", "ci/2026.002.029-tp.2"]) == 3

  def test_resolve(self):
    assert version_scheme.resolve("2026.002.029") == "2026.002.029-tp.dev"
    assert version_scheme.resolve("2026.002.029-tp.3") == "2026.002.029-tp.3"
    assert version_scheme.resolve("2026.003.000") == "2026.003.000-tp.dev"


class TestGetVersion:
  def test_dev_build_gets_dev_suffix(self, tmp_path):
    _write_version(tmp_path, "2026.002.029")
    assert get_version(str(tmp_path)) == "2026.002.029-tp.dev"

  def test_published_build_is_unchanged(self, tmp_path):
    _write_version(tmp_path, "2026.002.029-tp.4")
    assert get_version(str(tmp_path)) == "2026.002.029-tp.4"


class TestCiVersionCli:
  @staticmethod
  def _run(*args: str, stdin: str = "") -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(REPO_ROOT / "ci" / "version"), *args],
                          capture_output=True, text=True, input=stdin)

  def test_check(self):
    assert self._run("check", "2026.002.029-tp.1").returncode == 0
    assert self._run("check", "2026.002.029-tp.dev").returncode == 1
    assert self._run("check", "2026.002.029").returncode == 1

  def test_base_and_dev(self, tmp_path):
    _write_version(tmp_path, "2026.002.029")
    root = str(tmp_path)
    assert self._run("base", "--repo-root", root).stdout.strip() == "2026.002.029"
    assert self._run("dev", "--repo-root", root).stdout.strip() == "2026.002.029-tp.dev"

  def test_next_from_stdin(self, tmp_path):
    _write_version(tmp_path, "2026.002.029")
    tags = "refs/tags/ci/2026.002.029-tp.1\nrefs/tags/ci/2026.002.029-tp.2\nrefs/tags/ci/2026.002.030-tp.9\n"
    assert self._run("next", "--repo-root", str(tmp_path), stdin=tags).stdout.strip() == "2026.002.029-tp.3"
