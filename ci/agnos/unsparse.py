#!/usr/bin/env python3
"""Unsparsify an Android sparse image into a raw partition image.

This mirrors the `unsparsify()` routine the device uses in
`system/hardware/tici/agnos.py`, but writes to a file and verifies the exact
size and SHA-256 of the resulting raw image.

Usage: unsparse.py <sparse.img> <raw.img> <expected_size> <expected_sha256>
"""
import hashlib
import struct
import sys

# chunk header: type (u16), reserved (u16), output block count (u32), total size (u32)
SPARSE_CHUNK_FMT = struct.Struct("H2xI4x")
SPARSE_MAGIC = 0xED26FF3A
CHUNK_RAW = 0xCAC1
CHUNK_FILL = 0xCAC2
CHUNK_DONT_CARE = 0xCAC3


def main() -> int:
  sparse_path, raw_path, expected_size, expected_hash = sys.argv[1:5]
  expected_size = int(expected_size)
  expected_hash = expected_hash.lower()

  with open(sparse_path, "rb") as f, open(raw_path, "wb") as out:
    def read(n: int) -> bytes:
      b = f.read(n)
      if len(b) != n:
        raise SystemExit(f"short read: wanted {n} bytes, got {len(b)}")
      return b

    magic = struct.unpack("I", read(4))[0]
    if magic != SPARSE_MAGIC:
      raise SystemExit(f"not an Android sparse image (magic={magic:#x})")

    major, minor = struct.unpack("HH", read(4))
    if (major, minor) != (1, 0):
      raise SystemExit(f"unsupported sparse version {major}.{minor}")

    read(2)  # file header size
    read(2)  # chunk header size
    block_size = struct.unpack("I", read(4))[0]
    read(4)  # total blocks
    num_chunks = struct.unpack("I", read(4))[0]
    read(4)  # crc32

    print(f"block_size={block_size} chunks={num_chunks}")

    digest = hashlib.sha256()
    written = 0
    for _ in range(num_chunks):
      chunk_type, out_blocks = SPARSE_CHUNK_FMT.unpack(read(12))
      if chunk_type == CHUNK_RAW:
        data = read(out_blocks * block_size)
        out.write(data)
        digest.update(data)
        written += len(data)
      elif chunk_type == CHUNK_FILL:
        filler = read(4) * (block_size // 4)
        for _ in range(out_blocks):
          out.write(filler)
          digest.update(filler)
          written += len(filler)
      elif chunk_type == CHUNK_DONT_CARE:
        zeros = b"\x00" * block_size
        for _ in range(out_blocks):
          out.write(zeros)
          digest.update(zeros)
          written += len(zeros)
      else:
        raise SystemExit(f"unhandled sparse chunk type {chunk_type:#x}")

  got = digest.hexdigest()
  print(f"wrote {written} bytes, sha256={got}")
  if written != expected_size:
    raise SystemExit(f"size mismatch: expected {expected_size}, got {written}")
  if got != expected_hash:
    raise SystemExit(f"hash mismatch: expected {expected_hash}, got {got}")
  print("OK")
  return 0


if __name__ == "__main__":
  sys.exit(main())
