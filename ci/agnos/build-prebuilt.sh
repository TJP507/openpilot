#!/usr/bin/env bash
#
# Build the comma 3X (larch64) prebuilt tree *inside* the AGNOS build image.
#
# Mirrors the build stage of sunnypilot's
# `.github/workflows/sunnypilot-build-prebuilt.yaml` (self-hosted tici runner):
# same environment setup, same release-tree assembly, same scons invocation.
# It produces the built tree and verifies that everything is regenerated from
# in-tree source (the source branch carries no committed build outputs) and
# that the pinned panda firmware is installed rather than compiled.
#
# Stripping / version.h / publishing happen in the workflow, on the runner.
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
# /etc/profile.d scripts are device-oriented and reference unbound vars, so
# relax `nounset` while sourcing the AGNOS profile.
# shellcheck disable=SC1091
set +u
source /etc/profile   # activates /usr/local/venv (scons/cython/capnpc/arm-none-eabi-*)
set -u
echo "uname -m: $(uname -m)"
if [ -f /TICI ]; then echo "/TICI present -> arch=larch64"; else echo "ERROR: /TICI missing" >&2; exit 1; fi
clang --version | head -1
echo -n "scons: "; scons --version | grep -i 'script' | head -1 || true

echo "== python environment (mirrors upstream) =="
export UV_PROJECT_ENVIRONMENT="${HOME}/venv"
export UV_PYTHON_PREFERENCE=managed
export UV_PYTHON_INSTALL_DIR="${HOME}/uv/python"
export VIRTUAL_ENV="${UV_PROJECT_ENVIRONMENT}"
# Use the real binary, not /usr/comma/shims/uv: the shim remounts/resizes the
# root filesystem and needs privileges a plain container does not have. The
# AGNOS venv already contains every dependency, so a failure here is non-fatal.
/usr/bin/uv sync || echo "WARNING: 'uv sync' failed; continuing with the AGNOS venv"

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

echo "== verify regenerated artifacts =="
missing=0
for f in \
  common/params_pyx.so \
  msgq_repo/msgq/ipc_pyx.so \
  msgq_repo/msgq/visionipc/visionipc_pyx.so \
  rednose_repo/rednose/helpers/ekf_sym_pyx.so \
  selfdrive/locationd/models/generated/libcar.so \
  selfdrive/locationd/models/generated/libpose.so \
  sunnypilot/selfdrive/locationd/models/generated/liblive.so \
  selfdrive/controls/lib/lateral_mpc_lib/c_generated_code/libacados_ocp_solver_lat.so \
  selfdrive/controls/lib/longitudinal_mpc_lib/c_generated_code/libacados_ocp_solver_long.so \
  selfdrive/pandad/pandad ; do
  if [ -f "$BUILD_DIR/$f" ]; then echo "  ok   $f"; else echo "  MISSING $f"; missing=1; fi
done
[ "$missing" = 0 ] || { echo "ERROR: build did not regenerate expected artifacts" >&2; exit 1; }

echo "== verify pinned panda firmware =="
python3 - "$BUILD_DIR" <<'PY'
import sys
build = sys.argv[1]
def sig(path):
  with open(path, 'rb') as f:
    f.seek(-128, 2)
    return f.read(128)
built = sig(f"{build}/panda/board/obj/panda_h7.bin.signed")
pinned = sig(f"{build}/panda/board/pinned/panda_h7.bin.signed")
print("  built  signature:", built.hex())
print("  pinned signature:", pinned.hex())
assert built == pinned, "panda firmware signature does not match the pinned staging signature"
assert built[:8].hex() == "406de22bd6d19eca", f"unexpected pinned signature prefix {built[:8].hex()}"
print("  OK: panda signature == 406de22bd6d19eca… (matches pinned staging-c3x)")
PY

echo "== panda/board/obj (should be the pinned files) =="
ls -la "$BUILD_DIR/panda/board/obj"
