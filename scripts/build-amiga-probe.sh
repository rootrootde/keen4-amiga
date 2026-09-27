#!/bin/sh
set -eu

cd "$(dirname "$0")/.."
mkdir -p build/amiga

image=sha256:369734d6aa2aa3650487b2b2b529fdadd2a6ecf0618947677165c676bbc996de
docker run --rm --platform linux/arm64 \
  --user "$(id -u):$(id -g)" \
  --volume "$PWD:/work" --workdir /work "$image" \
  /opt/m68k-amigaos/bin/m68k-amigaos-gcc \
  -std=c99 -O2 -Wall -Wextra -Werror -m68040 -mhard-float -noixemul \
  -I/opt/m68k-amigaos/usr/include/SDL \
  -o build/amiga/keen-probe probe/keen_probe.c \
  -L/opt/m68k-amigaos/usr/lib -lSDL -lm
