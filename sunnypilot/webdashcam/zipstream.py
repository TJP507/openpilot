"""
Streaming ZIP writer for the web dash cam.

The archive is written straight to the client as it is produced, so a large
selection never has to be buffered in memory or on disk. Sizes and CRCs are
unknown up front, so each entry uses a data descriptor. ZIP64 extended
information is used for any entry (or end record) that overflows the classic
4 GiB / 65535 limits, so archives larger than 4 GiB stay valid.

Kept free of aiohttp/raylib imports so it can be unit-tested off-device.
"""
from __future__ import annotations

import struct
import zlib

from openpilot.sunnypilot.webdashcam import timeutil

_U32_MAX = 0xFFFFFFFF
_U16_MAX = 0xFFFF


def _central_extra(size: int, offset: int) -> tuple[bytes, int]:
  """ZIP64 extended information extra field (header 0x0001) and version needed.

  Fields appear in spec order (uncompressed size, compressed size, relative
  header offset) and only when the corresponding fixed field overflowed.
  """
  body = b""
  if size >= _U32_MAX:
    body += struct.pack("<Q", size)  # uncompressed
    body += struct.pack("<Q", size)  # compressed (store: equal)
  if offset >= _U32_MAX:
    body += struct.pack("<Q", offset)
  if not body:
    return b"", 20
  return struct.pack("<HH", 0x0001, len(body)) + body, 45


class ZipStream:
  """Minimal streaming ZIP writer (store method, data descriptors).

  `response` is anything with an async `write(bytes)` (an aiohttp StreamResponse
  in production, a buffer in tests).
  """

  def __init__(self, response):
    self._response = response
    self._entries: list = []
    self._offset = 0

  async def _write(self, data: bytes) -> None:
    await self._response.write(data)
    self._offset += len(data)

  async def add(self, name: str, mtime: float, chunks) -> None:
    raw_name = name.encode("utf-8")
    dos_time, dos_date = timeutil.dos_datetime(mtime)
    offset = self._offset
    header = struct.pack("<IHHHHHIIIHH", 0x04034B50, 20, 0x0008, 0, dos_time, dos_date,
                         0, 0, 0, len(raw_name), 0)
    await self._write(header + raw_name)

    crc = 0
    size = 0
    async for chunk in chunks:
      crc = zlib.crc32(chunk, crc)
      size += len(chunk)
      await self._write(chunk)

    crc &= 0xFFFFFFFF
    if size >= _U32_MAX:
      # A single entry over 4 GiB needs the 24-byte ZIP64 data descriptor.
      await self._write(struct.pack("<IIQQ", 0x08074B50, crc, size, size))
    else:
      await self._write(struct.pack("<IIII", 0x08074B50, crc, size, size))
    self._entries.append((raw_name, crc, size, offset, dos_time, dos_date))

  async def finish(self) -> None:
    central_offset = self._offset
    any_zip64 = False
    for raw_name, crc, size, offset, dos_time, dos_date in self._entries:
      extra, version = _central_extra(size, offset)
      any_zip64 = any_zip64 or bool(extra)
      size_field = _U32_MAX if size >= _U32_MAX else size
      offset_field = _U32_MAX if offset >= _U32_MAX else offset
      record = struct.pack("<IHHHHHHIIIHHHHHII", 0x02014B50, version, version, 0x0008, 0,
                           dos_time, dos_date, crc, size_field, size_field,
                           len(raw_name), len(extra), 0, 0, 0, 0, offset_field)
      await self._write(record + raw_name + extra)

    central_size = self._offset - central_offset
    count = len(self._entries)
    if any_zip64 or central_offset >= _U32_MAX or central_size >= _U32_MAX or count >= _U16_MAX:
      zip64_offset = self._offset
      await self._write(struct.pack("<IQHHIIQQQQ", 0x06064B50, 44, 45, 45, 0, 0,
                                    count, count, central_size, central_offset))
      await self._write(struct.pack("<IIQI", 0x07064B50, 0, zip64_offset, 1))
      await self._write(struct.pack("<IHHHHIIH", 0x06054B50, 0, 0, _U16_MAX, _U16_MAX,
                                    _U32_MAX, _U32_MAX, 0))
    else:
      await self._write(struct.pack("<IHHHHIIH", 0x06054B50, 0, 0, count, count,
                                    central_size, central_offset, 0))
