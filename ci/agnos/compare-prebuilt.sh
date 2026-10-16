#!/usr/bin/env bash
#
# Compare a freshly built tree (built in the AGNOS image) against a published
# prebuilt tree (e.g. origin/staging-c3x). Reports compiled artifacts present
# in one tree but not the other, and the architecture of key binaries.
#
# Usage: compare-prebuilt.sh <built-tree> <prebuilt-tree>
set -euo pipefail

built="${1:?usage: compare-prebuilt.sh <built-tree> <prebuilt-tree>}"
prebuilt="${2:?usage: compare-prebuilt.sh <built-tree> <prebuilt-tree>}"

rel() { sed "s#^$1/##"; }

echo "== .so present in built but NOT in prebuilt =="
comm -23 \
  <(find "$built" -type f -name '*.so*' 2>/dev/null | rel "$built" | sort -u) \
  <(find "$prebuilt" -type f -name '*.so*' 2>/dev/null | rel "$prebuilt" | sort -u)

echo
echo "== .so present in prebuilt but NOT in built =="
comm -13 \
  <(find "$built" -type f -name '*.so*' 2>/dev/null | rel "$built" | sort -u) \
  <(find "$prebuilt" -type f -name '*.so*' 2>/dev/null | rel "$prebuilt" | sort -u)

echo
echo "== ELF executables (non-.so) present in built but NOT in prebuilt =="
comm -23 \
  <(find "$built" -type f ! -name '*.so*' -exec sh -c 'file -b "$1" | grep -q ELF && echo "$1"' _ {} \; 2>/dev/null | rel "$built" | sort -u) \
  <(find "$prebuilt" -type f ! -name '*.so*' -exec sh -c 'file -b "$1" | grep -q ELF && echo "$1"' _ {} \; 2>/dev/null | rel "$prebuilt" | sort -u)

echo
echo "== key binary architectures (built) =="
find "$built" -type f -name '*.so*' 2>/dev/null | head -20 | while read -r f; do
  printf '%-70s %s\n' "${f#$built/}" "$(file -b "$f" | cut -d, -f1-2)"
done

echo
echo "== arch summary =="
for tree in "$built" "$prebuilt"; do
  echo "-- $tree"
  find "$tree" -type f \( -name '*.so*' -o -perm -u+x \) 2>/dev/null \
    | xargs -r file -b 2>/dev/null \
    | grep -oE 'ARM aarch64|ARM|Intel 80386|x86-64|ELF 64-bit LSB' \
    | sort | uniq -c | sort -rn | head
done
