#!/bin/sh
set -eu

if [ "$#" -ne 1 ] || [ ! -f "$1" ]; then
  printf 'usage: %s path/to/libSDL.a\n' "$0" >&2
  exit 1
fi
library=$(cd "$(dirname "$1")" && pwd)/$(basename "$1")
cd "$(dirname "$0")/.."
image=sha256:369734d6aa2aa3650487b2b2b529fdadd2a6ecf0618947677165c676bbc996de
mkdir -p build/amiga/relink-input
cp "$library" build/amiga/relink-input/libSDL.a
sysflags='-m68040 -mhard-float -noixemul -I/opt/m68k-amigaos/usr/include/SDL -DKEEN_AMIGA_RTG=1 -DCK_ENABLE_PLAYLOOP_DUMPER=1 -DFS_NO_OMNI_EXEDIR_FALLBACK=1 -DFS_NO_USER_XDG_FALLBACK=1'

docker run --rm --network none --platform linux/arm64 \
  --user "$(id -u):$(id -g)" \
  --volume "$PWD:/work" --workdir /work "$image" \
  make -C src -B -j2 all PLATFORM=amiga RENDERER=sdl1 BUILDASCPP=0 \
  WITH_KEEN4=1 WITH_KEEN5=0 WITH_KEEN6=0 DEBUG=0 \
  COMPILER=/opt/m68k-amigaos/bin/m68k-amigaos-gcc \
  BINDIR=../build/amiga/relinked OBJDIR=../build/amiga/relinked/obj \
  SYSFLAGS="$sysflags" SDL_CFLAGS=-DWITH_SDL \
  SDL_LIBS=/work/build/amiga/relink-input/libSDL.a
printf 'relinked binary: %s\n' "$PWD/build/amiga/relinked/omnispeak"
