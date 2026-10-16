# AGNOS build image + release pipeline (`ci/agnos/`)

A reproducible **comma 3X (larch64) build userland** as a container image, plus
the CI that builds openpilot's prebuilt tree inside it on GitHub-hosted arm64
runners. Implements the Option C build host: the source branch stays a true
source branch; CI compiles it and publishes the prebuilt tree.

## Release flow

```
dev-c3x  --build-prebuilt.yaml-->  staging-c3x-ci  --(owner tests on device)-->
promote-release.yaml -->  staging-c3x  -->  release-c3x
```

- **dev-c3x** — true source. **No committed build outputs** (see below).
- **staging-c3x-ci** — CI-published prebuilt tree (built + stripped in the AGNOS
  image). Never hand-edited.
- **staging-c3x / release-c3x** — promoted from a tested `staging-c3x-ci` commit
  by `promote-release.yaml`. Promoting to `release-c3x` requires the
  `production` GitHub environment (manual approval).

Devices never compile. `staging-c3x-ci` is what the owner points the device at
to validate a build before promotion.

## Versioning

`sunnypilot/common/version.h` holds **only the fork base** (e.g. `2026.002.029`).
Every build appends a fork suffix to it:

| build | version string | composed by |
| --- | --- | --- |
| on-device source (`dev-c3x`) | `<base>-tp.dev` | `system/version.py:get_version()` |
| CI-published (`staging-c3x-ci`) | `<base>-tp.<N>` | `build-prebuilt.yaml` (publish job) |

`N` starts at 1 and increments per base. It is derived from the
`ci/<base>-tp.<N>` tags that the publish job pushes for each published build, so
an `N` is never reused; the publish job holds the `publish-staging-c3x-ci`
concurrency lock, so two runs cannot pick the same `N`. `promote-release.yaml`
refuses to promote a commit whose `version.h` is `-tp.dev` or does not match
`^\d{4}\.\d{3}\.\d{3}-tp\.\d+$`, and refuses to re-tag an existing `v<version>`.
The promoted commit is copied unchanged — the version string never changes on
promotion.

The scheme is defined once, in `sunnypilot/common/version_scheme.py`, and shared
by the runtime (`openpilot.system.version`) and the `ci/version` helper:

```sh
ci/version base          # 2026.002.029
ci/version dev           # 2026.002.029-tp.dev
git ls-remote --tags origin 'refs/tags/ci/*' | cut -f2 | ci/version next   # next N
ci/version check 2026.002.029-tp.1   # exit 0 iff a published <base>-tp.<N>
```

Bumping the base (a sunnypilot sync) is just editing `version.h`; `N` restarts
at 1 for the new base.

## Why the AGNOS `system` partition

The build must run in the exact userland the device boots, or the artifacts
diverge (different clang, different vendored libraries, different Python). The
faithful, official source is comma's own AGNOS distribution. We pin it to the
entry that `dev-c3x`'s `system/hardware/tici/agnos.json` expects:

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

`agnos-builder` builds AGNOS *from source* (a multi-hour image build). The
distribution artifact is the same userland, is hash-pinned, and is what the
device actually runs — so we use it directly.

### Bumping AGNOS

1. Update `system/hardware/tici/agnos.json` on `dev-c3x` (as upstream does).
2. Update the pinned `url` / `hash` / `hash_raw` / `AGNOS_RAW_SIZE` at the top of
   `ci/agnos/fetch-agnos-rootfs.sh`, and `AGNOS_VERSION` in
   `.github/workflows/agnos-build-image.yaml`.
3. Re-run `agnos-build-image.yaml`, then pin the new digest in
   `build-prebuilt.yaml`'s `image` input default.

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

The image's only added layer is `git config --global --add safe.directory '*'`.

## Clean source

`dev-c3x` must contain no build outputs; everything is regenerated by `scons` in
the AGNOS image. Removed (and gitignored): `*.so`/`*.o`/`*.os`/`*.a`/`*.elf`,
Cython `*_pyx.cpp`, `cereal/gen/`, `cereal/services.h`, `cereal/messaging/bridge`,
`**/c_generated_code/`, `**/models/generated/`, `acados_ocp_*.json`,
`panda/board/obj/` (except `.placeholder`), and `panda/tests/libpanda/libpanda.so`.
The `openpilot/` import-compat layer keeps symlinks to the source dirs
(`openpilot/cereal -> ../cereal`, etc.). `build-prebuilt.sh` asserts the key
artifacts exist after the build, so a missing regeneration fails the pipeline.

## Pinned panda firmware

`panda/board/pinned/` holds the signed panda firmware (H7) exactly as published
on sunnypilot's `staging-c3x` (`465accad`), with `MANIFEST.sha256` and `SOURCE`.
`panda/SConscript` installs these into `panda/board/obj/` instead of compiling.

**Why:** a source build produces a per-commit, DEBUG-signed image
(`DEV-<short-commit>-DEBUG`, signed with `board/certs/debug`) whose RSA signature
changes every build. `pandad` re-flashes the panda whenever the signature
differs; that source-built DEBUG firmware is the suspected cause of the dev-only
cellular regression. Pinning keeps the exact release signature, so `pandad`
never re-flashes — on CI builds and on on-device dev builds alike.

`build-prebuilt.sh` verifies after every build that
`Panda.get_signature_from_firmware(panda/board/obj/panda_h7.bin.signed)` (the
trailing 128 bytes) equals the pinned signature `406de22bd6d19eca…`.

## Workflows

| workflow | trigger | does |
| --- | --- | --- |
| `agnos-build-image.yaml` | dispatch; `ci/agnos/{Dockerfile,fetch-agnos-rootfs.sh,unsparse.py}` change | builds + pushes `ghcr.io/tjp507/openpilot-agnos-build` |
| `build-prebuilt.yaml` | push to `dev-c3x`; dispatch | tests → build in the pinned image → strip → assign `<base>-tp.<N>` → publish `staging-c3x-ci` + tag `ci/<base>-tp.<N>` |
| `promote-release.yaml` | dispatch | copy a tested commit to `staging-c3x`/`release-c3x` + tag `v<version>` (guarded; `production` env for release) |

All third-party actions are pinned to full commit SHAs; the build image is
pinned by digest in `build-prebuilt.yaml`.

### Models

The tree ships the tinygrad models as committed chunks
(`selfdrive/modeld/models/*.pkl.chunkNNofMM` + `.chunkmanifest`), read at
runtime by `common/file_chunker.py`. Unlike sunnypilot — whose source branch does
not commit the models and whose publish job fetches canonical `.pkl`s from
HuggingFace — **our build needs no HF fetch**: the chunks are in-tree. The strip
step drops the `.onnx` files (as sunnypilot does); the device uses the tinygrad
pkl.

## Files

| file | purpose |
| --- | --- |
| `fetch-agnos-rootfs.sh` | download + verify + extract the pinned AGNOS rootfs |
| `unsparse.py` | Android-sparse → raw ext4 (mirrors device `agnos.py`) |
| `Dockerfile` | `FROM <imported AGNOS base>` + CI bits |
| `build-prebuilt.sh` | the in-container build (mirrors sunnypilot's build stage) |
| `compare-prebuilt.sh` | diff a built tree against a published prebuilt tree |
| `release_files.py` | vendored `tools/release/release_files.py` from sunnypilot `master`¹ |
| `../version` | `ci/version` — compose/validate fork versions (shared with the runtime) |

¹ `dev-c3x` is derived from a prebuilt branch and does not carry
`tools/release/`, so the tool is vendored here with a fork blacklist entry for
`ci/`. Its `ROOT` is derived from its own location, so it must stay at
`<repo-root>/ci/agnos/release_files.py`.

## Container notes

- `/etc/profile` activates `/usr/local/venv` and prepends `/usr/comma/shims` to
  `PATH`. The `uv`/`pip` shims are device-only: they remount `/`, resize the
  root filesystem, and remount `/tmp` (exit 32 in an unprivileged container).
  The build therefore calls `/usr/bin/uv` directly.
- `/etc/profile` also points `PYTHONPATH` at `/data/pythonpath` (the device's
  data partition, absent in the container); the build overrides `PYTHONPATH`.

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
