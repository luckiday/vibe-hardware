#!/usr/bin/env bash
# Pinned ESP-IDF toolchain — runs idf.py inside the fixed Docker image so the BUILD is
# bit-for-bit reproducible (no host-SDK drift). This is the authoritative build path.
#
# Override the image tag:  IDF_DOCKER_TAG=v5.5 ./idf.sh build
# NOTE: flashing needs host USB access (Docker can't reach /dev/cu.* on macOS) — after
# `./idf.sh build`, flash from the host with `./flash.sh` (esptool, no host re-build). See README.
set -euo pipefail
TAG="${IDF_DOCKER_TAG:-v5.5}"
HERE="$(cd "$(dirname "$0")" && pwd)"
exec docker run --rm -t \
  -v "$HERE":/project -w /project \
  -u "$(id -u):$(id -g)" -e HOME=/tmp \
  espressif/idf:"$TAG" \
  idf.py "$@"
