"""
Copyright (c) 2021-, Haibin Wen, sunnypilot, and a number of other contributors.

This file is part of sunnypilot and is licensed under the MIT License.
See the LICENSE.md file in the root directory for more details.

TylerPilot fork version scheme.

`sunnypilot/common/version.h` holds only the fork base version
(e.g. "2026.002.029") and nothing else. Our published builds append a fork
suffix to it:

  * CI (`build-prebuilt.yaml`) stamps  <base>-tp.<N>   (N increments per base)
  * on-device source builds show       <base>-tp.dev

See `ci/agnos/README.md` ("Versioning") for the full scheme. This module is
dependency-free on purpose so that both the runtime
(`openpilot.system.version.get_version`) and the CI helper (`ci/version`) share
one definition and cannot drift.
"""
import re

# "2026.002.029" — the only thing version.h holds.
BASE_RE = re.compile(r"^\d{4}\.\d{3}\.\d{3}$")
# "2026.002.029-tp.1" — a published CI build (what promote-release accepts).
FULL_RE = re.compile(r"^\d{4}\.\d{3}\.\d{3}-tp\.\d+$")
# The suffix an on-device source build carries.
DEV_SUFFIX = "-tp.dev"
# Tag prefix for published CI builds: ci/<base>-tp.<N>.
CI_TAG_PREFIX = "ci/"


def is_base(version: str) -> bool:
  """True for a bare fork base version (e.g. "2026.002.029")."""
  return bool(BASE_RE.match(version))


def is_full_version(version: str) -> bool:
  """True for a published <base>-tp.<N> version."""
  return bool(FULL_RE.match(version))


def dev_version(base: str) -> str:
  return f"{base}{DEV_SUFFIX}"


def ci_version(base: str, number: int) -> str:
  return f"{base}-tp.{number}"


def ci_tag(base: str, number: int) -> str:
  return f"{CI_TAG_PREFIX}{ci_version(base, number)}"


def ci_number_from_tag(tag: str, base: str) -> int | None:
  """The N if `tag` is `ci/<base>-tp.<N>`, otherwise None."""
  prefix = f"{CI_TAG_PREFIX}{base}-tp."
  if not tag.startswith(prefix):
    return None
  suffix = tag[len(prefix):]
  return int(suffix) if suffix.isdigit() else None


def next_ci_number(base: str, tags) -> int:
  """The next free N for `base` given an iterable of existing tag names."""
  numbers = [n for n in (ci_number_from_tag(tag, base) for tag in tags) if n is not None]
  return max(numbers, default=0) + 1


def resolve(version: str) -> str:
  """Compose the on-device version from the raw `version.h` value.

  A bare base gets the dev suffix; anything else — an already-stamped published
  version, or an unrecognized upstream value — is returned unchanged.
  """
  return dev_version(version) if is_base(version) else version
