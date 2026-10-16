#!/usr/bin/env bash
#
# Build the comma 3X (larch64) prebuilt tree *inside* the AGNOS build image.
#
# This mirrors the build stage of sunnypilot's
# `.github/workflows/sunnypilot-build-prebuilt.yaml` (self-hosted tici runner):
# same environment setup, same release-tree assembly, same scons invocation.
# It does NOT strip or publish (that is a later block); it only produces the
# built tree and records what scons produced under panda/board/obj.
#
# Env overrides:
#   REPO_DIR     repo checkout               (default /work)
#   BUILD_DIR    where the tree is assembled (default $REPO_DIR/build)
#   SCONS_CACHE  scons cache directory       (default /scons_cache)
set -euo pipefail

REPO_DIR="${REPO_DIR:-/work}"
BUILD_DIR="${BUILD_DIR:-$REPO_DIR/build}"
SCONS_CACHE="${SCONS_CACHE:-/scons_cache}"

echo "== AGNOS userland =="
# shellcheck disable=SC1091
source /etc/profile   # activates /usr/local/venv (scons/cython/capnpc/arm-none-eabi-*)
echo "uname -m: $(uname -m)"
if [ -f /TICI ]; then echo "/TICI present -> arch=larch64"; else echo "ERROR: /TICI missing" >&2; exit 1; fi
clang --version | head -1
echo -n "scons: "; scons --version | grep -i 'script' | head -1 || true

echo "== python environment (mirrors upstream) =="
export UV_PROJECT_ENVIRONMENT="${HOME}/venv"
export UV_PYTHON_PREFERENCE=managed
export UV_PYTHON_INSTALL_DIR="${HOME}/uv/python"
export VIRTUAL_ENV="${UV_PROJECT_ENVIRONMENT}"
# Best effort: the AGNOS venv already contains every dependency the build
# needs, so a failure here must not abort the build.
uv sync || echo "WARNING: 'uv sync' failed; continuing with the AGNOS venv"

echo "== assemble release tree =="
cd "$REPO_DIR"
mkdir -p "$BUILD_DIR" "$SCONS_CACHE"
export PYTHONPATH="$BUILD_DIR:$BUILD_DIR/msgq_repo:$BUILD_DIR/opendbc_repo:$BUILD_DIR/rednose_repo:$BUILD_DIR/teleoprtc_repo:$BUILD_DIR/tinygrad_repo"
"$REPO_DIR/ci/agnos/release_files.py" | xargs -0 cp -pR --parents -t "$BUILD_DIR" --

cd "$BUILD_DIR"
echo "== build locationd (-j1; parallel rednose OOMs the device) =="
scons -j1 cache_dir="$SCONS_CACHE" --minimal \
  openpilot/selfdrive/locationd openpilot/sunnypilot/selfdrive/locationd

echo "== build the rest (-j\$(nproc)) =="
mkdir -p "$BUILD_DIR/tmp"
export TMPDIR="$BUILD_DIR/tmp"
SKIP_TINYGRAD_COMPILE=1 scons -j"$(nproc)" cache_dir="$SCONS_CACHE" --minimal

touch "$BUILD_DIR/prebuilt"

echo "== panda/board/obj (recorded only; pinning is a later block) =="
ls -la "$BUILD_DIR/panda/board/obj" || true
