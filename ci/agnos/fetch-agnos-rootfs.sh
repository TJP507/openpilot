#!/usr/bin/env bash
#
# Fetch, verify, and extract the pinned AGNOS system rootfs.
#
# The comma 3X userland we build in is the AGNOS `system` partition. We take it
# verbatim from comma's official distribution CDN, pinned to the exact entry
# that the `dev-c3x` source branch's `system/hardware/tici/agnos.json` expects:
#
#   name:      system
#   url:       https://commadist.azureedge.net/agnosupdate/system-ef0d8793....img.xz
#   hash:      78acfe16...  (SHA-256 of the decompressed Android-sparse image)
#   hash_raw:  ef0d8793...  (SHA-256 of the unsparsified ext4 partition)
#   size:      4718592000   (unsparsified partition size)
#
# Both hashes are verified. Extraction uses `debugfs rdump`, which reads the
# ext4 image directly and does not need loop devices or mount privileges.
#
# Requires: curl, xz, e2fsprogs (debugfs), python3. Run as root so ownership and
# special files are preserved in the extracted tree.
#
# Usage: fetch-agnos-rootfs.sh [workdir]   (rootfs lands in <workdir>/rootfs)
set -euo pipefail

AGNOS_SYSTEM_URL="https://commadist.azureedge.net/agnosupdate/system-ef0d879302cb29e72110e9c8d3f947c830fd7d37c8192744fc9dbea1af78501f.img.xz"
AGNOS_SPARSE_SHA256="78acfe16a7b62a3a91fc7a81f40a693e4468cec1c69df7d0b1e550aacc646113"
AGNOS_RAW_SHA256="ef0d879302cb29e72110e9c8d3f947c830fd7d37c8192744fc9dbea1af78501f"
AGNOS_RAW_SIZE=4718592000

here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
workdir="${1:-$here/agnos-work}"
rootfs="$workdir/rootfs"

if [ "$(id -u)" -ne 0 ]; then
  echo "WARNING: not running as root; extracted ownership/special files may be lossy" >&2
fi

mkdir -p "$workdir"
cd "$workdir"

echo "== download AGNOS system image =="
curl -fSL --retry 3 --retry-delay 5 -o system.img.xz "$AGNOS_SYSTEM_URL"
ls -la system.img.xz

echo "== decompress + verify sparse-image hash =="
xz -dc system.img.xz > system.sparse.img
echo "${AGNOS_SPARSE_SHA256}  system.sparse.img" | sha256sum -c -
rm -f system.img.xz

echo "== unsparsify + verify raw ext4 hash =="
python3 "$here/unsparse.py" system.sparse.img system.raw.img "$AGNOS_RAW_SIZE" "$AGNOS_RAW_SHA256"
rm -f system.sparse.img

echo "== extract rootfs (debugfs rdump; no loop/mount needed) =="
rm -rf "$rootfs"
mkdir -p "$rootfs"
debugfs -R "rdump / $rootfs" system.raw.img
rm -f system.raw.img

echo "== done =="
echo -n "AGNOS VERSION: "; cat "$rootfs/VERSION" 2>/dev/null || echo "?"
echo -n "AGNOS BUILD:   "; cat "$rootfs/BUILD" 2>/dev/null | head -1 || echo "?"
if [ -f "$rootfs/TICI" ]; then
  echo "/TICI present -> SConstruct arch=larch64"
else
  echo "ERROR: /TICI missing; build would not detect larch64" >&2
  exit 1
fi
