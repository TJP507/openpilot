# AGNOS build image (`ci/agnos/`)

A reproducible **comma 3X (larch64) build userland** as a container image, plus
the workflow that builds openpilot's prebuilt tree inside it on GitHub-hosted
arm64 runners.

This implements the Option C build host: `dev-c3x` stays the **source** branch;
CI compiles it in an AGNOS-userland image and (in a later block) strips +
publishes the result to `staging-c3x` → `release-c3x`. Devices never compile.

## Why the AGNOS `system` partition

The build must run in the exact userland the device boots, or the artifacts
diverge (different clang, different vendored libraries, different Python). The
faithful, official source is comma's own AGNOS distribution. We pin it to the
entry that `dev-c3x`'s `system/hardware/tici/agnos.json` already expects:

| field | value |
| --- | --- |
| partition | `system` |
| url | `https://commadist.azureedge.net/agnosupdate/system-ef0d879302cb29e72110e9c8d3f947c830fd7d37c8192744fc9dbea1af78501f.img.xz` |
| `hash` (decompressed Android-sparse image) | `78acfe16a7b62a3a91fc7a81f40a693e4468cec1c69df7d0b1e550aacc646113` |
| `hash_raw` (unsparsified ext4 partition) | `ef0d879302cb29e72110e9c8d3f947c830fd7d37c8192744fc9dbea1af78501f` |
| `size` (unsparsified) | `4718592000` bytes |
| AGNOS `VERSION` / `BUILD` | `18.4` / `c58d12b539d863edcec0f2daabda43604d7d9b38` |

`fetch-agnos-rootfs.sh` downloads the `.xz`, verifies the decompressed sparse
image hash, unsparsifies it (mirroring the device's `agnos.py`) and verifies the
raw ext4 hash, then extracts the tree with `debugfs rdump` (no loop devices or
mount privileges). The extracted rootfs is imported as an arm64 image and the
`ci/agnos/Dockerfile` layers the CI bits on top.

### Why not `commaai/agnos-builder`

`agnos-builder` builds AGNOS *from source* (a multi-hour Yocto/Ubuntu image
build). The distribution artifact is the same userland, is hash-pinned, and is
what the device actually runs — so we use it directly.

## What the image already contains

The AGNOS rootfs is a complete build userland, so the image adds almost nothing:

- `clang`/`clang++` (larch64), `gcc`/`aarch64-linux-gnu-gcc`, `ld`, `git`(+lfs),
  `uv`, `python3.12` + headers.
- `/usr/local/venv` — the comma build venv: `scons`, `cython`, `capnpc`,
  `arm-none-eabi-{gcc,objcopy,size}`, `numpy`, and every vendored openpilot
  dependency (`acados`, `capnproto`, `eigen`, `ffmpeg`, `zeromq`, …).
- Qt5 (Core/Gui/Widgets/Charts), EGL/GLESv2/GL, libdrm/libgbm, OpenCL
  (`libOpenCL` + Adreno userspace).
- `/TICI` — makes `SConstruct` classify the build as `arch = "larch64"`.

The image's only added layer is `git config --global --add safe.directory '*'`
(the repo is bind-mounted from the runner and may be owned by a different uid).

## Files

| file | purpose |
| --- | --- |
| `fetch-agnos-rootfs.sh` | download + verify + extract the pinned AGNOS rootfs |
| `unsparse.py` | Android-sparse → raw ext4 (mirrors device `agnos.py`) |
| `Dockerfile` | `FROM <imported AGNOS base>` + CI bits |
| `build-prebuilt.sh` | the in-container build (mirrors sunnypilot's build stage) |
| `release_files.py` | vendored `tools/release/release_files.py` from sunnypilot `master`¹ |

¹ `dev-c3x` is derived from a prebuilt branch and does not carry
`tools/release/` (upstream strips it from published branches), so the tool is
vendored here. Its `ROOT` is derived from its own location, so it must stay at
`<repo-root>/ci/agnos/release_files.py`.

## Workflows

- **`.github/workflows/agnos-build-image.yaml`** — builds and pushes
  `ghcr.io/tjp507/openpilot-agnos-build:<agnos-version>` (and the imported
  `…-agnos-base` image) on `ubuntu-24.04-arm`. Runs on `workflow_dispatch` and
  on changes to `ci/agnos/**`.
- **`.github/workflows/build-prebuilt-test.yaml`** — `workflow_dispatch` only.
  Checks out `dev-c3x`, runs `build-prebuilt.sh` inside the image, and uploads
  the built tree as an artifact. No strip/publish (later block).

For strict reproducibility, pin the image by digest
(`ghcr.io/tjp507/openpilot-agnos-build@sha256:…`) in the test workflow's `image`
input; the image workflow prints the digest after pushing.

## Reproduce locally

```sh
# 1. Extract the rootfs (needs e2fsprogs, xz-utils, python3; run as root)
sudo ci/agnos/fetch-agnos-rootfs.sh /tmp/agnos

# 2. Import it as an arm64 base image and build the CI image
sudo tar -C /tmp/agnos/rootfs --numeric-owner -cf - . \
  | docker import --platform linux/arm64 - ghcr.io/tjp507/openpilot-agnos-base:18.4
docker build --platform linux/arm64 \
  --build-arg AGNOS_BASE=ghcr.io/tjp507/openpilot-agnos-base:18.4 \
  -t ghcr.io/tjp507/openpilot-agnos-build:18.4 -f ci/agnos/Dockerfile ci/agnos

# 3. Smoke test (arm64; use qemu/binfmt on x86_64)
docker run --rm --platform linux/arm64 ghcr.io/tjp507/openpilot-agnos-build:18.4 \
  bash -c 'source /etc/profile; uname -m; clang --version | head -1; scons --version | head -1'
```

## Proof build (Block 10a)

`build-prebuilt-test.yaml` compiled `dev-c3x` in the image on `ubuntu-24.04-arm`:

- image build (`agnos-build-image`): ~4m30s incl. download/verify/extract/import/push;
  pushed digest `ghcr.io/tjp507/openpilot-agnos-build@sha256:af307d4c…`.
- proof build job: ~2m50s total; `scons` ~1m32s (fast because `dev-c3x` already
  commits 18 prebuilt `.so`, so many targets are up to date).
- comparison vs `origin/staging-c3x` (`compare-prebuilt.sh`): canonical `.so`
  and ELF-executable sets are **identical**, all aarch64. Only differences were
  transport/expected: `upload-artifact` dereferences symlinks and (by default)
  drops hidden files, and the tree is unstripped. `panda/board/obj` was rebuilt
  as `DEV-8351ae21-DEBUG` (signature differs from the pinned committed
  `DEV-unknown-DEBUG`) — the known pinning issue, not solved here.

## Container notes

- `/etc/profile` activates `/usr/local/venv` and prepends `/usr/comma/shims` to
  `PATH`. The `uv`/`pip` shims are device-only: they remount `/`, resize the
  root filesystem, and remount `/tmp` (exit 32 in an unprivileged container).
  The build therefore calls `/usr/bin/uv` directly.
- `/etc/profile` also points `PYTHONPATH` at `/data/pythonpath` (the device's
  data partition, absent in the container); the build overrides `PYTHONPATH`.
