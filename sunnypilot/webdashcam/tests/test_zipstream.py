"""
Tests for the streaming ZIP writer, including the ZIP64 central-directory
records that keep archives larger than 4 GiB valid.
"""
from __future__ import annotations

import asyncio
import struct
import zipfile

import pytest

from openpilot.sunnypilot.webdashcam.zipstream import ZipStream

_U32_MAX = 0xFFFFFFFF


class _Buf:
  """Async-write target that accumulates into a bytearray (stands in for the
  aiohttp StreamResponse)."""

  def __init__(self) -> None:
    self.data = bytearray()

  async def write(self, data: bytes) -> None:
    self.data += data


async def _add(z: ZipStream, name: str, payload: bytes) -> None:
  async def chunks():
    yield payload
  await z.add(name, 1700000000.0, chunks())


def _find_central_dir(data: bytes) -> int:
  off = data.find(b"PK\x01\x02")
  assert off >= 0, "no central directory record"
  return off


def _parse_central(data: bytes, off: int) -> tuple[int, int, int, bytes]:
  version = struct.unpack_from("<H", data, off + 6)[0]
  size32 = struct.unpack_from("<I", data, off + 24)[0]
  offset32 = struct.unpack_from("<I", data, off + 42)[0]
  name_len = struct.unpack_from("<H", data, off + 28)[0]
  extra_len = struct.unpack_from("<H", data, off + 30)[0]
  extra = data[off + 46 + name_len:off + 46 + name_len + extra_len]
  return version, size32, offset32, extra


def test_zip64_central_directory_offset():
  buf = _Buf()
  z = ZipStream(buf)
  z._offset = _U32_MAX  # pretend >4 GiB of entries were already written

  async def run():
    await _add(z, "a.mp4", b"AAAAA")
    await _add(z, "b.mp4", b"AAAAA")
    await z.finish()

  asyncio.run(run())
  data = bytes(buf.data)
  assert b"PK\x06\x06" in data, "no ZIP64 end-of-central-directory record"

  off = _find_central_dir(data)
  version, size32, offset32, extra = _parse_central(data, off)
  assert version == 45
  assert offset32 == _U32_MAX
  assert size32 == 5
  assert struct.unpack_from("<HH", extra, 0) == (0x0001, 8)
  assert struct.unpack_from("<Q", extra, 4)[0] == _U32_MAX

  # Entry b starts after a's local header (30 + len("a.mp4")) + payload + descriptor.
  next_off = off + 46 + 5 + len(extra)
  _version, _size32, _offset32, extra_b = _parse_central(data, next_off)
  want_b = _U32_MAX + 35 + 5 + 16
  assert struct.unpack_from("<Q", extra_b, 4)[0] == want_b


def test_zip64_extra_carries_size_and_offset():
  from openpilot.sunnypilot.webdashcam.zipstream import _central_extra

  extra, version = _central_extra(_U32_MAX + 10, _U32_MAX + 10)
  assert version == 45
  assert struct.unpack_from("<HH", extra, 0) == (0x0001, 24)
  # Spec order: uncompressed, compressed, offset.
  assert struct.unpack_from("<Q", extra, 4)[0] == _U32_MAX + 10
  assert struct.unpack_from("<Q", extra, 12)[0] == _U32_MAX + 10
  assert struct.unpack_from("<Q", extra, 20)[0] == _U32_MAX + 10


def test_small_archive_is_classic_zip():
  buf = _Buf()
  z = ZipStream(buf)

  async def run():
    await _add(z, "2026-10-14/19-42-10_front.mp4", b"hello world")
    await z.finish()

  asyncio.run(run())
  data = bytes(buf.data)
  assert b"PK\x06\x06" not in data, "small archive should not use ZIP64"
  assert b"PK\x01\x02" in data and b"PK\x05\x06" in data


class _FileResp:
  def __init__(self, fh) -> None:
    self._fh = fh

  async def write(self, data: bytes) -> None:
    self._fh.write(data)


async def _zeros(size: int):
  chunk = b"\x00" * (1 << 20)
  remaining = size
  while remaining > 0:
    n = min(len(chunk), remaining)
    yield chunk[:n]
    remaining -= n


@pytest.mark.slow
def test_zip64_end_to_end_over_4gib(tmp_path):
  # Three ~2.2 GiB entries: each is under the 4 GiB per-entry limit, but the
  # third sits past the 4 GiB archive offset (the reported bug).
  big = 2_200_000_000
  sizes = [big, big, 1000]
  names = [
    "2026-10-14/00-00-00_front.mp4",
    "2026-10-14/00-01-00_front.mp4",
    "2026-10-14/00-02-00_front.mp4",
  ]
  path = tmp_path / "big.zip"
  with open(path, "wb") as fh:
    z = ZipStream(_FileResp(fh))

    async def run():
      for name, size in zip(names, sizes, strict=True):
        await z.add(name, 1700000000.0, _zeros(size))
      await z.finish()

    asyncio.run(run())

  assert path.stat().st_size > 1 << 32
  with zipfile.ZipFile(path) as zf:
    assert zf.namelist() == names
    assert zf.testzip() is None  # verifies every entry's CRC
    for name, size in zip(names, sizes, strict=True):
      with zf.open(name) as fp:
        total = 0
        while True:
          b = fp.read(1 << 20)
          if not b:
            break
          total += len(b)
        assert total == size
