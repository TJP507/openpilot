# syntax=docker/dockerfile:1
#
# AGNOS build userland for openpilot prebuilt builds (comma 3X / larch64).
#
# The base image is the AGNOS `system` partition imported verbatim from comma's
# official distribution CDN (see fetch-agnos-rootfs.sh and README.md). It is the
# exact userland the device boots, so the toolchain, libraries, and Python
# environment match the device bit for bit:
#
#   - clang / clang++ (the larch64 compiler), gcc / aarch64-linux-gnu-gcc, ld
#   - /usr/local/venv: the comma build venv (scons, cython, capnpc,
#     arm-none-eabi-{gcc,objcopy,size}, numpy, and every vendored openpilot
#     dependency: acados, capnproto, eigen, ffmpeg, zeromq, ...)
#   - uv, git (+ git-lfs), python3.12 with headers
#   - Qt5 (Core/Gui/Widgets/Charts), EGL/GLESv2/GL, libdrm/libgbm
#   - OpenCL (libOpenCL + Adreno userspace)
#
# `/TICI` is present, so SConstruct's `TICI = os.path.isfile('/TICI')` resolves
# and `uname -m == aarch64` is classified as `arch = "larch64"`.
ARG AGNOS_BASE=ghcr.io/tjp507/openpilot-agnos-base:18.4
FROM ${AGNOS_BASE}

LABEL org.opencontainers.image.source="https://github.com/TJP507/openpilot"
LABEL org.opencontainers.image.title="openpilot-agnos-build"
LABEL org.opencontainers.image.description="comma 3X (AGNOS) userland for building openpilot prebuilt trees"

ENV DEBIAN_FRONTEND=noninteractive

# /work is bind-mounted from the runner and may be owned by a different uid.
RUN git config --global --add safe.directory '*'
